from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app
from app.models.content import Team
from app.models.core import Role
from app.security import create_token

from .conftest import make_user


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(u):
    return {"Authorization": f"Bearer {create_token(u.id)}"}


def test_plans_endpoint_is_fixed_and_unauthenticated_ok(client):
    r = client.get("/api/mythic/plans").json()
    codes = {p["code"]: p for p in r["plans"]}
    assert codes["A"]["monthly_kes"] == 1000 and codes["A"]["cohort_target_kes"] == 49000
    assert codes["B"]["monthly_kes"] == 700 and codes["B"]["cohort_target_kes"] == 70000
    assert r["live_payments"] is False


def test_member_endpoints_require_auth(client):
    assert client.get("/api/mythic/me").status_code == 401
    assert client.post("/api/mythic/contributions/1/pay").status_code == 401


def test_admin_endpoints_forbidden_for_members(client, db):
    m = make_user(db, "mem@x.com")
    for path in ("/api/mythic/admin/overview", "/api/mythic/admin/payout-batches", "/api/admin/results",
                 "/api/admin/announcements"):
        assert client.get(path, headers=auth(m)).status_code == 403
    assert client.post("/api/mythic/admin/payout-batches/1/execute", headers=auth(m)).status_code == 403


def test_callback_requires_secret(client):
    assert client.post("/api/mythic/callbacks/wrong/stk", json={}).status_code == 404
    ok = client.post(f"/api/mythic/callbacks/{settings.CALLBACK_SECRET}/stk", json={"junk": 1})
    assert ok.status_code == 200  # malformed bodies are acknowledged but change nothing


def test_cms_cannot_change_plan_terms(client, db):
    fin = make_user(db, "f@x.com", Role.finance_admin.value)
    h = auth(fin)
    assert client.put("/api/mythic/admin/content/landing_description",
                      json={"value": {"text": "Welcome"}}, headers=h).status_code == 200
    assert client.put("/api/mythic/admin/content/landing_description",
                      json={"value": {"monthly_kes": 5}}, headers=h).status_code == 400
    assert client.put("/api/mythic/admin/content/plans", json={"value": {"x": 1}}, headers=h).status_code == 400
    assert client.get("/api/mythic/content").json()["landing_description"] == {"text": "Welcome"}


def test_cohort_creation_endpoint_rejects_custom_size(client, db):
    fin = make_user(db, "f2@x.com", Role.finance_admin.value)
    assert client.post("/api/mythic/admin/cohorts", json={"name": "x", "size": 9}, headers=auth(fin)).status_code == 400
    assert client.post("/api/mythic/admin/cohorts", json={"name": "x", "size": 7}, headers=auth(fin)).status_code == 200


def test_results_public_only_shows_published(client, db):
    ed = make_user(db, "ed@x.com", Role.content_admin.value)
    pub = make_user(db, "pub@x.com", Role.results_admin.value)
    ts = [Team(name=f"T{i}") for i in range(3)]
    db.add_all(ts)
    db.flush()
    r = client.post("/api/admin/results/tournaments", headers=auth(ed), json={
        "name": "Cup", "game": "CODM", "mode": "battle_royale", "starts_on": "2026-10-01"})
    tid = r.json()["id"]
    body = {"match_no": 1, "entries": [{"team_id": t.id, "placement": i + 1, "kills": 3, "placement_points": 10 - i,
                                        "kill_points": 3} for i, t in enumerate(ts)]}
    assert client.post(f"/api/admin/results/{tid}/matches", json=body, headers=auth(ed)).status_code == 200
    assert client.post(f"/api/admin/results/{tid}/matches", json=body, headers=auth(ed)).status_code == 409
    assert client.get("/api/results").json() == []
    assert client.get(f"/api/results/{tid}").status_code == 404  # draft hidden
    client.post(f"/api/admin/results/{tid}/status", json={"status": "review"}, headers=auth(ed))
    assert client.post(f"/api/admin/results/{tid}/status", json={"status": "published"},
                       headers=auth(ed)).status_code == 403
    assert client.post(f"/api/admin/results/{tid}/status", json={"status": "published"},
                       headers=auth(pub)).status_code == 200
    listing = client.get("/api/results").json()
    assert len(listing) == 1 and len(listing[0]["podium"]) == 3
    assert client.get(f"/api/results/{tid}/standings").json()[0]["total_points"] == 13
    # content admins cannot rewrite published results
    assert client.put(f"/api/admin/results/{tid}/matches/1", json=body, headers=auth(ed)).status_code == 403


def test_announcement_flow_over_http(client, db):
    ed = make_user(db, "e2@x.com", Role.content_admin.value)
    h = auth(ed)
    base = {"title": "Server maintenance", "category": "Maintenance", "summary": "Down tonight",
            "content_html": "<p>Hi</p><script>x</script>"}
    assert client.post("/api/admin/announcements", json=base | {"target": {"audience": "mythic"}},
                       headers=h).status_code == 403
    aid = client.post("/api/admin/announcements", json=base, headers=h).json()["id"]
    assert client.get("/api/announcements").json() == []  # draft not public
    assert client.post(f"/api/admin/announcements/{aid}/publish", json={}, headers=h).status_code == 200
    items = client.get("/api/announcements").json()
    assert len(items) == 1 and client.get("/api/announcements/latest").json()[0]["id"] == aid
    d = client.get(f"/api/announcements/{items[0]['slug']}").json()
    assert "<script" not in d["content_html"]
    assert client.get("/api/announcements?q=maint").json()
    assert client.get("/api/announcements?category=Scrims").json() == []
    # members cannot publish
    m = make_user(db, "plain@x.com")
    assert client.post(f"/api/admin/announcements/{aid}/publish", json={}, headers=auth(m)).status_code == 403
