from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.mythic import (Cohort, CohortMember, Contribution, ExceptionCase, LedgerEntry, Payout,
                               PayoutBatch)
from app.services import mythic as svc
from app.services.plans import MEMBER_CAP_KES, PLANS

from .conftest import make_user


def stk_ok(checkout, receipt, amount):
    return {"Body": {"stkCallback": {"CheckoutRequestID": checkout, "ResultCode": 0, "ResultDesc": "ok",
                                     "CallbackMetadata": {"Item": [
                                         {"Name": "Amount", "Value": amount},
                                         {"Name": "MpesaReceiptNumber", "Value": receipt}]}}}}


def b2c_ok(conv, receipt, amount=7000):
    return {"Result": {"OriginatorConversationID": conv, "ResultCode": 0,
                       "ResultParameters": {"ResultParameter": [
                           {"Key": "TransactionReceipt", "Value": receipt},
                           {"Key": "TransactionAmount", "Value": amount}]}}}


def build_active_cohort(db, admins, size=7):
    fin, ver = admins["finance1"], admins["verifier"]
    c = svc.create_cohort(db, fin, f"C{size}", size, date(2026, 11, 1))
    users = []
    for i in range(size):
        u = make_user(db, f"p{size}_{i}@x.com")
        a = svc.submit_application(db, u, gamer_tag=f"p{i}", codm_uid=f"{size}00000{i:02d}", rank="Legendary",
                                   email=u.email, phone=f"0712345{i:03d}", preferred_plan="A" if size == 7 else "B",
                                   screenshot_path="x.png")
        svc.review_application(db, ver, a, "approved", None)
        svc.assign_member(db, fin, c.id, a.id)
        users.append(u)
    db.flush()
    assert c.status == "awaiting_acceptance"
    db.commit()
    for u in users:
        svc.accept_terms(db, u)
    db.commit()
    svc.activate_cohort(db, fin, c.id, date(2026, 11, 1))
    db.commit()
    return c, users


def pay_all(db, provider, c, users, only_months=None):
    n = 0
    for con in db.query(Contribution).filter_by(cohort_id=c.id).order_by(Contribution.month_no).all():
        if only_months and con.month_no not in only_months:
            continue
        m = db.get(CohortMember, con.member_id)
        u = next(x for x in users if x.id == m.user_id)
        att = svc.initiate_payment(db, u, con.id, provider)
        db.commit()  # routers commit between the request and the provider callback
        n += 1
        svc.handle_stk_callback(db, stk_ok(att.checkout_request_id, f"RCPT{con.id:05d}", con.amount_kes))
        db.commit()


# ----------------------------------------------------------- plan rules
def test_only_two_fixed_plans_and_cap():
    assert set(PLANS) == {"A", "B"}
    a, b = PLANS["A"], PLANS["B"]
    assert (a.members, a.monthly_kes, a.months, a.cohort_target) == (7, 1000, 7, 49000)
    assert (b.members, b.monthly_kes, b.months, b.cohort_target) == (10, 700, 10, 70000)
    assert a.per_member_total == b.per_member_total == MEMBER_CAP_KES == 7000
    with pytest.raises(TypeError):
        PLANS["C"] = None  # immutable mapping


def test_custom_cohort_size_rejected(db, admins):
    for bad in (5, 8, 12):
        with pytest.raises(svc.MythicError):
            svc.create_cohort(db, admins["finance1"], "bad", bad, None)


def test_cohort_terms_snapshot(db, admins):
    c = svc.create_cohort(db, admins["finance1"], "A1", 10, None)
    assert (c.capacity, c.monthly_kes, c.months, c.plan_code) == (10, 700, 10, "B")


# -------------------------------------------------------- registration
def test_duplicate_application_and_uid_blocked(db, admins):
    u = make_user(db, "dup@x.com")
    kw = dict(gamer_tag="t", codm_uid="12345678", rank="r", email=u.email, phone="0712345678",
              preferred_plan="A", screenshot_path="s.png")
    svc.submit_application(db, u, **kw)
    with pytest.raises(svc.MythicError):
        svc.submit_application(db, u, **kw)
    u2 = make_user(db, "dup2@x.com")
    with pytest.raises(svc.MythicError):
        svc.submit_application(db, u2, **kw)


