from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.escalations import cases
from app.models import User
from app.security.jwt import current_user, require_role

router = APIRouter(prefix="/escalations", tags=["escalations"])
agents_router = APIRouter(prefix="/admin", tags=["admin"])


class PersonIn(BaseModel):
    order_id: str | None = None
    conversation_id: str | None = None
    reason: str | None = Field(None, max_length=300)
    preferred_time: str | None = Field(None, max_length=40)


class ActIn(BaseModel):
    action: Literal["assign", "start", "resolve", "reassign"]
    agent_id: str | None = None
    resolution: str | None = None
    note: str | None = Field(None, max_length=1000)


@router.post("", status_code=201)
def talk_to_person(body: PersonIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return cases.request_person(db, user, body.order_id, body.conversation_id, body.reason, body.preferred_time)


@router.get("")
def queue(status: str | None = None, mine: bool = False, trigger: str | None = None,
          user: User = Depends(require_role("agent", "admin")), db: Session = Depends(get_db)):
    return cases.queue(db, user, status, mine, trigger)


@router.get("/{escalation_id}")
def detail(escalation_id: str, user: User = Depends(require_role("agent", "admin")), db: Session = Depends(get_db)):
    return cases.detail(db, user, escalation_id)


@router.patch("/{escalation_id}")
def act(escalation_id: str, body: ActIn, user: User = Depends(require_role("agent", "admin")), db: Session = Depends(get_db)):
    return cases.act(db, user, escalation_id, body.action, body.agent_id, body.resolution, body.note)


@agents_router.get("/agents")
def agents(_: User = Depends(require_role("agent", "admin")), db: Session = Depends(get_db)):
    return cases.agents(db)
