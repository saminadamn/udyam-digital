import json
import random
from pathlib import Path

import pytest

from app.advisor.rules import Profile, build_bundle, default_bundle, eligible_products, validate_bundle
from app.pricing.service import price
from app.rules.engine import SEGMENT_KEY

SEGS = list(SEGMENT_KEY)
BIG = dict(city_tier=1, employees=200, sites=12, gst_status="Active", gstin_valid=True)


def rules_of(violations):
    return {v.rule for v in violations}


def with_base(pid, catalogue):
    req = catalogue[pid].requires_one_of
    return [(pid, 1)] + ([(req[0], 1)] if req else [])


@pytest.mark.parametrize("seg", SEGS)
def test_big_business_can_buy_every_product_with_its_base(seg, catalogue):
    for pid in catalogue:
        assert validate_bundle(Profile(seg, **BIG), with_base(pid, catalogue), catalogue) == []


def test_city_tier_rule_for_every_product(catalogue):
    for pid, p in catalogue.items():
        for tier in (1, 2):
            v = validate_bundle(Profile(SEGS[0], **(BIG | {"city_tier": tier})), with_base(pid, catalogue), catalogue)
            assert ("CITY_TIER" in rules_of(v)) == (tier not in p.city_tiers), (pid, tier)


def test_min_employees_rule_for_every_product(catalogue):
    for pid, p in catalogue.items():
        below = validate_bundle(Profile(SEGS[1], **(BIG | {"employees": p.min_employees - 1})), with_base(pid, catalogue), catalogue) if p.min_employees > 1 else []
        at = validate_bundle(Profile(SEGS[1], **(BIG | {"employees": p.min_employees})), with_base(pid, catalogue), catalogue)
        if p.min_employees > 1:
            assert "MIN_EMPLOYEES" in rules_of(below), pid
        assert "MIN_EMPLOYEES" not in rules_of(at), pid


def test_min_sites_rule_for_every_product(catalogue):
    for pid, p in catalogue.items():
        at = validate_bundle(Profile(SEGS[2], **(BIG | {"sites": p.min_sites})), with_base(pid, catalogue), catalogue)
        assert "MIN_SITES" not in rules_of(at), pid
        if p.min_sites > 1:
            below = validate_bundle(Profile(SEGS[2], **(BIG | {"sites": p.min_sites - 1})), with_base(pid, catalogue), catalogue)
            assert "MIN_SITES" in rules_of(below), pid


@pytest.mark.parametrize("status,valid,allowed", [
    ("Active", True, True),
    ("Active", False, False),
    ("Cancelled", True, False),
    ("Suspended", True, False),
    ("None", False, False),
])
def test_gstin_rule_needs_valid_and_active(status, valid, allowed, catalogue):
    gst_products = [pid for pid, p in catalogue.items() if p.requires_gstin]
    assert len(gst_products) == 10
    for pid in catalogue:
        v = validate_bundle(Profile(SEGS[3], **(BIG | {"gst_status": status, "gstin_valid": valid})), with_base(pid, catalogue), catalogue)
        flagged = "GSTIN_REQUIRED" in rules_of(v)
        assert flagged == (pid in gst_products and not allowed), (pid, status, valid)


def test_dependency_rule_for_every_product(catalogue):
    for pid, p in catalogue.items():
        alone = validate_bundle(Profile(SEGS[2], **BIG), [(pid, 1)], catalogue)
        assert ("DEPENDENCY" in rules_of(alone)) == bool(p.requires_one_of), pid
        for base in p.requires_one_of:
            ok = validate_bundle(Profile(SEGS[2], **BIG), [(pid, 1), (base, 1)], catalogue)
            assert "DEPENDENCY" not in rules_of(ok), (pid, base)


def test_every_rejection_has_a_reason(catalogue):
    v = validate_bundle(Profile(SEGS[0], city_tier=2, employees=1, sites=1), [(pid, 1) for pid in catalogue], catalogue)
    assert v and all(x.message and x.rule and x.product_id for x in v)


def test_structural_errors(catalogue):
    v = validate_bundle(Profile(**({"segment": SEGS[0]} | BIG)), [("P01", 1), ("P01", 1), ("P99", 1), ("P07", 0)], catalogue)
    assert {"DUPLICATE", "UNKNOWN_PRODUCT", "BAD_QUANTITY"} <= rules_of(v)


