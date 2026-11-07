from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.escalations import sla
from app.escalations.cases import biz_label
from app.escalations.service import open_for_order, summary
from app.models import Business, Order, OrderEvent, User
from app.orders import simulator, state_machine
from app.security.jwt import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


class AdvanceIn(BaseModel):
    to_state: str | None = None
    delay_hours: float = Field(0, ge=0, le=24 * 30)
    auto_book: bool = True


def _order(db: Session, order_id: str) -> Order:
    o = db.get(Order, order_id) or db.scalar(select(Order).where(Order.display_id == order_id))
    if not o:
        raise ApiError(404, "NOT_FOUND", "Order not found.")
    return o


@router.get("/orders")
def orders(_: User = Depends(require_role("admin", "agent")), db: Session = Depends(get_db)):
    out = []
    for o in db.scalars(select(Order).order_by(Order.created_at.desc()).limit(100)):
        biz = db.get(Business, o.business_id)
        e = open_for_order(db, o.id)
        out.append({"order_id": o.id, "display_id": o.display_id, "state": o.state, "business": biz_label(biz),
                    "segment": biz.segment if biz else None, "state_due_at": o.state_due_at, "expected_install_date": o.expected_install_date,
                    "allowed_next": sorted(state_machine.TRANSITIONS.get(o.state, set())),
                    "escalation": summary(db, e, "en") if e else None})
    return {"orders": out}


@router.get("/orders/{order_id}/events")
def events(order_id: str, _: User = Depends(require_role("admin", "agent")), db: Session = Depends(get_db)):
    o = _order(db, order_id)
    rows = db.scalars(select(OrderEvent).where(OrderEvent.order_id == o.id).order_by(OrderEvent.id)).all()
    return {"events": [{"from": e.from_state, "to": e.to_state, "actor": e.actor, "note": e.note, "at": e.created_at} for e in rows]}


@router.post("/orders/{order_id}/advance")
def advance(order_id: str, body: AdvanceIn, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if not body.to_state and not body.delay_hours:
        raise ApiError(422, "VALIDATION_ERROR", "Give a state to move to, a delay, or both.")
    return simulator.advance(db, _order(db, order_id), body.to_state, body.delay_hours, f"simulator:{user.id}", body.auto_book)


@router.post("/sla/scan")
def scan(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {"actions": sla.scan(db)}
