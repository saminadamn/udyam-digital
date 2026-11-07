"""Installation booking and expected dates (DESIGN.md D4.2). Booking happens automatically once KYC is verified."""
from __future__ import annotations

import zlib
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.escalations.service import IST, fmt_date, notify, tr
from app.models import Order, OrderEvent, Product, QuoteItem
from app.orders import state_machine

SLOTS = ("10:00-12:00", "12:00-14:00", "14:00-16:00", "16:00-18:00")


def install_days(db: Session, order: Order) -> int:
    d = db.scalar(select(func.max(Product.install_days)).join(QuoteItem, QuoteItem.product_id == Product.product_id)
                  .where(QuoteItem.quote_id == order.quote_id, QuoteItem.selected == 1))
    return int(d or 1)


def entered(db: Session, order: Order, state: str) -> datetime | None:
    at = db.scalar(select(OrderEvent.created_at).where(OrderEvent.order_id == order.id, OrderEvent.to_state == state)
                   .order_by(OrderEvent.id.desc()))
    return datetime.fromisoformat(at) if at else None


def slot_of(order: Order) -> tuple[date, str] | None:
    if not order.install_slot:
        return None
    d, s = order.install_slot.split("|")
    return date.fromisoformat(d), s


def slot_text(order: Order, lang: str) -> str | None:
    s = slot_of(order)
    if not s:
        return None
    d, window = s
    a, b = window.split("-")
    if lang == "en":
        ha, hb = int(a[:2]), int(b[:2])
        h12 = lambda h: str(h % 12 or 12)
        pa, pb = ("am" if ha < 12 else "pm"), ("am" if hb < 12 else "pm")
        part = f"{h12(ha)}-{h12(hb)} {pb}" if pa == pb else f"{h12(ha)} {pa}-{h12(hb)} {pb}"
    else:
        part = f"{a}-{b}"
    return tr(lang, "detail.visit", date=fmt_date(d, lang), slot=part)


def install_due(order: Order) -> datetime | None:
    """Late after the end of the visit window on the expected install date, plus 24 hours (D4.3)."""
    s = slot_of(order)
    if not s:
        return None
    d, window = s
    end = datetime.combine(d, time(int(window.split("-")[1][:2])), IST)
    return end + timedelta(hours=24)


def book(db: Session, order: Order, actor: str, on: date | None = None, slot: str | None = None, note: str | None = None) -> None:
    verified = entered(db, order, "KYC_VERIFIED") or datetime.now(IST)
    d = on or (verified.astimezone(IST).date() + timedelta(days=install_days(db, order)))
    if d.weekday() == 6:
        d += timedelta(days=1)
    slot = slot or SLOTS[zlib.crc32(order.id.encode()) % len(SLOTS)]
    order.install_slot = f"{d.isoformat()}|{slot}"
    order.expected_install_date = d.isoformat()
    order.expected_live_date = (d + timedelta(days=1)).isoformat()
    state_machine.transition(db, order, "INSTALL_BOOKED", actor, note or f"technician visit {d.isoformat()} {slot}")
    due = install_due(order)
    order.state_due_at = due.isoformat(timespec="seconds") if due else None
    lang = _lang(db, order)
    notify(db, order.user_id, order.id, "install_booked", lang, {"date": d.isoformat(), "slot": slot, "text": slot_text(order, lang)})


def on_verified(db: Session, order: Order, actor: str = "system:fulfilment") -> None:
    if order.state == "KYC_VERIFIED":
        book(db, order, actor)


def _lang(db: Session, order: Order) -> str:
    from app.models import User

    u = db.get(User, order.user_id)
    return u.language if u else "en"
