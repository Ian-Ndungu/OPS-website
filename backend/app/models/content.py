from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .core import utcnow


# ------------------------------------------------------------- results
class Team(Base):
    """Minimal team table. In the existing OPS app, reuse your Team model."""
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    logo_url: Mapped[str | None] = mapped_column(String(255))


class Tournament(Base):
    __tablename__ = "tournaments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    game: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(16))  # battle_royale | multiplayer
    game_mode: Mapped[str | None] = mapped_column(String(64))  # e.g. Hardpoint, Classic BR
    starts_on: Mapped[date] = mapped_column(Date, index=True)
    event_status: Mapped[str] = mapped_column(String(16), default="upcoming")  # upcoming|completed
    # Publication workflow: draft -> review -> published -> archived
    pub_status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    mvp_player: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Match(Base):
    __tablename__ = "result_matches"
    __table_args__ = (UniqueConstraint("tournament_id", "match_no", name="uq_match_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)
    match_no: Mapped[int] = mapped_column(Integer)
    game_mode: Mapped[str | None] = mapped_column(String(64))
    team_a_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))  # multiplayer
    team_b_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    score_a: Mapped[int | None] = mapped_column(Integer)
    score_b: Mapped[int | None] = mapped_column(Integer)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    mvp_player: Mapped[str | None] = mapped_column(String(64))
    screenshot_path: Mapped[str | None] = mapped_column(String(255))


class MatchEntry(Base):
    """Battle Royale per-team result for one match."""
    __tablename__ = "result_match_entries"
    __table_args__ = (UniqueConstraint("match_id", "team_id", name="uq_entry_team"),
                      UniqueConstraint("match_id", "placement", name="uq_entry_placement"))
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("result_matches.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    placement: Mapped[int] = mapped_column(Integer)
    kills: Mapped[int] = mapped_column(Integer, default=0)
    placement_points: Mapped[int] = mapped_column(Integer, default=0)
    kill_points: Mapped[int] = mapped_column(Integer, default=0)


class ResultRevision(Base):
    __tablename__ = "result_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ------------------------------------------------------- announcements
class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(String(400))
    content_html: Mapped[str] = mapped_column(Text)  # sanitized on write
    image_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)  # draft|scheduled|published|archived
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Targeting: {"audience": "everyone|verified|divisions|mythic|cohorts", "divisions": [...], "cohort_ids": [...]}
    target: Mapped[dict] = mapped_column(JSON, default=lambda: {"audience": "everyone"})
    email_notify: Mapped[bool] = mapped_column(Boolean, default=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
