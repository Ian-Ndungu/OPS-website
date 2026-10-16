from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.content import Team
from app.models.core import Notification
from app.models.mythic import CohortMember
from app.services import announcements as ann
from app.services import results as res

from .conftest import make_user


# ------------------------------------------------------------- results
def teams(db, n=4):
    out = [Team(name=f"Team{i}") for i in range(n)]
    db.add_all(out)
    db.flush()
    return out


def br_match(ts, no=1):
    return {"match_no": no, "entries": [
        {"team_id": t.id, "placement": i + 1, "kills": 5 - i, "placement_points": 12 - 3 * i, "kill_points": 5 - i}
        for i, t in enumerate(ts)]}


def test_battle_royale_standings_and_workflow(db, admins):
    ed, pub = admins["content"], admins["results"]
    ts = teams(db)
    t = res.create_tournament(db, ed, name="Weekly", game="CODM", mode="battle_royale", game_mode="BR",
                              starts_on=date(2026, 10, 1))
    res.add_match(db, ed, t.id, br_match(ts, 1))
    res.add_match(db, ed, t.id, br_match(list(reversed(ts)), 2))
    st = res.standings(db, t)
    assert st[0]["total_points"] == st[1]["total_points"] or st[0]["total_points"] > st[1]["total_points"]
    assert [r["rank"] for r in st] == [1, 2, 3, 4]
    # workflow: content admin cannot publish
    res.transition(db, ed, t.id, "review", can_publish=False)
    with pytest.raises(res.ResultsError):
        res.transition(db, ed, t.id, "published", can_publish=False)
    res.transition(db, pub, t.id, "published", can_publish=True)
    assert t.pub_status == "published" and t.revision == 1


def test_validation_and_duplicates(db, admins):
    ed = admins["content"]
    ts = teams(db)
    t = res.create_tournament(db, ed, name="V", game="CODM", mode="battle_royale", game_mode=None,
                              starts_on=date(2026, 10, 1))
    bad = br_match(ts)
    bad["entries"][1]["placement"] = 1  # duplicate placement
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, bad)
    gap = br_match(ts)
    gap["entries"][3]["placement"] = 9
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, gap)
    neg = br_match(ts)
    neg["entries"][0]["kills"] = -1
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, neg)
    res.add_match(db, ed, t.id, br_match(ts, 1))
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, br_match(ts, 1))  # duplicate match number


def test_multiplayer_validation_and_standings(db, admins):
    ed = admins["content"]
    a, b, c, _ = teams(db)
    t = res.create_tournament(db, ed, name="MP", game="CODM", mode="multiplayer", game_mode="Hardpoint",
                              starts_on=date(2026, 10, 2))
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, {"match_no": 1, "team_a_id": a.id, "team_b_id": a.id, "score_a": 1, "score_b": 0})
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, {"match_no": 1, "team_a_id": a.id, "team_b_id": b.id, "score_a": 3, "score_b": 3})
    with pytest.raises(res.ResultsError):
        res.add_match(db, ed, t.id, {"match_no": 1, "team_a_id": a.id, "team_b_id": b.id, "score_a": 3,
                                     "score_b": 1, "winner_team_id": b.id})
    res.add_match(db, ed, t.id, {"match_no": 1, "team_a_id": a.id, "team_b_id": b.id, "score_a": 250, "score_b": 200})
    res.add_match(db, ed, t.id, {"match_no": 2, "team_a_id": c.id, "team_b_id": a.id, "score_a": 100, "score_b": 250})
    st = res.standings(db, t)
    assert st[0]["team"] == a.name and st[0]["wins"] == 2


