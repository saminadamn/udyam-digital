"""Quotes (DESIGN.md D3.3) and quote acceptance into an order (D3.4).

The quote holds every recommended item: core items start selected, add-ons start unselected. Every change
re-runs validate_bundle on the selected set and recomputes locks, so an invalid bundle can never be stored
or accepted.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.i18n import text
from app.models import Agent, Business, Conversation, Lead, Order, Quote, QuoteItem, Recommendation, User, now_iso
from app.orders import state_machine
from app.pricing.service import price, rule_for, unit_price
from app.rules.catalogue import cached_from_db
from app.rules.engine import BASE_LINKS, SEGMENT_KEY, Profile, rules_version, validate_bundle

QUOTE_VALID_DAYS = 7


def _profile(biz: Business) -> Profile:
    return Profile(segment=biz.segment, city_tier=biz.city_tier, employees=biz.employees, sites=biz.sites,
                   gst_status=biz.gst_status or "None", gstin_valid=biz.gst_status in ("Active", "Cancelled", "Suspended"))


def _key(biz: Business) -> str:
    return SEGMENT_KEY[biz.segment]


def qty_bounds(pid: str, biz: Business, catalogue) -> tuple[int, int] | None:
    basis = catalogue[pid].quantity_basis
    if basis == "per_site":
        return (1, max(1, biz.sites))
    if basis == "per_user":
        return (1, max(1, biz.employees))
    return None


def locks(selected: list[str], catalogue, lang: str) -> dict[str, str]:
    """Selected items that can't be removed, with a reason in the owner's language."""
    out: dict[str, str] = {}
    sel = set(selected)
    and_ = text(lang, "and_list")
    for pid in selected:
        needers = []
        for other in selected:
            req = catalogue[other].requires_one_of
            if other != pid and pid in req and not ((set(req) & sel) - {pid}):
                needers.append(catalogue[other].name)
        if needers:
            names = needers[0] if len(needers) == 1 else ", ".join(needers[:-1]) + f" {and_} " + needers[-1]
            out[pid] = text(lang, "lock_needed_by", names=names)
        elif pid in BASE_LINKS and not ((sel & BASE_LINKS) - {pid}):
            out[pid] = text(lang, "lock_link")
    return out


def _owned_quote(db: Session, user: User, quote_id: str) -> tuple[Quote, Business]:
    q = db.get(Quote, quote_id)
    biz = db.get(Business, q.business_id) if q else None
    if not q or not biz or biz.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "Quote not found.")
    return q, biz


def _items(db: Session, quote_id: str) -> list[QuoteItem]:
    rows = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote_id))
    return sorted(rows, key=lambda i: (i.role != "core", i.product_id not in BASE_LINKS, i.product_id))


def _recalc(db: Session, q: Quote, biz: Business, items: list[QuoteItem], lang: str) -> None:
    catalogue = cached_from_db()
    key = _key(biz)
    selected = [(i.product_id, i.qty) for i in items if i.selected]
    errs = validate_bundle(_profile(biz), selected, catalogue)
    if errs:
        raise ApiError(422, "INELIGIBLE", "This change would make the plan invalid.", {"reasons": [e.message for e in errs]})
    lk = locks([p for p, _ in selected], catalogue, lang)
    for i in items:
        u = unit_price(i.product_id, key, catalogue)
        i.unit_price_inr, i.line_monthly_inr, i.line_setup_inr = u, u * i.qty, catalogue[i.product_id].setup_fee_inr * i.qty
        i.locked = 1 if (i.selected and i.product_id in lk) else 0
        i.lock_reason = lk.get(i.product_id) if i.selected else None
    totals = price(selected, key, catalogue)
    q.monthly_total_inr, q.setup_total_inr = totals["monthly_total_inr"], totals["setup_total_inr"]
    q.contract_months, q.max_install_days, q.pricing_rule = totals["contract_months"], totals["max_install_days"], totals["pricing_rule"]


def view(db: Session, q: Quote, biz: Business, lang: str) -> dict:
    catalogue = cached_from_db()
    items = _items(db, q.id)
    out_items = []
    for i in items:
        b = qty_bounds(i.product_id, biz, catalogue)
        out_items.append({
            "product_id": i.product_id, "name": catalogue[i.product_id].name, "qty": i.qty, "role": i.role, "selected": bool(i.selected),
            "unit_price_inr": i.unit_price_inr, "line_monthly_inr": i.line_monthly_inr, "line_setup_inr": i.line_setup_inr,
            "setup_fee_inr": catalogue[i.product_id].setup_fee_inr, "locked": bool(i.locked), "lock_reason": i.lock_reason,
            "what_it_does": text(lang, "products")[i.product_id], "why": (text(lang, "why").get(i.product_id) or text(lang, "products")[i.product_id]),
            "qty_editable": b is not None and b[0] < b[1], "qty_min": b[0] if b else i.qty, "qty_max": b[1] if b else i.qty,
            "install_days": catalogue[i.product_id].install_days, "min_contract_months": catalogue[i.product_id].min_contract_months,
            "requires_one_of": list(catalogue[i.product_id].requires_one_of),
        })
    spend = q.current_spend_inr
    order = db.scalar(select(Order).where(Order.quote_id == q.id))
    return {
        "quote_id": q.id, "status": q.status, "segment": biz.segment, "items": out_items,
        "monthly_total_inr": q.monthly_total_inr, "setup_total_inr": q.setup_total_inr, "contract_months": q.contract_months,
        "max_install_days": q.max_install_days, "live_in_days": q.max_install_days + 1, "pricing_rule": q.pricing_rule,
        "current_spend_inr": spend, "difference_inr": None if spend is None else q.monthly_total_inr - spend,
        "valid_until": q.valid_until, "assisted": _assisted(biz, [i.product_id for i in items if i.selected]),
        "order_id": order.id if order else None, "order_display_id": order.display_id if order else None,
    }


def _assisted(biz: Business, selected: list[str]) -> bool:
    return bool({"P10", "P05", "P06"} & set(selected)) or biz.sites >= 3


def create(db: Session, user: User, recommendation_id: str) -> dict:
    rec = db.get(Recommendation, recommendation_id)
    conv = db.get(Conversation, rec.conversation_id) if rec else None
    if not rec or not conv or conv.user_id != user.id:
        raise ApiError(404, "RECOMMENDATION_NOT_FOUND", "This recommendation was not found.")
    if rec.rules_version != rules_version():
        raise ApiError(409, "RECOMMENDATION_STALE", "Our plans changed since this suggestion. Please get a fresh one.")
    existing = db.scalar(select(Quote).where(Quote.recommendation_id == rec.id, Quote.status == "draft"))
    biz = db.get(Business, rec.business_id)
    if existing and existing.valid_until >= date.today().isoformat():
        return view(db, existing, biz, conv.language)
    for old in db.scalars(select(Quote).where(Quote.business_id == biz.id, Quote.status == "draft")):
        old.status = "superseded"
    lead = db.get(Lead, conv.lead_id) if conv.lead_id else None
    q = Quote(business_id=biz.id, recommendation_id=rec.id, status="draft", pricing_rule=rule_for(_key(biz)),
              current_spend_inr=biz.monthly_spend_inr if biz.monthly_spend_inr is not None else (lead.monthly_telecom_spend_inr if lead else None),
              valid_until=(date.today() + timedelta(days=QUOTE_VALID_DAYS)).isoformat())
    db.add(q)
    db.flush()
    items = [QuoteItem(quote_id=q.id, product_id=it["product_id"], qty=int(it["qty"]), role=it["role"], selected=1 if it["role"] == "core" else 0,
                       unit_price_inr=0, line_monthly_inr=0, line_setup_inr=0) for it in json.loads(rec.items)]
    db.add_all(items)
    _recalc(db, q, biz, items, conv.language)
    db.commit()
    return view(db, q, biz, conv.language)


def get(db: Session, user: User, quote_id: str) -> dict:
    q, biz = _owned_quote(db, user, quote_id)
    return view(db, q, biz, user.language)


def update_item(db: Session, user: User, quote_id: str, product_id: str, selected: bool | None, qty: int | None) -> dict:
    q, biz = _owned_quote(db, user, quote_id)
    if q.status != "draft":
        raise ApiError(409, "QUOTE_NOT_DRAFT", "This quote has already been accepted.")
    items = _items(db, q.id)
    item = next((i for i in items if i.product_id == product_id), None)
    if not item:
        raise ApiError(404, "NOT_FOUND", "This item is not part of your quote.")
    catalogue = cached_from_db()
    lang = user.language
    if selected is False and item.selected:
        lk = locks([i.product_id for i in items if i.selected], catalogue, lang)
        if product_id in lk:
            raise ApiError(409, "DEPENDENCY_LOCKED", lk[product_id], {"reason": lk[product_id], "product_id": product_id})
        item.selected = 0
    elif selected is True and not item.selected:
        item.selected = 1
    if qty is not None:
        b = qty_bounds(product_id, biz, catalogue)
        if b is None or b[0] == b[1]:
            raise ApiError(422, "QTY_NOT_EDITABLE", "The quantity of this item is fixed.", {"product_id": product_id})
        if not (b[0] <= qty <= b[1]):
            raise ApiError(422, "QTY_OUT_OF_RANGE", f"Choose between {b[0]} and {b[1]}.", {"min": b[0], "max": b[1]})
        item.qty = qty
    _recalc(db, q, biz, items, lang)
    db.commit()
    return view(db, q, biz, lang)


def set_spend(db: Session, user: User, quote_id: str, spend: int) -> dict:
    q, biz = _owned_quote(db, user, quote_id)
    q.current_spend_inr = spend
    biz.monthly_spend_inr = spend
    lead = db.scalar(select(Lead).where(Lead.business_id == biz.id))
    if lead:
        lead.monthly_telecom_spend_inr = spend
    db.commit()
    return view(db, q, biz, user.language)


def _display_id(db: Session) -> str:
    prefix = "UD-" + datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%y%m") + "-"
    n = db.scalar(select(func.count()).select_from(Order).where(Order.display_id.like(prefix + "%"))) or 0
    return f"{prefix}{n + 1:04d}"


def _assisted_escalation(db: Session, order: Order, biz: Business, selected: list[str], lang: str) -> None:
    if not _assisted(biz, selected):
        return
    from app.escalations.service import create

    why = "SD-WAN" if "P10" in selected else "leased line" if {"P05", "P06"} & set(selected) else f"{biz.sites} sites"
    create(db, trigger="assisted_deal", priority="P2", skill="account_manager", reason=f"Assisted deal: {why}; confirm site survey",
           lang=lang, order=order, sla_hours=24)


def accept(db: Session, user: User, quote_id: str) -> dict:
    q, biz = _owned_quote(db, user, quote_id)
    existing = db.scalar(select(Order).where(Order.quote_id == q.id))
    if existing:
        raise ApiError(409, "ORDER_EXISTS", "This quote is already an order.", {"order_id": existing.id, "display_id": existing.display_id})
    if q.status != "draft":
        raise ApiError(409, "QUOTE_NOT_ACCEPTABLE", "This quote can no longer be accepted.")
    if q.valid_until < date.today().isoformat():
        q.status = "expired"
        db.commit()
        raise ApiError(409, "QUOTE_EXPIRED", "This quote has expired. Prices have been refreshed.")
    items = _items(db, q.id)
    selected = [(i.product_id, i.qty) for i in items if i.selected]
    catalogue = cached_from_db()
    errs = validate_bundle(_profile(biz), selected, catalogue)
    if errs or not any(p in BASE_LINKS for p, _ in selected):
        raise ApiError(422, "INELIGIBLE", "This plan can't be ordered as it is.", {"reasons": [e.message for e in errs] or ["Every plan needs an internet connection."]})
    _recalc(db, q, biz, items, user.language)
    q.status, q.accepted_at = "accepted", now_iso()
    order = Order(display_id=_display_id(db), quote_id=q.id, business_id=biz.id, user_id=user.id, payment_status="pending")
    state_machine.create(db, order, "user", f"Accepted quote {q.id}: Rs {q.monthly_total_inr}/month, {len(selected)} products")
    sel_ids = [p for p, _ in selected]
    _assisted_escalation(db, order, biz, sel_ids, user.language)
    from app.notifications.service import notify

    notify(db, user.id, order.id, "quote_ready", user.language, {"display_id": order.display_id, "monthly_total_inr": q.monthly_total_inr})
    lead = db.scalar(select(Lead).where(Lead.business_id == biz.id))
    if lead:
        lead.advisor_outcome, lead.stage_reached, lead.quote_accepted_date = "ordered", "Quote accepted", now_iso()[:10]
    db.commit()
    return {"quote_id": q.id, "status": q.status, "order_id": order.id, "display_id": order.display_id, "state": order.state,
            "next_step": "consent", "assisted": _assisted(biz, sel_ids)}


def order_view(db: Session, order: Order, detail: bool = False) -> dict:
    q = db.get(Quote, order.quote_id)
    out = {"order_id": order.id, "display_id": order.display_id, "state": order.state, "monthly_total_inr": q.monthly_total_inr,
           "setup_total_inr": q.setup_total_inr, "contract_months": q.contract_months, "payment_status": order.payment_status,
           "created_at": order.created_at, "assigned_agent_id": order.assigned_agent_id}
    if detail:
        catalogue = cached_from_db()
        out["items"] = [{"product_id": i.product_id, "name": catalogue[i.product_id].name, "qty": i.qty, "line_monthly_inr": i.line_monthly_inr}
                        for i in _items(db, q.id) if i.selected]
        from app.models import KycCase

        case = db.scalar(select(KycCase).where(KycCase.order_id == order.id))
        out["kyc_case_id"] = case.id if case else None
        out["consent_id"] = case.consent_id if case else None
        out["kyc_status"] = case.status if case else None
        out["gstin_masked"] = case.gstin_masked if case else None
        agent = db.get(Agent, order.assigned_agent_id) if order.assigned_agent_id else None
        out["account_manager"] = agent.name.split()[0] if agent else None
    return out
