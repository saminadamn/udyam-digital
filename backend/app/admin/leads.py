"""Admin leads (DESIGN.md D3.8, screens A2/A3): the 5,000 imported leads plus every app lead, one table, sorted by propensity.

Personal data stays masked: contact names become "First L.", phones "••••••4321", GSTIN/Udyam the D2 masked forms."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.admin import lead_sync
from app.config import get_settings
from app.errors import ApiError
from app.escalations.cases import _chat, biz_label
from app.models import (Agent, AuditLog, Business, CallLog, Conversation, Lead, LeadNote, Order, Quote, QuoteItem, User, now_iso)
from app.notifications import providers
from app.notifications.service import notify
from app.rules.catalogue import cached_from_db
from app.security.crypto import decrypt
from app.security.masking import mask_gstin, mask_udyam, scrub

OUTCOMES = ("connected", "no_answer", "callback_requested", "interested", "converted", "not_interested")
NOT_CLOSED = ("abandoned", "escalated")
SORTS = {"propensity_score": Lead.propensity_score, "created_date": Lead.created_date, "last_contacted_at": Lead.last_contacted_at,
         "lead_id": Lead.lead_id}


def mask_name(name: str | None) -> str | None:
    if not name:
        return None
    parts = name.split()
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


def bucket_conversion(db: Session) -> dict[str, float]:
    """How often each bucket converted in the imported history, computed live (A2 badge: "converts ~15.9%")."""
    rows = db.execute(select(Lead.propensity_bucket, func.count(), func.sum(case((Lead.outcome == "Activated", 1), else_=0)))
                      .where(Lead.origin == "import", Lead.propensity_bucket.is_not(None)).group_by(Lead.propensity_bucket)).all()
    return {b: round(100 * (a or 0) / n, 1) for b, n, a in rows if n}


def _conv(db: Session, lead: Lead) -> Conversation | None:
    if lead.origin != "app":
        return None
    return db.scalars(select(Conversation).where(Conversation.lead_id == lead.lead_id).order_by(Conversation.created_at.desc())).first()


def _app_user(db: Session, lead: Lead) -> User | None:
    c = _conv(db, lead)
    return db.get(User, c.user_id) if c else None


def refresh(db: Session) -> None:
    """Before showing the table: mark stalled app leads as abandoned and score any app lead that has a segment but no score."""
    lead_sync.sweep_abandoned(db, get_settings().advisor_abandon_minutes)
    for lead in db.scalars(select(Lead).where(Lead.origin == "app", Lead.segment.is_not(None), Lead.propensity_score.is_(None))):
        lead_sync.score(lead)
    db.commit()


def _propensity(lead: Lead, conv_pct: dict[str, float]) -> dict | None:
    if lead.propensity_bucket is None:
        return None
    return {"score": lead.propensity_score, "bucket": lead.propensity_bucket, "bucket_conversion_pct": conv_pct.get(lead.propensity_bucket),
            "reasons": json.loads(lead.propensity_reasons or "[]")}


def _last_call(db: Session, lead_id: str) -> CallLog | None:
    return db.scalars(select(CallLog).where(CallLog.lead_id == lead_id).order_by(CallLog.created_at.desc())).first()


def _agent_name(db: Session, agent_id: str | None) -> str | None:
    a = db.get(Agent, agent_id) if agent_id else None
    return a.name.split()[0] if a else None


KIND = {"Micro retail & services": "Shop", "Professional offices": "Office", "Small multi-site businesses": "Chain", "Small manufacturers": "Factory"}


def _app_label(lead: Lead) -> str:
    kind = KIND.get(lead.segment or "", "New lead")
    return f"{kind} in {lead.city}" if lead.city else f"{kind} (still in the advisor)"


def _item(db: Session, lead: Lead, conv_pct: dict[str, float]) -> dict:
    user = _app_user(db, lead) if lead.origin == "app" else None
    biz = db.get(Business, lead.business_id) if lead.business_id else None
    call = _last_call(db, lead.lead_id)
    return {"lead_id": lead.lead_id, "origin": lead.origin,
            "business_name": lead.business_name or biz_label(biz) or _app_label(lead),
            "contact": mask_name(lead.contact_name) or (user.phone_masked if user else None),
            "segment": lead.segment, "city": lead.city, "lead_source": lead.lead_source, "created_date": lead.created_date,
            "stage_reached": lead.stage_reached or "Lead", "outcome": lead.outcome, "drop_reason": lead.drop_reason,
            "advisor_outcome": lead.advisor_outcome, "lead_status": lead.lead_status, "propensity": _propensity(lead, conv_pct),
            "last_contacted_at": lead.last_contacted_at,
            "last_call": {"call_id": call.id, "outcome": call.outcome, "at": call.created_at, "agent": _agent_name(db, call.agent_id)} if call else None}


def _filters(q, *, bucket=None, status=None, advisor_outcome=None, segment=None, source=None, origin=None, not_contacted=False,
             preset=None, search=None):
    if preset == "not_closed":
        q = q.where(Lead.advisor_outcome.in_(NOT_CLOSED))
    elif preset == "hot_uncontacted":
        # Prospects only: a lead that already became a customer isn't someone to chase for a first sale.
        q = q.where(Lead.propensity_bucket == "High", Lead.last_contacted_at.is_(None), Lead.lead_status == "open",
                    or_(Lead.outcome.is_(None), Lead.outcome != "Activated"))
    if bucket:
        q = q.where(Lead.propensity_bucket.in_(bucket.split(",")))
    if status:
        q = q.where(Lead.lead_status.in_(status.split(",")))
    if advisor_outcome:
        q = q.where(Lead.advisor_outcome.in_(advisor_outcome.split(",")))
    if segment:
        q = q.where(Lead.segment.in_(segment.split(",")))
    if source:
        q = q.where(Lead.lead_source.in_(source.split(",")))
    if origin:
        q = q.where(Lead.origin == origin)
    if not_contacted:
        q = q.where(Lead.last_contacted_at.is_(None))
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Lead.lead_id.ilike(like), Lead.business_name.ilike(like), Lead.city.ilike(like)))
    return q


def listing(db: Session, *, sort: str = "-propensity_score", page: int = 1, page_size: int = 50, **filters) -> dict:
    refresh(db)
    base = _filters(select(Lead), **filters)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    desc = sort.startswith("-")
    col = SORTS.get(sort.lstrip("-"), Lead.propensity_score)
    order = [col.is_(None), col.desc() if desc else col.asc(), Lead.lead_id]
    page, page_size = max(page, 1), min(max(page_size, 1), 200)
    rows = db.scalars(base.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    conv_pct = bucket_conversion(db)

    def n(**f):
        return db.scalar(select(func.count()).select_from(_filters(select(Lead), **f).subquery()))

    return {"items": [_item(db, r, conv_pct) for r in rows], "total": total, "page": page, "page_size": page_size,
            "counts": {"all": n(), "not_closed": n(preset="not_closed"), "hot_uncontacted": n(preset="hot_uncontacted"),
                       "app": n(origin="app")},
            "bucket_conversion_pct": conv_pct}


def _lead(db: Session, lead_id: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise ApiError(404, "NOT_FOUND", "Lead not found.")
    return lead


def _quote(db: Session, lead: Lead) -> dict | None:
    if not lead.business_id:
        return None
    q = db.scalars(select(Quote).where(Quote.business_id == lead.business_id).order_by(Quote.created_at.desc())).first()
    if not q:
        return None
    cat = cached_from_db()
    items = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == q.id, QuoteItem.selected == 1)).all()
    order = db.scalar(select(Order).where(Order.quote_id == q.id))
    return {"quote_id": q.id, "status": q.status, "monthly_total_inr": q.monthly_total_inr, "setup_total_inr": q.setup_total_inr,
            "items": [f"{cat[i.product_id].name} × {i.qty}" if i.qty > 1 else cat[i.product_id].name for i in items],
            "created_at": q.created_at, "order": {"order_id": order.id, "display_id": order.display_id, "state": order.state} if order else None}


def detail(db: Session, user: User, lead_id: str) -> dict:
    lead = _lead(db, lead_id)
    conv_pct = bucket_conversion(db)
    conv = _conv(db, lead)
    app_user = db.get(User, conv.user_id) if conv else None
    out = _item(db, lead, conv_pct) | {
        "business_type": lead.business_type, "state": lead.state, "city_tier": lead.city_tier, "employees": lead.employee_count,
        "sites": lead.num_sites, "turnover_band": lead.annual_turnover_band, "has_gstin": lead.has_gstin, "gstin_masked": mask_gstin(lead.gstin),
        "has_udyam": lead.has_udyam, "udyam_masked": mask_udyam(lead.udyam_number), "current_internet": lead.current_internet,
        "current_provider": lead.current_provider, "monthly_telecom_spend_inr": lead.monthly_telecom_spend_inr,
        "products_of_interest": [p for p in (lead.products_of_interest or "").split(";") if p], "preferred_language": lead.preferred_language,
        "contact_role": lead.contact_role, "customer_follow_up_calls": lead.customer_follow_up_calls,
        "dates": {k: getattr(lead, k) for k in ("created_date", "contacted_date", "needs_assessed_date", "quote_accepted_date", "kyc_complete_date", "activated_date")},
        "whatsapp_opt_in": bool(app_user and app_user.whatsapp_opt_in), "can_dial": bool(app_user),
        "assigned_agent": _agent_name(db, lead.assigned_agent_id)}
    chat = _chat(db, conv)
    calls = db.scalars(select(CallLog).where(CallLog.lead_id == lead.lead_id).order_by(CallLog.created_at.desc())).all()
    notes = db.scalars(select(LeadNote).where(LeadNote.lead_id == lead.lead_id).order_by(LeadNote.created_at.desc())).all()
    db.add(AuditLog(actor_user_id=user.id, action="view_lead", entity="lead", entity_id=lead.lead_id))
    db.commit()
    return {"lead": out, "propensity": out["propensity"],
            "conversation_summary": chat["summary"] if chat else None, "conversation": chat, "quote": _quote(db, lead),
            "calls": [{"call_id": c.id, "provider": c.provider, "outcome": c.outcome, "duration_s": c.duration_s, "at": c.created_at,
                       "agent": _agent_name(db, c.agent_id) or "Admin"} for c in calls],
            "notes": [{"note_id": n.id, "body": n.body, "at": n.created_at, "agent": _agent_name(db, n.agent_id) or "Admin"} for n in notes]}


def _staff_agent(db: Session, user: User) -> Agent | None:
    return db.scalar(select(Agent).where(Agent.user_id == user.id))


def _twiml(customer: str, caller_id: str) -> str:
    return (f'<Response><Say voice="alice">Accel Business. Connecting you to the lead now.</Say>'
            f'<Dial callerId="{caller_id}">{customer}</Dial></Response>')


def call(db: Session, user: User, lead_id: str, mode: str) -> dict:
    """Log a follow-up call. mock: the agent dials from their own phone and records it here. twilio: ring the agent, then bridge to the
    customer. Imported leads have no number in the app, so they're always logged as mock calls (503 falls back to mock, D3.8)."""
    lead = _lead(db, lead_id)
    now = datetime.now(timezone.utc)
    last = _last_call(db, lead.lead_id)
    cooldown = get_settings().call_cooldown_hours
    if last and datetime.fromisoformat(last.created_at) > now - timedelta(hours=cooldown):
        hours = max(1, round((now - datetime.fromisoformat(last.created_at)).total_seconds() / 3600))
        by = _agent_name(db, last.agent_id) or "Admin"
        raise ApiError(409, "RECENTLY_CALLED", f"Called {hours} h ago by {by}.",
                       {"called_at": last.created_at, "by": by, "call_id": last.id, "outcome": last.outcome})
    agent = _staff_agent(db, user)
    provider, ref, status, notice = "mock", None, "logged", None
    if mode == "twilio":
        customer = _app_user(db, lead)
        to_customer = decrypt(customer.phone_enc) if customer else None
        to_agent = decrypt(user.phone_enc)
        s = get_settings()
        if not providers.twilio_configured() or not s.twilio_voice_from:
            notice = "Twilio voice isn't configured, so this was logged as a mock call."
        elif not to_customer:
            notice = "Imported leads have no phone number in the app, so this was logged as a mock call."
        else:
            res = providers.TwilioProvider(s).call(to_agent, _twiml(to_customer, s.twilio_voice_from))
            if res.ok:
                provider, ref, status = "twilio", res.ref, "ringing"
            else:
                notice = f"Twilio call failed ({res.error}); logged as a mock call."
    if provider == "mock":
        ref = providers.MockProvider().call("", "").ref
    c = CallLog(lead_id=lead.lead_id, agent_id=agent.id if agent else None, provider=provider, provider_ref=ref)
    db.add(c)
    lead.last_contacted_at = now_iso()
    if lead.lead_status == "open":
        lead.lead_status = "contacted"
    if agent:
        lead.assigned_agent_id = agent.id
    db.add(AuditLog(actor_user_id=user.id, action="call_lead", entity="lead", entity_id=lead.lead_id))
    db.commit()
    return {"call_id": c.id, "status": status, "provider": provider, "notice": notice, "lead_id": lead.lead_id}


