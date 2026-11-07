"""SLA scan (DESIGN.md D4.3). Finds orders whose current state is past its due time and acts once per breach."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.escalations import service as esc
from app.models import Escalation, Notification, Order, User
from app.orders import state_machine

log = logging.getLogger("udyam.sla")
KYC_STATES = {"QUOTE_ACCEPTED", "CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_FLAGGED", "HUMAN_REVIEW"}
ESCALATE = {"CONSENT_GIVEN": ("P3", "kyc"), "KYC_SUBMITTED": ("P1", "kyc"), "KYC_FLAGGED": ("P3", "kyc"), "HUMAN_REVIEW": ("P1", "kyc"),
            "KYC_VERIFIED": ("P2", "install"), "INSTALL_BOOKED": ("P1", "install"), "INSTALLED": ("P2", "install")}
REMIND_FIRST = {"QUOTE_ACCEPTED": 24 * 7, "CONSENT_GIVEN": 72, "KYC_FLAGGED": 48}
REASON = {"CONSENT_GIVEN": "No documents uploaded 72 h after consent; offer help",
          "KYC_SUBMITTED": "KYC checks stuck for over an hour",
          "KYC_FLAGGED": "Customer hasn't fixed flagged documents in 48 h",
          "HUMAN_REVIEW": "KYC review not picked up within 4 h",
          "KYC_VERIFIED": "Verified 24 h ago but no installation slot booked",
          "INSTALL_BOOKED": "Installation overdue. {slot}",
          "INSTALLED": "Installed 48 h ago but service not live"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _late_hours(order: Order, now: datetime) -> float:
    return round((now - datetime.fromisoformat(order.state_due_at)).total_seconds() / 3600, 1)


def _reminded(db: Session, order: Order) -> bool:
    return db.scalar(select(Notification.id).where(Notification.order_id == order.id, Notification.template == "kyc_reminder_24h",
                                                   Notification.created_at >= order.state_entered_at)) is not None


def handle(db: Session, order: Order, now: datetime) -> dict | None:
    user = db.get(User, order.user_id)
    lang = user.language if user else "en"
    st = order.state
    if st in REMIND_FIRST and not _reminded(db, order):
        esc.notify(db, order.user_id, order.id, "kyc_reminder_24h", lang, {"display_id": order.display_id, "state": st})
        order.state_due_at = (datetime.fromisoformat(order.state_entered_at) + timedelta(hours=REMIND_FIRST[st])).isoformat(timespec="seconds")
        if datetime.fromisoformat(order.state_due_at) > now:
            return {"order_id": order.id, "state": st, "action": "reminder"}
    if st == "QUOTE_ACCEPTED":
        state_machine.transition(db, order, "CANCELLED", "system:sla", "quote expired after 7 days without consent")
        return {"order_id": order.id, "state": st, "action": "cancelled"}
    if st not in ESCALATE:
        return None
    if esc.open_for_order(db, order.id, ("sla_breach",)):
        return None
    existing = esc.open_for_order(db, order.id, ("kyc_flag",)) if st in KYC_STATES else None
    if existing:
        if st == "HUMAN_REVIEW" and existing.priority != "P1":
            existing.priority = "P1"
            return {"order_id": order.id, "state": st, "action": "raised_priority", "escalation_id": existing.id}
        return None
    prio, skill = ESCALATE[st]
    from app.orders.fulfilment import slot_text

    reason = REASON[st].format(slot=slot_text(order, "en") or order.expected_install_date) + f". Late by {_late_hours(order, now):g} h"
    fulfilment_late = st in ("INSTALL_BOOKED", "INSTALLED", "KYC_VERIFIED")
    e = esc.create(db, trigger="sla_breach", priority=prio, skill=skill, reason=reason, lang=lang, order=order)
    if fulfilment_late:
        esc.notify(db, order.user_id, order.id, "delay_escalated", lang, {"message": esc.customer_message(db, e, lang)})
    log.info("sla_breach %s state=%s escalation=%s agent=%s", order.display_id, st, e.id, e.assigned_agent_id)
    return {"order_id": order.id, "display_id": order.display_id, "state": st, "action": "escalated", "escalation_id": e.id,
            "priority": prio, "agent_id": e.assigned_agent_id}


def scan(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or _now()
    stamp = now.isoformat(timespec="seconds")
    orders = db.scalars(select(Order).where(Order.state_due_at.is_not(None), Order.state_due_at < stamp,
                                            Order.state.not_in(("LIVE", "CANCELLED")))).all()
    out = [r for o in orders if (r := handle(db, o, now))]
    db.commit()
    return out


def breached(db: Session, now: datetime | None = None) -> list[Escalation]:
    stamp = (now or _now()).isoformat(timespec="seconds")
    return db.scalars(select(Escalation).where(Escalation.status.in_(esc.OPEN), Escalation.sla_due_at < stamp)).all()


def run_once() -> list[dict]:
    from app.db import SessionLocal

    with SessionLocal() as db:
        return scan(db)


async def loop(interval: int) -> None:
    while True:
        try:
            done = await asyncio.to_thread(run_once)
            if done:
                log.info("sla scan: %s", done)
        except Exception:
            log.exception("sla scan failed")
        await asyncio.sleep(interval)
