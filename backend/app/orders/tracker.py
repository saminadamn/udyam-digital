"""Customer tracker (DESIGN.md D3.4 GET /orders/{id}/tracker, screen C9)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.escalations import service as esc
from app.escalations.service import IST, fmt_date, tr
from app.models import Escalation, KycCase, Order, OrderEvent
from app.orders.fulfilment import install_days, slot_text

STEPS = ("KYC_VERIFIED", "INSTALL_BOOKED", "INSTALLED", "LIVE")
PRE = ("QUOTE_ACCEPTED", "CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_FLAGGED", "HUMAN_REVIEW")
FULFILMENT = ("KYC_VERIFIED", "INSTALL_BOOKED", "INSTALLED")
SHOWN = ("sla_breach", "user_request", "kyc_flag", "assisted_deal", "advisor_failed")


def _reached(db: Session, order: Order) -> dict[str, str]:
    out: dict[str, str] = {}
    for ev in db.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id)):
        out[ev.to_state] = ev.created_at
    return out


def visible_escalation(db: Session, order: Order) -> Escalation | None:
    rows = db.scalars(select(Escalation).where(Escalation.order_id == order.id, Escalation.status.in_(esc.OPEN))
                      .order_by(Escalation.created_at.desc())).all()
    rows = [e for e in rows if not (e.trigger == "kyc_flag" and e.priority == "P3")]
    return min(rows, key=lambda e: SHOWN.index(e.trigger)) if rows else None


def view(db: Session, order: Order, lang: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    reached = _reached(db, order)
    days = install_days(db, order)
    pos = STEPS.index(order.state) if order.state in STEPS else -1
    late = bool(order.state_due_at) and order.state in FULFILMENT and datetime.fromisoformat(order.state_due_at) < now
    steps = []
    for i, key in enumerate(STEPS):
        status = "done" if i < pos or (key == "LIVE" and pos == 3) else "current" if i == pos else "upcoming"
        at = reached.get(key) if status != "upcoming" else None
        expected, detail = None, None
        if key == "KYC_VERIFIED":
            detail = tr(lang, "detail.verified", date=fmt_date(datetime.fromisoformat(at).astimezone(IST).date(), lang)) if at else None
        elif key == "INSTALL_BOOKED":
            detail = slot_text(order, lang) if order.install_slot else None
        else:
            expected = order.expected_install_date if key == "INSTALLED" else order.expected_live_date
            when = "detail.installed" if key == "INSTALLED" else "detail.live"
            if status == "done" and at:
                detail = tr(lang, when, date=fmt_date(datetime.fromisoformat(at).astimezone(IST).date(), lang))
            elif expected:
                detail = tr(lang, "detail.expected", date=fmt_date(expected, lang))
            else:
                detail = tr(lang, "detail.after_verify", days=days + (1 if key == "LIVE" else 0))
        step = {"key": key, "label": tr(lang, f"step.{key}"), "status": status, "at": at, "expected": expected, "detail": detail,
                "late": late and (status == "current" or (order.state == "INSTALL_BOOKED" and key == "INSTALLED"))}
        steps.append(step)
    e = visible_escalation(db, order)
    breach = e is not None and e.trigger == "sla_breach"
    delayed = late or breach
    case = db.scalar(select(KycCase).where(KycCase.order_id == order.id))
    next_action = "consent" if order.state == "QUOTE_ACCEPTED" else "kyc" if order.state in ("CONSENT_GIVEN", "KYC_FLAGGED") else None
    return {"order_id": order.id, "display_id": order.display_id, "state": order.state, "headline": tr(lang, f"status.{order.state}"),
            "pre_verification": order.state in PRE, "steps": steps, "delayed": delayed,
            "delay_message": (tr(lang, "delay.install") if order.state in ("KYC_VERIFIED", "INSTALL_BOOKED") else tr(lang, "delay.other")) if delayed else None,
            "escalation": esc.summary(db, e, lang) if e else None, "install_days": days,
            "expected_install_date": order.expected_install_date, "expected_live_date": order.expected_live_date,
            "kyc_case_id": case.id if case else None, "next_action": next_action, "payment_status": order.payment_status,
            "as_of": now.isoformat(timespec="seconds")}