def set_outcome(db: Session, user: User, call_id: str, outcome: str, duration_s: int | None, note: str | None) -> dict:
    c = db.get(CallLog, call_id)
    if not c:
        raise ApiError(404, "NOT_FOUND", "Call not found.")
    if outcome not in OUTCOMES:
        raise ApiError(400, "VALIDATION_ERROR", "Unknown call outcome.", {"field": "outcome", "allowed": list(OUTCOMES)})
    lead = db.get(Lead, c.lead_id)
    c.outcome, c.duration_s = outcome, duration_s
    lead.lead_status = {"converted": "converted", "not_interested": "closed"}.get(outcome, "contacted")
    agent = _staff_agent(db, user)
    if note and note.strip():
        db.add(LeadNote(lead_id=lead.lead_id, agent_id=agent.id if agent else None, body=scrub(note.strip())[:2000]))
    sent, status = False, None
    if outcome == "interested":
        customer = _app_user(db, lead)
        if customer:
            wa = notify(db, customer.id, None, "advisor_link", customer.language, {"lead_id": lead.lead_id}, in_app=False)
            status = wa.status
            sent = wa.status in ("sent", "queued", "delivered")
    db.commit()
    return {"call_id": c.id, "outcome": c.outcome, "duration_s": c.duration_s, "lead_status": lead.lead_status,
            "advisor_link_sent": sent, "advisor_link_status": status}


def add_note(db: Session, user: User, lead_id: str, body: str) -> dict:
    lead = _lead(db, lead_id)
    agent = _staff_agent(db, user)
    n = LeadNote(lead_id=lead.lead_id, agent_id=agent.id if agent else None, body=scrub(body.strip())[:2000])
    db.add(n)
    db.commit()
    return {"note_id": n.id, "body": n.body, "at": n.created_at}
