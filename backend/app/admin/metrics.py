"""The pilot metrics strip (analysis/bundles_and_metrics.md section 3; DESIGN.md D3.8 GET /admin/metrics).

Both columns are computed from the database on every call: the baseline from the 5,000 imported leads (Apr-Jun 2026), the
current value from app leads and their orders. Nothing is hard-coded except the pilot targets."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import mean

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import CallLog, Conversation, Escalation, Lead, Order, OrderEvent

DIGITAL = ("Website form", "WhatsApp campaign")
STRIP = ("lead_to_activation", "days_to_activate", "cac_per_activation", "churn_6m", "chase_calls_per_customer")
META = {
    "lead_to_activation": ("Lead-to-activation", 0.11, "pct", "higher"),
    "days_to_activate": ("Days from lead to live", 8, "days", "lower"),
    "cac_per_activation": ("CAC per activation", 8000, "inr", "lower"),
    "churn_6m": ("6-month churn", 0.11, "pct", "lower"),
    "chase_calls_per_customer": ("Status-chase calls per customer", 0.5, "num", "lower"),
    "kyc_completion": ("KYC completion", 0.85, "pct", "higher"),
    "escalation_resolution_hours": ("Escalation resolution", 24, "hours", "lower"),
}


def _days(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 86400


def baseline(db: Session) -> dict:
    imp = Lead.origin == "import"
    act = Lead.outcome == "Activated"
    n, n_act, cost = db.execute(select(func.count(), func.sum(case((act, 1), else_=0)), func.sum(Lead.acquisition_cost_inr)).where(imp)).one()
    days, churn, chase = db.execute(select(func.avg(Lead.days_lead_to_activation),
                                           func.avg(case((Lead.churned_within_6_months == "Y", 1.0), else_=0.0)),
                                           func.avg(Lead.customer_follow_up_calls)).where(imp, act)).one()
    quoted = db.scalar(select(func.count()).where(imp, Lead.quote_accepted_date.is_not(None)))
    kyc = db.scalar(select(func.count()).where(imp, Lead.kyc_complete_date.is_not(None)))
    return {"lead_to_activation": round(n_act / n, 3) if n else None, "days_to_activate": round(days, 1) if days is not None else None,
            "cac_per_activation": round(cost / n_act) if n_act else None, "churn_6m": round(churn, 3) if churn is not None else None,
            "chase_calls_per_customer": round(chase, 2) if chase is not None else None,
            "kyc_completion": round(kyc / quoted, 3) if quoted else None, "escalation_resolution_hours": None,
            "_n": n, "_activated": n_act}


def cost_per_lead(db: Session) -> dict[str, float]:
    """What a lead from each source cost in the imported history; app leads from no known source cost what digital leads cost."""
    rows = dict(db.execute(select(Lead.lead_source, func.avg(Lead.acquisition_cost_inr)).where(Lead.origin == "import").group_by(Lead.lead_source)).all())
    digital = db.scalar(select(func.avg(Lead.acquisition_cost_inr)).where(Lead.origin == "import", Lead.lead_source.in_(DIGITAL)))
    return rows | {"_default": digital or 0}


def _assisted_ids(db: Session, leads: list[Lead]) -> set[str]:
    ids = {l.lead_id for l in leads}
    by_biz = {l.business_id: l.lead_id for l in leads if l.business_id}
    out = set(db.scalars(select(CallLog.lead_id).where(CallLog.lead_id.in_(ids))))
    out |= {x for x in db.scalars(select(Escalation.lead_id).where(Escalation.lead_id.in_(ids))) if x}
    biz_orders = dict(db.execute(select(Order.id, Order.business_id).where(Order.business_id.in_(by_biz))).all())
    for oid in db.scalars(select(Escalation.order_id).where(Escalation.order_id.in_(biz_orders), Escalation.trigger.in_(("assisted_deal", "user_request")))):
        out.add(by_biz[biz_orders[oid]])
    return out


def current(db: Session, frm: str | None = None, to: str | None = None, segment: str | None = None, channel: str = "all",
            now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    q = select(Lead).where(Lead.origin == "app")
    if frm:
        q = q.where(Lead.created_date >= frm)
    if to:
        q = q.where(Lead.created_date <= to)
    if segment and segment != "all":
        q = q.where(Lead.segment == segment)
    leads = list(db.scalars(q))
    if channel in ("self_serve", "assisted"):
        assisted = _assisted_ids(db, leads)
        leads = [l for l in leads if (l.lead_id in assisted) == (channel == "assisted")]
    n = len(leads)
    by_biz = {l.business_id: l for l in leads if l.business_id}
    orders = list(db.scalars(select(Order).where(Order.business_id.in_(by_biz)))) if by_biz else []
    live = {o.id: o for o in orders if o.state == "LIVE"}
    out: dict = {"_n": n, "_orders": len(orders), "_activated": len(live)}

    out["lead_to_activation"] = round(len(live) / n, 3) if n else None

    starts = {}
    for l in leads:
        c = db.scalars(select(Conversation.created_at).where(Conversation.lead_id == l.lead_id).order_by(Conversation.created_at)).first()
        starts[l.lead_id] = c or (l.created_date + "T00:00:00+00:00" if l.created_date else None)
    spans = []
    for o in live.values():
        at = db.scalar(select(OrderEvent.created_at).where(OrderEvent.order_id == o.id, OrderEvent.to_state == "LIVE").order_by(OrderEvent.id.desc()))
        start = starts.get(by_biz[o.business_id].lead_id)
        if at and start:
            spans.append(_days(start, at))
    out["days_to_activate"] = round(mean(spans), 1) if spans else None

    costs = cost_per_lead(db)
    spend = sum(costs.get(l.lead_source, costs["_default"]) or 0 for l in leads)
    out["cac_per_activation"] = round(spend / len(live)) if live else None
    out["_spend"] = round(spend)

    six_months_ago = (now - timedelta(days=182)).date().isoformat()
    mature = [l for l in leads if l.outcome == "Activated" and l.activated_date and l.activated_date <= six_months_ago]
    out["churn_6m"] = round(sum(1 for l in mature if l.churned_within_6_months == "Y") / len(mature), 3) if mature else None
    first_live = min((l.activated_date for l in leads if l.activated_date), default=None)
    out["_churn_ready_on"] = (date.fromisoformat(first_live) + timedelta(days=182)).isoformat() if first_live else None

    active = [o for o in orders if o.state != "CANCELLED"]
    chases = db.scalar(select(func.count()).select_from(Escalation).where(Escalation.order_id.in_([o.id for o in active]),
                                                                          Escalation.trigger == "user_request")) if active else 0
    out["chase_calls_per_customer"] = round(chases / len(active), 2) if active else None
    out["_chases"] = chases

    ids = [o.id for o in orders]
    reached = lambda st: set(db.scalars(select(OrderEvent.order_id).where(OrderEvent.order_id.in_(ids), OrderEvent.to_state == st))) if ids else set()
    consented, verified = reached("CONSENT_GIVEN"), reached("KYC_VERIFIED")
    out["kyc_completion"] = round(len(verified & consented) / len(consented), 3) if consented else None

    res = db.execute(select(Escalation.created_at, Escalation.resolved_at).where(Escalation.resolved_at.is_not(None))).all()
    hours = [_days(a, b) * 24 for a, b in res if a and b]
    out["escalation_resolution_hours"] = round(mean(hours), 1) if hours else None
    return out


def _note(key: str, cur: dict, base: dict) -> str:
    n, orders, act = cur["_n"], cur["_orders"], cur["_activated"]
    return {
        "lead_to_activation": f"{act} of {n} app leads live" if n else "No app leads yet",
        "days_to_activate": f"average over {act} live customers" if act else "No app customer is live yet",
        "cac_per_activation": f"Rs {cur['_spend']:,} lead cost over {act} activations" if act else "No activations yet",
        "churn_6m": (f"First app customers reach 6 months on {cur['_churn_ready_on']}" if cur["_churn_ready_on"] else "Needs live customers")
                    if cur["churn_6m"] is None else "",
        "chase_calls_per_customer": f"{cur['_chases']} 'talk to a person' requests on {orders} orders" if orders else "No orders yet",
        "kyc_completion": "of orders that gave consent",
        "escalation_resolution_hours": "created to resolved",
    }[key]


def metrics(db: Session, frm: str | None = None, to: str | None = None, segment: str | None = None, channel: str = "all") -> dict:
    base, cur = baseline(db), current(db, frm, to, segment, channel)
    items = []
    for key, (label, target, unit, better) in META.items():
        items.append({"key": key, "label": label, "baseline": base[key], "target": target, "current": cur[key], "unit": unit,
                      "better": better, "note": _note(key, cur, base), "strip": key in STRIP})
    return {"metrics": items, "baseline_period": "Apr-Jun 2026 (imported leads)", "baseline_leads": base["_n"],
            "app_leads": cur["_n"], "app_orders": cur["_orders"], "filters": {"from": frm, "to": to, "segment": segment or "all", "channel": channel}}