def test_reject_requires_reason_and_phone_validation(db, admins):
    u = make_user(db, "r@x.com")
    a = svc.submit_application(db, u, gamer_tag="t", codm_uid="99999999", rank="r", email=u.email,
                               phone="+254712345678", preferred_plan="B", screenshot_path="s.png")
    assert a.phone == "254712345678"
    with pytest.raises(svc.MythicError):
        svc.review_application(db, admins["verifier"], a, "rejected", "")
    with pytest.raises(svc.MythicError):
        svc.normalize_phone("12345")


def test_only_approved_can_be_assigned(db, admins):
    c = svc.create_cohort(db, admins["finance1"], "x", 7, None)
    u = make_user(db, "na@x.com")
    a = svc.submit_application(db, u, gamer_tag="t", codm_uid="88888888", rank="r", email=u.email,
                               phone="0712345678", preferred_plan="A", screenshot_path="s.png")
    with pytest.raises(svc.MythicError):
        svc.assign_member(db, admins["finance1"], c.id, a.id)


def test_draw_is_random_reproducible_and_waitlists_overflow(db, admins):
    fin, ver = admins["finance1"], admins["verifier"]
    c = svc.create_cohort(db, fin, "Draw", 7, None)
    apps = []
    for i in range(10):
        u = make_user(db, f"d{i}@x.com")
        a = svc.submit_application(db, u, gamer_tag=f"d{i}", codm_uid=f"7770000{i:02d}", rank="r", email=u.email,
                                   phone=f"0722222{i:03d}", preferred_plan="A", screenshot_path="s.png")
        svc.review_application(db, ver, a, "approved", None)
        apps.append(a)
    now = datetime.now(timezone.utc)
    p = svc.set_period(db, fin, "A", now, now + timedelta(days=3), date(2026, 12, 1))
    res = svc.run_draw(db, fin, p.id)
    assert res["assigned"] == 7 and res["waitlisted"] == 3 and len(res["seed"]) == 32
    assert db.get(Cohort, c.id).status == "awaiting_acceptance"
    assert sorted(a.waitlist_position for a in apps if a.waitlist_position) == [1, 2, 3]
    with pytest.raises(svc.MythicError):
        svc.run_draw(db, fin, p.id)  # no re-draws


def test_activation_requires_all_acceptances(db, admins):
    fin, ver = admins["finance1"], admins["verifier"]
    c = svc.create_cohort(db, fin, "Acc", 7, None)
    us = []
    for i in range(7):
        u = make_user(db, f"ac{i}@x.com")
        a = svc.submit_application(db, u, gamer_tag="t", codm_uid=f"5550000{i}", rank="r", email=u.email,
                                   phone="0712345678", preferred_plan="A", screenshot_path="s.png")
        svc.review_application(db, ver, a, "approved", None)
        svc.assign_member(db, fin, c.id, a.id)
        us.append(u)
    for u in us[:6]:
        svc.accept_terms(db, u)
    with pytest.raises(svc.MythicError):
        svc.activate_cohort(db, fin, c.id, date(2026, 11, 1))


# ------------------------------------------------------- contributions
def test_activation_creates_full_schedule(db, admins):
    c, users = build_active_cohort(db, admins, 10)
    cons = db.query(Contribution).filter_by(cohort_id=c.id).all()
    assert len(cons) == 100 and all(x.amount_kes == 700 for x in cons)
    assert sum(x.amount_kes for x in cons) == 70000


