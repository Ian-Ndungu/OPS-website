import calendar
import hashlib
import json
import random
import re
import secrets
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.core import Role, User
from ..models.mythic import (Application, Cohort, CohortMember, CohortStatus, Contribution,
                             ExceptionCase, LedgerEntry, Payout, PayoutApproval, PayoutBatch,
                             PaymentAttempt, PaymentStatus, RefundRequest, RegistrationPeriod,
                             VerificationStatus)
from ..providers.payments import PaymentProvider, ProviderError, get_provider
from .common import audit, notify
from .plans import PLANS, plan_by_code

TERMS_VERSION = "v1"
MANDATORY_REFUND_KINDS = {"pre_activation_cancel", "cohort_cancelled", "legal"}
REFUND_KINDS = MANDATORY_REFUND_KINDS | {"exceptional", "death_incapacity", "dispute"}
LIVE_STATES = {CohortStatus.active.value, CohortStatus.contributions_in_progress.value,
               CohortStatus.fully_funded.value, CohortStatus.payout_approval_pending.value,
               CohortStatus.processing_payouts.value}


class MythicError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------- helpers
def normalize_phone(raw: str) -> str:
    p = re.sub(r"[\s\-+]", "", raw or "")
    if re.fullmatch(r"0[17]\d{8}", p):
        p = "254" + p[1:]
    if not re.fullmatch(r"254[17]\d{8}", p):
        raise MythicError("Enter a valid Kenyan M-Pesa number (e.g. 07XXXXXXXX)")
    return p


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _cohort(db: Session, cohort_id: int, lock: bool = False) -> Cohort:
    q = select(Cohort).where(Cohort.id == cohort_id)
    if lock:
        q = q.with_for_update()
    c = db.execute(q).scalar_one_or_none()
    if not c:
        raise MythicError("Cohort not found", 404)
    return c


def ledger_net(db: Session, cohort_id: int) -> int:
    ins = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_kes), 0))
                    .where(LedgerEntry.cohort_id == cohort_id, LedgerEntry.direction == "in"))
    outs = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_kes), 0))
                     .where(LedgerEntry.cohort_id == cohort_id, LedgerEntry.direction == "out"))
    return int(ins) - int(outs)


def paid_total(db: Session, member_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Contribution.amount_kes), 0))
                         .where(Contribution.member_id == member_id,
                                Contribution.status == PaymentStatus.paid.value)))


# ------------------------------------------------------- registration
def submit_application(db: Session, user: User, *, gamer_tag, codm_uid, rank, email, phone,
                       preferred_plan, screenshot_path) -> Application:
    if preferred_plan not in PLANS:
        raise MythicError("Preferred cohort must be 7 or 10 players")
    existing = db.scalar(select(Application).where(Application.user_id == user.id))
    if existing:
        if existing.status == VerificationStatus.resubmission_required.value:
            return resubmit_application(db, user, existing, gamer_tag=gamer_tag, codm_uid=codm_uid,
                                        rank=rank, email=email, phone=phone,
                                        preferred_plan=preferred_plan, screenshot_path=screenshot_path)
        raise MythicError("You already have a Mythic Circle application", 409)
    if db.scalar(select(Application).where(Application.codm_uid == codm_uid)):
        raise MythicError("This CODM UID has already been used for an application", 409)
    app = Application(user_id=user.id, gamer_tag=gamer_tag, codm_uid=codm_uid, rank=rank, email=email,
                      phone=normalize_phone(phone), preferred_plan=preferred_plan,
                      screenshot_path=screenshot_path)
    db.add(app)
    db.flush()
    audit(db, user.id, "mythic.application.submitted", "application", app.id)
    return app


def resubmit_application(db, user, app, **f):
    app.gamer_tag, app.codm_uid, app.rank, app.email = f["gamer_tag"], f["codm_uid"], f["rank"], f["email"]
    app.phone, app.preferred_plan = normalize_phone(f["phone"]), f["preferred_plan"]
    app.screenshot_path = f["screenshot_path"]
    app.status = VerificationStatus.pending.value
    audit(db, user.id, "mythic.application.resubmitted", "application", app.id)
    return app


def review_application(db: Session, admin: User, app: Application, decision: str, note: str | None):
    allowed = {"under_review", "approved", "rejected", "resubmission_required"}
    if decision not in allowed:
        raise MythicError("Invalid decision")
    if decision in {"rejected", "resubmission_required"} and not (note or "").strip():
        raise MythicError("A reason is required so the applicant can respond")
    before = app.status
    app.status, app.reviewer_id, app.review_note = decision, admin.id, note
    if decision == "approved":
        # Evidence must have been supplied; admin confirms by approving.
        user = db.get(User, app.user_id)
        user.is_verified_member = True
    audit(db, admin.id, f"mythic.application.{decision}", "application", app.id,
          {"status": before}, {"status": decision, "note": note})
    notify(db, app.user_id, "mythic", f"Mythic Circle application: {decision.replace('_', ' ')}",
           note or "", "/dashboard/mythic-circle")


def set_period(db: Session, admin: User, plan_code, opens_at, closes_at, proposed_start) -> RegistrationPeriod:
    plan_by_code(plan_code)
    if closes_at <= opens_at:
        raise MythicError("Closing time must be after opening time")
    p = RegistrationPeriod(plan_code=plan_code, opens_at=opens_at, closes_at=closes_at,
                           proposed_start=proposed_start, created_by=admin.id, is_open=False)
    db.add(p)
    db.flush()
    audit(db, admin.id, "mythic.period.created", "period", p.id, after={"plan": plan_code})
    return p


