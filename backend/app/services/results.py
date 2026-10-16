from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.content import Match, MatchEntry, ResultRevision, Team, Tournament
from ..models.core import User
from .common import audit


class ResultsError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


MODES = {"battle_royale", "multiplayer"}


def _t(db: Session, tid: int) -> Tournament:
    t = db.get(Tournament, tid)
    if not t:
        raise ResultsError("Tournament not found", 404)
    return t


def create_tournament(db: Session, admin: User, *, name, game, mode, game_mode, starts_on) -> Tournament:
    if mode not in MODES:
        raise ResultsError("Mode must be battle_royale or multiplayer")
    t = Tournament(name=name, game=game, mode=mode, game_mode=game_mode, starts_on=starts_on,
                   created_by=admin.id)
    db.add(t)
    db.flush()
    audit(db, admin.id, "results.tournament.created", "tournament", t.id)
    return t


# --------------------------------------------------------- validation
def validate_match(t: Tournament, data: dict):
    if t.mode == "battle_royale":
        entries = data.get("entries") or []
        if len(entries) < 2:
            raise ResultsError("A Battle Royale match needs at least two teams")
        teams = [e["team_id"] for e in entries]
        places = [e["placement"] for e in entries]
        if len(set(teams)) != len(teams):
            raise ResultsError("A team appears more than once in this match")
        if len(set(places)) != len(places):
            raise ResultsError("Two teams cannot share a placement")
        if sorted(places) != list(range(1, len(places) + 1)):
            raise ResultsError("Placements must run 1..N without gaps")
        for e in entries:
            for k in ("kills", "placement_points", "kill_points"):
                if e.get(k, 0) < 0:
                    raise ResultsError(f"{k.replace('_', ' ').title()} cannot be negative")
    else:
        a, b = data.get("team_a_id"), data.get("team_b_id")
        sa, sb = data.get("score_a"), data.get("score_b")
        if not a or not b or a == b:
            raise ResultsError("Multiplayer match needs two different teams")
        if sa is None or sb is None or sa < 0 or sb < 0:
            raise ResultsError("Scores must be zero or greater")
        if sa == sb:
            raise ResultsError("Draws are not recorded; enter the deciding scores")
        expected = a if sa > sb else b
        if data.get("winner_team_id") not in (None, expected):
            raise ResultsError("Winner does not match the recorded scores")
        data["winner_team_id"] = expected


def _check_teams(db: Session, ids: list[int]):
    found = {i for (i,) in db.execute(select(Team.id).where(Team.id.in_(ids)))}
    if found != set(ids):
        raise ResultsError("Unknown team in submission")


def _editable(t: Tournament, reason: str | None):
    if t.pub_status == "archived":
        raise ResultsError("Archived results cannot be edited", 409)
    if t.pub_status == "published" and not (reason or "").strip():
        raise ResultsError("A correction reason is required for published results", 409)


def _apply_match(db: Session, t: Tournament, m: Match, data: dict):
    if t.mode == "battle_royale":
        entries = data["entries"]
        _check_teams(db, [e["team_id"] for e in entries])
        for old in db.scalars(select(MatchEntry).where(MatchEntry.match_id == m.id)):
            db.delete(old)
        db.flush()
        for e in entries:
            db.add(MatchEntry(match_id=m.id, team_id=e["team_id"], placement=e["placement"],
                              kills=e.get("kills", 0), placement_points=e.get("placement_points", 0),
                              kill_points=e.get("kill_points", 0)))
    else:
        _check_teams(db, [data["team_a_id"], data["team_b_id"]])
        m.team_a_id, m.team_b_id = data["team_a_id"], data["team_b_id"]
        m.score_a, m.score_b, m.winner_team_id = data["score_a"], data["score_b"], data["winner_team_id"]
    m.game_mode = data.get("game_mode") or t.game_mode
    m.mvp_player = data.get("mvp_player")
    if data.get("screenshot_path"):
        m.screenshot_path = data["screenshot_path"]


def add_match(db: Session, admin: User, tid: int, data: dict) -> Match:
    t = _t(db, tid)
    _editable(t, data.get("reason"))
    validate_match(t, data)
    if db.scalar(select(Match).where(Match.tournament_id == tid, Match.match_no == data["match_no"])):
        raise ResultsError("A result for this match number already exists", 409)
    if t.pub_status == "published":
        _snapshot(db, t, admin, data.get("reason"))
    m = Match(tournament_id=tid, match_no=data["match_no"])
    db.add(m)
    db.flush()
    _apply_match(db, t, m, data)
    audit(db, admin.id, "results.match.added", "tournament", tid, after={"match_no": m.match_no})
    return m


def update_match(db: Session, admin: User, tid: int, match_no: int, data: dict) -> Match:
    t = _t(db, tid)
    _editable(t, data.get("reason"))
    m = db.scalar(select(Match).where(Match.tournament_id == tid, Match.match_no == match_no))
    if not m:
        raise ResultsError("Match not found", 404)
    validate_match(t, data)
    if t.pub_status == "published":
        _snapshot(db, t, admin, data.get("reason"))
    _apply_match(db, t, m, data)
    audit(db, admin.id, "results.match.updated", "tournament", tid, after={"match_no": match_no})
    return m


def set_mvp(db: Session, admin: User, tid: int, mvp: str | None, reason: str | None = None):
    t = _t(db, tid)
    _editable(t, reason)
    if t.pub_status == "published":
        _snapshot(db, t, admin, reason)
    t.mvp_player = mvp
    audit(db, admin.id, "results.mvp.set", "tournament", tid, after={"mvp": mvp})


