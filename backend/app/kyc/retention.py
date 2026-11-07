"""Document retention (DESIGN.md D2.8): delete document files and OCR text once a case's retention_until has passed
(90 days after verification, 30 days after an abandoned/withdrawn case), and mark the rows deleted. Cases still being worked on
(submitted or in human review) are never purged. Runs hourly with the API and from the command line:
    python -m app.kyc.retention"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.kyc import storage
from app.models import KycCase, KycDocument, now_iso
from app.security.crypto import decrypt

log = logging.getLogger("udyam.retention")
IN_PROGRESS = ("submitted", "review", "human_review")


def purge(db: Session, now: datetime | None = None) -> dict:
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    cases = db.scalars(select(KycCase).where(KycCase.retention_until.is_not(None), KycCase.retention_until < stamp,
                                             KycCase.status.not_in(IN_PROGRESS))).all()
    files = docs = 0
    for case in cases:
        for d in db.scalars(select(KycDocument).where(KycDocument.case_id == case.id, KycDocument.status != "deleted")):
            path = decrypt(d.storage_path_enc) if d.storage_path_enc else None
            if path and storage.delete(path):
                files += 1
            d.ocr_text_enc, d.extracted = None, "{}"  # the encrypted path stays as a record; the file itself is gone
            d.status, d.deleted_at = "deleted", now_iso()
            docs += 1
        folder = Path(get_settings().upload_dir) / case.id
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    db.commit()
    out = {"cases": len(cases), "documents": docs, "files_deleted": files}
    if docs:
        log.info("retention purge: %s", out)
    return out


def run_once() -> dict:
    from app.db import SessionLocal

    with SessionLocal() as db:
        return purge(db)


async def loop(interval: int) -> None:
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            log.exception("retention purge failed")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    print(run_once())