def test_publish_needs_matches_and_published_edits_create_revisions(db, admins):
    ed, pub = admins["content"], admins["results"]
    ts = teams(db)
    t = res.create_tournament(db, ed, name="R", game="CODM", mode="battle_royale", game_mode=None,
                              starts_on=date(2026, 10, 1))
    with pytest.raises(res.ResultsError):
        res.transition(db, ed, t.id, "review", can_publish=False)
    res.add_match(db, ed, t.id, br_match(ts))
    res.transition(db, ed, t.id, "review", can_publish=False)
    res.transition(db, pub, t.id, "published", can_publish=True)
    fix = br_match(ts)
    fix["entries"][0]["kills"] = 9
    with pytest.raises(res.ResultsError):
        res.update_match(db, pub, t.id, 1, fix)  # reason required
    fix["reason"] = "Kill count corrected after VOD review"
    res.update_match(db, pub, t.id, 1, fix)
    revs = res.revisions(db, t.id)
    assert [r["revision"] for r in revs] == [2, 1] and revs[0]["reason"].startswith("Kill count")
    res.transition(db, pub, t.id, "archived", can_publish=True)
    with pytest.raises(res.ResultsError):
        res.update_match(db, pub, t.id, 1, fix)


# ------------------------------------------------------- announcements
def payload(**kw):
    d = {"title": "Scrim night", "category": "Scrims", "summary": "Join us", "content_html": "<p>Hi</p>"}
    d.update(kw)
    return d


def test_sanitization_strips_scripts_and_bad_urls(db, admins):
    a = ann.create(db, admins["content"], payload(content_html=(
        '<p onclick="x()">ok</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a>'
        '<a href="https://ops.gg">good</a><img src="x" onerror="alert(1)">')))
    h = a.content_html
    assert "<script" not in h and "onclick" not in h and "javascript:" not in h and "onerror" not in h
    assert 'href="https://ops.gg"' in h and 'rel="noopener' in h


def test_unknown_category_and_targeted_permissions(db, admins):
    with pytest.raises(ann.AnnouncementError):
        ann.create(db, admins["content"], payload(category="Nope"))
    with pytest.raises(ann.AnnouncementError) as e:
        ann.create(db, admins["content"], payload(target={"audience": "mythic"}))
    assert e.value.status_code == 403
    ann.create(db, admins["finance1"], payload(target={"audience": "mythic"}))  # finance may


def test_publish_notifies_targeted_recipients_only(db, admins):
    m1 = make_user(db, "m1@x.com", is_verified_member=True, game_division="CODM")
    m2 = make_user(db, "m2@x.com", is_verified_member=False, game_division="PUBG")
    a = ann.create(db, admins["content"], payload(target={"audience": "divisions", "divisions": ["CODM"]}))
    ann.publish(db, admins["content"], a)
    db.flush()
    assert db.query(Notification).filter_by(user_id=m1.id).count() == 1
    assert db.query(Notification).filter_by(user_id=m2.id).count() == 0
    ann.publish(db, admins["content"], a)  # republish does not re-notify
    db.flush()
    assert db.query(Notification).filter_by(user_id=m1.id).count() == 1


def test_visibility_rules(db, admins):
    verified = make_user(db, "v@x.com", is_verified_member=True)
    plain = make_user(db, "pl@x.com")
    pub = ann.create(db, admins["content"], payload(title="Public"))
    ver = ann.create(db, admins["content"], payload(title="Verified only", target={"audience": "verified"}))
    for a in (pub, ver):
        ann.publish(db, admins["content"], a)
    draft = ann.create(db, admins["content"], payload(title="Draft"))
    titles = lambda u: {x.title for x in db.scalars(ann.visible_query(u, db))}
    assert titles(None) == {"Public"}
    assert titles(plain) == {"Public"}
    assert titles(verified) == {"Public", "Verified only"}
    assert draft.title not in titles(verified)


def test_scheduling_publishes_when_due(db, admins):
    a = ann.create(db, admins["content"], payload())
    ann.publish(db, admins["content"], a, datetime.now(timezone.utc) + timedelta(hours=2))
    assert a.status == "scheduled" and ann.publish_due(db) == 0
    a.publish_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert ann.publish_due(db) == 1 and a.status == "published"
