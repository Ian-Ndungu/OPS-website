import asyncio
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401
from .config import settings
from .db import SessionLocal
from .routers import announcements, auth, clan, media, mythic, results
from .services import announcements as ann_svc
from .services import mythic as mythic_svc


async def _scheduler():
    """Every minute: publish due announcements. Daily-ish: overdue + reminders (idempotent enough
    for a single instance; use a real scheduler/cron in multi-instance deployments)."""
    last_daily = None
    while True:
        try:
            with SessionLocal() as db:
                ann_svc.publish_due(db)
                if last_daily != date.today():
                    mythic_svc.mark_overdue(db)
                    mythic_svc.send_reminders(db)
                    last_daily = date.today()
                db.commit()
        except Exception:
            pass
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_scheduler())
    yield
    task.cancel()


app = FastAPI(title="OPS Esports API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS.split(","), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
# Only public image folders are served; clan screenshots are admin-only via the API.
for sub in ("announcements", "match-screenshots"):
    os.makedirs(os.path.join(settings.UPLOAD_DIR, sub), exist_ok=True)
    # Public media routes read durable database uploads, with legacy disk fallback.

for r in (auth.router, clan.router, media.router, mythic.router, results.router, announcements.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "live_payments": settings.live_money_allowed}
