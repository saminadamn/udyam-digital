from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import Product, User
from app.notifications.providers import status as messaging_status
from app.voice import status as voice_status
from app.security.jwt import require_role

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    s = get_settings()
    n = db.scalar(select(func.count()).select_from(Product))
    return {"status": "ok" if n else "degraded", "products": n,
            "providers": {"llm": s.llm_provider if s.llm_api_key or s.llm_provider == "template" else "template",
                          "otp": s.otp_mode, "ocr": s.ocr_engine, "messaging": messaging_status(), "voice": voice_status()}}


@router.post("/admin/seed")
def seed(_: User = Depends(require_role("admin"))):
    if get_settings().app_env not in ("dev", "demo"):
        raise ApiError(403, "FORBIDDEN", "Seeding is only allowed in dev or demo.")
    from app import seed as seeder
    from app.advisor.service import known_cities
    from app.rules.catalogue import cached_from_db

    out = seeder.run(verbose=False)
    cached_from_db.cache_clear()
    known_cities.cache_clear()
    return out
