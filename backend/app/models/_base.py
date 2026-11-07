import os
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uuid7() -> str:
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms << 80) | (0x7 << 76) | ((rand >> 62) & 0xFFF) << 64 | (0b10 << 62) | (rand & ((1 << 62) - 1))
    return str(uuid.UUID(int=value))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid7().replace('-', '')}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def id_col(prefix: str) -> Mapped[str]:
    return mapped_column(String, primary_key=True, default=lambda: new_id(prefix))


def created_col() -> Mapped[str]:
    return mapped_column(String, default=now_iso)


__all__ = ["Base", "new_id", "now_iso", "id_col", "created_col"]
