import os
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.core import AuditLog, Role, User
from ..models.mythic import (Application, Cohort, CohortMember, Contribution, ExceptionCase, MythicContent,
                             PayoutBatch, RefundRequest, RegistrationPeriod)
from ..security import current_user, require_roles
from ..services import mythic as svc
from ..services.common import audit
from ..services.plans import PLANS

router = APIRouter(prefix="/api/mythic", tags=["mythic-circle"])
verifier = require_roles(Role.clan_verifier)
finance = require_roles(Role.finance_admin)
content_admin = require_roles(Role.content_admin, Role.finance_admin)

ALLOWED_IMG = {"image/png", "image/jpeg", "image/webp"}
CMS_KEYS = {"landing_description", "banner", "faqs", "policy_documents", "registration_announcement",
            "enrollment_enabled"}


def run(db: Session, fn, *a, **kw):
    try:
        res = fn(db, *a, **kw)
        db.commit()
        return res
    except svc.MythicError as e:
        db.rollback()
        raise HTTPException(e.status_code, str(e))


def save_upload(f: UploadFile, sub: str) -> str:
    if f.content_type not in ALLOWED_IMG:
        raise HTTPException(400, "Only PNG, JPEG or WebP images are allowed")
    data = f.file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Image must be under 5MB")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[f.content_type]
    d = os.path.join(settings.UPLOAD_DIR, sub)
    os.makedirs(d, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(d, name), "wb") as fh:
        fh.write(data)
    return f"{sub}/{name}"


# ------------------------------------------------------------ public
@router.get("/plans")
def plans(db: Session = Depends(get_db)):
    """Fixed plans + live availability. Plan terms come from code, never the CMS."""
    out = []
    for p in PLANS.values():
        open_cohorts = db.scalars(select(Cohort).where(Cohort.plan_code == p.code,
                                                       Cohort.status == "registration_open")).all()
        slots = 0
        for c in open_cohorts:
            n = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(CohortMember)
                          .where(CohortMember.cohort_id == c.id, CohortMember.status != "withdrawn"))
            slots += c.capacity - n
        period = db.scalar(select(RegistrationPeriod).where(RegistrationPeriod.plan_code == p.code,
                                                            RegistrationPeriod.is_open.is_(True)))
        out.append({"code": p.code, "members": p.members, "monthly_kes": p.monthly_kes, "months": p.months,
                    "total_commitment_kes": p.per_member_total, "expected_payout_kes": p.payout_per_member,
                    "cohort_target_kes": p.cohort_target, "available_slots": slots,
                    "registration_open": bool(period),
                    "proposed_start": period.proposed_start if period else None})
    return {"plans": out, "provider_fee_note": settings.PROVIDER_FEE_NOTE,
            "live_payments": settings.live_money_allowed}


@router.get("/content")
def public_content(db: Session = Depends(get_db)):
    return {r.key: r.value for r in db.scalars(select(MythicContent))}


