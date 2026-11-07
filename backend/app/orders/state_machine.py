"""Order state machine (DESIGN.md D4.1, SLA windows from D4.3)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Order, OrderEvent, now_iso

TRANSITIONS: dict[str | None, set[str]] = {
    None: {"QUOTE_ACCEPTED"},
    "QUOTE_ACCEPTED": {"CONSENT_GIVEN", "CANCELLED"},
    "CONSENT_GIVEN": {"KYC_SUBMITTED", "CANCELLED"},
    "KYC_SUBMITTED": {"KYC_VERIFIED", "KYC_FLAGGED"},
    "KYC_FLAGGED": {"KYC_SUBMITTED", "HUMAN_REVIEW", "QUOTE_ACCEPTED", "CANCELLED"},
    "HUMAN_REVIEW": {"KYC_VERIFIED", "KYC_FLAGGED", "CANCELLED"},
    "KYC_VERIFIED": {"INSTALL_BOOKED"},
    "INSTALL_BOOKED": {"INSTALL_BOOKED", "INSTALLED"},
    "INSTALLED": {"LIVE"},
    "LIVE": set(),
    "CANCELLED": set(),
}
SLA_HOURS = {"QUOTE_ACCEPTED": 24, "CONSENT_GIVEN": 24, "KYC_SUBMITTED": 1, "KYC_FLAGGED": 24, "HUMAN_REVIEW": 4,
             "KYC_VERIFIED": 24, "INSTALLED": 48}
"""First 'late after' per state. INSTALL_BOOKED is set by fulfilment.book from the visit date. QUOTE_ACCEPTED, CONSENT_GIVEN
and KYC_FLAGGED get a reminder at this point and a second deadline after it (see escalations/sla.py)."""


def due_at(state: str, entered: datetime) -> str | None:
    h = SLA_HOURS.get(state)
    return (entered + timedelta(hours=h)).isoformat(timespec="seconds") if h else None


def transition(db: Session, order: Order, to_state: str, actor: str, note: str | None = None) -> OrderEvent:
    current = order.state if order.state else None
    if to_state not in TRANSITIONS.get(current, set()):
        raise ApiError(409, "INVALID_TRANSITION", f"An order can't move from {current} to {to_state}.",
                       {"from": current, "allowed": sorted(TRANSITIONS.get(current, set()))})
    now = datetime.now(timezone.utc)
    order.state = to_state
    order.state_entered_at = now.isoformat(timespec="seconds")
    order.state_due_at = due_at(to_state, now)
    order.updated_at = now_iso()
    ev = OrderEvent(order_id=order.id, from_state=current, to_state=to_state, actor=actor, note=note)
    db.add(ev)
    _after(db, order, to_state)
    return ev


def _after(db: Session, order: Order, to_state: str) -> None:
    """Side effects every transition shares: the lead row follows the order (for the admin dashboard and metrics), and going
    live tells the customer. Other states' messages carry details only their own service knows (slot, fix, agent)."""
    from app.admin.lead_sync import on_order_state

    on_order_state(db, order, to_state)
    if to_state == "LIVE":
        from app.notifications.service import notify
        from app.models import User

        u = db.get(User, order.user_id)
        notify(db, order.user_id, order.id, "live", u.language if u else "en", {"display_id": order.display_id})


def create(db: Session, order: Order, actor: str, note: str | None = None) -> OrderEvent:
    """Place a new order in its first state, QUOTE_ACCEPTED, and log the event."""
    now = datetime.now(timezone.utc)
    order.state = "QUOTE_ACCEPTED"
    order.state_entered_at = now.isoformat(timespec="seconds")
    order.state_due_at = due_at("QUOTE_ACCEPTED", now)
    db.add(order)
    db.flush()
    ev = OrderEvent(order_id=order.id, from_state=None, to_state="QUOTE_ACCEPTED", actor=actor, note=note)
    db.add(ev)
    return ev
