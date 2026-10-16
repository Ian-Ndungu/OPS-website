from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.clan import ClanRequest
from ..models.core import Role, User, utcnow
from ..security import require_roles

router = APIRouter(prefix="/api/clan", tags=["clan"])
reviewer = require_roles(Role.clan_verifier)
MAX_IMAGE = 5 * 1024 * 1024


@router.post("/requests", status_code=201)
async def apply(gamer_tag: str = Form(..., min_length=2, max_length=64),
                player_id: str = Form(..., min_length=1, max_length=80),
                game: str = Form(..., min_length=2, max_length=80),
                clan_tag: str = Form(..., min_length=1, max_length=32),
                email: EmailStr = Form(...), contact: str = Form(..., min_length=3, max_length=100),
                message: str = Form(..., min_length=20, max_length=3000),
                name_updated: bool = Form(...), screenshot: UploadFile = File(...),
                db: Session = Depends(get_db)):
    fields = dict(gamer_tag=gamer_tag, player_id=player_id, game=game, clan_tag=clan_tag,
                  email=str(email).lower(), contact=contact, message=message)
    fields = {k: v.strip() for k, v in fields.items()}
    if not name_updated or any(not v for v in fields.values()) or len(fields["message"]) < 20:
        raise HTTPException(422, "Complete all fields and confirm your profile name includes the clan tag.")
    if fields["clan_tag"].casefold() not in fields["gamer_tag"].casefold():
        raise HTTPException(422, "Your updated in-game name must include the clan tag.")
    data = await screenshot.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "Screenshot must be 5 MB or smaller.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise HTTPException(422, "Upload a PNG, JPEG, or WebP screenshot.")
    row = ClanRequest(**fields, screenshot=data, screenshot_type=mime)
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/admin/requests")
def requests(status: Literal["pending", "approved", "rejected", "all"] = "pending",
             _: User = Depends(reviewer), db: Session = Depends(get_db)):
    query = select(ClanRequest).order_by(ClanRequest.created_at.desc())
    if status != "all":
        query = query.where(ClanRequest.status == status)
    return [{k: getattr(r, k) for k in ("id", "gamer_tag", "player_id", "game", "clan_tag", "email",
             "contact", "message", "status", "review_note", "created_at", "reviewed_at")}
            for r in db.scalars(query).all()]


@router.get("/admin/requests/{request_id}/screenshot")
def image(request_id: int, _: User = Depends(reviewer), db: Session = Depends(get_db)):
    row = db.get(ClanRequest, request_id)
    if not row:
        raise HTTPException(404, "Request not found")
    return Response(row.screenshot, media_type=row.screenshot_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class Review(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)


@router.post("/admin/requests/{request_id}/review")
def review(request_id: int, body: Review, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    row = db.scalar(select(ClanRequest).where(ClanRequest.id == request_id).with_for_update())
    if not row:
        raise HTTPException(404, "Request not found")
    if row.status != "pending":
        raise HTTPException(409, "This request has already been reviewed")
    row.status, row.review_note = body.status, body.note.strip()
    row.reviewed_by, row.reviewed_at = user.id, utcnow()
    db.commit()
    return {"id": row.id, "status": row.status}
