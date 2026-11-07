"""Escalation API logic (DESIGN.md D3.7): talk to a person, the agent queue, full case context, and resolutions."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.escalations import service as esc
from app.escalations.service import OPEN
from app.models import (Agent, AuditLog, Business, Conversation, Escalation, KycCase, KycCheck, KycDocument, Lead, Message, Order,
                        OrderEvent, Product, Quote, QuoteItem, Recommendation, User, now_iso)
from app.orders import fulfilment, state_machine
from app.security.masking import scrub

POST_ORDER = {"KYC_VERIFIED", "INSTALL_BOOKED", "INSTALLED", "LIVE"}
PRIO = {"P1": 0, "P2": 1, "P3": 2}
RESOLUTIONS = {
    "kyc_flag": ("approved", "ask_fix", "rejected"),
    "sla_breach": ("rebooked", "installed", "went_live", "contacted"),
    "user_request": ("contacted", "rebooked", "no_answer"),
    "advisor_failed": ("contacted", "quoted", "no_answer"),
    "assisted_deal": ("survey_booked", "contacted"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _agent_of(db: Session, user: User) -> Agent | None:
    return db.scalar(select(Agent).where(Agent.user_id == user.id))


def request_person(db: Session, user: User, order_id: str | None, conversation_id: str | None, reason: str | None, preferred_time: str | None) -> dict:
    order = db.get(Order, order_id) if order_id else None
    if order_id and (not order or order.user_id != user.id):
        raise ApiError(404, "NOT_FOUND", "Order not found.")
    conv = db.get(Conversation, conversation_id) if conversation_id else None
    if conversation_id and (not conv or conv.user_id != user.id):
        raise ApiError(404, "NOT_FOUND", "Conversation not found.")
    if not order and not conv:
        raise ApiError(422, "VALIDATION_ERROR", "Tell us which order or chat this is about.")
    lang = user.language
    if order:
        existing = esc.open_for_order(db, order.id, ("user_request", "sla_breach"))
    else:
        existing = db.scalar(select(Escalation).where(Escalation.conversation_id == conv.id, Escalation.status.in_(OPEN)))
    if existing:
        raise ApiError(409, "ESCALATION_EXISTS", esc.customer_message(db, existing, lang), esc.summary(db, existing, lang))
    hour_ago = (_now() - timedelta(hours=1)).isoformat(timespec="seconds")
    recent = db.scalar(select(func.count()).select_from(Escalation).join(Order, Order.id == Escalation.order_id, isouter=True)
                       .join(Conversation, Conversation.id == Escalation.conversation_id, isouter=True)
                       .where(Escalation.trigger == "user_request", Escalation.created_at >= hour_ago,
                              (Order.user_id == user.id) | (Conversation.user_id == user.id)))
    if recent >= 3:
        raise ApiError(429, "RATE_LIMITED", "You've asked for a call a few times already. Someone will reach you soon.")
    skill = "install" if order and order.state in POST_ORDER else "sales"
    text = (reason or "Customer asked to talk to a person").strip()[:300]
    if preferred_time:
        text += f" (prefers {preferred_time.strip()[:40]})"
    e = esc.create(db, trigger="user_request", priority="P2", skill=skill, reason=scrub(text), lang=lang, order=order,
                   conversation_id=conv.id if conv else None, lead_id=conv.lead_id if conv else None, user_id=user.id)
    if conv:
        conv.status = "escalated"
    db.commit()
    return esc.summary(db, e, lang) | {"escalation_id": e.id}


def _business(db: Session, e: Escalation) -> tuple[Business | None, Order | None]:
    order = db.get(Order, e.order_id) if e.order_id else None
    if not order and e.kyc_case_id:
        case = db.get(KycCase, e.kyc_case_id)
        order = db.get(Order, case.order_id) if case else None
    biz = db.get(Business, order.business_id) if order else None
    if not biz and e.conversation_id:
        conv = db.get(Conversation, e.conversation_id)
        biz = db.get(Business, conv.business_id) if conv and conv.business_id else None
    return biz, order


def biz_label(biz: Business | None) -> str | None:
    if not biz:
        return None
    if biz.name:
        return biz.name
    kind = biz.business_type or {"Micro retail & services": "Shop", "Professional offices": "Office"}.get(biz.segment, "Business")
    return f"{kind} in {biz.city}" if biz.city else kind


def _row(db: Session, e: Escalation, now: datetime) -> dict:
    biz, order = _business(db, e)
    agent = db.get(Agent, e.assigned_agent_id) if e.assigned_agent_id else None
    age = int((now - datetime.fromisoformat(e.created_at)).total_seconds() // 60)
    breached = e.status in OPEN and bool(e.sla_due_at) and datetime.fromisoformat(e.sla_due_at) < now
    return {"escalation_id": e.id, "trigger": e.trigger, "priority": e.priority, "status": e.status, "business": biz_label(biz),
            "segment": biz.segment if biz else None, "city": biz.city if biz else None, "reason": e.reason, "language": e.language,
            "order_id": order.id if order else None, "order_display_id": order.display_id if order else None,
            "order_state": order.state if order else None, "age_minutes": age, "sla_due_at": e.sla_due_at, "breached": breached,
            "agent": agent.name if agent else None, "agent_id": agent.id if agent else None}


def queue(db: Session, user: User, status: str | None, mine: bool, trigger: str | None) -> dict:
    now = _now()
    statuses = tuple(s for s in (status or "open,assigned,in_progress").split(",") if s) if status != "all" else None
    q = select(Escalation)
    if statuses:
        q = q.where(Escalation.status.in_(statuses))
    if trigger:
        q = q.where(Escalation.trigger.in_(trigger.split(",")))
    if mine:
        me = _agent_of(db, user)
        q = q.where(Escalation.assigned_agent_id == (me.id if me else "-"))
    rows = [_row(db, e, now) for e in db.scalars(q.limit(500))]
    rows.sort(key=lambda r: (not r["breached"], PRIO.get(r["priority"], 9), r["sla_due_at"] or "9"))
    open_rows = db.scalars(select(Escalation).where(Escalation.status.in_(OPEN))).all()
    counts = {"open": sum(e.status == "open" for e in open_rows), "assigned": sum(e.status in ("assigned", "in_progress") for e in open_rows),
              "breached": sum(bool(e.sla_due_at) and datetime.fromisoformat(e.sla_due_at) < now for e in open_rows)}
    return {"items": rows, "counts": counts}


TYPE_LABEL = {"micro": "Shop or small service", "prof": "Clinic or office", "multi": "Several branches", "mfg": "Factory or workshop"}
NEED_LABEL = {"pos": "UPI and billing", "whatsapp": "WhatsApp business", "cctv": "CCTV", "email": "business email", "wifi": "guest Wi-Fi",
              "backup": "data backup", "website": "website", "calls": "business calls", "tollfree": "toll-free number", "security": "security"}


def profile_summary(answers: dict, needs: list[str]) -> str | None:
    parts = []
    if answers.get("type"):
        parts.append(TYPE_LABEL.get(answers["type"], str(answers["type"])))
    team = answers.get("team")
    if isinstance(team, list) and team:
        parts.append(f"{team[0]} people" + (f", {team[1]} sites" if len(team) > 1 and team[1] and team[1] > 1 else ""))
    city = answers.get("city")
    if isinstance(city, dict) and city.get("city"):
        parts.append(f"{city['city']}, {city.get('state') or ''}".rstrip(", "))
    gst = answers.get("gst")
    if gst:
        parts.append("no GST" if gst == "no" else "has GSTIN")
    if answers.get("internet"):
        parts.append(f"now on {answers['internet']}")
    if needs:
        parts.append("wants " + ", ".join(NEED_LABEL.get(n, n) for n in needs))
    return " · ".join(parts) or None


def _chat(db: Session, conv: Conversation | None) -> dict | None:
    if not conv:
        return None
    s = json.loads(conv.profile_json or "{}")
    answers = s.get("answers", {})
    msgs = db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)).all()
    summary = profile_summary(answers, s.get("needs") or [])
    return {"conversation_id": conv.id, "language": conv.language, "status": conv.status, "failed_turns": conv.failed_turns,
            "answers": {k: (scrub(v) if isinstance(v, str) else v) for k, v in answers.items()}, "summary": scrub(summary) if summary else None,
            "messages": [{"role": m.role, "content": scrub(m.content), "at": m.created_at, "flag": m.validation_status} for m in msgs[-12:]]}


def _quote(db: Session, order: Order | None) -> tuple[dict | None, Conversation | None]:
    if not order:
        return None, None
    q = db.get(Quote, order.quote_id)
    rows = db.execute(select(QuoteItem, Product).join(Product, Product.product_id == QuoteItem.product_id)
                      .where(QuoteItem.quote_id == q.id, QuoteItem.selected == 1)).all()
    rec = db.get(Recommendation, q.recommendation_id) if q.recommendation_id else None
    conv = db.get(Conversation, rec.conversation_id) if rec else None
    return {"quote_id": q.id, "monthly_total_inr": q.monthly_total_inr, "setup_total_inr": q.setup_total_inr, "contract_months": q.contract_months,
            "items": [{"product_id": p.product_id, "name": p.name, "qty": i.qty, "line_monthly_inr": i.line_monthly_inr,
                       "install_days": p.install_days} for i, p in rows]}, conv


def _kyc(db: Session, order: Order | None) -> dict | None:
    case = db.scalar(select(KycCase).where(KycCase.order_id == order.id)) if order else None
    if not case:
        return None
    checks = db.scalars(select(KycCheck).where(KycCheck.case_id == case.id).order_by(KycCheck.id)).all()
    docs = db.scalars(select(KycDocument).where(KycDocument.case_id == case.id).order_by(KycDocument.doc_type, KycDocument.version)).all()
    return {"case_id": case.id, "status": case.status, "verdict": case.verdict, "gstin_masked": case.gstin_masked, "udyam_masked": case.udyam_masked,
            "registry": json.loads(case.registry_snapshot) if case.registry_snapshot else None, "submitted_at": case.submitted_at,
            "checks": [{"check_code": c.check_code, "result": c.result, "severity": c.severity, "detail": c.detail_internal,
                        "customer_message": c.message_customer} for c in checks],
            "flags": [{"check_code": c.check_code, "severity": c.severity, "detail": c.detail_internal} for c in checks if c.result == "fail"],
            "documents": [{"document_id": d.id, "doc_type": d.doc_type, "version": d.version, "status": d.status, "ocr_confidence": d.ocr_confidence,
                           "sharpness": d.sharpness, "deleted_at": d.deleted_at} for d in docs]}


def detail(db: Session, user: User, escalation_id: str) -> dict:
    e = db.get(Escalation, escalation_id)
    if not e:
        raise ApiError(404, "NOT_FOUND", "Escalation not found.")
    biz, order = _business(db, e)
    customer = db.get(User, order.user_id) if order else None
    conv = db.get(Conversation, e.conversation_id) if e.conversation_id else None
    quote, quote_conv = _quote(db, order)
    conv = conv or quote_conv
    if not customer and conv:
        customer = db.get(User, conv.user_id)
    lead = db.scalar(select(Lead).where(Lead.business_id == biz.id)) if biz else None
    if not lead and e.lead_id:
        lead = db.get(Lead, e.lead_id)
    events = db.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id)).all() if order else []
    history = db.scalars(select(Escalation).where(Escalation.order_id == order.id, Escalation.id != e.id).order_by(Escalation.created_at)).all() if order else []
    agent = db.get(Agent, e.assigned_agent_id) if e.assigned_agent_id else None
    db.add(AuditLog(actor_user_id=user.id, action="view_escalation", entity="escalation", entity_id=e.id))
    db.commit()
    lang = customer.language if customer else (e.language or "en")
    answered = json.loads(conv.profile_json or "{}").get("answers", {}).get("type") if conv else None
    btype = (biz.business_type if biz else None) or TYPE_LABEL.get(answered or "")
    return {
        "escalation": _row(db, e, _now()) | {"required_skill": e.required_skill, "created_at": e.created_at, "assigned_at": e.assigned_at,
                                              "first_response_at": e.first_response_at, "resolved_at": e.resolved_at, "resolution": e.resolution,
                                              "resolution_note": e.resolution_note, "customer_was_told": esc.customer_message(db, e, lang),
                                              "resolutions": RESOLUTIONS.get(e.trigger, ("contacted",)),
                                              "agent_languages": json.loads(agent.languages) if agent else []},
        "customer": {"phone_masked": customer.phone_masked, "language": customer.language, "whatsapp_opt_in": bool(customer.whatsapp_opt_in)} if customer else None,
        "business": {"name": biz_label(biz), "type": btype, "segment": biz.segment, "city": biz.city, "state": biz.state, "city_tier": biz.city_tier,
                     "employees": biz.employees, "sites": biz.sites, "current_internet": biz.current_internet, "monthly_spend_inr": biz.monthly_spend_inr,
                     "gst_status": biz.gst_status, "gstin_masked": biz.gstin_masked, "has_udyam": bool(biz.has_udyam)} if biz else None,
        "lead": {"lead_id": lead.lead_id, "source": lead.lead_source, "propensity_bucket": lead.propensity_bucket,
                 "propensity_score": lead.propensity_score, "status": lead.lead_status} if lead else None,
        "chat": _chat(db, conv),
        "quote": quote,
        "order": {"order_id": order.id, "display_id": order.display_id, "state": order.state, "state_due_at": order.state_due_at,
                  "expected_install_date": order.expected_install_date, "expected_live_date": order.expected_live_date,
                  "visit": fulfilment.slot_text(order, "en"), "payment_status": order.payment_status,
                  "events": [{"from": v.from_state, "to": v.to_state, "actor": v.actor, "note": v.note, "at": v.created_at} for v in events]} if order else None,
        "kyc": _kyc(db, order),
        "history": [{"escalation_id": h.id, "trigger": h.trigger, "priority": h.priority, "status": h.status, "reason": h.reason,
                     "resolution": h.resolution, "created_at": h.created_at} for h in history],
    }


def _resolve_effects(db: Session, e: Escalation, order: Order | None, resolution: str, actor: str, note: str) -> None:
    if not order:
        return
    if e.trigger == "kyc_flag":
        case = db.get(KycCase, e.kyc_case_id) if e.kyc_case_id else db.scalar(select(KycCase).where(KycCase.order_id == order.id))
        if resolution == "approved":
            if order.state == "KYC_FLAGGED":
                state_machine.transition(db, order, "HUMAN_REVIEW", actor, "opened by agent")
            state_machine.transition(db, order, "KYC_VERIFIED", actor, f"approved: {note}")
            if case:
                case.status, case.verdict, case.verified_at = "verified", "verified", now_iso()
            esc.notify(db, order.user_id, order.id, "kyc_verified", db.get(User, order.user_id).language, {"by": "agent"})
            fulfilment.on_verified(db, order, actor)
        elif resolution == "ask_fix":
            if order.state == "HUMAN_REVIEW":
                state_machine.transition(db, order, "KYC_FLAGGED", actor, f"customer asked to fix: {note}")
            if case:
                case.status = "flagged"
            esc.notify(db, order.user_id, order.id, "kyc_fix_needed", db.get(User, order.user_id).language, {"note": note})
        elif resolution == "rejected":
            state_machine.transition(db, order, "CANCELLED", actor, f"rejected: {note}")
            if case:
                case.status = "rejected"
    elif resolution == "rebooked" and order.state in ("INSTALL_BOOKED", "KYC_VERIFIED"):
        fulfilment.book(db, order, actor, on=datetime.now(esc.IST).date() + timedelta(days=1), note=f"rebooked by agent: {note}")
    elif resolution == "installed" and order.state == "INSTALL_BOOKED":
        state_machine.transition(db, order, "INSTALLED", actor, note)
    elif resolution == "went_live" and order.state == "INSTALLED":
        order.payment_status = "paid" if order.payment_status == "pending" else order.payment_status
        state_machine.transition(db, order, "LIVE", actor, note)


def act(db: Session, user: User, escalation_id: str, action: str, agent_id: str | None, resolution: str | None, note: str | None) -> dict:
    e = db.get(Escalation, escalation_id)
    if not e:
        raise ApiError(404, "NOT_FOUND", "Escalation not found.")
    me = _agent_of(db, user)
    admin = user.role == "admin"
    if e.status not in OPEN:
        raise ApiError(409, "INVALID_STATE", "This case is already closed.", {"status": e.status})
    if action in ("start", "resolve") and not admin and (not me or e.assigned_agent_id != me.id):
        raise ApiError(403, "FORBIDDEN", "This case isn't assigned to you.")
    actor = f"agent:{me.id}" if me else f"admin:{user.id}"
    if action in ("assign", "reassign"):
        target = db.get(Agent, agent_id) if agent_id else (me if action == "assign" else None)
        if action == "reassign" and not agent_id:
            others = [a for a in db.scalars(select(Agent).where(Agent.active == 1)) if a.id != e.assigned_agent_id and (e.required_skill or "") in json.loads(a.skills)]
            counts = esc.open_counts(db)
            others.sort(key=lambda a: ((e.language or "") not in json.loads(a.languages), counts.get(a.id, 0)))
            target = others[0] if others else None
        if not target:
            raise ApiError(422, "VALIDATION_ERROR", "Pick an agent.")
        if not admin and action == "assign" and target.id != (me.id if me else None):
            raise ApiError(403, "FORBIDDEN", "Only an admin can assign cases to someone else.")
        e.assigned_agent_id, e.assigned_at, e.status = target.id, now_iso(), "assigned"
        _, order = _business(db, e)
        if order:
            order.assigned_agent_id = target.id
    elif action == "start":
        e.status = "in_progress"
        e.first_response_at = e.first_response_at or now_iso()
    elif action == "resolve":
        allowed = RESOLUTIONS.get(e.trigger, ("contacted",))
        if resolution not in allowed:
            raise ApiError(422, "VALIDATION_ERROR", f"Resolution must be one of: {', '.join(allowed)}.", {"allowed": list(allowed)})
        if not note or len(note.strip()) < 5:
            raise ApiError(422, "VALIDATION_ERROR", "Add a short note so the next person knows what happened.")
        _, order = _business(db, e)
        _resolve_effects(db, e, order, resolution, actor, note.strip())
        e.status, e.resolution, e.resolution_note, e.resolved_at = "resolved", resolution, scrub(note.strip())[:1000], now_iso()
        e.first_response_at = e.first_response_at or now_iso()
    else:
        raise ApiError(422, "VALIDATION_ERROR", "Unknown action.")
    db.add(AuditLog(actor_user_id=user.id, action=f"escalation_{action}", entity="escalation", entity_id=e.id))
    db.commit()
    return _row(db, e, _now()) | {"resolution": e.resolution}


def agents(db: Session) -> dict:
    counts = esc.open_counts(db)
    return {"agents": [{"id": a.id, "name": a.name, "languages": json.loads(a.languages), "skills": json.loads(a.skills),
                        "open_cases": counts.get(a.id, 0), "max_open": a.max_open, "active": bool(a.active)}
                       for a in db.scalars(select(Agent).order_by(Agent.name))]}
