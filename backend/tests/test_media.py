import base64
import pytest
from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app
from app.models.core import Role
from app.models.media import PublicImage
from app.security import create_token
from .conftest import make_user

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jGZkAAAAASUVORK5CYII=")


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_persists_and_public_image_survives_missing_disk(client, db, tmp_path, monkeypatch):
    from app.config import settings
    admin = make_user(db, "media@example.com", Role.content_admin.value)
    h = {"Authorization": f"Bearer {create_token(admin.id)}"}
    upload = client.post("/api/admin/announcements/upload", headers=h, files={"file": ("poster.png", PNG, "image/png")})
    assert upload.status_code == 200
    path = upload.json()["path"]
    assert db.get(PublicImage, path).data == PNG
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    response = client.get(upload.json()["url"])
    assert response.status_code == 200
    assert response.content == PNG and response.headers["content-type"] == "image/png"
    assert client.head(upload.json()["url"]).status_code == 200
    body = dict(title="Clan scrims", category="Scrims", summary="Registration is open", content_html="<p>Join us</p>", image_path=path)
    created = client.post("/api/admin/announcements", headers=h, json=body).json()
    aid = created["id"]
    assert client.get("/api/admin/announcements", headers=h).json()[0]["image_path"] == path
    assert client.patch(f"/api/admin/announcements/{aid}", headers=h, json={"title": "Updated scrims"}).status_code == 200
    client.post(f"/api/admin/announcements/{aid}/publish", headers=h, json={})
    public = client.get("/api/announcements").json()[0]
    assert public["image"] == upload.json()["url"]
    assert client.get(public["image"]).content == PNG
    # Saving an image on a published announcement sends its unchanged audience.
    response = client.patch(f"/api/admin/announcements/{aid}", headers=h,
                            json={"image_path": path, "target": {"audience": "everyone", "divisions": [], "cohort_ids": []}})
    assert response.status_code == 200


def test_upload_validation_and_private_folders(client, db):
    endpoint = "/api/admin/announcements/upload"
    assert client.post(endpoint, files={"file": ("x.png", PNG, "image/png")}).status_code == 401
    admin = make_user(db, "adminmedia@example.com", Role.content_admin.value)
    h = {"Authorization": f"Bearer {create_token(admin.id)}"}
    assert client.post(endpoint, headers=h, files={"file": ("x.png", b"<svg/>", "image/png")}).status_code == 422
    assert client.post(endpoint, headers=h, files={"file": ("x.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")}).status_code == 413
    assert client.get("/uploads/clan-screenshots/private.png").status_code == 404
    assert client.get("/uploads/announcements/missing.png").status_code == 404


def test_legacy_disk_image_still_served(client, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    folder = tmp_path / "announcements"
    folder.mkdir()
    (folder / "legacy.png").write_bytes(PNG)
    assert client.get("/uploads/announcements/legacy.png").content == PNG
