import enum
from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, CheckConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .core import utcnow


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    resubmission_required = "resubmission_required"


class CohortStatus(str, enum.Enum):
    registration_open = "registration_open"
    filled = "filled"
    awaiting_acceptance = "awaiting_acceptance"
    active = "active"
    contributions_in_progress = "contributions_in_progress"
    fully_funded = "fully_funded"
    payout_approval_pending = "payout_approval_pending"
    processing_payouts = "processing_payouts"
    completed = "completed"
    paused = "paused"
    disputed = "disputed"
    cancelled = "cancelled"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    overdue = "overdue"
    reversed = "reversed"
    refunded = "refunded"


class RegistrationPeriod(Base):
    __tablename__ = "mythic_registration_periods"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(1))
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    proposed_start: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    drawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    draw_seed: Mapped[str | None] = mapped_column(String(64))  # recorded for auditability


class Application(Base):
    __tablename__ = "mythic_applications"
    # One application per user, ever active: prevents duplicates.
    __table_args__ = (UniqueConstraint("user_id", name="uq_application_user"),
                      UniqueConstraint("codm_uid", name="uq_application_uid"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    gamer_tag: Mapped[str] = mapped_column(String(64))
    codm_uid: Mapped[str] = mapped_column(String(32))
    screenshot_path: Mapped[str] = mapped_column(String(255))
    rank: Mapped[str] = mapped_column(String(48))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))  # 2547XXXXXXXX
    preferred_plan: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(32), default=VerificationStatus.pending.value, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("mythic_registration_periods.id"))
    waitlist_position: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Cohort(Base):
    __tablename__ = "mythic_cohorts"
    __table_args__ = (CheckConstraint("plan_code in ('A','B')", name="ck_cohort_plan"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    plan_code: Mapped[str] = mapped_column(String(1))
    # Terms are snapshotted at creation and are immutable afterwards.
    capacity: Mapped[int] = mapped_column(Integer)
    monthly_kes: Mapped[int] = mapped_column(Integer)
    months: Mapped[int] = mapped_column(Integer)
    terms_version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[str] = mapped_column(String(40), default=CohortStatus.registration_open.value, index=True)
    status_before_pause: Mapped[str | None] = mapped_column(String(40))
    proposed_start: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    members: Mapped[list["CohortMember"]] = relationship(back_populates="cohort")


class CohortMember(Base):
    __tablename__ = "mythic_cohort_members"
    # A user can belong to only one live cohort membership.
    __table_args__ = (UniqueConstraint("user_id", name="uq_member_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohorts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    application_id: Mapped[int] = mapped_column(ForeignKey("mythic_applications.id"))
    payout_phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24), default="assigned")  # assigned|accepted|withdrawn|inactive
    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_terms_version: Mapped[str | None] = mapped_column(String(32))
    cohort: Mapped[Cohort] = relationship(back_populates="members")


class Contribution(Base):
    """One scheduled monthly instalment for one member."""
    __tablename__ = "mythic_contributions"
    __table_args__ = (UniqueConstraint("member_id", "month_no", name="uq_contribution_month"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohort_members.id"), index=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohorts.id"), index=True)
    month_no: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    amount_kes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.pending.value, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mpesa_receipt: Mapped[str | None] = mapped_column(String(32), unique=True)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentAttempt(Base):
    """An STK push request. Becomes 'paid' only via a verified provider callback."""
    __tablename__ = "mythic_payment_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    contribution_id: Mapped[int] = mapped_column(ForeignKey("mythic_contributions.id"), index=True)
    checkout_request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    merchant_request_id: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(20))
    amount_kes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="initiated")  # initiated|succeeded|failed
    raw_callback: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerEntry(Base):
    """Append-only double-sided ledger. Entries are never edited or deleted;
    corrections are new entries (reversal / refund)."""
    __tablename__ = "mythic_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohorts.id"), index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("mythic_cohort_members.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)  # contribution|reversal|refund|payout|payout_reversal|provider_fee
    direction: Mapped[str] = mapped_column(String(3))  # in | out
    amount_kes: Mapped[int] = mapped_column(Integer)
    provider_ref: Mapped[str | None] = mapped_column(String(64), unique=True)
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("mythic_contributions.id"))
    payout_id: Mapped[int | None] = mapped_column(ForeignKey("mythic_payouts.id"))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PayoutBatch(Base):
    __tablename__ = "mythic_payout_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohorts.id"), index=True)
    # pending_approval | approved | rejected | processing | completed | needs_resolution
    status: Mapped[str] = mapped_column(String(24), default="pending_approval", index=True)
    manifest: Mapped[dict] = mapped_column(JSON)          # frozen at creation
    manifest_hash: Mapped[str] = mapped_column(String(64))  # approvals bind to this hash
    total_kes: Mapped[int] = mapped_column(Integer)
    reconciliation: Mapped[dict] = mapped_column(JSON)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payouts: Mapped[list["Payout"]] = relationship(back_populates="batch")
    approvals: Mapped[list["PayoutApproval"]] = relationship(back_populates="batch")


class PayoutApproval(Base):
    __tablename__ = "mythic_payout_approvals"
    __table_args__ = (UniqueConstraint("batch_id", "admin_id", name="uq_approval_admin"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mythic_payout_batches.id"), index=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(8))  # approve | reject
    manifest_hash: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    batch: Mapped[PayoutBatch] = relationship(back_populates="approvals")


class Payout(Base):
    __tablename__ = "mythic_payouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mythic_payout_batches.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohort_members.id"))
    phone: Mapped[str] = mapped_column(String(20))
    amount_kes: Mapped[int] = mapped_column(Integer)
    # queued | submitted | succeeded | failed | resolved
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(32))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    raw_callback: Mapped[dict | None] = mapped_column(JSON)
    batch: Mapped[PayoutBatch] = relationship(back_populates="payouts")


class ExceptionCase(Base):
    """Financial exceptions block payout while unresolved."""
    __tablename__ = "mythic_exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohorts.id"), index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("mythic_cohort_members.id"))
    kind: Mapped[str] = mapped_column(String(32))  # failed_payment|dispute|inactivity|death_incapacity|reconciliation_mismatch|other
    detail: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefundRequest(Base):
    __tablename__ = "mythic_refund_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohort_members.id"), index=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("mythic_cohorts.id"))
    reason_kind: Mapped[str] = mapped_column(String(32))  # pre_activation_cancel|exceptional|death_incapacity|cohort_cancelled|legal|dispute
    detail: Mapped[str] = mapped_column(Text)
    # Refund = confirmed contributions of the member, calculated by the system.
    calculated_kes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="requested", index=True)  # requested|approved|denied|paid
    decision_reason: Mapped[str | None] = mapped_column(Text)  # mandatory on denial
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MythicContent(Base):
    """CMS blocks. Keys are whitelisted; plan terms are NOT editable here."""
    __tablename__ = "mythic_content"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
