"""Notification service (DESIGN.md D1.1, D3.9, D4.5).

Every event writes an in-app row and a WhatsApp row. The WhatsApp row is `skipped_no_optin` unless the user opted in at login
(or later on the tracker). With the mock provider the row is "sent" straight away and the notifications table is the outbox the
demo shows (A6). With Twilio the row stays `queued` until the dispatcher sends it after the request's transaction commits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import Notification, Order, User, now_iso
from app.notifications import providers
from app.security.crypto import decrypt

log = logging.getLogger("udyam.notify")
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATES = ("quote_ready", "kyc_verified", "kyc_fix_needed", "kyc_review", "install_booked", "delay_escalated", "live",
             "kyc_reminder_24h", "agent_assigned", "advisor_link")
REQUIRED = {"install_booked": ("date", "slot"), "delay_escalated": ("message",), "agent_assigned": ("message",), "kyc_fix_needed": ("fix",)}
LINKS = {"quote_ready": "/order/{order_id}/consent", "kyc_reminder_24h.QUOTE_ACCEPTED": "/order/{order_id}/consent",
         "kyc_reminder_24h.CONSENT_GIVEN": "/order/{order_id}/kyc", "kyc_reminder_24h.KYC_FLAGGED": "/order/{order_id}/kyc",
         "kyc_fix_needed": "/order/{order_id}/kyc", "advisor_link": "/advisor"}
TWILIO_FINAL = {"delivered", "failed"}


@lru_cache
def _strings(lang: str) -> dict:
    f = TEMPLATE_DIR / f"{lang}.json"
    return json.loads((f if f.exists() else TEMPLATE_DIR / "en.json").read_text(encoding="utf-8"))


def template_key(template: str, params: dict, has_order: bool) -> str:
    if template == "kyc_reminder_24h":
        state = params.get("state") if params.get("state") in ("QUOTE_ACCEPTED", "CONSENT_GIVEN", "KYC_FLAGGED") else "CONSENT_GIVEN"
        return f"{template}.{state}"
    if not has_order and f"{template}.no_order" in _strings("en"):
        return f"{template}.no_order"
    return template


def _tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.।,:])", r"\1", s)
    s = re.sub(r"([.।])\s*[.।]", r"\1", s)
    return s.strip()


def link_for(key: str, order: Order | None) -> str:
    base = get_settings().public_app_url.rstrip("/")
    path = LINKS.get(key) or ("/order/{order_id}" if order else "/advisor")
    return base + path.format(order_id=order.id if order else "")


def render(template: str, lang: str, params: dict | None = None, order: Order | None = None) -> str:
    """The WhatsApp/in-app text for one event, in the user's language (falls back to English per key)."""
    if template not in TEMPLATES:
        raise ApiError(404, "TEMPLATE_NOT_FOUND", f"No template called {template}.")
    params = params or {}
    key = template_key(template, params, order is not None or bool(params.get("display_id")))
    own, en = _strings(lang), _strings("en")
    text = own.get(key) or en[key]
    v: dict = defaultdict(str, {k: ("" if val is None else val) for k, val in params.items()})
    v["display_id"] = params.get("display_id") or (order.display_id if order else "")
    v["link"] = link_for(key, order)
    if "monthly_total_inr" in params and "total" not in params:
        v["total"] = f"{int(params['monthly_total_inr']):,}"
    if template == "install_booked":
        v["slot"] = params.get("text") or f"{params.get('date', '')} {params.get('slot', '')}".strip()
    if template == "kyc_fix_needed" and not params.get("fix"):
        v["fix"] = params.get("note") or ""
    return _tidy((own.get("_prefix") or en["_prefix"]) + text.format_map(v))


def _payload(payload: dict, preview: str) -> str:
    return json.dumps({**payload, "preview": preview}, ensure_ascii=False)


def notify(db: Session, user_id: str, order_id: str | None, template: str, lang: str, payload: dict | None = None,
           whatsapp: bool = True, in_app: bool = True) -> Notification | None:
    """Record an event for the customer. Returns the WhatsApp row (or None if WhatsApp wasn't requested)."""
    payload = payload or {}
    user = db.get(User, user_id)
    order = db.get(Order, order_id) if order_id else None
    lang = lang or (user.language if user else "en")
    preview = render(template, lang, payload, order)
    body = _payload(payload, preview)
    if in_app:
        db.add(Notification(user_id=user_id, order_id=order_id, channel="in_app", template=template, language=lang, payload=body,
                            status="sent", sent_at=now_iso()))
    if not whatsapp:
        return None
    opted = bool(user and user.whatsapp_opt_in)
    wa = Notification(user_id=user_id, order_id=order_id, channel="whatsapp", template=template, language=lang, payload=body,
                      status="queued" if opted else "skipped_no_optin")
    db.add(wa)
    db.flush()
    provider = providers.get_provider()
    if opted and provider.name == "mock":
        deliver(db, wa, provider)
    return wa


def _callback() -> str | None:
    base = get_settings().public_api_url.rstrip("/")
    return f"{base}/api/v1/notifications/webhook/twilio" if base else None