def test_payment_only_confirmed_by_callback(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    con = db.query(Contribution).filter_by(cohort_id=c.id, month_no=1).first()
    m = db.get(CohortMember, con.member_id)
    u = next(x for x in users if x.id == m.user_id)
    att = svc.initiate_payment(db, u, con.id, provider)
    db.commit()
    assert con.status == "pending"  # initiating never marks paid
    with pytest.raises(svc.MythicError):
        svc.initiate_payment(db, u, con.id, provider)  # prompt already in flight
    assert svc.handle_stk_callback(db, stk_ok(att.checkout_request_id, "ABC1", 1000)) == "paid"
    assert con.status == "paid" and db.get(Cohort, c.id).status == "contributions_in_progress"
    assert svc.handle_stk_callback(db, stk_ok(att.checkout_request_id, "ABC1", 1000)) == "duplicate"
    assert db.query(LedgerEntry).filter_by(kind="contribution").count() == 1


def test_wrong_amount_or_unknown_checkout_not_credited(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    con = db.query(Contribution).filter_by(cohort_id=c.id, month_no=1).first()
    u = next(x for x in users if x.id == db.get(CohortMember, con.member_id).user_id)
    att = svc.initiate_payment(db, u, con.id, provider)
    db.commit()
    assert svc.handle_stk_callback(db, stk_ok(att.checkout_request_id, "BAD1", 10)) == "mismatch"
    assert con.status == "pending"
    assert db.query(ExceptionCase).filter_by(kind="reconciliation_mismatch").count() == 1
    with pytest.raises(svc.MythicError):
        svc.handle_stk_callback(db, stk_ok("ws_CO_nope", "X", 1000))


def test_failed_callback_marks_failed(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    con = db.query(Contribution).filter_by(cohort_id=c.id, month_no=1).first()
    u = next(x for x in users if x.id == db.get(CohortMember, con.member_id).user_id)
    att = svc.initiate_payment(db, u, con.id, provider)
    db.commit()
    payload = {"Body": {"stkCallback": {"CheckoutRequestID": att.checkout_request_id, "ResultCode": 1032,
                                        "ResultDesc": "Cancelled"}}}
    assert svc.handle_stk_callback(db, payload) == "failed"
    assert con.status == "failed"
    assert db.query(LedgerEntry).count() == 0


def test_overdue_marking(db, admins):
    c, _ = build_active_cohort(db, admins)
    assert svc.mark_overdue(db, date(2026, 11, 20)) == 7  # month-1 instalments of 7 members
    assert db.query(Contribution).filter_by(status="overdue").count() == 7


# ------------------------------------------------ funding and payouts
def fund_fully(db, provider, admins, size=7):
    c, users = build_active_cohort(db, admins, size)
    pay_all(db, provider, c, users)
    return c, users


def test_not_fully_funded_until_every_period_paid(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    pay_all(db, provider, c, users, only_months=set(range(1, 7)))
    assert db.get(Cohort, c.id).status == "contributions_in_progress"
    with pytest.raises(svc.MythicError):
        svc.request_payout_batch(db, admins["finance1"], c.id)


@pytest.mark.parametrize("size,target", [(7, 49000), (10, 70000)])
def test_fully_funded_reconciliation(db, admins, provider, size, target):
    c, _ = fund_fully(db, provider, admins, size)
    assert db.get(Cohort, c.id).status == "fully_funded"
    rec = svc.reconciliation(db, db.get(Cohort, c.id))
    assert rec["eligible"] and rec["target_kes"] == target == rec["ledger_net_kes"]
    assert rec["total_payout_liability_kes"] == size * 7000


def test_two_person_approval_and_simultaneous_payout(db, admins, provider):
    c, users = fund_fully(db, provider, admins)
    f1, f2 = admins["finance1"], admins["finance2"]
    b = svc.request_payout_batch(db, f1, c.id)
    assert b.total_kes == 49000 and len(b.payouts) == 7 and db.get(Cohort, c.id).status == "payout_approval_pending"
    with pytest.raises(svc.MythicError):
        svc.execute_batch(db, f1, b.id, provider)  # not approved
    svc.decide_batch(db, f1, b.id, "approve", None)
    with pytest.raises(svc.MythicError):
        svc.decide_batch(db, f1, b.id, "approve", None)  # same admin twice
    assert b.status == "pending_approval"
    with pytest.raises(svc.MythicError):
        svc.execute_batch(db, f1, b.id, provider)  # one approval is not enough
    svc.decide_batch(db, f2, b.id, "approve", None)
    assert b.status == "approved" and b.locked_at
    svc.execute_batch(db, f1, b.id, provider)
    assert len(provider.b2c) == 7 and all(a == 7000 for _, a, _ in provider.b2c)
    assert db.get(Cohort, c.id).status == "processing_payouts"
    # settle 6 of 7 -> cohort must NOT complete
    pays = db.query(Payout).filter_by(batch_id=b.id).all()
    for p in pays[:-1]:
        svc.handle_b2c_result(db, b2c_ok(p.conversation_id, f"PAY{p.id}"))
    assert db.get(Cohort, c.id).status == "processing_payouts"
    svc.handle_b2c_result(db, b2c_ok(pays[-1].conversation_id, f"PAY{pays[-1].id}"))
    assert db.get(Cohort, c.id).status == "completed"
    assert svc.ledger_net(db, c.id) == 0


def test_failed_payout_blocks_completion_until_resolved(db, admins, provider):
    c, users = fund_fully(db, provider, admins)
    f1, f2 = admins["finance1"], admins["finance2"]
    b = svc.request_payout_batch(db, f1, c.id)
    svc.decide_batch(db, f1, b.id, "approve", None)
    svc.decide_batch(db, f2, b.id, "approve", None)
    bad_phone = b.manifest["items"][0]["phone"]
    provider.fail_phones.add(bad_phone)
    svc.execute_batch(db, f1, b.id, provider)
    failed = db.query(Payout).filter_by(batch_id=b.id, status="failed").all()
    assert len(failed) >= 1
    for p in db.query(Payout).filter_by(batch_id=b.id, status="submitted").all():
        svc.handle_b2c_result(db, b2c_ok(p.conversation_id, f"P{p.id}"))
    assert db.get(Cohort, c.id).status != "completed" and b.status == "needs_resolution"
    provider.fail_phones.clear()
    for p in failed:
        svc.retry_failed_payout(db, f1, p.id, provider)
        svc.handle_b2c_result(db, b2c_ok(p.conversation_id, f"R{p.id}"))
    assert db.get(Cohort, c.id).status == "completed"


def test_open_exception_blocks_payout(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    db.add(ExceptionCase(cohort_id=c.id, kind="dispute", detail="member disputes a payment"))
    db.flush()
    pay_all(db, provider, c, users)
    assert db.get(Cohort, c.id).status == "contributions_in_progress"  # not fully funded
    exc = db.query(ExceptionCase).first()
    svc.resolve_exception(db, admins["finance1"], exc.id, "Resolved with member; evidence attached")
    svc.recheck_funding(db, db.get(Cohort, c.id))
    assert db.get(Cohort, c.id).status == "fully_funded"


def test_reversal_after_funding_blocks_execution(db, admins, provider):
    c, users = fund_fully(db, provider, admins)
    f1, f2 = admins["finance1"], admins["finance2"]
    b = svc.request_payout_batch(db, f1, c.id)
    svc.decide_batch(db, f1, b.id, "approve", None)
    svc.decide_batch(db, f2, b.id, "approve", None)
    con = db.query(Contribution).filter_by(cohort_id=c.id).first()
    svc.mark_reversed(db, f1, con.id, "chargeback")
    with pytest.raises(svc.MythicError):
        svc.execute_batch(db, f1, b.id, provider)  # funds no longer verified
    assert provider.b2c == []


def test_tampered_manifest_blocks_execution(db, admins, provider):
    c, users = fund_fully(db, provider, admins)
    f1, f2 = admins["finance1"], admins["finance2"]
    b = svc.request_payout_batch(db, f1, c.id)
    svc.decide_batch(db, f1, b.id, "approve", None)
    svc.decide_batch(db, f2, b.id, "approve", None)
    m = db.get(CohortMember, b.manifest["items"][0]["member_id"])
    m.payout_phone = "254799999999"  # destination changed after approval
    with pytest.raises(svc.MythicError):
        svc.execute_batch(db, f1, b.id, provider)
    assert provider.b2c == []


def test_rejection_requires_new_approval_process(db, admins, provider):
    c, _ = fund_fully(db, provider, admins)
    b = svc.request_payout_batch(db, admins["finance1"], c.id)
    svc.decide_batch(db, admins["finance2"], b.id, "reject", "numbers look off")
    assert b.status == "rejected" and db.get(Cohort, c.id).status == "fully_funded"
    b2 = svc.request_payout_batch(db, admins["finance1"], c.id)
    assert b2.id != b.id and b2.status == "pending_approval"


# ------------------------------------------------------------- refunds
def test_refund_rules(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    pay_all(db, provider, c, users, only_months={1})
    u = users[0]
    r = svc.request_refund(db, u, "exceptional", "Medical emergency")
    assert r.calculated_kes == 1000  # exactly what was paid: no penalty or confiscation
    with pytest.raises(svc.MythicError):
        svc.decide_refund(db, admins["finance1"], r.id, False, "")  # denial needs written reason
    svc.decide_refund(db, admins["finance1"], r.id, True, "Approved")
    svc.mark_refund_paid(db, admins["finance1"], r.id, "REFUND123")
    assert svc.paid_total(db, db.get(CohortMember, r.member_id).id) == 0
    assert db.query(LedgerEntry).filter_by(kind="refund").one().amount_kes == 1000


def test_mandatory_refund_cannot_be_denied_and_pre_activation_cancel_frees_slot(db, admins):
    fin, ver = admins["finance1"], admins["verifier"]
    c = svc.create_cohort(db, fin, "Pre", 7, None)
    us = []
    for i in range(7):
        u = make_user(db, f"pre{i}@x.com")
        a = svc.submit_application(db, u, gamer_tag="t", codm_uid=f"4440000{i}", rank="r", email=u.email,
                                   phone="0712345678", preferred_plan="A", screenshot_path="s.png")
        svc.review_application(db, ver, a, "approved", None)
        svc.assign_member(db, fin, c.id, a.id)
        us.append(u)
    assert db.get(Cohort, c.id).status == "awaiting_acceptance"
    r = svc.request_refund(db, us[0], "pre_activation_cancel", "changed my mind")
    assert db.get(Cohort, c.id).status == "registration_open"  # slot re-opened
    with pytest.raises(svc.MythicError):
        svc.decide_refund(db, fin, r.id, False, "no")


def test_cancel_cohort_refunds_everyone_in_full(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    pay_all(db, provider, c, users, only_months={1, 2})
    svc.cancel_cohort(db, admins["finance1"], c.id, "organiser decision")
    refunds = db.query(svc.RefundRequest).filter_by(cohort_id=c.id).all()
    assert len(refunds) == 7 and all(r.calculated_kes == 2000 for r in refunds)


def test_public_progress_hides_individuals(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    pay_all(db, provider, c, users, only_months={1})
    prog = svc.cohort_public_progress(db, db.get(Cohort, c.id))
    assert prog["collected_kes"] == 7000 and prog["percent"] == round(100 * 7000 / 49000, 1)
    assert set(prog) == {"cohort_id", "name", "plan", "members", "capacity", "target_kes", "collected_kes",
                         "percent", "status"}


def test_pause_blocks_payments(db, admins, provider):
    c, users = build_active_cohort(db, admins)
    svc.set_pause(db, admins["finance1"], c.id, True, "audit")
    con = db.query(Contribution).filter_by(cohort_id=c.id).first()
    u = next(x for x in users if x.id == db.get(CohortMember, con.member_id).user_id)
    with pytest.raises(svc.MythicError):
        svc.initiate_payment(db, u, con.id, provider)
    svc.set_pause(db, admins["finance1"], c.id, False, "done")
    assert db.get(Cohort, c.id).status == "active"


def test_live_money_gate():
    from app.config import Settings
    s = Settings(LIVE_PAYMENTS_ENABLED=True, DARAJA_ENV="production", COMPLIANCE_SIGNOFF_REF="")
    assert not s.live_money_allowed
    s = Settings(LIVE_PAYMENTS_ENABLED=True, DARAJA_ENV="production", COMPLIANCE_SIGNOFF_REF="LEGAL-2026-01")
    assert s.live_money_allowed
    assert not Settings().live_money_allowed


def test_funding_detected_with_production_session_settings(db_prod, admins, provider):
    """Regression: with autoflush off, the final payment must still flip the cohort to fully_funded."""
    db = db_prod
    for u in admins.values():
        db.merge(u)
    db.commit()
    c, users = build_active_cohort(db, admins)
    pay_all(db, provider, c, users)
    assert db.get(Cohort, c.id).status == "fully_funded"
    b = svc.request_payout_batch(db, admins["finance1"], c.id)
    db.commit()
    assert b.total_kes == 49000
