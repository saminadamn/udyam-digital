from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.kyc import service
from app.models import User
from app.security import ratelimit
from app.security.jwt import current_user

router = APIRouter(prefix="/kyc", tags=["kyc"])


def _lookup_limit(user: User) -> None:
    """Registry lookups are capped so the mock GSTN/Udyam APIs can't be used to enumerate businesses."""
    s = get_settings()
    ratelimit.hit(f"lookup:{user.id}", s.lookup_rate_limit, s.lookup_rate_window_s, "Too many lookups. Please try again in a few minutes.")


@router.get("/gstin/{gstin}")
def gstin(gstin: str, order_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _lookup_limit(user)
    return service.gstin_lookup(db, user, gstin, order_id)


@router.get("/udyam/{num}")
def udyam(num: str, order_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _lookup_limit(user)
    return service.udyam_lookup(db, user, num, order_id)


@router.post("/upload", status_code=201)
async def upload(case_id: str = Form(...), doc_type: str = Form(...), language: str | None = Form(None), file: UploadFile = File(...),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit = get_settings().upload_max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if not data:
        raise ApiError(400, "EMPTY_FILE", "That file is empty.")
    return service.upload(db, user, case_id, doc_type, file.filename, data, language)


@router.post("/{case_id}/submit", status_code=202)
def submit(case_id: str, tasks: BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = service.submit(db, user, case_id)
    tasks.add_task(service.run_checks_task, case_id)
    return out


@router.get("/{case_id}/result")
def result(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.result(db, user, case_id)