def deliver(db: Session, ntf: Notification, provider=None) -> Notification:
    """Hand one queued WhatsApp row to the provider and record what happened. No retry loop: failed rows show in red with a Resend button."""
    provider = provider or providers.get_provider()
    user = db.get(User, ntf.user_id)
    phone = decrypt(user.phone_enc) if user else None
    if not phone:
        ntf.status, ntf.error = "failed", "no phone number on file"
        return ntf
    preview = json.loads(ntf.payload or "{}").get("preview") or render(ntf.template, ntf.language, json.loads(ntf.payload or "{}"),
                                                                       db.get(Order, ntf.order_id) if ntf.order_id else None)
    res = provider.send_whatsapp(phone, preview, _callback() if provider.name == "twilio" else None)
    ntf.provider_ref = res.ref or f"{provider.name}-failed"
    ntf.status = res.status if res.ok else "failed"
    ntf.error = res.error
    if res.ok:
        ntf.sent_at = now_iso()
    else:
        log.warning("whatsapp %s failed: %s", ntf.id, res.error)
    return ntf


def dispatch_pending(db: Session, limit: int = 25) -> int:
    """Send WhatsApp rows that are queued and haven't been handed to a provider yet (the Twilio path)."""
    rows = db.scalars(select(Notification).where(Notification.channel == "whatsapp", Notification.status == "queued",
                                                 Notification.provider_ref.is_(None)).order_by(Notification.created_at).limit(limit)).all()
    provider = providers.get_provider()
    for n in rows:
        deliver(db, n, provider)
    if rows:
        db.commit()
    return len(rows)


def run_dispatch_once() -> int:
    from app.db import SessionLocal

    with SessionLocal() as db:
        return dispatch_pending(db)


async def loop(interval: int) -> None:
    while True:
        try:
            await asyncio.to_thread(run_dispatch_once)
        except Exception:
            log.exception("notification dispatch failed")
        await asyncio.sleep(interval)


def send(db: Session, actor: User, user_id: str, order_id: str | None, template: str, language: str | None, params: dict) -> dict:
    """POST /notifications/whatsapp: a service or an admin (re)sends one WhatsApp message. Opt-in is still enforced."""
    if template not in TEMPLATES:
        raise ApiError(404, "TEMPLATE_NOT_FOUND", f"No template called {template}.")
    user = db.get(User, user_id)
    if not user:
        raise ApiError(404, "NOT_FOUND", "User not found.")
    order = db.get(Order, order_id) if order_id else None
    if order_id and (not order or order.user_id != user.id):
        raise ApiError(404, "NOT_FOUND", "Order not found for this user.")
    missing = [k for k in REQUIRED.get(template, ()) if not params.get(k) and not (template == "install_booked" and params.get("text"))]
    if missing:
        raise ApiError(422, "PARAMS_MISSING", "Some template values are missing.", {"missing": missing})
    wa = notify(db, user.id, order_id, template, language or user.language, params, in_app=False)
    db.commit()
    return {"notification_id": wa.id, "status": wa.status, "preview": json.loads(wa.payload)["preview"]}


def _row(n: Notification, staff: bool, users: dict[str, User], orders: dict[str, Order]) -> dict:
    payload = json.loads(n.payload or "{}")
    preview = payload.pop("preview", "")
    out = {"id": n.id, "channel": n.channel, "template": n.template, "language": n.language, "status": n.status, "preview": preview,
           "order_id": n.order_id, "display_id": orders[n.order_id].display_id if n.order_id in orders else payload.get("display_id"),
           "created_at": n.created_at, "sent_at": n.sent_at}
    if staff:
        u = users.get(n.user_id)
        out |= {"user_id": n.user_id, "to": u.phone_masked if u else None, "provider_ref": n.provider_ref, "error": n.error, "params": payload}
    return out


def listing(db: Session, user: User, scope: str | None, channel: str | None, status: str | None, order_id: str | None, limit: int) -> dict:
    staff = user.role in ("admin", "agent") and scope == "all"
    q = select(Notification)
    if not staff:
        q = q.where(Notification.user_id == user.id)
    if channel:
        q = q.where(Notification.channel.in_(channel.split(",")))
    if status:
        q = q.where(Notification.status.in_(status.split(",")))
    if order_id:
        q = q.where(Notification.order_id == order_id)
    rows = db.scalars(q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(min(max(limit, 1), 500))).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows})))} if staff else {}
    orders = {o.id: o for o in db.scalars(select(Order).where(Order.id.in_({r.order_id for r in rows if r.order_id})))}
    out = {"items": [_row(r, staff, users, orders) for r in rows]}
    if staff:
        out["provider"] = providers.status()
    return out


def webhook(db: Session, params: dict[str, str]) -> None:
    sid = params.get("MessageSid") or params.get("SmsSid")
    n = db.scalar(select(Notification).where(Notification.provider_ref == sid)) if sid else None
    if not n:
        return
    from app.notifications.providers.twilio import STATUS

    new = STATUS.get(params.get("MessageStatus") or params.get("SmsStatus") or "", n.status)
    if n.status in TWILIO_FINAL and new not in TWILIO_FINAL:
        return
    n.status = new
    if new == "failed":
        n.error = f"twilio {params.get('ErrorCode', '')}: {params.get('ErrorMessage', 'undelivered')}".strip()
    db.commit()