MUST_REFUSE = [
    ("WhatsApp API without a GSTIN", dict(city_tier=2, employees=3, sites=1), [("P01", 1), ("P15", 1)], "GSTIN_REQUIRED"),
    ("Biz Fibre 1G in a tier 2 city", dict(city_tier=2, employees=8, sites=1, gst_status="Active", gstin_valid=True), [("P03", 1)], "CITY_TIER"),
    ("Cloud CCTV with no connection", dict(city_tier=1, employees=2, sites=1), [("P23", 2)], "DEPENDENCY"),
    ("SD-WAN for only 2 sites", dict(city_tier=1, employees=15, sites=2, gst_status="Active", gstin_valid=True), [("P02", 2), ("P10", 2)], "MIN_SITES"),
    ("Leased line on a cancelled GSTIN", dict(city_tier=1, employees=40, sites=1, gst_status="Cancelled", gstin_valid=True), [("P05", 1)], "GSTIN_REQUIRED"),
    ("Static IP on a leased line", dict(city_tier=1, employees=40, sites=1, gst_status="Active", gstin_valid=True), [("P05", 1), ("P11", 1)], "DEPENDENCY"),
    ("Cloud Telephony for a 2-person office", dict(city_tier=1, employees=2, sites=1, gst_status="Active", gstin_valid=True), [("P01", 1), ("P12", 1)], "MIN_EMPLOYEES"),
    ("Machine IoT for a 6-person unit", dict(city_tier=2, employees=6, sites=1, gst_status="Active", gstin_valid=True), [("P01", 1), ("P24", 2)], "MIN_EMPLOYEES"),
    ("Toll-free on a suspended GSTIN", dict(city_tier=1, employees=5, sites=1, gst_status="Suspended", gstin_valid=True), [("P13", 1)], "GSTIN_REQUIRED"),
]


@pytest.mark.parametrize("name,prof,items,rule", MUST_REFUSE, ids=[m[0] for m in MUST_REFUSE])
def test_must_refuse(name, prof, items, rule, catalogue):
    assert rule in rules_of(validate_bundle(Profile(SEGS[1], **prof), items, catalogue))


def test_starter_bundles_from_phase1_pass(catalogue):
    spec = json.loads((Path(__file__).resolve().parents[1] / "app" / "rules" / "bundles.json").read_text())
    checked = 0
    for b in spec["bundles"]:
        seg = next(s for s, k in SEGMENT_KEY.items() if k == b["key"])
        for prof in b["profiles"]:
            p = Profile(seg, prof["city_tier"], prof["employees"], prof["sites"], prof["gst_status"], prof["gst_status"] == "Active")
            d = default_bundle(p, catalogue)
            assert validate_bundle(p, d["core"], catalogue) == [], (b["name"], prof["label"])
            non_gst_addons = [a for a in d["addons"] if not catalogue[a[0]].requires_gstin or p.gst_ok]
            assert validate_bundle(p, d["core"] + non_gst_addons, catalogue) == [], (b["name"], prof["label"])
            checked += 1
    assert checked == 8


def test_phase1_prices(catalogue):
    office = Profile(SEGS[1], 2, 13, 1, "Active", True)
    assert price(default_bundle(office, catalogue)["core"], "prof", catalogue)["monthly_total_inr"] == 6055
    shop = Profile(SEGS[0], 1, 3, 1, "Active", True)
    assert price(default_bundle(shop, catalogue)["core"], "micro", catalogue)["monthly_total_inr"] == 1597
    chain = Profile(SEGS[2], 2, 61, 7, "Active", True)
    assert price(default_bundle(chain, catalogue)["core"], "multi", catalogue)["monthly_total_inr"] == 19575
    factory = Profile(SEGS[3], 2, 74, 1, "Active", True)
    assert price(default_bundle(factory, catalogue)["core"], "mfg", catalogue)["monthly_total_inr"] == 15430


def test_eligible_products_explains_every_exclusion(catalogue):
    r = eligible_products(Profile(SEGS[0], city_tier=2, employees=2, sites=1), catalogue)
    assert set(r["eligible"]) | set(r["ineligible"]) == set(catalogue)
    assert "P03" in r["ineligible"] and "P15" in r["ineligible"] and "P01" in r["eligible"]
    assert r["eligible"]["P23"]["requires_one_of"]
    assert all(r["ineligible"][pid] for pid in r["ineligible"])