def toggle_period(db: Session, admin: User, period: RegistrationPeriod, is_open: bool):
    before = period.is_open
    period.is_open = is_open
    audit(db, admin.id, "mythic.period.open" if is_open else "mythic.period.close", "period", period.id,
          {"is_open": before}, {"is_open": is_open})


# ------------------------------------------------------------- cohorts
def create_cohort(db: Session, admin: User, name: str, size: int, proposed_start: date | None) -> Cohort:
    plan = next((p for p in PLANS.values() if p.members == size), None)
    if not plan:
        raise MythicError("Only 7-member and 10-member cohorts are permitted")
    c = Cohort(name=name, plan_code=plan.code, capacity=plan.members, monthly_kes=plan.monthly_kes,
               months=plan.months, proposed_start=proposed_start, terms_version=TERMS_VERSION)
    db.add(c)
    db.flush()
    audit(db, admin.id, "mythic.cohort.created", "cohort", c.id,
          after={"plan": plan.code, "capacity": plan.members})
    return c


def _mark_filled_if_needed(db: Session, c: Cohort):
    n = db.scalar(select(func.count()).select_from(CohortMember)
                  .where(CohortMember.cohort_id == c.id, CohortMember.status != "withdrawn"))
    if n >= c.capacity and c.status == CohortStatus.registration_open.value:
        c.status = CohortStatus.filled.value
        c.status = CohortStatus.awaiting_acceptance.value  # filled -> pending activation


def _add_member(db: Session, c: Cohort, app: Application) -> CohortMember:
    if db.scalar(select(CohortMember).where(CohortMember.user_id == app.user_id)):
        raise MythicError("Member already belongs to a cohort", 409)
    m = CohortMember(cohort_id=c.id, user_id=app.user_id, application_id=app.id, payout_phone=app.phone)
    db.add(m)
    db.flush()
    app.waitlist_position = None
    notify(db, app.user_id, "mythic", f"You have a place in {c.name}",
           "Review and accept the terms to proceed.", "/dashboard/mythic-circle")
    return m


def assign_member(db: Session, admin: User, cohort_id: int, application_id: int) -> CohortMember:
    c = _cohort(db, cohort_id, lock=True)
    app = db.get(Application, application_id)
    if not app or app.status != VerificationStatus.approved.value:
        raise MythicError("Only approved applicants can be assigned")
    if c.status != CohortStatus.registration_open.value:
        raise MythicError("Cohort is not open for assignment", 409)
    if app.preferred_plan != c.plan_code:
        raise MythicError("Applicant preferred a different plan", 409)
    m = _add_member(db, c, app)
    _mark_filled_if_needed(db, c)
    audit(db, admin.id, "mythic.cohort.member_assigned", "cohort", c.id, after={"application": app.id})
    return m


def run_draw(db: Session, admin: User, period_id: int) -> dict:
    """Fair, auditable random assignment of approved applicants into open
    cohorts of the period's plan. The seed is stored so the draw can be
    reproduced and verified. Overflow applicants join the waiting list."""
    period = db.get(RegistrationPeriod, period_id)
    if not period:
        raise MythicError("Period not found", 404)
    if period.drawn_at:
        raise MythicError("Draw already performed for this period", 409)
    eligible = list(db.scalars(
        select(Application).where(
            Application.status == VerificationStatus.approved.value,
            Application.preferred_plan == period.plan_code,
            ~Application.user_id.in_(select(CohortMember.user_id))).order_by(Application.id)))
    seed = secrets.token_hex(16)
    random.Random(seed).shuffle(eligible)
    cohorts = list(db.scalars(select(Cohort).where(
        Cohort.plan_code == period.plan_code,
        Cohort.status == CohortStatus.registration_open.value).order_by(Cohort.id).with_for_update()))
    assigned, waitlisted = 0, 0
    pos = 1 + int(db.scalar(select(func.coalesce(func.max(Application.waitlist_position), 0))))
    for app in eligible:
        app.period_id = period.id
        placed = False
        for c in cohorts:
            if c.status != CohortStatus.registration_open.value:
                continue
            _add_member(db, c, app)
            _mark_filled_if_needed(db, c)
            assigned += 1
            placed = True
            break
        if not placed:
            app.waitlist_position = pos
            pos += 1
            waitlisted += 1
    period.drawn_at, period.draw_seed, period.is_open = datetime.now(timezone.utc), seed, False
    audit(db, admin.id, "mythic.draw.executed", "period", period.id,
          after={"seed": seed, "assigned": assigned, "waitlisted": waitlisted})
    return {"seed": seed, "assigned": assigned, "waitlisted": waitlisted}


def promote_waitlist(db: Session, admin: User, cohort_id: int) -> int:
    c = _cohort(db, cohort_id, lock=True)
    if c.status != CohortStatus.registration_open.value:
        raise MythicError("Cohort is not open", 409)
    n = 0
    for app in db.scalars(select(Application).where(
            Application.waitlist_position.is_not(None), Application.preferred_plan == c.plan_code,
            Application.status == VerificationStatus.approved.value).order_by(Application.waitlist_position)):
        if c.status != CohortStatus.registration_open.value:
            break
        _add_member(db, c, app)
        _mark_filled_if_needed(db, c)
        n += 1
    audit(db, admin.id, "mythic.waitlist.promoted", "cohort", c.id, after={"count": n})
    return n


def accept_terms(db: Session, user: User) -> CohortMember:
    m = db.scalar(select(CohortMember).where(CohortMember.user_id == user.id))
    if not m or m.status == "withdrawn":
        raise MythicError("You are not in a cohort", 404)
    c = _cohort(db, m.cohort_id)
    if c.status != CohortStatus.awaiting_acceptance.value:
        raise MythicError("Cohort is not awaiting acceptance", 409)
    m.status, m.accepted_terms_at, m.accepted_terms_version = "accepted", datetime.now(timezone.utc), c.terms_version
    audit(db, user.id, "mythic.terms.accepted", "member", m.id, after={"version": c.terms_version})
    return m


