from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.content import Announcement
from ..models.core import Notification, Role, User
from ..security import current_user, optional_user, require_roles
from ..services import announcements as svc
from .media import save_public_image

router = APIRouter(prefix="/api", tags=["announcements"])
admin_dep = require_roles(Role.content_admin, Role.finance_admin)


def run(db: Session, fn, *a, **kw):
    try:
        r = fn(db, *a, **kw)
        db.commit()
        return r
    except svc.AnnouncementError as e:
        db.rollback()
        raise HTTPException(e.status_code, str(e))


def card(a: Announcement, author: str | None = None, full: bool = False) -> dict:
    d = {"id": a.id, "slug": a.slug, "title": a.title, "category": a.category, "summary": a.summary,
         "image": f"/uploads/{a.image_path}" if a.image_path else None, "pinned": a.pinned,
         "featured": a.featured, "published_at": a.published_at, "author": author}
    if full:
        d["content_html"] = a.content_html
    return d


def _authors(db: Session, rows) -> dict:
    ids = {a.author_id for a in rows}
    return {u.id: u.gamer_tag for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


@router.get("/announcements")
def list_public(q: str | None = None, category: str | None = None, limit: int = 20, offset: int = 0,
                user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    stmt = svc.visible_query(user, db)
    if category:
        stmt = stmt.where(Announcement.category == category)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Announcement.title.ilike(like), Announcement.summary.ilike(like)))
    stmt = stmt.order_by(Announcement.pinned.desc(), Announcement.published_at.desc()).limit(min(limit, 50)).offset(offset)
    rows = list(db.scalars(stmt))
    au = _authors(db, rows)
    return [card(a, au.get(a.author_id)) for a in rows]


@router.get("/announcements/latest")
def latest(limit: int = 3, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(svc.visible_query(user, db).order_by(Announcement.pinned.desc(),
                                                                Announcement.published_at.desc()).limit(min(limit, 10))))
    au = _authors(db, rows)
    return [card(a, au.get(a.author_id)) for a in rows]


@router.get("/announcements/categories")
def categories():
    return svc.CATEGORIES


@router.get("/announcements/{slug}")
def detail(slug: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    a = db.scalar(svc.visible_query(user, db).where(Announcement.slug == slug))
    if not a:
        raise HTTPException(404, "Announcement not found")
    return card(a, _authors(db, [a]).get(a.author_id), full=True)


# ---------------------------------------------------- notifications
@router.get("/notifications")
def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(50))
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read,
             "created_at": n.created_at} for n in rows]


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404)
    n.read = True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- admin
class TargetIn(BaseModel):
    audience: str = "everyone"
    divisions: list[str] = []
    cohort_ids: list[int] = []


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str
    summary: str = Field(min_length=3, max_length=400)
    content_html: str
    image_path: str | None = None
    pinned: bool = False
    featured: bool = False
    email_notify: bool = False
    target: TargetIn = TargetIn()


class AnnouncementPatch(BaseModel):
    title: str | None = None
    category: str | None = None
    summary: str | None = None
    content_html: str | None = None
    image_path: str | None = None
    pinned: bool | None = None
    featured: bool | None = None
    email_notify: bool | None = None
    target: TargetIn | None = None


def _get(db: Session, aid: int) -> Announcement:
    a = db.get(Announcement, aid)
    if not a:
        raise HTTPException(404)
    return a


@router.get("/admin/announcements")
def admin_list(status: str | None = None, _: User = Depends(admin_dep), db: Session = Depends(get_db)):
    q = select(Announcement).order_by(Announcement.id.desc())
    if status:
        q = q.where(Announcement.status == status)
    return [card(a) | {"status": a.status, "publish_at": a.publish_at, "image_path": a.image_path, "target": a.target, "content_html": a.content_html}
            for a in db.scalars(q)]


@router.post("/admin/announcements")
def create(body: AnnouncementIn, admin: User = Depends(admin_dep), db: Session = Depends(get_db)):
    a = run(db, svc.create, admin, body.model_dump())
    return {"id": a.id, "slug": a.slug}


@router.patch("/admin/announcements/{aid}")
def patch(aid: int, body: AnnouncementPatch, admin: User = Depends(admin_dep), db: Session = Depends(get_db)):
    run(db, svc.update, admin, _get(db, aid), body.model_dump(exclude_unset=True))
    return {"ok": True}


@router.post("/admin/announcements/upload")
def upload(file: UploadFile = File(...), _: User = Depends(admin_dep), db: Session = Depends(get_db)):
    path = save_public_image(file, "announcements", db)
    return {"path": path, "url": f"/uploads/{path}"}


class PublishIn(BaseModel):
    publish_at: datetime | None = None


@router.post("/admin/announcements/{aid}/publish")
def publish(aid: int, body: PublishIn = PublishIn(), admin: User = Depends(admin_dep), db: Session = Depends(get_db)):
    a = run(db, svc.publish, admin, _get(db, aid), body.publish_at)
    return {"status": a.status}


@router.post("/admin/announcements/{aid}/unpublish")
def unpublish(aid: int, admin: User = Depends(admin_dep), db: Session = Depends(get_db)):
    run(db, svc.unpublish, admin, _get(db, aid))
    return {"ok": True}


@router.post("/admin/announcements/{aid}/archive")
def archive(aid: int, admin: User = Depends(admin_dep), db: Session = Depends(get_db)):
    run(db, svc.archive, admin, _get(db, aid))
    return {"ok": True}
