"""Demo simulator (DESIGN.md D3.4 POST /admin/orders/{id}/advance, screen A7). Moves orders and makes them late on cue."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.errors import ApiError
from app.escalations.service import IST
from app.models import Order, now_iso
from app.orders import fulfilment, state_machine


def make_late(db: Session, order: Order, hours: float) -> None:
    """Push the current state's deadline `hours` into the past so the SLA job sees a breach on its next scan."""
    now = datetime.now(timezone.utc)
    due = now - timedelta(hours=hours)
    if order.state == "INSTALL_BOOKED" and order.install_slot:
        _, window = fulfilment.slot_of(order)
        visit = (due - timedelta(hours=24)).astimezone(IST).date()
        order.install_slot = f"{visit.isoformat()}|{window}"
        order.expected_install_date = visit.isoformat()
        order.expected_live_date = (visit + timedelta(days=1)).isoformat()
        entered = datetime.fromisoformat(order.state_entered_at)
        order.state_entered_at = min(entered, due - timedelta(hours=24 * (fulfilment.install_days(db, order) + 1))).isoformat(timespec="seconds")
    else:
        sla = state_machine.SLA_HOURS.get(order.state)
        if sla is None:
            raise ApiError(409, "NO_DEADLINE", f"Orders in {order.state} have no deadline to miss.")
        order.state_entered_at = (due - timedelta(hours=sla)).isoformat(timespec="seconds")
    order.state_due_at = due.isoformat(timespec="seconds")
    order.updated_at = now_iso()


def advance(db: Session, order: Order, to_state: str | None, delay_hours: float = 0, actor: str = "simulator", auto_book: bool = True) -> dict:
    if to_state:
        if to_state == "INSTALL_BOOKED" and order.state in ("KYC_VERIFIED", "INSTALL_BOOKED"):
            rebook = order.state == "INSTALL_BOOKED"
            on = (datetime.now(IST).date() + timedelta(days=1)) if rebook else None
            fulfilment.book(db, order, actor, on=on, note="rebooked by simulator" if rebook else None)
        else:
            if to_state == "LIVE" and order.payment_status != "paid":
                order.payment_status = "paid"
            state_machine.transition(db, order, to_state, actor, "simulator")
            if to_state == "KYC_VERIFIED" and auto_book:
                fulfilment.on_verified(db, order, actor)
    if delay_hours and delay_hours > 0:
        make_late(db, order, delay_hours)
    db.commit()
    return {"order_id": order.id, "display_id": order.display_id, "state": order.state, "state_due_at": order.state_due_at,
            "expected_install_date": order.expected_install_date, "expected_live_date": order.expected_live_date,
            "allowed_next": sorted(state_machine.TRANSITIONS.get(order.state, set()))}
