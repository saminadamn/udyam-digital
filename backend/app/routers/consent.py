from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.kyc import service
from app.models import User
from app.security.jwt import current_user

router = APIRouter(prefix="/consent", tags=["consent"])


class ConsentIn(BaseModel):
    purpose: str = service.PURPOSE
    order_id: str
    notice_version: str
    granted: bool
    language: str | None = None


@router.get("/notice")
def get_notice(purpose: str = service.PURPOSE, language: str = "en"):
    return service.notice(purpose, language)


@router.post("", status_code=201)
def give(body: ConsentIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.purpose != service.PURPOSE:
        from app.errors import ApiError

        raise ApiError(422, "BAD_PURPOSE", "Only KYC consent is taken here.")
    client = f"{request.client.host if request.client else ''}|{request.headers.get('user-agent', '')}"
    return service.give_consent(db, user, body.order_id, body.notice_version, body.granted, body.language, client)


@router.delete("/{consent_id}")
def withdraw(consent_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.withdraw(db, user, consent_id)
