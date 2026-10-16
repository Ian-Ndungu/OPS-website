import logging
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import bleach
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.content import Announcement
from ..models.core import Role, User
from ..models.mythic import CohortMember
from .common import audit, notify

log = logging.getLogger(__name__)

CATEGORIES = ["General", "Clan News", "Tournament Updates", "Scrims", "Recruitment", "Mythic Circle",
              "Important Notices", "Maintenance"]
AUDIENCES = {"everyone", "verified", "divisions", "mythic", "cohorts"}

ALLOWED_TAGS = ["p", "br", "strong", "b", "em", "i", "u", "s", "h2", "h3", "h4", "ul", "ol", "li",
                "blockquote", "a", "code", "pre", "hr", "img"]
ALLOWED_ATTRS = {"a": ["href", "title", "rel", "target"], "img": ["src", "alt", "title"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


class AnnouncementError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def sanitize_html(html: str) -> str:
    clean = bleach.clean(html or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                         protocols=ALLOWED_PROTOCOLS, strip=True)
    # force safe link behaviour
    clean = re.sub(r"<a ", '<a rel="noopener noreferrer nofollow" target="_blank" ', clean)
    return clean


def slugify(title: str, db: Session) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "post"
    slug, n = base, 2
    while db.scalar(select(Announcement.id).where(Announcement.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def check_target_permission(admin: User, target: dict):
    """Everyone/verified: any content admin. Division notices: content admins.
    Mythic Circle / cohort notices touch financial members: finance admins only."""
    aud = target.get("audience", "everyone")
    if aud not in AUDIENCES:
        raise AnnouncementError("Unknown audience")
    if aud == "divisions" and not target.get("divisions"):
        raise AnnouncementError("Select at least one game division")
    if aud == "cohorts" and not target.get("cohort_ids"):
        raise AnnouncementError("Select at least one cohort")
    if aud in {"mythic", "cohorts"} and admin.role not in {Role.finance_admin.value, Role.super_admin.value}:
        raise AnnouncementError("Only finance administrators can send Mythic Circle or cohort notices", 403)


def create(db: Session, admin: User, data: dict) -> Announcement:
    if data["category"] not in CATEGORIES:
        raise AnnouncementError("Unknown category")
    target = data.get("target") or {"audience": "everyone"}
    check_target_permission(admin, target)
    a = Announcement(title=data["title"], slug=slugify(data["title"], db), category=data["category"],
                     summary=data["summary"], content_html=sanitize_html(data["content_html"]),
                     image_path=data.get("image_path"), pinned=data.get("pinned", False),
                     featured=data.get("featured", False), author_id=admin.id, target=target,
                     email_notify=data.get("email_notify", False))
    db.add(a)
    db.flush()
    audit(db, admin.id, "announcement.created", "announcement", a.id)
    return a


def update(db: Session, admin: User, a: Announcement, data: dict) -> Announcement:
    if a.status == "archived":
        raise AnnouncementError("Archived announcements cannot be edited", 409)
    if "target" in data and data["target"]:
        check_target_permission(admin, data["target"])
        if a.status == "published" and a.notified and data["target"] != a.target:
            raise AnnouncementError("Audience of a published notice cannot change; unpublish and republish", 409)
        a.target = data["target"]
    for k in ("title", "summary", "pinned", "featured", "email_notify", "image_path"):
        if k in data and data[k] is not None:
            setattr(a, k, data[k])
    if "category" in data and data["category"]:
        if data["category"] not in CATEGORIES:
            raise AnnouncementError("Unknown category")
        a.category = data["category"]
    if data.get("content_html") is not None:
        a.content_html = sanitize_html(data["content_html"])
    audit(db, admin.id, "announcement.updated", "announcement", a.id)
    return a


def recipients(db: Session, target: dict) -> list[User]:
    aud = target.get("audience", "everyone")
    q = select(User)
    if aud == "verified":
        q = q.where(User.is_verified_member.is_(True))
    elif aud == "divisions":
        q = q.where(User.game_division.in_(target.get("divisions", [])))
    elif aud == "mythic":
        q = q.where(User.id.in_(select(CohortMember.user_id).where(CohortMember.status != "withdrawn")))
    elif aud == "cohorts":
        q = q.where(User.id.in_(select(CohortMember.user_id).where(
            CohortMember.cohort_id.in_(target.get("cohort_ids", [])), CohortMember.status != "withdrawn")))
    return list(db.scalars(q))


def _send_email(to: str, subject: str, body: str):
    if not settings.SMTP_HOST:
        log.info("SMTP not configured; skipping email to %s", to)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
    except Exception:  # email must never break publishing
        log.exception("email send failed")


def _fanout(db: Session, a: Announcement):
    if a.notified:
        return
    for u in recipients(db, a.target):
        notify(db, u.id, "announcement", a.title, a.summary, f"/announcements/{a.slug}")
        if a.email_notify:
            _send_email(u.email, a.title, f"{a.summary}\n\nRead more: {settings.PUBLIC_BASE_URL}/announcements/{a.slug}")
    a.notified = True


def publish(db: Session, admin: User, a: Announcement, when: datetime | None = None):
    if a.status == "archived":
        raise AnnouncementError("Archived announcements cannot be published", 409)
    check_target_permission(admin, a.target)
    now = datetime.now(timezone.utc)
    if when and when > now:
        a.status, a.publish_at = "scheduled", when
        audit(db, admin.id, "announcement.scheduled", "announcement", a.id, after={"at": when.isoformat()})
        return a
    a.status, a.published_at = "published", now
    _fanout(db, a)
    audit(db, admin.id, "announcement.published", "announcement", a.id)
    return a


def publish_due(db: Session) -> int:
    now = datetime.now(timezone.utc)
    n = 0
    for a in db.scalars(select(Announcement).where(Announcement.status == "scheduled", Announcement.publish_at <= now)):
        a.status, a.published_at = "published", now
        _fanout(db, a)
        audit(db, None, "announcement.published_scheduled", "announcement", a.id)
        n += 1
    return n


def unpublish(db: Session, admin: User, a: Announcement):
    if a.status != "published":
        raise AnnouncementError("Announcement is not published", 409)
    a.status = "draft"
    audit(db, admin.id, "announcement.unpublished", "announcement", a.id)


def archive(db: Session, admin: User, a: Announcement):
    a.status = "archived"
    audit(db, admin.id, "announcement.archived", "announcement", a.id)


def visible_query(user: User | None, db: Session):
    """Published announcements the viewer may see. Visitors see only 'everyone'."""
    q = select(Announcement).where(Announcement.status == "published")
    if not user:
        return q.where(Announcement.target["audience"].as_string() == "everyone")
    ids = [a.id for a in db.scalars(q) if _visible_to(db, a, user)]
    return select(Announcement).where(Announcement.id.in_(ids))


def _visible_to(db: Session, a: Announcement, user: User) -> bool:
    if user.role in {r.value for r in Role if r != Role.member}:
        return True
    t = a.target or {"audience": "everyone"}
    aud = t.get("audience", "everyone")
    if aud == "everyone":
        return True
    if aud == "verified":
        return user.is_verified_member
    if aud == "divisions":
        return user.game_division in t.get("divisions", [])
    m = db.scalar(select(CohortMember).where(CohortMember.user_id == user.id, CohortMember.status != "withdrawn"))
    if aud == "mythic":
        return m is not None
    if aud == "cohorts":
        return m is not None and m.cohort_id in t.get("cohort_ids", [])
    return False
