import time
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)
_denied: dict[str, float] = {}


def issue(user: User) -> str:
    s = get_settings()
    now = int(time.time())
    payload = {"sub": user.id, "role": user.role, "lang": user.language, "iat": now, "exp": now + s.jwt_expires_min * 60, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def revoke(token: str) -> None:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        _denied[claims["jti"]] = claims["exp"]
    except jwt.PyJWTError:
        pass


def api_error(status: int, code: str, message: str, **details) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, "details": details})


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise api_error(401, "UNAUTHENTICATED", "Please log in.")
    try:
        claims = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise api_error(401, "UNAUTHENTICATED", "Your session has expired. Please log in again.")
    if claims.get("jti") in _denied:
        raise api_error(401, "UNAUTHENTICATED", "You have logged out.")
    user = db.get(User, claims["sub"])
    if not user:
        raise api_error(401, "UNAUTHENTICATED", "Account not found.")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise api_error(403, "FORBIDDEN", "You don't have access to this.")
        return user
    return dep
