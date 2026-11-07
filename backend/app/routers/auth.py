import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import Business, Consent, OtpRequest, User, now_iso
from app.security import jwt as jwtsec
from app.security import ratelimit
from app.security.crypto import encrypt, pii_hash
from app.security.masking import mask_phone

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["auth"])
PHONE_RE = re.compile(r"^(?:\+91|91|0)?([6-9]\d{9})$")
_pending_phone: dict[str, str] = {}


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=16)


class OtpVerifyIn(BaseModel):
    request_id: str
    code: str = Field(min_length=6, max_length=6)
    language: str = "hi"
    whatsapp_opt_in: bool | None = None   # None: keep what the user chose before (a re-login doesn't withdraw consent)


class MePatch(BaseModel):
    language: str | None = None
    whatsapp_opt_in: bool | None = None


def _phone(raw: str) -> str:
    m = PHONE_RE.match(re.sub(r"[\s-]", "", raw))
    if not m:
        raise ApiError(400, "PHONE_INVALID", "Please enter a valid 10-digit mobile number.", {"field": "phone"})
    return "+91" + m.group(1)


def _code_hash(request_id: str, code: str) -> str:
    return hashlib.sha256(f"{request_id}:{code}:{get_settings().jwt_secret}".encode()).hexdigest()


def user_out(u: User) -> dict:
    return {"id": u.id, "role": u.role, "language": u.language, "phone_masked": u.phone_masked, "whatsapp_opt_in": bool(u.whatsapp_opt_in)}


def _set_whatsapp(db: Session, u: User, on: bool) -> None:
    if bool(u.whatsapp_opt_in) == on:
        return
    u.whatsapp_opt_in = 1 if on else 0
    if on:
        db.add(Consent(user_id=u.id, purpose="whatsapp_updates", notice_version="wa-v1.0", language=u.language, granted=1, granted_at=now_iso()))
    else:
        for c in db.scalars(select(Consent).where(Consent.user_id == u.id, Consent.purpose == "whatsapp_updates", Consent.withdrawn_at.is_(None))):
            c.withdrawn_at = now_iso()


@router.post("/otp/request")
def otp_request(body: OtpRequestIn, request: Request, db: Session = Depends(get_db)):
    st = get_settings()
    ratelimit.hit(f"otp-ip:{ratelimit.client_ip(request)}", st.otp_ip_rate_limit, 600, "Too many codes requested. Try again in 10 minutes.")
    phone = _phone(body.phone)
    h = pii_hash(phone)
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec="seconds")
    recent = db.scalar(select(func.count()).select_from(OtpRequest).where(OtpRequest.phone_hash == h, OtpRequest.created_at >= since))
    if recent >= 3:
        raise ApiError(429, "RATE_LIMITED", "Too many codes requested. Try again in 10 minutes.")
    code = f"{secrets.randbelow(10**6):06d}"
    req = OtpRequest(phone_hash=h, code_hash="", expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"))
    db.add(req)
    db.flush()
    req.code_hash = _code_hash(req.id, code)
    db.commit()
    _pending_phone[req.id] = phone
    out = {"request_id": req.id, "expires_in": 300}
    if get_settings().otp_mode == "mock":
        out["dev_code"] = code
    return out


@router.post("/otp/verify")
def otp_verify(body: OtpVerifyIn, request: Request, db: Session = Depends(get_db)):
    req = db.get(OtpRequest, body.request_id)
    if not req or req.consumed_at:
        raise ApiError(400, "OTP_INVALID", "That code is not valid. Please request a new one.")
    if req.expires_at < now_iso():
        raise ApiError(410, "OTP_EXPIRED", "That code has expired. Please request a new one.")
    if req.attempts >= 5:
        raise ApiError(429, "OTP_TOO_MANY_ATTEMPTS", "Too many wrong attempts. Please request a new code.")
    if not secrets.compare_digest(req.code_hash, _code_hash(req.id, body.code)):
        req.attempts += 1
        db.commit()
        raise ApiError(400, "OTP_INVALID", "That code is not right.", {"attempts_left": max(0, 5 - req.attempts)})
    req.consumed_at = now_iso()
    user = db.scalar(select(User).where(User.phone_hash == req.phone_hash))
    phone = _pending_phone.pop(req.id, None)
    if not user:
        if not phone:
            raise ApiError(400, "OTP_INVALID", "Please request a new code.")
        user = User(phone_enc=encrypt(phone), phone_hash=req.phone_hash, phone_masked=mask_phone(phone), role="customer", language=body.language)
        db.add(user)
        db.flush()
    if body.language in get_settings().langs:
        user.language = body.language
    user.last_login_at = now_iso()
    if body.whatsapp_opt_in is not None:
        _set_whatsapp(db, user, body.whatsapp_opt_in)
    db.commit()
    return {"token": jwtsec.issue(user), "user": user_out(user)}


@router.post("/logout", status_code=204)
def logout(request: Request, _: User = Depends(jwtsec.current_user)):
    auth = request.headers.get("authorization", "")
    jwtsec.revoke(auth.removeprefix("Bearer ").strip())


@me_router.get("/me")
def me(user: User = Depends(jwtsec.current_user), db: Session = Depends(get_db)):
    biz = db.scalar(select(Business).where(Business.user_id == user.id).order_by(Business.created_at.desc()))
    return {"user": user_out(user), "business": None if not biz else {"id": biz.id, "name": biz.name, "segment": biz.segment, "gstin_masked": biz.gstin_masked}}


@me_router.patch("/me")
def patch_me(body: MePatch, user: User = Depends(jwtsec.current_user), db: Session = Depends(get_db)):
    if body.language is not None:
        if body.language not in get_settings().langs:
            raise ApiError(400, "VALIDATION_ERROR", "Unsupported language.", {"field": "language"})
        user.language = body.language
    if body.whatsapp_opt_in is not None:
        _set_whatsapp(db, user, body.whatsapp_opt_in)
    db.commit()
    return me(user, db)