def test_build_bundle_never_returns_an_invalid_bundle(catalogue):
    rng = random.Random(7)
    needs = ["pos", "whatsapp", "cctv", "email", "wifi", "backup", "website", "calls", "tollfree", "sms", "security", "failover",
             "static_ip", "fleet", "machines", "sdwan", "firewall"]
    for _ in range(2000):
        status = rng.choice(["Active", "Cancelled", "Suspended", "None"])
        p = Profile(rng.choice(SEGS), rng.choice([1, 2]), rng.choice([1, 2, 3, 5, 9, 10, 14, 25, 60, 150]), rng.choice([1, 1, 2, 3, 7, 12]),
                    status, status != "None" and rng.random() > 0.2, rng.sample(needs, rng.randint(0, 5)))
        b = build_bundle(p, catalogue)
        assert b["violations"] == [], (p, b["violations"])
        assert any(pid in {"P01", "P02", "P03", "P04", "P05", "P06"} for pid, _ in b["core"]), p
        for pid in b["blocked"]:
            assert pid not in {x for x, _ in b["core"] + b["addons"]}


def test_build_bundle_blocks_wanted_gst_product_with_reason(catalogue):
    b = build_bundle(Profile(SEGS[0], 2, 3, 1, "None", False, ["whatsapp", "pos"]), catalogue)
    assert "P15" in b["blocked"] and b["blocked"]["P15"][0]["rule"] == "GSTIN_REQUIRED"
    assert "P19" in {pid for pid, _ in b["core"]}
    assert b["wanted_blocked"] == ["P15"]


def test_small_manufacturer_falls_back_from_leased_line(catalogue):
    b = build_bundle(Profile(SEGS[3], 2, 6, 1, "Active", True), catalogue)
    links = [pid for pid, _ in b["core"] if pid in {"P01", "P02", "P03", "P04", "P05", "P06"}]
    assert links and links[0] != "P05" and "P05" not in {pid for pid, _ in b["core"]}


# ---- plan options (essential / recommended / quick / grow / secure / complete) ----
from app.advisor.rules import plan_options  # noqa: E402

PROFILES = [
    dict(city_tier=1, employees=3, sites=1, gst_status="Active", gstin_valid=True),
    dict(city_tier=2, employees=2, sites=1, gst_status="None", gstin_valid=False),
    dict(city_tier=2, employees=13, sites=1, gst_status="Active", gstin_valid=True),
    dict(city_tier=2, employees=61, sites=7, gst_status="Active", gstin_valid=True),
    dict(city_tier=3, employees=74, sites=1, gst_status="Active", gstin_valid=True),
    dict(city_tier=2, employees=74, sites=1, gst_status="Active", gstin_valid=True),
]


@pytest.mark.parametrize("seg", SEGS)
@pytest.mark.parametrize("p", PROFILES)
def test_every_plan_option_passes_the_rules_and_options_are_distinct(seg, p, catalogue):
    prof = Profile(seg, **p)
    bundle = build_bundle(prof, catalogue)
    if not bundle["core"]:
        pytest.skip("no plan is sold here; the advisor hands this business to a person")
    opts = plan_options(prof, catalogue, bundle)
    keys = [o["key"] for o in opts]
    assert "recommended" in keys and len(keys) == len(set(keys))
    assert next(o for o in opts if o["key"] == "recommended")["core"] == bundle["core"]
    cores = [frozenset(o["core"]) for o in opts]
    assert len(cores) == len(set(cores)), "two options with the same plan"
    elig = eligible_products(prof, catalogue)["eligible"]
    for o in opts:
        assert validate_bundle(prof, o["core"] + o["addons"], catalogue) == [], o["key"]
        assert all(pid in elig for pid, _ in o["core"] + o["addons"]), o["key"]


def test_options_cover_price_speed_and_scope(catalogue):
    prof = Profile("Professional offices", **PROFILES[2])
    opts = {o["key"]: o for o in plan_options(prof, catalogue, build_bundle(prof, catalogue))}
    assert {"essential", "recommended", "quick", "grow", "secure", "complete"} <= set(opts)
    cost = {k: price(o["core"], prof.key, catalogue) for k, o in opts.items()}
    assert cost["essential"]["monthly_total_inr"] < cost["recommended"]["monthly_total_inr"] < cost["complete"]["monthly_total_inr"]
    assert cost["quick"]["max_install_days"] < cost["recommended"]["max_install_days"]


def test_no_gstin_means_no_gstin_only_products_in_any_option(catalogue):
    prof = Profile("Micro retail & services", **PROFILES[1])
    for o in plan_options(prof, catalogue, build_bundle(prof, catalogue)):
        assert not any(catalogue[pid].requires_gstin for pid, _ in o["core"] + o["addons"]), o["key"]


def test_leased_line_is_never_swapped_for_5g(catalogue):
    prof = Profile("Small manufacturers", **PROFILES[5])
    bundle = build_bundle(prof, catalogue)
    assert any(pid in ("P05", "P06") for pid, _ in bundle["core"]), "expected a leased line for this factory"
    assert "quick" not in {o["key"] for o in plan_options(prof, catalogue, bundle)}
