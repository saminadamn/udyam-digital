"""Pricing rule (DESIGN.md D2.4 quotes.pricing_rule; documented in docs/PRICING.md).

micro_min_v1   Micro retail & services pay each product's catalogue minimum. The case calls this segment
               very price-sensitive and its median bundle is Rs 2,470 (Phase 1 [F]).
midpoint_v1    Every other segment pays the rounded midpoint of the catalogue min-max range.

Monthly total  = sum(unit price x qty) over selected items.
Setup          = sum(one_time_setup_inr x qty) over selected items, shown separately, paid once.
Contract       = the longest min_contract_months among selected items.
Install days   = the longest typical_install_days among selected items (used for "live in about N days").
"""
from app.rules.engine import Catalogue, Items

RULE_MICRO = "micro_min_v1"
RULE_MID = "midpoint_v1"


def rule_for(segment_key: str) -> str:
    return RULE_MICRO if segment_key == "micro" else RULE_MID


def unit_price(pid: str, segment_key: str, catalogue: Catalogue) -> int:
    p = catalogue[pid]
    price = p.price_min_inr if segment_key == "micro" else round((p.price_min_inr + p.price_max_inr) / 2)
    assert p.price_min_inr <= price <= p.price_max_inr
    return price


def price(items: Items, segment_key: str, catalogue: Catalogue) -> dict:
    lines = []
    for pid, qty in items:
        p = catalogue[pid]
        u = unit_price(pid, segment_key, catalogue)
        lines.append({"product_id": pid, "qty": qty, "unit_price_inr": u, "line_monthly_inr": u * qty, "line_setup_inr": p.setup_fee_inr * qty})
    return {
        "lines": lines,
        "monthly_total_inr": sum(l["line_monthly_inr"] for l in lines),
        "setup_total_inr": sum(l["line_setup_inr"] for l in lines),
        "contract_months": max((catalogue[pid].min_contract_months for pid, _ in items), default=0),
        "max_install_days": max((catalogue[pid].install_days for pid, _ in items), default=0),
        "pricing_rule": rule_for(segment_key),
    }