def activate_cohort(db: Session, admin: User, cohort_id: int, start: date) -> Cohort:
    c = _cohort(db, cohort_id, lock=True)
    if c.status != CohortStatus.awaiting_acceptance.value:
        raise MythicError("Cohort must be awaiting acceptance", 409)
    members = list(db.scalars(select(CohortMember).where(CohortMember.cohort_id == c.id,
                                                         CohortMember.status != "withdrawn")))
    if len(members) != c.capacity:
        raise MythicError(f"Cohort needs exactly {c.capacity} members", 409)
    if any(m.status != "accepted" for m in members):
        raise MythicError("All participants must accept the terms before activation", 409)
    c.start_date, c.status = start, CohortStatus.active.value
    for m in members:
        for k in range(c.months):
            db.add(Contribution(member_id=m.id, cohort_id=c.id, month_no=k + 1,
                                due_date=add_months(start, k), amount_kes=c.monthly_kes))
    audit(db, admin.id, "mythic.cohort.activated", "cohort", c.id, after={"start": start.isoformat()})
    for m in members:
        notify(db, m.user_id, "mythic", f"{c.name} is now active",
               f"First contribution of KSh {c.monthly_kes:,} is due {start:%d %b %Y}.", "/dashboard/mythic-circle")
    return c


def set_pause(db: Session, admin: User, cohort_id: int, paused: bool, reason: str):
    c = _cohort(db, cohort_id, lock=True)
    if paused:
        if c.status not in LIVE_STATES:
            raise MythicError("Only live cohorts can be paused", 409)
        c.status_before_pause, c.status = c.status, CohortStatus.paused.value
    else:
        if c.status != CohortStatus.paused.value:
            raise MythicError("Cohort is not paused", 409)
        c.status, c.status_before_pause = c.status_before_pause or CohortStatus.active.value, None
    audit(db, admin.id, "mythic.cohort.pause" if paused else "mythic.cohort.resume", "cohort", c.id,
          after={"reason": reason})


# ------------------------------------------------------ contributions
def initiate_payment(db: Session, user: User, contribution_id: int,
                     provider: PaymentProvider | None = None) -> PaymentAttempt:
    con = db.get(Contribution, contribution_id)
    m = db.get(CohortMember, con.member_id) if con else None
    if not con or m.user_id != user.id:
        raise MythicError("Contribution not found", 404)
    c = _cohort(db, con.cohort_id)
    if c.status not in {CohortStatus.active.value, CohortStatus.contributions_in_progress.value}:
        raise MythicError("Cohort is not accepting contributions", 409)
    if con.status in {PaymentStatus.paid.value, PaymentStatus.refunded.value}:
        raise MythicError("This instalment is already settled", 409)
    in_flight = db.scalar(select(PaymentAttempt).where(PaymentAttempt.contribution_id == con.id,
                                                       PaymentAttempt.status == "initiated"))
    if in_flight:
        raise MythicError("A payment prompt is already awaiting your confirmation", 409)
    prov = provider or get_provider()
    try:
        res = prov.stk_push(m.payout_phone, con.amount_kes, f"MYTHIC{con.id}", "OPS Mythic")
    except ProviderError as e:
        raise MythicError(str(e), 502)
    att = PaymentAttempt(contribution_id=con.id, checkout_request_id=res.checkout_request_id,
                         merchant_request_id=res.merchant_request_id, phone=m.payout_phone,
                         amount_kes=con.amount_kes)
    db.add(att)
    audit(db, user.id, "mythic.payment.initiated", "contribution", con.id)
    return att


def _parse_stk(payload: dict):
    cb = payload["Body"]["stkCallback"]
    items = {i["Name"]: i.get("Value") for i in (cb.get("CallbackMetadata") or {}).get("Item", [])}
    return cb["CheckoutRequestID"], int(cb["ResultCode"]), cb.get("ResultDesc", ""), items


def handle_stk_callback(db: Session, payload: dict) -> str:
    """Only place a contribution becomes 'paid'. Requires a known checkout id,
    ResultCode 0, matching amount, and a unique M-Pesa receipt."""
    try:
        checkout_id, code, desc, items = _parse_stk(payload)
    except (KeyError, TypeError, ValueError):
        raise MythicError("Malformed callback", 400)
    att = db.execute(select(PaymentAttempt).where(PaymentAttempt.checkout_request_id == checkout_id)
                     .with_for_update()).scalar_one_or_none()
    if not att:
        raise MythicError("Unknown checkout request", 404)
    if att.status != "initiated":
        return "duplicate"
    att.raw_callback = payload
    con = db.execute(select(Contribution).where(Contribution.id == att.contribution_id)
                     .with_for_update()).scalar_one()
    if code != 0:
        att.status = "failed"
        if con.status != PaymentStatus.paid.value:
            con.status = (PaymentStatus.overdue.value if con.due_date < date.today()
                          else PaymentStatus.failed.value)
        audit(db, None, "mythic.payment.failed", "contribution", con.id, after={"desc": desc})
        return "failed"
    receipt, amount = items.get("MpesaReceiptNumber"), items.get("Amount")
    if not receipt or amount is None or int(float(amount)) != att.amount_kes:
        att.status = "failed"
        db.add(ExceptionCase(cohort_id=con.cohort_id, member_id=con.member_id,
                             kind="reconciliation_mismatch",
                             detail=f"Callback amount/receipt mismatch for checkout {checkout_id}"))
        audit(db, None, "mythic.payment.mismatch", "contribution", con.id)
        return "mismatch"
    if db.scalar(select(LedgerEntry).where(LedgerEntry.provider_ref == receipt)):
        return "duplicate"
    if con.status == PaymentStatus.paid.value:
        db.add(ExceptionCase(cohort_id=con.cohort_id, member_id=con.member_id, kind="other",
                             detail=f"Duplicate payment {receipt} received for settled instalment; refund required"))
        att.status = "succeeded"
        return "overpaid"
    att.status = "succeeded"
    con.status, con.paid_at, con.mpesa_receipt = PaymentStatus.paid.value, datetime.now(timezone.utc), receipt
    con.reconciled = True
    db.add(LedgerEntry(cohort_id=con.cohort_id, member_id=con.member_id, kind="contribution",
                       direction="in", amount_kes=att.amount_kes, provider_ref=receipt,
                       contribution_id=con.id, note=f"Month {con.month_no}"))
    c = _cohort(db, con.cohort_id, lock=True)
    if c.status == CohortStatus.active.value:
        c.status = CohortStatus.contributions_in_progress.value
    m = db.get(CohortMember, con.member_id)
    notify(db, m.user_id, "mythic", "Payment received",
           f"KSh {att.amount_kes:,} for month {con.month_no}. Receipt {receipt}.", "/dashboard/mythic-circle")
    db.flush()  # reconciliation queries must see this payment (sessions run with autoflush off)
    _check_fully_funded(db, c)
    audit(db, None, "mythic.payment.confirmed", "contribution", con.id, after={"receipt": receipt})
    return "paid"


