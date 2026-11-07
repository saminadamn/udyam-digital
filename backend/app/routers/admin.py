"""Admin leads, calls and metrics (DESIGN.md D3.8, screens A2, A3)."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.admin import leads, metrics
from app.db import get_db
from app.models import User
from app.security.jwt import require_role

router = APIRouter(prefix="/admin", tags=["admin"])
staff = require_role("agent", "admin")


class CallIn(BaseModel):
    mode: Literal["twilio", "mock"] = "mock"


class OutcomeIn(BaseModel):
    outcome: str
    duration_s: int | None = Field(None, ge=0, le=6 * 3600)
    note: str | None = Field(None, max_length=2000)


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.get("/leads")
def list_leads(bucket: str | None = None, status: str | None = None, advisor_outcome: str | None = None, segment: str | None = None,
               source: str | None = None, origin: Literal["import", "app"] | None = None, not_contacted: bool = False,
               preset: Literal["not_closed", "hot_uncontacted"] | None = None, q: str | None = None, sort: str = "-propensity_score",
               page: int = 1, page_size: int = 50, _: User = Depends(staff), db: Session = Depends(get_db)):
    return leads.listing(db, sort=sort, page=page, page_size=page_size, bucket=bucket, status=status, advisor_outcome=advisor_outcome,
                         segment=segment, source=source, origin=origin, not_contacted=not_contacted, preset=preset, search=q)


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: str, user: User = Depends(staff), db: Session = Depends(get_db)):
    return leads.detail(db, user, lead_id)


@router.post("/leads/{lead_id}/call", status_code=201)
def call_lead(lead_id: str, body: CallIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    return leads.call(db, user, lead_id, body.mode)


@router.patch("/calls/{call_id}")
def call_outcome(call_id: str, body: OutcomeIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    return leads.set_outcome(db, user, call_id, body.outcome, body.duration_s, body.note)


@router.post("/leads/{lead_id}/notes", status_code=201)
def add_note(lead_id: str, body: NoteIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    return leads.add_note(db, user, lead_id, body.body)


@router.get("/metrics")
def get_metrics(from_: str | None = Query(None, alias="from"), to: str | None = None, segment: str | None = None,
                channel: Literal["self_serve", "assisted", "all"] = "all", _: User = Depends(staff), db: Session = Depends(get_db)):
    return metrics.metrics(db, from_, to, segment, channel)
