"""Keep app leads (origin=app) in step with the advisor and the order, so the admin leads table and the pilot metrics read straight
from the leads table, like the 5,000 imported rows (DESIGN.md D2.2 leads, D3.8)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Lead, Order, Quote, now_iso

LANG_NAME = {"hi": "Hindi", "en": "English", "mr": "Marathi", "ta": "Tamil", "bn": "Bengali", "kn": "Kannada", "gu": "Gujarati", "te": "Telugu"}
FIELD_LABEL = {"type": "business type", "team": "team size", "city": "city", "gst": "GST", "internet": "current internet", "needs": "needs"}


def model_input(lead: Lead) -> dict | None:
    """The propensity model's input for one lead (imported or app). None until we know the segment."""
    if not lead.segment:
        return None
    return {"segment": lead.segment, "lead_source": lead.lead_source or "Website form",
            "preferred_language": LANG_NAME.get(lead.preferred_language or "", lead.preferred_language or "Hindi"),
            "current_internet": lead.current_internet if lead.current_internet not in (None, "None") else "Unknown",
            "annual_turnover_band": lead.annual_turnover_band or "40 lakh - 1.5 cr", "has_gstin": lead.has_gstin or "N",
            "has_udyam": lead.has_udyam or "N", "city_tier": lead.city_tier or 1, "num_sites": lead.num_sites or 1,
            "employee_count": lead.employee_count or 1, "products_of_interest": lead.products_of_interest or "",
            "monthly_telecom_spend_inr": lead.monthly_telecom_spend_inr if lead.monthly_telecom_spend_inr is not None else 2000}


def score(lead: Lead) -> None:
    x = model_input(lead)
    if not x:
        return
    try:
        from app.propensity import predict

        p = predict(x)
    except Exception:  # model file missing or unreadable: the table still works, just without a bucket
        return
    lead.propensity_score, lead.propensity_bucket, lead.propensity_reasons = p["score"], p["bucket"], json.dumps(p["top_3_reasons"])


def from_conversation(db: Session, conv: Conversation, profile: dict, needs_products: list[str]) -> None:
    """After every advisor turn: copy what we've learned onto the lead and re-score it."""
    lead = db.get(Lead, conv.lead_id) if conv.lead_id else None
    if not lead:
        return
    lead.segment = profile.get("segment") or lead.segment
    lead.employee_count = profile.get("employees") or lead.employee_count
    lead.num_sites = profile.get("sites") or lead.num_sites
    lead.city = profile.get("city") or lead.city
    lead.city_tier = profile.get("city_tier") or lead.city_tier
    lead.state = profile.get("state") or lead.state
    if profile.get("has_gstin") is not None:
        lead.has_gstin = "Y" if profile["has_gstin"] else "N"
    lead.current_internet = profile.get("current_internet") or lead.current_internet
    if needs_products:
        lead.products_of_interest = ";".join(sorted(set(needs_products)))
    if lead.stage_reached in (None, "Lead"):
        lead.stage_reached = "Contacted"
        lead.contacted_date = now_iso()[:10]
    if profile.get("complete") and lead.stage_reached == "Contacted":
        lead.stage_reached = "Needs assessed"
        lead.needs_assessed_date = now_iso()[:10]
    if lead.advisor_outcome == "abandoned":
        lead.advisor_outcome, lead.drop_reason = "not_started", None
    score(lead)


def lead_for_order(db: Session, order: Order) -> Lead | None:
    return db.scalars(select(Lead).where(Lead.business_id == order.business_id, Lead.origin == "app").order_by(Lead.created_date.desc())).first()


def on_order_state(db: Session, order: Order, state: str) -> None:
    lead = lead_for_order(db, order)
    if not lead:
        return
    today = now_iso()[:10]
    if state == "KYC_VERIFIED":
        lead.stage_reached, lead.kyc_complete_date = "KYC complete", today
    elif state == "LIVE":
        lead.stage_reached, lead.outcome, lead.activated_date, lead.lead_status, lead.drop_reason = "Activated", "Activated", today, "converted", None
        if lead.created_date:
            lead.days_lead_to_activation = (date.fromisoformat(today) - date.fromisoformat(lead.created_date[:10])).days
        q = db.get(Quote, order.quote_id)
        if q:
            lead.monthly_bundle_value_inr, lead.one_time_setup_inr, lead.contract_months = q.monthly_total_inr, q.setup_total_inr, q.contract_months
    elif state == "CANCELLED":
        lead.outcome, lead.drop_reason = "Dropped", "Order cancelled before going live"


def _last_activity(db: Session, lead: Lead, conv: Conversation | None) -> datetime | None:
    stamps = [conv.updated_at or conv.created_at] if conv else []
    if lead.business_id:
        q = db.scalars(select(Quote).where(Quote.business_id == lead.business_id).order_by(Quote.created_at.desc())).first()
        if q:
            stamps.append(q.created_at)
    stamps = [s for s in stamps if s]
    return max(datetime.fromisoformat(s) for s in stamps) if stamps else None


def sweep_abandoned(db: Session, minutes: int, now: datetime | None = None) -> int:
    """An app lead that stops mid-advisor or at the quote, with no order, for `minutes` is 'abandoned' (advisor could not close).
    The conversation stays open: if the owner comes back and answers, from_conversation flips the lead back."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)
    n = 0
    for lead in db.scalars(select(Lead).where(Lead.origin == "app", Lead.advisor_outcome.in_(("not_started", "quoted")))):
        conv = db.scalars(select(Conversation).where(Conversation.lead_id == lead.lead_id).order_by(Conversation.created_at.desc())).first()
        last = _last_activity(db, lead, conv)
        if not last or last > cutoff:
            continue
        if lead.business_id and db.scalar(select(Order.id).where(Order.business_id == lead.business_id)):
            continue
        if lead.advisor_outcome == "quoted":
            reason = "Left at the quote"
        else:
            missing = []
            if conv and conv.profile_json:
                answers = json.loads(conv.profile_json).get("answers", {})
                missing = [f for f in FIELD_LABEL if f not in answers]
            reason = f"Left the advisor at the {FIELD_LABEL[missing[0]]} question" if missing else "Left before seeing the plan"
        lead.advisor_outcome, lead.drop_reason, lead.outcome = "abandoned", reason, "Dropped"
        n += 1
    return n