def mark_reversed(db: Session, admin: User, contribution_id: int, reason: str):
    con = db.get(Contribution, contribution_id)
    if not con or con.status != PaymentStatus.paid.value:
        raise MythicError("Only paid contributions can be reversed", 409)
    con.status, con.reconciled = PaymentStatus.reversed.value, False
    db.add(LedgerEntry(cohort_id=con.cohort_id, member_id=con.member_id, kind="reversal", direction="out",
                       amount_kes=con.amount_kes, contribution_id=con.id,
                       provider_ref=f"REV-{con.mpesa_receipt}", note=reason))
    db.add(ExceptionCase(cohort_id=con.cohort_id, member_id=con.member_id, kind="failed_payment",
                         detail=f"Reversal: {reason}"))
    audit(db, admin.id, "mythic.payment.reversed", "contribution", con.id, after={"reason": reason})


def mark_overdue(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    rows = db.scalars(select(Contribution).where(
        Contribution.status.in_([PaymentStatus.pending.value, PaymentStatus.failed.value]),
        Contribution.due_date < today))
    n = 0
    for con in rows:
        con.status = PaymentStatus.overdue.value
        m = db.get(CohortMember, con.member_id)
        notify(db, m.user_id, "mythic", "Contribution overdue",
               f"Month {con.month_no} (KSh {con.amount_kes:,}) was due {con.due_date:%d %b}.",
               "/dashboard/mythic-circle")
        n += 1
    return n


def send_reminders(db: Session, today: date | None = None, days_ahead: int = 3) -> int:
    today = today or date.today()
    n = 0
    for con in db.scalars(select(Contribution).where(Contribution.status == PaymentStatus.pending.value)):
        if 0 <= (con.due_date - today).days <= days_ahead:
            m = db.get(CohortMember, con.member_id)
            notify(db, m.user_id, "mythic", "Contribution due soon",
                   f"KSh {con.amount_kes:,} due {con.due_date:%d %b}.", "/dashboard/mythic-circle")
            n += 1
    return n


# ----------------------------------------------- funding & reconciliation
def reconciliation(db: Session, c: Cohort) -> dict:
    members = list(db.scalars(select(CohortMember).where(CohortMember.cohort_id == c.id,
                                                         CohortMember.status != "withdrawn")))
    plan = plan_by_code(c.plan_code)
    rows, ok = [], True
    for m in members:
        paid = paid_total(db, m.id)
        unreconciled = db.scalar(select(func.count()).select_from(Contribution).where(
            Contribution.member_id == m.id, Contribution.status == PaymentStatus.paid.value,
            Contribution.reconciled.is_(False)))
        periods_done = db.scalar(select(func.count()).select_from(Contribution).where(
            Contribution.member_id == m.id, Contribution.status == PaymentStatus.paid.value))
        row_ok = paid == plan.per_member_total and periods_done == c.months and unreconciled == 0
        ok &= row_ok
        rows.append({"member_id": m.id, "user_id": m.user_id, "paid_kes": paid,
                     "required_kes": plan.per_member_total, "periods_paid": periods_done,
                     "unreconciled": unreconciled, "ok": row_ok})
    # Ledger per-contribution cross-check
    ledger_in = int(db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_kes), 0)).where(
        LedgerEntry.cohort_id == c.id, LedgerEntry.kind == "contribution")))
    paid_sum = sum(r["paid_kes"] for r in rows)
    open_exceptions = int(db.scalar(select(func.count()).select_from(ExceptionCase).where(
        ExceptionCase.cohort_id == c.id, ExceptionCase.resolved.is_(False))))
    net = ledger_net(db, c.id)
    checks = {
        "all_periods_paid": all(r["periods_paid"] == c.months for r in rows) and len(rows) == c.capacity,
        "exact_contributions": all(r["paid_kes"] == plan.per_member_total for r in rows),
        "all_reconciled": all(r["unreconciled"] == 0 for r in rows),
        "ledger_matches_contributions": ledger_in == paid_sum,
        "sufficient_funds": net >= plan.cohort_target,
        "no_open_exceptions": open_exceptions == 0,
    }
    return {"cohort_id": c.id, "target_kes": plan.cohort_target, "ledger_net_kes": net,
            "total_payout_liability_kes": plan.payout_per_member * len(rows), "members": rows,
            "open_exceptions": open_exceptions, "checks": checks, "eligible": all(checks.values()) and ok}


