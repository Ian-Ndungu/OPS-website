from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.content import Team, Tournament
from ..models.core import Role, User
from ..security import require_roles
from ..services import results as svc
from .media import save_public_image

router = APIRouter(prefix="/api", tags=["results"])
editor = require_roles(Role.content_admin, Role.results_admin)
publisher = require_roles(Role.results_admin)


def run(db: Session, fn, *a, **kw):
    try:
        r = fn(db, *a, **kw)
        db.commit()
        return r
    except svc.ResultsError as e:
        db.rollback()
        raise HTTPException(e.status_code, str(e))


# --------------------------------------------------------------- public
@router.get("/results")
def list_results(game: str | None = None, mode: str | None = None, tournament_id: int | None = None,
                 date_from: date | None = None, date_to: date | None = None, status: str | None = None,
                 db: Session = Depends(get_db)):
    q = select(Tournament).where(Tournament.pub_status == "published").order_by(Tournament.starts_on.desc())
    if game:
        q = q.where(Tournament.game == game)
    if mode:
        q = q.where(Tournament.mode == mode)
    if tournament_id:
        q = q.where(Tournament.id == tournament_id)
    if date_from:
        q = q.where(Tournament.starts_on >= date_from)
    if date_to:
        q = q.where(Tournament.starts_on <= date_to)
    if status in {"completed", "upcoming"}:
        q = q.where(Tournament.event_status == status)
    out = []
    for t in db.scalars(q):
        st = svc.standings(db, t)
        out.append({"id": t.id, "name": t.name, "game": t.game, "mode": t.mode, "game_mode": t.game_mode,
                    "starts_on": t.starts_on, "event_status": t.event_status, "mvp_player": t.mvp_player,
                    "podium": st[:3], "team_count": len(st)})
    return out


@router.get("/results/{tid}")
def tournament_results(tid: int, db: Session = Depends(get_db)):
    t = db.get(Tournament, tid)
    if not t or t.pub_status != "published":
        raise HTTPException(404, "Results not found")
    return svc.tournament_view(db, t)


@router.get("/results/{tid}/standings")
def get_standings(tid: int, db: Session = Depends(get_db)):
    t = db.get(Tournament, tid)
    if not t or t.pub_status != "published":
        raise HTTPException(404, "Results not found")
    return svc.standings(db, t)


@router.get("/results-filters")
def filters(db: Session = Depends(get_db)):
    rows = db.execute(select(Tournament.id, Tournament.name, Tournament.game)
                      .where(Tournament.pub_status == "published")).all()
    return {"games": sorted({r.game for r in rows}), "tournaments": [{"id": r.id, "name": r.name} for r in rows]}


# ---------------------------------------------------------------- admin
class TournamentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    game: str
    mode: str
    game_mode: str | None = None
    starts_on: date


class EntryIn(BaseModel):
    team_id: int
    placement: int = Field(ge=1)
    kills: int = Field(default=0, ge=0)
    placement_points: int = Field(default=0, ge=0)
    kill_points: int = Field(default=0, ge=0)


class MatchIn(BaseModel):
    match_no: int = Field(ge=1)
    game_mode: str | None = None
    entries: list[EntryIn] | None = None
    team_a_id: int | None = None
    team_b_id: int | None = None
    score_a: int | None = Field(default=None, ge=0)
    score_b: int | None = Field(default=None, ge=0)
    winner_team_id: int | None = None
    mvp_player: str | None = None
    screenshot_path: str | None = None
    reason: str | None = None  # required when correcting published results


def _data(body: MatchIn) -> dict:
    d = body.model_dump()
    if d.get("entries") is not None:
        d["entries"] = [e if isinstance(e, dict) else e for e in d["entries"]]
    return d


@router.get("/admin/results")
def admin_list(_: User = Depends(editor), db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "game": t.game, "mode": t.mode, "starts_on": t.starts_on,
             "pub_status": t.pub_status, "revision": t.revision}
            for t in db.scalars(select(Tournament).order_by(Tournament.starts_on.desc()))]


@router.post("/admin/results/tournaments")
def new_tournament(body: TournamentIn, admin: User = Depends(editor), db: Session = Depends(get_db)):
    t = run(db, svc.create_tournament, admin, **body.model_dump())
    return {"id": t.id}


@router.get("/admin/results/{tid}")
def admin_view(tid: int, _: User = Depends(editor), db: Session = Depends(get_db)):
    t = db.get(Tournament, tid)
    if not t:
        raise HTTPException(404)
    return svc.tournament_view(db, t)  # includes drafts: standings preview


@router.post("/admin/results/{tid}/matches")
def add_match(tid: int, body: MatchIn, admin: User = Depends(editor), db: Session = Depends(get_db)):
    _guard_correction(db, tid, admin)
    m = run(db, svc.add_match, admin, tid, _data(body))
    return {"match_no": m.match_no}


@router.put("/admin/results/{tid}/matches/{match_no}")
def update_match(tid: int, match_no: int, body: MatchIn, admin: User = Depends(editor), db: Session = Depends(get_db)):
    _guard_correction(db, tid, admin)
    run(db, svc.update_match, admin, tid, match_no, _data(body))
    return {"ok": True}


def _guard_correction(db: Session, tid: int, admin: User):
    """Only results admins may alter already-published results."""
    t = db.get(Tournament, tid)
    if t and t.pub_status == "published" and admin.role not in {Role.results_admin.value, Role.super_admin.value}:
        raise HTTPException(403, "Only results administrators can correct published results")


@router.post("/admin/results/{tid}/screenshot")
def upload_screenshot(tid: int, file: UploadFile = File(...), _: User = Depends(editor), db: Session = Depends(get_db)):
    return {"path": save_public_image(file, "match-screenshots", db)}


class MvpIn(BaseModel):
    mvp_player: str | None
    reason: str | None = None


@router.put("/admin/results/{tid}/mvp")
def mvp(tid: int, body: MvpIn, admin: User = Depends(editor), db: Session = Depends(get_db)):
    _guard_correction(db, tid, admin)
    run(db, svc.set_mvp, admin, tid, body.mvp_player, body.reason)
    return {"ok": True}


class StatusIn(BaseModel):
    status: str  # review | draft | published | archived


@router.post("/admin/results/{tid}/status")
def set_status(tid: int, body: StatusIn, admin: User = Depends(editor), db: Session = Depends(get_db)):
    can_publish = admin.role in {Role.results_admin.value, Role.super_admin.value}
    t = run(db, svc.transition, admin, tid, body.status, can_publish=can_publish)
    return {"pub_status": t.pub_status}


@router.get("/admin/results/{tid}/revisions")
def revisions(tid: int, _: User = Depends(editor), db: Session = Depends(get_db)):
    return svc.revisions(db, tid)


class TeamIn(BaseModel):
    name: str
    logo_url: str | None = None


@router.get("/teams")
def teams(db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "logo_url": t.logo_url} for t in db.scalars(select(Team).order_by(Team.name))]


@router.post("/admin/teams")
def add_team(body: TeamIn, _: User = Depends(editor), db: Session = Depends(get_db)):
    t = Team(**body.model_dump())
    db.add(t)
    db.commit()
    return {"id": t.id}
