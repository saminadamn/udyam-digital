"""Pricing rule (docs/PRICING.md): micro pays catalogue minimum, everyone else the rounded midpoint; totals, setup, contract, install."""
import pytest

from app.pricing.service import RULE_MICRO, RULE_MID, price, rule_for, unit_price

SEGMENTS = ["micro", "prof", "multi", "mfg"]


@pytest.mark.parametrize("seg", SEGMENTS)
def test_unit_price_rule_for_every_product(seg, catalogue):
    for pid, p in catalogue.items():
        u = unit_price(pid, seg, catalogue)
        want = p.price_min_inr if seg == "micro" else round((p.price_min_inr + p.price_max_inr) / 2)
        assert u == want and p.price_min_inr <= u <= p.price_max_inr, pid


def test_totals_setup_contract_and_install(catalogue):
    items = [("P02", 1), ("P08", 3), ("P12", 3), ("P11", 1)]
    out = price(items, "prof", catalogue)
    assert out["monthly_total_inr"] == sum(unit_price(p, "prof", catalogue) * q for p, q in items)
    assert out["setup_total_inr"] == sum(catalogue[p].setup_fee_inr * q for p, q in items)
    assert out["contract_months"] == max(catalogue[p].min_contract_months for p, _ in items)
    assert out["max_install_days"] == max(catalogue[p].install_days for p, _ in items)
    assert out["pricing_rule"] == RULE_MID and [l["line_monthly_inr"] for l in out["lines"]] == [unit_price(p, "prof", catalogue) * q for p, q in items]


def test_phase1_reference_totals(catalogue):
    """Dukaan Digital core Rs 1,597 and Office Pro core Rs 6,055 (analysis/bundles_and_metrics.md)."""
    assert price([("P01", 1), ("P07", 2)], "micro", catalogue)["monthly_total_inr"] == 1597
    assert price([("P02", 1), ("P08", 3), ("P16", 7), ("P20", 6), ("P17", 1)], "prof", catalogue)["monthly_total_inr"] == 6055


def test_rule_names_and_empty_quote(catalogue):
    assert rule_for("micro") == RULE_MICRO and all(rule_for(s) == RULE_MID for s in SEGMENTS[1:])
    out = price([], "prof", catalogue)
    assert (out["monthly_total_inr"], out["setup_total_inr"], out["contract_months"], out["max_install_days"]) == (0, 0, 0, 0)
