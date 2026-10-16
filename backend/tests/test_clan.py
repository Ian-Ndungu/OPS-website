import pytest
from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app
from app.models.clan import ClanRequest
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


def submit(client, **overrides):
    data = dict(gamer_tag="OPSKe Player", player_id="12345", game="PUBG Mobile", clan_tag="OPSKe",
                email="player@example.com", contact="discord-player", message="I would love to join and play with the clan.",
                name_updated="true")
    data.update(overrides)
    return client.post("/api/clan/requests", data=data,
                       files={"screenshot": ("profile.png", b"\x89PNG\r\n\x1a\n" + b"test", "image/png")})


def test_guest_application_private_review(client, db):
    response = submit(client)
    assert response.status_code == 201
    rid = response.json()["id"]
    assert db.get(ClanRequest, rid).status == "pending"
    base = "/api/clan/admin/requests"
    assert client.get(base).status_code == 401
    assert client.get(f"{base}/{rid}/screenshot").status_code == 401
    member = make_user(db, "member@example.com")
    assert client.get(base, headers=auth(member)).status_code == 403
    assert client.post(f"{base}/{rid}/review", json={"status": "approved"}, headers=auth(member)).status_code == 403
    reviewer = make_user(db, "review@example.com", Role.clan_verifier.value)
    h = auth(reviewer)
    listing = client.get(base, headers=h).json()
    assert listing[0]["email"] == "player@example.com"
    assert "screenshot" not in listing[0]
    image = client.get(f"{base}/{rid}/screenshot", headers=h)
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "no-store"
    assert client.post(f"{base}/{rid}/review", json={"status": "approved", "note": "Tag checked"}, headers=h).status_code == 200
    assert db.get(ClanRequest, rid).reviewed_by == reviewer.id
    assert client.get(base, headers=h).json() == []
    assert len(client.get(base + "?status=approved", headers=h).json()) == 1
    assert client.post(f"{base}/{rid}/review", json={"status": "rejected"}, headers=h).status_code == 409


def test_application_validation(client):
    assert submit(client, name_updated="false").status_code == 422
    assert submit(client, gamer_tag="No tag").status_code == 422
    assert submit(client, email="invalid").status_code == 422
    assert submit(client, message="short").status_code == 422
    data = dict(gamer_tag="OPSKe Player", player_id="1", game="PUBG", clan_tag="OPSKe",
                email="x@example.com", contact="abc", message="I want to join this clan.", name_updated="true")
    assert client.post("/api/clan/requests", data=data).status_code == 422
    for content, expected in [(b"<svg>bad</svg>", 422), (b"x" * (5 * 1024 * 1024 + 1), 413)]:
        response = client.post("/api/clan/requests", data=data, files={"screenshot": ("image.png", content, "image/png")})
        assert response.status_code == expected


def test_account_pending_until_admin_approval(client, db):
    credentials = {"email": "new@example.com", "password": "password123", "gamer_tag": "Player"}
    registered = client.post("/api/auth/register", json=credentials)
    assert registered.status_code == 200 and registered.json()["status"] == "pending"
    assert "token" not in registered.json()
    login = {"username": credentials["email"], "password": credentials["password"]}
    assert client.post("/api/auth/login", data=login).status_code == 403
    from sqlalchemy import select
    from app.models.core import User
    pending = db.scalar(select(User).where(User.email == credentials["email"]))
    assert client.get("/api/auth/me", headers=auth(pending)).status_code == 401
    reviewer = make_user(db, "admin@example.com", Role.super_admin.value)
    h = auth(reviewer)
    base = "/api/auth/admin/accounts"
    assert client.get(base).status_code == 401
    member = make_user(db, "existing@example.com")
    assert client.get(base, headers=auth(member)).status_code == 403
    assert client.post(f"{base}/{pending.id}/review", json={"approved": True}, headers=auth(member)).status_code == 403
    assert client.get(base, headers=h).json()[0]["id"] == pending.id
    assert client.post(f"{base}/{pending.id}/review", json={"approved": True}, headers=h).status_code == 200
    result = client.post("/api/auth/login", data=login)
    assert result.status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + result.json()["access_token"]}).status_code == 200
    assert client.get(base, headers=h).json() == []
    assert client.post(f"{base}/{pending.id}/review", json={"approved": True}, headers=h).status_code == 409
    assert client.post("/api/auth/login", data={"username": "existing@example.com", "password": "password123"}).status_code == 200


def test_rejected_account_cannot_login(client, db):
    client.post("/api/auth/register", json={"email": "reject@example.com", "password": "password123", "gamer_tag": "Player"})
    reviewer = make_user(db, "reviewer@example.com", Role.clan_verifier.value)
    h = auth(reviewer)
    base = "/api/auth/admin/accounts"
    uid = client.get(base, headers=h).json()[0]["id"]
    assert client.post(f"{base}/{uid}/review", json={"approved": False}, headers=h).status_code == 200
    assert client.post("/api/auth/login", data={"username": "reject@example.com", "password": "password123"}).status_code == 403