# ---------------------------------------------------------- standings
def standings(db: Session, t: Tournament) -> list[dict]:
    matches = list(db.scalars(select(Match).where(Match.tournament_id == t.id).order_by(Match.match_no)))
    teams = {x.id: x for x in db.scalars(select(Team))}
    rows: dict[int, dict] = {}

    def row(tid):
        return rows.setdefault(tid, {"team_id": tid, "team": teams[tid].name, "logo_url": teams[tid].logo_url,
                                     "matches": 0, "wins": 0, "kills": 0, "placement_points": 0,
                                     "kill_points": 0, "total_points": 0, "best_placement": None,
                                     "score_for": 0, "score_against": 0})

    if t.mode == "battle_royale":
        for m in matches:
            for e in db.scalars(select(MatchEntry).where(MatchEntry.match_id == m.id)):
                r = row(e.team_id)
                r["matches"] += 1
                r["kills"] += e.kills
                r["placement_points"] += e.placement_points
                r["kill_points"] += e.kill_points
                r["total_points"] += e.placement_points + e.kill_points
                r["wins"] += 1 if e.placement == 1 else 0
                r["best_placement"] = e.placement if r["best_placement"] is None else min(r["best_placement"], e.placement)
        order = sorted(rows.values(), key=lambda r: (-r["total_points"], -r["wins"], -r["kills"],
                                                     r["best_placement"] or 99, r["team"]))
    else:
        for m in matches:
            a, b = row(m.team_a_id), row(m.team_b_id)
            a["matches"] += 1
            b["matches"] += 1
            a["score_for"] += m.score_a
            a["score_against"] += m.score_b
            b["score_for"] += m.score_b
            b["score_against"] += m.score_a
            (a if m.winner_team_id == m.team_a_id else b)["wins"] += 1
            (a if m.winner_team_id == m.team_a_id else b)["total_points"] += 1
        order = sorted(rows.values(), key=lambda r: (-r["wins"], -(r["score_for"] - r["score_against"]), r["team"]))
    for i, r in enumerate(order, 1):
        r["rank"] = i
    return order


def match_list(db: Session, t: Tournament) -> list[dict]:
    teams = {x.id: x for x in db.scalars(select(Team))}
    out = []
    for m in db.scalars(select(Match).where(Match.tournament_id == t.id).order_by(Match.match_no)):
        d = {"match_no": m.match_no, "game_mode": m.game_mode, "mvp_player": m.mvp_player,
             "screenshot": m.screenshot_path}
        if t.mode == "battle_royale":
            ents = db.scalars(select(MatchEntry).where(MatchEntry.match_id == m.id).order_by(MatchEntry.placement))
            d["entries"] = [{"team_id": e.team_id, "team": teams[e.team_id].name, "logo_url": teams[e.team_id].logo_url,
                             "placement": e.placement, "kills": e.kills, "placement_points": e.placement_points,
                             "kill_points": e.kill_points, "total": e.placement_points + e.kill_points}
                            for e in ents]
            d["winner"] = d["entries"][0]["team"] if d["entries"] else None
        else:
            d.update({"team_a": teams[m.team_a_id].name, "team_b": teams[m.team_b_id].name,
                      "team_a_id": m.team_a_id, "team_b_id": m.team_b_id, "score_a": m.score_a,
                      "score_b": m.score_b, "winner": teams[m.winner_team_id].name})
        out.append(d)
    return out


def tournament_view(db: Session, t: Tournament) -> dict:
    return {"id": t.id, "name": t.name, "game": t.game, "mode": t.mode, "game_mode": t.game_mode,
            "starts_on": t.starts_on, "event_status": t.event_status, "pub_status": t.pub_status,
            "mvp_player": t.mvp_player, "revision": t.revision, "published_at": t.published_at,
            "standings": standings(db, t), "matches": match_list(db, t)}


# ----------------------------------------------------------- workflow
def _snapshot(db: Session, t: Tournament, admin: User, reason: str | None):
    t.revision += 1
    view = tournament_view(db, t)
    view = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in view.items()}
    db.add(ResultRevision(tournament_id=t.id, revision=t.revision, snapshot=view, reason=reason, actor_id=admin.id))


def transition(db: Session, admin: User, tid: int, target: str, *, can_publish: bool) -> Tournament:
    t = _t(db, tid)
    allowed = {("draft", "review"), ("review", "draft"), ("review", "published"), ("published", "archived"),
               ("draft", "archived"), ("review", "archived")}
    if (t.pub_status, target) not in allowed:
        raise ResultsError(f"Cannot move from {t.pub_status} to {target}", 409)
    if target in {"published", "archived"} and not can_publish:
        raise ResultsError("Only results administrators can publish or archive", 403)
    if target in {"review", "published"}:
        if not db.scalar(select(Match.id).where(Match.tournament_id == tid)):
            raise ResultsError("Add at least one match result first", 409)
    before = t.pub_status
    t.pub_status = target
    if target == "published":
        t.published_at = datetime.now(timezone.utc)
        t.event_status = "completed"
        _snapshot(db, t, admin, "Initial publication")
    audit(db, admin.id, f"results.{target}", "tournament", tid, {"status": before}, {"status": target})
    return t


def revisions(db: Session, tid: int) -> list[dict]:
    return [{"revision": r.revision, "reason": r.reason, "actor_id": r.actor_id, "created_at": r.created_at,
             "snapshot": r.snapshot}
            for r in db.scalars(select(ResultRevision).where(ResultRevision.tournament_id == tid)
                                .order_by(ResultRevision.revision.desc()))]
