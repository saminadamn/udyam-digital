"""Notifications (DESIGN.md D3.9, screen A6 outbox)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import User
from app.notifications import service
from app.notifications.providers.twilio import valid_signature
from app.security.jwt import current_user, require_role

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SendIn(BaseModel):
    user_id: str
    order_id: str | None = None
    template: str
    language: str | None = None
    params: dict = Field(default_factory=dict)


@router.post("/whatsapp", status_code=202)
def send_whatsapp(body: SendIn, user: User = Depends(require_role("admin", "agent")), db: Session = Depends(get_db)):
    return service.send(db, user, body.user_id, body.order_id, body.template, body.language, body.params)


@router.get("")
def list_notifications(scope: str | None = None, channel: str | None = None, status: str | None = None, order_id: str | None = None,
                       limit: int = 100, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.listing(db, user, scope, channel, status, order_id, limit)


@router.post("/webhook/twilio", status_code=204)
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    params = {k: str(v) for k, v in (await request.form()).items()}
    s = get_settings()
    url = (s.public_api_url.rstrip("/") + request.url.path) if s.public_api_url else str(request.url)
    if not valid_signature(s.twilio_auth_token, url, params, request.headers.get("X-Twilio-Signature")):
        raise ApiError(403, "FORBIDDEN", "Bad signature.")
    service.webhook(db, params)
    return Response(status_code=204)