# ------------------------------------------------------------ member
@router.post("/applications")
def apply(gamer_tag: str = Form(...), codm_uid: str = Form(..., pattern=r"^\d{6,20}$"), rank: str = Form(...),
          email: EmailStr = Form(...), phone: str = Form(...), preferred_plan: str = Form(...),
          screenshot: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    enabled = db.get(MythicContent, "enrollment_enabled")
    if enabled and enabled.value.get("enabled") is False:
        raise HTTPException(409, "Enrollment is currently disabled")
    path = save_upload(screenshot, "clan-screenshots")
    app = run(db, svc.submit_application, user, gamer_tag=gamer_tag, codm_uid=codm_uid, rank=rank,
              email=email, phone=phone, preferred_plan=preferred_plan, screenshot_path=path)
    return {"id": app.id, "status": app.status}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.member_dashboard(db, user)


@router.post("/me/accept-terms")
def accept(user: User = Depends(current_user), db: Session = Depends(get_db)):
    run(db, svc.accept_terms, user)
    return {"ok": True}


@router.post("/contributions/{cid}/pay")
def pay(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    att = run(db, svc.initiate_payment, user, cid)
    return {"checkout_request_id": att.checkout_request_id, "message": "Approve the M-Pesa prompt on your phone."}


@router.get("/contributions/{cid}/receipt")
def receipt(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return run(db, svc.receipt_for, user, cid)


@router.get("/me/payout-receipt")
def payout_receipt(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return run(db, svc.payout_receipt_for, user)


class RefundIn(BaseModel):
    kind: str
    detail: str


@router.post("/me/refund-requests")
def refund(body: RefundIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = run(db, svc.request_refund, user, body.kind, body.detail)
    return {"id": r.id, "status": r.status, "calculated_kes": r.calculated_kes}


@router.get("/me/notifications")
def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..models.core import Notification
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.id.desc()).limit(50))
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
             "read": n.read, "created_at": n.created_at} for n in rows]


# ------------------------------------------------- provider callbacks
def _check_secret(secret: str):
    if secret != settings.CALLBACK_SECRET:
        raise HTTPException(404)


@router.post("/callbacks/{secret}/stk")
def stk_callback(secret: str, payload: dict, db: Session = Depends(get_db)):
    _check_secret(secret)
    try:
        run(db, svc.handle_stk_callback, payload)
    except HTTPException as e:
        if e.status_code in (400, 404):
            return {"ResultCode": 0, "ResultDesc": "Accepted"}  # never leak validity to callers
        raise
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/callbacks/{secret}/b2c-result")
def b2c_result(secret: str, payload: dict, db: Session = Depends(get_db)):
    _check_secret(secret)
    try:
        run(db, svc.handle_b2c_result, payload)
    except HTTPException as e:
        if e.status_code not in (400, 404):
            raise
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/callbacks/{secret}/b2c-timeout")
def b2c_timeout(secret: str, payload: dict):
    _check_secret(secret)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


# ----------------------------------------------------------- admin
@router.get("/admin/overview")
def admin_overview(_: User = Depends(require_roles(Role.finance_admin, Role.clan_verifier)),
                   db: Session = Depends(get_db)):
    return svc.overview(db)


class ReviewIn(BaseModel):
    decision: str
    note: str | None = None


@router.get("/admin/applications")
def list_apps(status: str | None = None, _: User = Depends(verifier), db: Session = Depends(get_db)):
    q = select(Application).order_by(Application.id.desc())
    if status:
        q = q.where(Application.status == status)
    return [{"id": a.id, "user_id": a.user_id, "gamer_tag": a.gamer_tag, "codm_uid": a.codm_uid, "rank": a.rank,
             "email": a.email, "phone": a.phone, "plan": a.preferred_plan, "status": a.status,
             "screenshot": f"/api/mythic/admin/screenshots/{a.id}", "note": a.review_note,
             "waitlist_position": a.waitlist_position, "created_at": a.created_at,
             "assigned": db.scalar(select(CohortMember.id).where(CohortMember.user_id == a.user_id)) is not None}
            for a in db.scalars(q)]


@router.get("/admin/screenshots/{app_id}")
def screenshot(app_id: int, _: User = Depends(verifier), db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(404)
    path = os.path.join(settings.UPLOAD_DIR, a.screenshot_path)
    if not os.path.abspath(path).startswith(os.path.abspath(settings.UPLOAD_DIR)) or not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path)


@router.post("/admin/applications/{aid}/review")
def review(aid: int, body: ReviewIn, admin: User = Depends(verifier), db: Session = Depends(get_db)):
    a = db.get(Application, aid)
    if not a:
        raise HTTPException(404)
    run(db, svc.review_application, admin, a, body.decision, body.note)
    return {"id": a.id, "status": a.status}


class PeriodIn(BaseModel):
    plan_code: str
    opens_at: datetime
    closes_at: datetime
    proposed_start: date | None = None


@router.post("/admin/periods")
def create_period(body: PeriodIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    try:
        p = run(db, svc.set_period, admin, body.plan_code, body.opens_at, body.closes_at, body.proposed_start)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": p.id}


@router.get("/admin/periods")
def list_periods(_: User = Depends(finance), db: Session = Depends(get_db)):
    return [{"id": p.id, "plan": p.plan_code, "is_open": p.is_open, "opens_at": p.opens_at,
             "closes_at": p.closes_at, "drawn_at": p.drawn_at, "draw_seed": p.draw_seed}
            for p in db.scalars(select(RegistrationPeriod).order_by(RegistrationPeriod.id.desc()))]


@router.post("/admin/periods/{pid}/{action}")
def period_action(pid: int, action: str, admin: User = Depends(finance), db: Session = Depends(get_db)):
    p = db.get(RegistrationPeriod, pid)
    if not p:
        raise HTTPException(404)
    if action in ("open", "close"):
        run(db, svc.toggle_period, admin, p, action == "open")
        return {"is_open": p.is_open}
    if action == "draw":
        return run(db, svc.run_draw, admin, pid)
    raise HTTPException(400, "Unknown action")


class CohortIn(BaseModel):
    name: str
    size: int  # 7 or 10 only
    proposed_start: date | None = None


@router.post("/admin/cohorts")
def new_cohort(body: CohortIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    c = run(db, svc.create_cohort, admin, body.name, body.size, body.proposed_start)
    return {"id": c.id, "plan": c.plan_code}


@router.get("/admin/cohorts")
def list_cohorts(_: User = Depends(finance), db: Session = Depends(get_db)):
    return [svc.cohort_public_progress(db, c) | {"monthly_kes": c.monthly_kes, "months": c.months,
                                                 "start_date": c.start_date}
            for c in db.scalars(select(Cohort).order_by(Cohort.id.desc()))]


@router.get("/admin/cohorts/{cid}")
def cohort_detail(cid: int, _: User = Depends(finance), db: Session = Depends(get_db)):
    c = db.get(Cohort, cid)
    if not c:
        raise HTTPException(404)
    outstanding = db.scalars(select(Contribution).where(Contribution.cohort_id == cid,
                                                        Contribution.status.in_(["overdue", "failed"])))
    return {"progress": svc.cohort_public_progress(db, c), "reconciliation": svc.reconciliation(db, c),
            "outstanding": [{"member_id": x.member_id, "month_no": x.month_no, "amount_kes": x.amount_kes,
                             "status": x.status} for x in outstanding]}


class AssignIn(BaseModel):
    application_id: int


@router.post("/admin/cohorts/{cid}/assign")
def assign(cid: int, body: AssignIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    m = run(db, svc.assign_member, admin, cid, body.application_id)
    return {"member_id": m.id}


class ActivateIn(BaseModel):
    start_date: date


@router.post("/admin/cohorts/{cid}/activate")
def activate(cid: int, body: ActivateIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    c = run(db, svc.activate_cohort, admin, cid, body.start_date)
    return {"status": c.status}


class ReasonIn(BaseModel):
    reason: str


@router.post("/admin/cohorts/{cid}/pause")
def pause(cid: int, body: ReasonIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.set_pause, admin, cid, True, body.reason)
    return {"ok": True}


@router.post("/admin/cohorts/{cid}/resume")
def resume(cid: int, body: ReasonIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.set_pause, admin, cid, False, body.reason)
    return {"ok": True}


@router.post("/admin/cohorts/{cid}/cancel")
def cancel(cid: int, body: ReasonIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.cancel_cohort, admin, cid, body.reason)
    return {"ok": True}


@router.post("/admin/cohorts/{cid}/promote-waitlist")
def promote(cid: int, admin: User = Depends(finance), db: Session = Depends(get_db)):
    return {"promoted": run(db, svc.promote_waitlist, admin, cid)}


@router.post("/admin/cohorts/{cid}/recheck-funding")
def recheck(cid: int, _: User = Depends(finance), db: Session = Depends(get_db)):
    c = db.get(Cohort, cid)
    run(db, lambda d: svc.recheck_funding(d, c))
    return {"status": c.status}


@router.get("/admin/exceptions")
def exceptions(_: User = Depends(finance), db: Session = Depends(get_db)):
    return [{"id": e.id, "cohort_id": e.cohort_id, "member_id": e.member_id, "kind": e.kind, "detail": e.detail,
             "resolved": e.resolved, "resolution": e.resolution}
            for e in db.scalars(select(ExceptionCase).order_by(ExceptionCase.id.desc()))]


class ResolveIn(BaseModel):
    resolution: str


@router.post("/admin/exceptions/{eid}/resolve")
def resolve_exc(eid: int, body: ResolveIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.resolve_exception, admin, eid, body.resolution)
    return {"ok": True}


@router.post("/admin/contributions/{cid}/reverse")
def reverse(cid: int, body: ReasonIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.mark_reversed, admin, cid, body.reason)
    return {"ok": True}


# payouts
@router.post("/admin/cohorts/{cid}/payout-batch")
def request_batch(cid: int, admin: User = Depends(finance), db: Session = Depends(get_db)):
    b = run(db, svc.request_payout_batch, admin, cid)
    return {"batch_id": b.id, "total_kes": b.total_kes, "manifest_hash": b.manifest_hash}


@router.get("/admin/payout-batches")
def batches(_: User = Depends(finance), db: Session = Depends(get_db)):
    out = []
    for b in db.scalars(select(PayoutBatch).order_by(PayoutBatch.id.desc())):
        out.append({"id": b.id, "cohort_id": b.cohort_id, "status": b.status, "total_kes": b.total_kes,
                    "manifest": b.manifest, "manifest_hash": b.manifest_hash, "reconciliation": b.reconciliation,
                    "approvals": [{"admin_id": a.admin_id, "decision": a.decision} for a in b.approvals],
                    "payouts": [{"id": p.id, "member_id": p.member_id, "amount_kes": p.amount_kes,
                                 "status": p.status, "receipt": p.mpesa_receipt} for p in b.payouts]})
    return out


class DecisionIn(BaseModel):
    decision: str
    note: str | None = None


@router.post("/admin/payout-batches/{bid}/decision")
def decide(bid: int, body: DecisionIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    b = run(db, svc.decide_batch, admin, bid, body.decision, body.note)
    return {"status": b.status}


@router.post("/admin/payout-batches/{bid}/execute")
def execute(bid: int, admin: User = Depends(finance), db: Session = Depends(get_db)):
    b = run(db, svc.execute_batch, admin, bid)
    return {"status": b.status}


@router.post("/admin/payouts/{pid}/retry")
def retry(pid: int, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.retry_failed_payout, admin, pid)
    return {"ok": True}


class SettleIn(BaseModel):
    note: str


@router.post("/admin/payouts/{pid}/resolve")
def resolve_payout(pid: int, body: SettleIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.resolve_payout, admin, pid, body.note)
    return {"ok": True}


# refunds
@router.get("/admin/refunds")
def refunds(_: User = Depends(finance), db: Session = Depends(get_db)):
    return [{"id": r.id, "member_id": r.member_id, "kind": r.reason_kind, "detail": r.detail,
             "calculated_kes": r.calculated_kes, "status": r.status, "decision_reason": r.decision_reason}
            for r in db.scalars(select(RefundRequest).order_by(RefundRequest.id.desc()))]


class RefundDecisionIn(BaseModel):
    approve: bool
    reason: str | None = None


@router.post("/admin/refunds/{rid}/decision")
def refund_decision(rid: int, body: RefundDecisionIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    r = run(db, svc.decide_refund, admin, rid, body.approve, body.reason)
    return {"status": r.status}


class RefundPaidIn(BaseModel):
    provider_ref: str


@router.post("/admin/refunds/{rid}/paid")
def refund_paid(rid: int, body: RefundPaidIn, admin: User = Depends(finance), db: Session = Depends(get_db)):
    run(db, svc.mark_refund_paid, admin, rid, body.provider_ref)
    return {"ok": True}


@router.get("/admin/ledger")
def ledger(cohort_id: int | None = None, _: User = Depends(finance), db: Session = Depends(get_db)):
    from ..models.mythic import LedgerEntry
    q = select(LedgerEntry).order_by(LedgerEntry.id.desc()).limit(500)
    if cohort_id:
        q = q.where(LedgerEntry.cohort_id == cohort_id)
    return [{"id": e.id, "cohort_id": e.cohort_id, "member_id": e.member_id, "kind": e.kind,
             "direction": e.direction, "amount_kes": e.amount_kes, "ref": e.provider_ref,
             "created_at": e.created_at} for e in db.scalars(q)]


@router.get("/admin/audit")
def audit_trail(_: User = Depends(finance), db: Session = Depends(get_db)):
    return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "entity": a.entity_type,
             "entity_id": a.entity_id, "before": a.before, "after": a.after, "at": a.created_at}
            for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(500))]


class ContentIn(BaseModel):
    value: dict


@router.put("/admin/content/{key}")
def put_content(key: str, body: ContentIn, admin: User = Depends(content_admin), db: Session = Depends(get_db)):
    # Whitelist: plan terms (members, monthly amount, months, payout) can never be set here.
    if key not in CMS_KEYS:
        raise HTTPException(400, "Unknown content key")
    banned = {"members", "capacity", "monthly_kes", "months", "payout", "plan", "plans", "contribution"}
    if banned & {str(k).lower() for k in body.value}:
        raise HTTPException(400, "Plan terms are fixed and cannot be changed through content management")
    row = db.get(MythicContent, key)
    before = row.value if row else None
    if row:
        row.value, row.updated_by = body.value, admin.id
    else:
        db.add(MythicContent(key=key, value=body.value, updated_by=admin.id))
    audit(db, admin.id, "mythic.content.updated", "content", key, before, body.value)
    db.commit()
    return {"ok": True}
