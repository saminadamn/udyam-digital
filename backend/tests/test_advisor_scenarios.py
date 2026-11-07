"""15 judge-style advisor scenarios (DESIGN.md D6.1 test_advisor_scenarios.py), written the way a judge would type: free text,
typos, Hindi and other scripts, asks for things the business can't have. Every one must end in a bundle the rules engine accepts
and a short, plain explanation with the price in it. Results are also written to docs/advisor_scenarios.md for the report."""
import re
from pathlib import Path

import pytest

from tests.test_advisor import CODE, login, run_conversation

CONNECTIONS = {"P01", "P02", "P03", "P04", "P05", "P06"}
# Active: 32TTNXB7384T1ZW (Kerala), 33MFTXS9954Q1Z9 (Tamil Nadu). Cancelled: 29OKAXP4077P1ZL. Suspended: 27KYVXC5489I1ZX.
S = [
    dict(id="01_tier2_kirana_no_gstin", lang="en", why="tier 2, no GSTIN, wants WhatsApp: must refuse P15 with an unlock",
         answers=["kirana store", "me and 2 helpers, so 3 people", "Patna", "no gst", "phone hotspot", "upi payments and whatsapp for customers"],
         expect=dict(segment="Micro retail & services", tier=2, gst="None", blocked={"P15"}, includes={"P19"})),
    dict(id="02_five_site_restaurant_chain", lang="en", why="5 outlets, active GSTIN: multi-site bundle, one connection per site",
         answers=["We own a chain of 5 restaurants", "5 outlets and 45 staff", "Bengaluru", "33MFTXS9954Q1Z9", "business broadband",
                  "billing, guest wifi and cctv cameras"],
         expect=dict(segment="Small multi-site businesses", tier=1, gst="Active", blocked=set(), includes={"P19", "P22", "P23"}, sites=5, per_site={"P19": 5})),
    dict(id="03_one_person_salon", lang="en", why="the smallest possible business: 1 person, tier 2",
         answers=["I run a beauty salon", "just 1, only me", "Indore", "don't have one", "mobile data", "UPI"],
         expect=dict(segment="Micro retail & services", tier=2, gst="None", blocked=set(), includes={"P19"}, employees=1)),
    dict(id="04_manufacturer_wants_iot", lang="en", why="30-person factory with GSTIN asks for machine monitoring and a firewall",
         answers=["we manufacture auto parts", "30 workers", "Ludhiana", "32TTNXB7384T1ZW", "leased line", "machine monitoring sensors and a firewall"],
         expect=dict(segment="Small manufacturers", tier=2, gst="Active", blocked=set(), includes={"P24", "P21"})),
    dict(id="05_small_factory_iot_ineligible", lang="en", why="IoT needs 10+ employees: 6-person unit must be refused with a reason",
         answers=["small workshop, we make furniture", "6 people", "Nagpur", "32TTNXB7384T1ZW", "home broadband", "machine sensors"],
         expect=dict(segment="Small manufacturers", tier=2, gst="Active", blocked={"P24"}, includes=set())),
    dict(id="06_two_shops_want_sdwan", lang="en", why="SD-WAN needs 3+ sites: 2 branches must be refused",
         answers=["2 branches of our mobile shop", "2 branches, 9 staff", "Surat", "33MFTXS9954Q1Z9", "business broadband", "sd-wan and billing"],
         expect=dict(segment="Small multi-site businesses", tier=2, gst="Active", blocked={"P10"}, includes={"P19"}, sites=2)),
    dict(id="07_hindi_medical_store", lang="hi", why="Hindi free text throughout",
         answers=["मेरा मेडिकल स्टोर है", "4 लोग", "कानपुर", "GST नहीं है", "घर का ब्रॉडबैंड", "UPI और बिलिंग"],
         expect=dict(segment="Micro retail & services", tier=2, gst="None", blocked=set(), includes={"P19"})),
    dict(id="08_cancelled_gstin_wants_whatsapp", lang="en", why="GSTIN found but Cancelled: GST-only products blocked",
         answers=["Shop or small service", "1-5 people", "Mysuru", "29OKAXP4077P1ZL", "Home broadband", "WhatsApp for customers, CCTV cameras"],
         expect=dict(segment="Micro retail & services", tier=2, gst="Cancelled", blocked={"P15"}, includes={"P23"})),
    dict(id="09_ca_firm_suspended_wants_tollfree", lang="en", why="Suspended GSTIN asks for a toll-free number",
         answers=["chartered accountant firm", "8 people", "Mumbai", "27KYVXC5489I1ZX", "Business broadband", "toll free number, business email"],
         expect=dict(segment="Professional offices", tier=1, gst="Suspended", blocked={"P13"}, includes={"P16"})),
    dict(id="10_tiny_office_wants_telephony", lang="en", why="Cloud telephony needs 3+ employees: 2-person office refused",
         answers=["Clinic or office", "2 people", "Delhi", "32TTNXB7384T1ZW", "Business broadband", "phone lines"],
         expect=dict(segment="Professional offices", tier=1, gst="Active", blocked={"P12"}, includes=set(), employees=2)),
    dict(id="11_coaching_centre_tier1", lang="en", why="25-person coaching centre, active GSTIN, wants calls and email",
         answers=["coaching centre", "25 teachers and staff", "Hyderabad", "33MFTXS9954Q1Z9", "fibre", "phone lines, business email, data backup"],
         expect=dict(segment="Professional offices", tier=1, gst="Active", blocked=set(), includes={"P12", "P16", "P17"})),
    dict(id="12_messy_caps_and_typos", lang="en", why="caps, abbreviations, typos",
         answers=["CLINIC", "abt 7 ppl", "pune.", "NO GST", "BROADBAND AT HOME", "emial and back up"],
         expect=dict(segment="Professional offices", tier=1, gst="None", blocked=set(), includes={"P17"})),
    dict(id="13_tamil_chips_textile_unit", lang="ta", why="Tamil chips for a manufacturer",
         answers=[("chips_type", 3), ("chips_team", 2), "Coimbatore", "33MFTXS9954Q1Z9", ("chips_internet", 3), ("chips_needs", 2, 9)],
         expect=dict(segment="Small manufacturers", tier=2, gst="Active", blocked=set(), includes={"P23", "P20"})),
    dict(id="14_marathi_bakery_add_gst_later", lang="mr", why="Marathi chips, says GST later: treated as no GSTIN for eligibility",
         answers=[("chips_type", 0), ("chips_team", 0), "Nashik", ("chips_gst", 1), ("chips_internet", 0), ("chips_needs", 0, 1)],
         expect=dict(segment="Micro retail & services", tier=2, gst="None", blocked={"P15"}, includes={"P19"})),
    dict(id="15_gujarati_three_pharmacies", lang="gu", why="Gujarati, 3 pharmacy branches, active GSTIN, wants WhatsApp and Wi-Fi",
         answers=[("chips_type", 2), ("chips_team_chain", 0), "Vadodara", "33MFTXS9954Q1Z9", ("chips_internet", 2), ("chips_needs", 1, 4)],
         expect=dict(segment="Small multi-site businesses", tier=2, gst="Active", blocked=set(), includes={"P15", "P22"})),
]
RESULTS: dict[str, str] = {}


