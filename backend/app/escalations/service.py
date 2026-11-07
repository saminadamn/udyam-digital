"""Escalations: one place to create, assign and describe them (DESIGN.md D4.4)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Agent, Escalation, Order, now_iso

IST = timezone(timedelta(hours=5, minutes=30))
OPEN = ("open", "assigned", "in_progress")
CALLBACK_HOURS = {"P1": 2, "P2": 4, "P3": 24}
WORK_START, WORK_END = 9, 19


@lru_cache
def _strings() -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "i18n" / "tracker_messages.json").read_text(encoding="utf-8"))


def tr(lang: str, key: str, **kw) -> str:
    s = _strings()
    return (s.get(lang, {}).get(key) or s["en"][key]).format(**kw)


def fmt_date(d: date | str, lang: str) -> str:
    d = date.fromisoformat(d[:10]) if isinstance(d, str) else d
    return f"{d.day} {tr(lang, 'months').split(',')[d.month - 1]}"


def fmt_time(dt: datetime | str, lang: str) -> str:
    dt = (datetime.fromisoformat(dt) if isinstance(dt, str) else dt).astimezone(IST)
    if lang != "en":
        return dt.strftime("%H:%M")
    h = dt.hour % 12 or 12
    m = f":{dt.minute:02d}" if dt.minute else ""
    return f"{h}{m} {'am' if dt.hour < 12 else 'pm'}"


def open_counts(db: Session) -> dict[str, int]:
    return dict(db.execute(select(Escalation.assigned_agent_id, func.count()).where(Escalation.status.in_(OPEN))
                           .group_by(Escalation.assigned_agent_id)).all())


def assign_agent(db: Session, skill: str, lang: str | None) -> Agent | None:
    """Active agents with the skill and room under max_open; language match first, then fewest open cases, then longest since last assignment."""
    counts = open_counts(db)
    last = dict(db.execute(select(Escalation.assigned_agent_id, func.max(Escalation.assigned_at)).group_by(Escalation.assigned_agent_id)).all())
    pool = [a for a in db.scalars(select(Agent).where(Agent.active == 1)) if skill in json.loads(a.skills) and counts.get(a.id, 0) < a.max_open]
    if not pool:
        return None
    pool.sort(key=lambda a: (lang not in json.loads(a.languages), counts.get(a.id, 0), last.get(a.id) or ""))
    return pool[0]


def notify(db: Session, user_id: str, order_id: str | None, template: str, lang: str, payload: dict) -> None:
    """Kept for the Phase 4 call sites; the notification service renders, enforces opt-in and sends (D4.5)."""
    from app.notifications.service import notify as send

    send(db, user_id, order_id, template, lang, payload)


def first_name(agent: Agent | None) -> str | None:
    return agent.name.split()[0] if agent else None


def callback_due(start: datetime, hours: float) -> datetime:
    """Promise a call inside working hours (Mon-Sat 09:00-19:00 IST): time outside them doesn't count, then round up to 15 minutes."""
    t = start.astimezone(IST)
    def open_at(d: datetime) -> datetime:
        d = d.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        return d + timedelta(days=1) if d.weekday() == 6 else d

    if t.weekday() == 6 or t.hour >= WORK_END:
        t = open_at(t + timedelta(days=1))
    elif t.hour < WORK_START:
        t = open_at(t)
    left = timedelta(hours=hours)
    while True:
        close = t.replace(hour=WORK_END, minute=0, second=0, microsecond=0)
        if t + left <= close:
            t += left
            break
        left -= close - t
        t = open_at(t + timedelta(days=1))
    extra = (-t.minute) % 15
    t = (t + timedelta(minutes=extra)).replace(second=0, microsecond=0)
    return t.astimezone(timezone.utc)


def when_text(iso: str, lang: str, now: datetime | None = None) -> str:
    due = datetime.fromisoformat(iso).astimezone(IST)
    today = (now or datetime.now(timezone.utc)).astimezone(IST).date()
    return fmt_time(due, lang) if due.date() == today else f"{fmt_date(due.date(), lang)}, {fmt_time(due, lang)}"


def customer_message(db: Session, esc: Escalation, lang: str) -> str:
    agent = db.get(Agent, esc.assigned_agent_id) if esc.assigned_agent_id else None
    when = when_text(esc.sla_due_at, lang) if esc.sla_due_at else ""
    return tr(lang, "agent.call", name=first_name(agent), time=when) if agent else tr(lang, "agent.queue", time=when)


def summary(db: Session, esc: Escalation, lang: str) -> dict:
    agent = db.get(Agent, esc.assigned_agent_id) if esc.assigned_agent_id else None
    return {"id": esc.id, "escalation_id": esc.id, "trigger": esc.trigger, "priority": esc.priority, "status": esc.status,
            "agent_name": first_name(agent), "agent": {"name": first_name(agent), "languages": json.loads(agent.languages)} if agent else None,
            "sla_due_at": esc.sla_due_at, "message": customer_message(db, esc, lang)}


def open_for_order(db: Session, order_id: str, triggers: tuple[str, ...] | None = None) -> Escalation | None:
    q = select(Escalation).where(Escalation.order_id == order_id, Escalation.status.in_(OPEN))
    if triggers:
        q = q.where(Escalation.trigger.in_(triggers))
    return db.scalars(q.order_by(Escalation.created_at.desc())).first()


def create(db: Session, *, trigger: str, priority: str, skill: str, reason: str, lang: str | None, order: Order | None = None,
           kyc_case_id: str | None = None, conversation_id: str | None = None, lead_id: str | None = None, user_id: str | None = None,
           sla_hours: float | None = None, notify_customer: bool = True) -> Escalation:
    agent = assign_agent(db, skill, lang)
    due = callback_due(datetime.now(timezone.utc), sla_hours if sla_hours is not None else CALLBACK_HOURS.get(priority, 4))
    esc = Escalation(trigger=trigger, priority=priority, order_id=order.id if order else None, kyc_case_id=kyc_case_id,
                     conversation_id=conversation_id, lead_id=lead_id, reason=reason[:1000], required_skill=skill, language=lang,
                     sla_due_at=due.isoformat(timespec="seconds"), status="assigned" if agent else "open",
                     assigned_agent_id=agent.id if agent else None, assigned_at=now_iso() if agent else None)
    db.add(esc)
    db.flush()
    if agent and order:
        order.assigned_agent_id = agent.id
    uid = user_id or (order.user_id if order else None)
    if notify_customer and uid:
        notify(db, uid, order.id if order else None, "agent_assigned", lang or "en",
               {"agent": first_name(agent), "message": customer_message(db, esc, lang or "en"), "trigger": trigger})
    return esc
