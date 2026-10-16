import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..models.media import PublicImage

router = APIRouter()
PUBLIC_FOLDERS = {"announcements", "match-screenshots"}
MAX_IMAGE = 5 * 1024 * 1024


def save_public_image(file: UploadFile, folder: str, db: Session) -> str:
    if folder not in PUBLIC_FOLDERS:
        raise HTTPException(400, "Invalid public image folder")
    data = file.file.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "Image must be 5 MB or smaller")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, ext = "image/png", "png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime, ext = "image/jpeg", "jpg"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime, ext = "image/webp", "webp"
    else:
        raise HTTPException(422, "Only PNG, JPEG or WebP images are allowed")
    path = f"{folder}/{uuid.uuid4().hex}.{ext}"
    db.add(PublicImage(path=path, content_type=mime, data=data))
    db.commit()
    return path


@router.api_route("/uploads/{folder}/{filename}", methods=["GET", "HEAD"])
def public_image(folder: str, filename: str, db: Session = Depends(get_db)):
    if folder not in PUBLIC_FOLDERS:
        raise HTTPException(404, "Image not found")
    image = db.get(PublicImage, f"{folder}/{filename}")
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=86400"}
    if image:
        return Response(image.data, media_type=image.content_type, headers=headers)
    # Preserve existing uploads when a persistent disk is configured.
    base = (Path(settings.UPLOAD_DIR) / folder).resolve()
    path = (base / filename).resolve()
    if path.parent != base or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path, headers=headers)