@pytest.mark.parametrize("sc", S, ids=[s["id"] for s in S])
def test_scenario(sc, client, catalogue):
    from app.rules.engine import Profile, validate_bundle

    h = login(client, f"+9195{int(sc['id'][:2]):08d}", sc["lang"])
    cid, questions, last = run_conversation(client, h, sc["lang"], sc["answers"])
    assert last["status"] == "ready_to_recommend", last
    prof, exp = last["profile"], sc["expect"]
    assert (prof["segment"], prof["city_tier"], prof["gst_status"] or "None") == (exp["segment"], exp["tier"], exp["gst"]), prof
    for k in ("sites", "employees"):
        if k in exp:
            assert prof[k] == exp[k], (k, prof)
    r = client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h)
    assert r.status_code == 200, r.text
    rec = r.json()
    core = [(i["product_id"], i["qty"]) for i in rec["items"]]
    addons = [(i["product_id"], i["qty"]) for i in rec["addons"]]
    profile = Profile(segment=prof["segment"], city_tier=prof["city_tier"], employees=prof["employees"], sites=prof["sites"],
                      gst_status=prof["gst_status"] or "None", gstin_valid=prof["gst_status"] not in (None, "None"))
    assert validate_bundle(profile, core + addons, catalogue) == [], "bundle breaks a catalogue rule"
    ids = {p for p, _ in core} | {p for p, _ in addons}
    assert CONNECTIONS & {p for p, _ in core}, "every bundle needs a connection"
    assert exp["includes"] <= ids, (exp["includes"], ids)
    for pid, qty in exp.get("per_site", {}).items():
        assert dict(core + addons)[pid] == qty
    assert {b["product_id"] for b in rec["blocked"]} == exp["blocked"], rec["blocked"]
    for b in rec["blocked"]:
        assert b["reasons"] and b["unlock"] and not CODE.search(b["unlock"])
    if exp["gst"] != "Active":
        assert not any(catalogue[p].requires_gstin for p in ids)
    text = rec["explanation"]
    assert not CODE.search(text) and f"{rec['monthly_total_inr']:,}" in text
    assert 1 <= len([s for s in re.split(r"[.!?।]\s*", text) if s.strip()]) <= 3
    assert len(rec["speak"]) <= 180
    RESULTS[sc["id"]] = (f"| {sc['id']} | {sc['lang']} | {sc['why']} | {rec['bundle_name']}: "
                         f"{', '.join(i['name'] for i in rec['items'])} | Rs {rec['monthly_total_inr']:,} | "
                         f"{'; '.join(b['name'] + ': ' + b['reasons'][0] for b in rec['blocked']) or '-'} |")


def test_write_report():
    if len(RESULTS) < len(S):
        pytest.skip("run the whole file to write the report")
    out = Path(__file__).resolve().parents[2] / "docs" / "advisor_scenarios.md"
    out.write_text("# Advisor: 15 judge-style scenarios\n\nGenerated by `pytest tests/test_advisor_scenarios.py`. Every bundle passed "
                   "`validate_bundle`; every explanation names the monthly price in at most 3 sentences with no product codes.\n\n"
                   "| scenario | lang | what it tests | bundle (core items) | monthly | refused, with reason |\n|---|---|---|---|---|---|\n"
                   + "\n".join(RESULTS[s["id"]] for s in S) + "\n", encoding="utf-8")


@pytest.mark.parametrize("said,seg,want", [("हम तीन लोग हैं", None, (3, 1)), ("three people", None, (3, 1)), ("just me", None, (1, 1)),
                                           ("five branches and twenty staff", "multi", (20, 5)), ("पाँच लोग", None, (5, 1))])
def test_spoken_number_words(said, seg, want):
    from app.advisor.parse import parse_team

    assert parse_team(said, "en", seg) == want
