import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(fernet_key(get_settings().app_encryption_key or get_settings().jwt_secret))


def fernet_key(secret: str) -> bytes:
    """A real Fernet key is used as is; any other secret (e.g. one a hosting dashboard generated) is stretched into one with SHA-256.
    Outside dev, config.check_secrets() requires APP_ENCRYPTION_KEY to be set and at least 32 characters."""
    try:
        Fernet(secret.encode())
        return secret.encode()
    except Exception:
        return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def encrypt(value: str | None) -> bytes | None:
    return None if value is None else _fernet().encrypt(value.encode())


def decrypt(token: bytes | None) -> str | None:
    return None if token is None else _fernet().decrypt(token).decode()


def pii_hash(value: str) -> str:
    return hmac.new(get_settings().pii_hash_key.encode(), value.encode(), hashlib.sha256).hexdigest()