def _check_fully_funded(db: Session, c: Cohort):
    if c.status != CohortStatus.contributions_in_progress.value:
        return
    if reconciliation(db, c)["eligible"]:
        c.status = CohortStatus.fully_funded.value
        for admin in db.scalars(select(User).where(User.role.in_([Role.finance_admin.value, Role.super_admin.value]))):
            notify(db, admin.id, "mythic", f"{c.name} is fully funded",
                   "Review reconciliation and request payout approval.", "/admin/mythic-circle")


def recheck_funding(db: Session, c: Cohort):
    """Admin-callable after resolving exceptions."""
    db.flush()
    _check_fully_funded(db, c)


def resolve_exception(db: Session, admin: User, exc_id: int, resolution: str):
    e = db.get(ExceptionCase, exc_id)
    if not e or e.resolved:
        raise MythicError("Exception not found or already resolved", 404)
    if not resolution.strip():
        raise MythicError("Resolution note required")
    e.resolved, e.resolution = True, resolution
    audit(db, admin.id, "mythic.exception.resolved", "exception", e.id, after={"resolution": resolution})


# ------------------------------------------------------------- payouts
def _manifest(db: Session, c: Cohort) -> dict:
    members = list(db.scalars(select(CohortMember).where(CohortMember.cohort_id == c.id,
                                                         CohortMember.status != "withdrawn")
                              .order_by(CohortMember.id)))
    plan = plan_by_code(c.plan_code)
    return {"cohort_id": c.id,
            "items": [{"member_id": m.id, "phone": m.payout_phone, "amount_kes": plan.payout_per_member}
                      for m in members]}


