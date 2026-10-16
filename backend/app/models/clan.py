from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base
from .core import utcnow


class ClanRequest(Base):
    __tablename__ = "clan_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    gamer_tag: Mapped[str] = mapped_column(String(64))
    player_id: Mapped[str] = mapped_column(String(80))
    game: Mapped[str] = mapped_column(String(80))
    clan_tag: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(255))
    contact: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    screenshot: Mapped[bytes] = mapped_column(LargeBinary)
    screenshot_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
