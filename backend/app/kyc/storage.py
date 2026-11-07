"""Encrypted document storage. Files are Fernet-encrypted on disk; the DB keeps only the encrypted path and a sha256."""
import hashlib
import uuid
from pathlib import Path

from app.config import get_settings
from app.security.crypto import _fernet

MIME = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"%PDF": "application/pdf"}


def sniff(data: bytes) -> str | None:
    return next((m for sig, m in MIME.items() if data.startswith(sig)), None)


def save(case_id: str, data: bytes) -> tuple[str, str]:
    root = Path(get_settings().upload_dir) / case_id
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4().hex}.bin"
    path.write_bytes(_fernet().encrypt(data))
    return str(path), hashlib.sha256(data).hexdigest()


def load(path: str) -> bytes:
    return _fernet().decrypt(Path(path).read_bytes())


def delete(path: str) -> bool:
    p = Path(path)
    if p.exists():
        p.unlink()
        return True
    return False