def _hash(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def request_payout_batch(db: Session, admin: User, cohort_id: int) -> PayoutBatch:
    c = _cohort(db, cohort_id, lock=True)
    if c.status != CohortStatus.fully_funded.value:
        raise MythicError("Cohort is not fully funded", 409)
    rec = reconciliation(db, c)
    if not rec["eligible"]:
        raise MythicError("Payout conditions not met: " + ", ".join(k for k, v in rec["checks"].items() if not v), 409)
    if db.scalar(select(PayoutBatch).where(PayoutBatch.cohort_id == c.id, PayoutBatch.status != "rejected")):
        raise MythicError("A payout batch already exists for this cohort", 409)
    man = _manifest(db, c)
    batch = PayoutBatch(cohort_id=c.id, manifest=man, manifest_hash=_hash(man),
                        total_kes=sum(i["amount_kes"] for i in man["items"]), reconciliation=rec,
                        requested_by=admin.id)
    db.add(batch)
    db.flush()
    for it in man["items"]:
        db.add(Payout(batch_id=batch.id, member_id=it["member_id"], phone=it["phone"],
                      amount_kes=it["amount_kes"]))
    c.status = CohortStatus.payout_approval_pending.value
    audit(db, admin.id, "mythic.payout.requested", "batch", batch.id,
          after={"hash": batch.manifest_hash, "total": batch.total_kes})
    return batch


def decide_batch(db: Session, admin: User, batch_id: int, decision: str, note: str | None) -> PayoutBatch:
    if decision not in {"approve", "reject"}:
        raise MythicError("Invalid decision")
    batch = db.execute(select(PayoutBatch).where(PayoutBatch.id == batch_id).with_for_update()).scalar_one_or_none()
    if not batch:
        raise MythicError("Batch not found", 404)
    if batch.status != "pending_approval":
        raise MythicError("Batch is no longer awaiting approval", 409)
    if db.scalar(select(PayoutApproval).where(PayoutApproval.batch_id == batch.id,
                                              PayoutApproval.admin_id == admin.id)):
        raise MythicError("You have already decided on this batch", 409)
    db.add(PayoutApproval(batch_id=batch.id, admin_id=admin.id, decision=decision,
                          manifest_hash=batch.manifest_hash, note=note))
    db.flush()
    c = _cohort(db, batch.cohort_id, lock=True)
    if decision == "reject":
        batch.status = "rejected"
        # A rejected batch is superseded: removed so a fresh request (new approval process) can be made.
        for p in list(batch.payouts):
            db.delete(p)
        c.status = CohortStatus.fully_funded.value
        audit(db, admin.id, "mythic.payout.rejected", "batch", batch.id, after={"note": note})
        return batch
    approvals = db.scalars(select(PayoutApproval).where(
        PayoutApproval.batch_id == batch.id, PayoutApproval.decision == "approve",
        PayoutApproval.manifest_hash == batch.manifest_hash)).all()
    if len({a.admin_id for a in approvals}) >= 2:
        batch.status, batch.locked_at = "approved", datetime.now(timezone.utc)
    audit(db, admin.id, "mythic.payout.approved_vote", "batch", batch.id, after={"count": len(approvals)})
    return batch


def execute_batch(db: Session, admin: User, batch_id: int, provider: PaymentProvider | None = None) -> PayoutBatch:
    """Re-verifies everything at the moment of disbursement, then submits all
    payouts together. Per-payout failures are tracked individually."""
    batch = db.execute(select(PayoutBatch).where(PayoutBatch.id == batch_id).with_for_update()).scalar_one_or_none()
    if not batch:
        raise MythicError("Batch not found", 404)
    if batch.status != "approved":
        raise MythicError("Batch requires two-person approval first", 409)
    c = _cohort(db, batch.cohort_id, lock=True)
    # 1. manifest unchanged vs. what was approved
    if _hash(_manifest(db, c)) != batch.manifest_hash or _hash(batch.manifest) != batch.manifest_hash:
        raise MythicError("Manifest differs from approved version; a new approval process is required", 409)
    # 2. verified funds right now
    rec = reconciliation(db, c)
    if not rec["checks"]["sufficient_funds"] or not rec["checks"]["exact_contributions"] \
            or not rec["checks"]["ledger_matches_contributions"] or rec["open_exceptions"]:
        raise MythicError("Verified funds / reconciliation check failed; payout blocked", 409)
    prov = provider or get_provider()
    batch.status, c.status = "processing", CohortStatus.processing_payouts.value
    for p in batch.payouts:
        if p.status != "queued":
            continue
        ref = f"MP{batch.id}-{p.id}-{secrets.token_hex(4)}"
        try:
            res = prov.b2c_payout(p.phone, p.amount_kes, ref, "OPS Mythic Circle payout")
            p.conversation_id, p.status = res.conversation_id, "submitted"
        except ProviderError as e:
            p.status, p.resolution_note = "failed", str(e)
    audit(db, admin.id, "mythic.payout.executed", "batch", batch.id)
    _finalize_batch(db, batch, c)
    return batch


def handle_b2c_result(db: Session, payload: dict) -> str:
    try:
        r = payload["Result"]
        conv, code = r["OriginatorConversationID"], int(r["ResultCode"])
        params = {i["Key"]: i.get("Value") for i in (r.get("ResultParameters") or {}).get("ResultParameter", [])}
    except (KeyError, TypeError, ValueError):
        raise MythicError("Malformed callback", 400)
    p = db.execute(select(Payout).where(Payout.conversation_id == conv).with_for_update()).scalar_one_or_none()
    if not p:
        raise MythicError("Unknown payout", 404)
    if p.status in {"succeeded", "resolved"}:
        return "duplicate"
    p.raw_callback = payload
    batch = db.get(PayoutBatch, p.batch_id)
    c = _cohort(db, batch.cohort_id, lock=True)
    if code == 0:
        amt = params.get("TransactionAmount")
        if amt is not None and int(float(amt)) != p.amount_kes:
            db.add(ExceptionCase(cohort_id=c.id, member_id=p.member_id, kind="reconciliation_mismatch",
                                 detail=f"Payout {p.id} settled amount {amt} != {p.amount_kes}"))
            p.status = "failed"
        else:
            p.status, p.mpesa_receipt = "succeeded", params.get("TransactionReceipt")
            db.add(LedgerEntry(cohort_id=c.id, member_id=p.member_id, kind="payout", direction="out",
                               amount_kes=p.amount_kes, payout_id=p.id,
                               provider_ref=p.mpesa_receipt or f"PAYOUT-{p.id}", note="Mythic payout"))
            m = db.get(CohortMember, p.member_id)
            notify(db, m.user_id, "mythic", "Payout sent",
                   f"KSh {p.amount_kes:,} sent to your M-Pesa. Receipt {p.mpesa_receipt}.", "/dashboard/mythic-circle")
    else:
        p.status, p.resolution_note = "failed", r.get("ResultDesc")
    _finalize_batch(db, batch, c)
    return p.status


def retry_failed_payout(db: Session, admin: User, payout_id: int, provider: PaymentProvider | None = None):
    """Retries ONLY the originally approved destination and amount."""
    p = db.get(Payout, payout_id)
    if not p or p.status != "failed":
        raise MythicError("Only failed payouts can be retried", 409)
    batch = db.get(PayoutBatch, p.batch_id)
    if _hash(batch.manifest) != batch.manifest_hash:
        raise MythicError("Manifest integrity failure", 409)
    approved = next(i for i in batch.manifest["items"] if i["member_id"] == p.member_id)
    if approved["phone"] != p.phone or approved["amount_kes"] != p.amount_kes:
        raise MythicError("Payout differs from approved manifest; new approval required", 409)
    ref = f"MP{batch.id}-{p.id}-{secrets.token_hex(4)}"
    try:
        res = (provider or get_provider()).b2c_payout(p.phone, p.amount_kes, ref, "OPS Mythic Circle payout")
    except ProviderError as e:
        raise MythicError(str(e), 502)
    p.conversation_id, p.status = res.conversation_id, "submitted"
    batch.status = "processing"
    audit(db, admin.id, "mythic.payout.retried", "payout", p.id)


def resolve_payout(db: Session, admin: User, payout_id: int, note: str):
    """Documented settlement process for a payout that cannot succeed
    (e.g. settled out-of-band and evidenced in the note)."""
    p = db.get(Payout, payout_id)
    if not p or p.status not in {"failed", "submitted"}:
        raise MythicError("Payout cannot be resolved in its current state", 409)
    if len(note.strip()) < 10:
        raise MythicError("A settlement note with evidence reference is required")
    p.status, p.resolution_note = "resolved", note
    batch = db.get(PayoutBatch, p.batch_id)
    audit(db, admin.id, "mythic.payout.resolved", "payout", p.id, after={"note": note})
    _finalize_batch(db, batch, _cohort(db, batch.cohort_id, lock=True))


def _finalize_batch(db: Session, batch: PayoutBatch, c: Cohort):
    states = {p.status for p in batch.payouts}
    if states and states <= {"succeeded", "resolved"}:
        batch.status, c.status = "completed", CohortStatus.completed.value
        for p in batch.payouts:
            m = db.get(CohortMember, p.member_id)
            notify(db, m.user_id, "mythic", f"{c.name} completed", "Your Mythic Circle is complete.",
                   "/dashboard/mythic-circle")
    elif "failed" in states and not ({"queued", "submitted"} & states):
        batch.status = "needs_resolution"


# -------------------------------------------------------------- refunds
def refundable_amount(db: Session, member_id: int) -> int:
    """Confirmed contributions not yet refunded. No fees, penalties or
    confiscation: members get back what they actually paid."""
    return paid_total(db, member_id)


def request_refund(db: Session, user: User, kind: str, detail: str, member_id: int | None = None) -> RefundRequest:
    if kind not in REFUND_KINDS:
        raise MythicError("Unknown refund reason")
    m = db.get(CohortMember, member_id) if member_id else db.scalar(
        select(CohortMember).where(CohortMember.user_id == user.id))
    if not m:
        raise MythicError("Membership not found", 404)
    is_admin = user.role in {Role.finance_admin.value, Role.super_admin.value}
    if m.user_id != user.id and not is_admin:
        raise MythicError("Not allowed", 403)
    c = _cohort(db, m.cohort_id)
    if kind == "pre_activation_cancel" and c.status in LIVE_STATES | {CohortStatus.completed.value}:
        raise MythicError("Cohort already started; use an exceptional withdrawal request", 409)
    if db.scalar(select(RefundRequest).where(RefundRequest.member_id == m.id,
                                             RefundRequest.status.in_(["requested", "approved"]))):
        raise MythicError("An open refund request already exists", 409)
    r = RefundRequest(member_id=m.id, cohort_id=c.id, reason_kind=kind, detail=detail,
                      calculated_kes=refundable_amount(db, m.id))
    db.add(r)
    if kind == "pre_activation_cancel":
        m.status = "withdrawn"
        c_obj = _cohort(db, c.id, lock=True)
        if c_obj.status == CohortStatus.awaiting_acceptance.value:
            c_obj.status = CohortStatus.registration_open.value  # reopen the vacant slot
    if kind in {"death_incapacity", "dispute"}:
        db.add(ExceptionCase(cohort_id=c.id, member_id=m.id, kind=kind, detail=detail))
    db.flush()
    audit(db, user.id, "mythic.refund.requested", "refund", r.id, after={"kind": kind, "kes": r.calculated_kes})
    return r


def decide_refund(db: Session, admin: User, refund_id: int, approve: bool, reason: str | None) -> RefundRequest:
    r = db.get(RefundRequest, refund_id)
    if not r or r.status != "requested":
        raise MythicError("Refund request not found or already decided", 404)
    if not approve:
        if r.reason_kind in MANDATORY_REFUND_KINDS:
            raise MythicError("This refund category is legally/contractually required and cannot be denied. "
                              "Escalate disputes through the dispute process.", 409)
        if not (reason or "").strip():
            raise MythicError("A written reason is required to deny a refund")
    r.status = "approved" if approve else "denied"
    r.decision_reason, r.decided_by = reason, admin.id
    audit(db, admin.id, "mythic.refund.approved" if approve else "mythic.refund.denied", "refund", r.id,
          after={"reason": reason})
    m = db.get(CohortMember, r.member_id)
    notify(db, m.user_id, "mythic", f"Refund request {r.status}", reason or "", "/dashboard/mythic-circle")
    return r


def mark_refund_paid(db: Session, admin: User, refund_id: int, provider_ref: str):
    r = db.get(RefundRequest, refund_id)
    if not r or r.status != "approved":
        raise MythicError("Refund must be approved first", 409)
    if db.scalar(select(LedgerEntry).where(LedgerEntry.provider_ref == provider_ref)):
        raise MythicError("Provider reference already recorded", 409)
    amount = refundable_amount(db, r.member_id)
    for con in db.scalars(select(Contribution).where(Contribution.member_id == r.member_id,
                                                     Contribution.status == PaymentStatus.paid.value)):
        con.status = PaymentStatus.refunded.value
    if amount:
        db.add(LedgerEntry(cohort_id=r.cohort_id, member_id=r.member_id, kind="refund", direction="out",
                           amount_kes=amount, provider_ref=provider_ref, note=r.reason_kind))
    r.status, r.calculated_kes = "paid", amount
    audit(db, admin.id, "mythic.refund.paid", "refund", r.id, after={"kes": amount, "ref": provider_ref})


def cancel_cohort(db: Session, admin: User, cohort_id: int, reason: str):
    c = _cohort(db, cohort_id, lock=True)
    if c.status == CohortStatus.completed.value:
        raise MythicError("Completed cohorts cannot be cancelled", 409)
    if db.scalar(select(PayoutBatch).where(PayoutBatch.cohort_id == c.id, PayoutBatch.status.in_(["processing"]))):
        raise MythicError("Payouts are being processed", 409)
    c.status = CohortStatus.cancelled.value
    for m in db.scalars(select(CohortMember).where(CohortMember.cohort_id == c.id, CohortMember.status != "withdrawn")):
        if not db.scalar(select(RefundRequest).where(RefundRequest.member_id == m.id,
                                                     RefundRequest.status.in_(["requested", "approved"]))):
            db.add(RefundRequest(member_id=m.id, cohort_id=c.id, reason_kind="cohort_cancelled",
                                 detail=reason, calculated_kes=refundable_amount(db, m.id)))
        notify(db, m.user_id, "mythic", f"{c.name} was cancelled", "Your confirmed contributions will be refunded in full.",
               "/dashboard/mythic-circle")
    audit(db, admin.id, "mythic.cohort.cancelled", "cohort", c.id, after={"reason": reason})


# ---------------------------------------------------------- read models
def cohort_public_progress(db: Session, c: Cohort) -> dict:
    """Aggregate only: no individual balances are exposed."""
    plan = plan_by_code(c.plan_code)
    collected = int(db.scalar(select(func.coalesce(func.sum(Contribution.amount_kes), 0)).where(
        Contribution.cohort_id == c.id, Contribution.status == PaymentStatus.paid.value)))
    members = db.scalar(select(func.count()).select_from(CohortMember).where(
        CohortMember.cohort_id == c.id, CohortMember.status != "withdrawn"))
    return {"cohort_id": c.id, "name": c.name, "plan": c.plan_code, "members": members, "capacity": c.capacity,
            "target_kes": plan.cohort_target, "collected_kes": collected,
            "percent": round(100 * collected / plan.cohort_target, 1), "status": c.status}


def member_dashboard(db: Session, user: User) -> dict:
    app = db.scalar(select(Application).where(Application.user_id == user.id))
    out = {"application": None, "membership": None}
    if app:
        steps = ["submitted", "under_review", "approved"]
        out["application"] = {"id": app.id, "status": app.status, "note": app.review_note,
                              "preferred_plan": app.preferred_plan, "waitlist_position": app.waitlist_position,
                              "progress": {"submitted": True,
                                           "reviewed": app.status in {"approved", "rejected", "resubmission_required"},
                                           "approved": app.status == "approved"}}
    m = db.scalar(select(CohortMember).where(CohortMember.user_id == user.id, CohortMember.status != "withdrawn"))
    if not m:
        return out
    c = _cohort(db, m.cohort_id)
    plan = plan_by_code(c.plan_code)
    cons = list(db.scalars(select(Contribution).where(Contribution.member_id == m.id).order_by(Contribution.month_no)))
    paid = sum(x.amount_kes for x in cons if x.status == PaymentStatus.paid.value)
    nxt = next((x for x in cons if x.status in {"pending", "failed", "overdue"}), None)
    batch = db.scalar(select(PayoutBatch).where(PayoutBatch.cohort_id == c.id, PayoutBatch.status != "rejected")
                      .order_by(PayoutBatch.id.desc()))
    payout = db.scalar(select(Payout).where(Payout.member_id == m.id, Payout.batch_id == batch.id)) if batch else None
    out["membership"] = {
        "member_id": m.id, "status": m.status, "terms_accepted": bool(m.accepted_terms_at),
        "cohort": {"id": c.id, "name": c.name, "plan": c.plan_code, "capacity": c.capacity,
                   "monthly_kes": c.monthly_kes, "months": c.months, "status": c.status,
                   "start_date": c.start_date, "proposed_start": c.proposed_start,
                   "expected_completion": add_months(c.start_date, c.months) if c.start_date else None,
                   "expected_payout_kes": plan.payout_per_member},
        "deposited_kes": paid, "remaining_kes": plan.per_member_total - paid,
        "next_due": {"id": nxt.id, "month_no": nxt.month_no, "due_date": nxt.due_date,
                     "amount_kes": nxt.amount_kes, "status": nxt.status} if nxt else None,
        "timeline": [{"id": x.id, "month_no": x.month_no, "due_date": x.due_date, "amount_kes": x.amount_kes,
                      "status": x.status, "receipt": x.mpesa_receipt} for x in cons],
        "cohort_progress": cohort_public_progress(db, c),
        "payout_readiness": c.status in {CohortStatus.fully_funded.value, CohortStatus.payout_approval_pending.value,
                                         CohortStatus.processing_payouts.value, CohortStatus.completed.value},
        "payout_status": payout.status if payout else ("not_started"),
        "provider_fee_note": "Provider charges (if any) are shown separately and never reduce your KSh 7,000 payout.",
    }
    return out


def receipt_for(db: Session, user: User, contribution_id: int) -> dict:
    con = db.get(Contribution, contribution_id)
    m = db.get(CohortMember, con.member_id) if con else None
    if not con or m.user_id != user.id or con.status != PaymentStatus.paid.value:
        raise MythicError("Receipt not available", 404)
    c = _cohort(db, con.cohort_id)
    return {"type": "contribution", "receipt_no": con.mpesa_receipt, "cohort": c.name,
            "month_no": con.month_no, "amount_kes": con.amount_kes, "paid_at": con.paid_at.isoformat(),
            "member": user.gamer_tag}


def payout_receipt_for(db: Session, user: User) -> dict:
    m = db.scalar(select(CohortMember).where(CohortMember.user_id == user.id))
    p = db.scalar(select(Payout).where(Payout.member_id == m.id, Payout.status.in_(["succeeded", "resolved"]))
                  .order_by(Payout.id.desc())) if m else None
    if not p:
        raise MythicError("No settled payout yet", 404)
    c = _cohort(db, m.cohort_id)
    return {"type": "payout", "receipt_no": p.mpesa_receipt or f"RESOLVED-{p.id}", "cohort": c.name,
            "amount_kes": p.amount_kes, "status": p.status, "member": user.gamer_tag}


def overview(db: Session) -> dict:
    def cnt(model, *w):
        return int(db.scalar(select(func.count()).select_from(model).where(*w)))
    return {
        "total_applicants": cnt(Application),
        "verified_members": cnt(Application, Application.status == "approved"),
        "active_cohorts": cnt(Cohort, Cohort.status.in_([CohortStatus.active.value,
                                                         CohortStatus.contributions_in_progress.value])),
        "fully_funded_cohorts": cnt(Cohort, Cohort.status == CohortStatus.fully_funded.value),
        "total_confirmed_contributions_kes": int(db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_kes), 0)).where(
            LedgerEntry.kind == "contribution"))),
        "pending_payments": cnt(Contribution, Contribution.status.in_(["pending", "overdue", "failed"])),
        "pending_payout_approvals": cnt(PayoutBatch, PayoutBatch.status == "pending_approval"),
        "completed_payouts": cnt(Payout, Payout.status.in_(["succeeded", "resolved"])),
    }
