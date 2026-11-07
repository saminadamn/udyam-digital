import json
import re

import pytest

from app.i18n import text

CODE = re.compile(r"\bP\s?\d{2}\b")


def chips(lang, key, *idx):
    labels = text(lang, key)
    return ", ".join(labels[i] for i in idx)


PROFILES = [
    dict(id="1_micro_t2_no_gst_hotspot", lang="en",
         answers=["Shop or small service", "1-5 people", "Lucknow", "No GST yet", "Mobile hotspot", "UPI and billing, WhatsApp for customers, CCTV cameras"],
         expect=dict(segment="Micro retail & services", tier=2, gst="None", blocked={"P15"}, includes={"P19", "P23"})),
    dict(id="2_micro_t1_active_gst_hi", lang="hi",
         answers=[("chips_type", 0), ("chips_team", 0), "Mumbai", "मेरा GST नंबर 03PJNXS4821G1ZB है", ("chips_internet", 1), ("chips_needs", 1)],
         expect=dict(segment="Micro retail & services", tier=1, gst="Active", blocked=set(), includes={"P15"})),
    dict(id="3_prof_t1_active_gst_freetext", lang="en",
         answers=["We run a dental clinic", "12 people work here", "Pune", "32TTNXB7384T1ZW", "Business broadband", "Business email, Data backup, Phone lines"],
         expect=dict(segment="Professional offices", tier=1, gst="Active", blocked=set(), includes={"P16", "P17", "P12"})),
    dict(id="4_prof_t2_small_no_gst", lang="en",
         answers=["Clinic or office", "4", "Indore", "No GST yet", "Home broadband", "Phone lines, Business email"],
         expect=dict(segment="Professional offices", tier=2, gst="None", blocked={"P12"}, includes={"P16"})),
    dict(id="5_multi_t1_big_active", lang="en",
         answers=["Chain with branches", "8+ branches, 60+ people", "Delhi", "32TTNXB7384T1ZW", "Business broadband", "Guest Wi-Fi, CCTV cameras, UPI and billing"],
         expect=dict(segment="Small multi-site businesses", tier=1, gst="Active", blocked=set(), includes={"P22", "P23", "P19"}, sites=8)),
    dict(id="6_multi_t2_small_freetext", lang="en",
         answers=["We have a chain of pharmacies", "3 branches and 15 staff", "Jaipur", "03PJNXS4821G1ZB", "Mobile hotspot", "Done"],
         expect=dict(segment="Small multi-site businesses", tier=2, gst="Active", blocked=set(), includes=set(), sites=3)),
    dict(id="7_mfg_t2_big_leased", lang="en",
         answers=["Factory or workshop", "More than 50", "Coimbatore", "32TTNXB7384T1ZW", "Leased line", "Virus protection, Data backup"],
         expect=dict(segment="Small manufacturers", tier=2, gst="Active", blocked=set(), includes={"P05", "P20", "P17"})),
    dict(id="8_mfg_t2_small_no_gst", lang="en",
         answers=["Factory or workshop", "6-20 people", "Nagpur", "I'll add it later", "Nothing yet", "CCTV cameras"],
         expect=dict(segment="Small manufacturers", tier=2, gst="None", blocked=set(), includes={"P23"}, excludes={"P05", "P06"})),
    dict(id="9_micro_t1_cancelled_gst_ta", lang="ta",
         answers=[("chips_type", 0), ("chips_team", 0), "Chennai", "29OKAXP4077P1ZL", ("chips_internet", 0), ("chips_needs", 1, 0)],
         expect=dict(segment="Micro retail & services", tier=1, gst="Cancelled", blocked={"P15"}, includes={"P19"})),
    dict(id="10_prof_t2_suspended_gst_mr", lang="mr",
         answers=[("chips_type", 1), ("chips_team", 1), "Nashik", "23QYBXS1811Q1ZD", ("chips_internet", 2), ("chips_needs", 8, 3)],
         expect=dict(segment="Professional offices", tier=2, gst="Suspended", blocked={"P13"}, includes={"P16"})),
]


def login(client, phone, lang):
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": r.json()["dev_code"], "language": lang})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def run_conversation(client, h, lang, answers):
    r = client.post("/api/v1/advisor/conversations", json={"language": lang}, headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["conversation_id"]
    questions = [r.json()["message"]]
    for a in answers:
        content = chips(lang, a[0], *a[1:]) if isinstance(a, tuple) else a
        r = client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": content}, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["escalation"] is None, (content, body)
        if body["status"] != "ready_to_recommend":
            questions.append(body["message"])
    return cid, questions, body


@pytest.mark.parametrize("p", PROFILES, ids=[p["id"] for p in PROFILES])
def test_profile_gets_valid_bundle(p, client, catalogue):
    from app.rules.engine import Profile, validate_bundle

    h = login(client, f"+9198{abs(hash(p['id'])) % 10**8:08d}", p["lang"])
    cid, questions, last = run_conversation(client, h, p["lang"], p["answers"])
    assert last["status"] == "ready_to_recommend", last
    assert len({q.get("field") for q in questions}) <= 6
    prof = last["profile"]
    exp = p["expect"]
    assert prof["segment"] == exp["segment"]
    assert prof["city_tier"] == exp["tier"]
    assert (prof["gst_status"] or "None") == exp["gst"]
    if "sites" in exp:
        assert prof["sites"] == exp["sites"]

    r = client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h)
    assert r.status_code == 200, r.text
    rec = r.json()
    core = [(i["product_id"], i["qty"]) for i in rec["items"]]
    addons = [(i["product_id"], i["qty"]) for i in rec["addons"]]
    profile = Profile(segment=prof["segment"], city_tier=prof["city_tier"], employees=prof["employees"], sites=prof["sites"],
                      gst_status=prof["gst_status"] or "None", gstin_valid=prof["gst_status"] not in (None, "None"))
    assert validate_bundle(profile, core, catalogue) == []
    assert validate_bundle(profile, core + addons, catalogue) == []
    ids = {pid for pid, _ in core}
    assert any(pid in {"P01", "P02", "P03", "P04", "P05", "P06"} for pid in ids), "every bundle needs a connection"
    assert exp["includes"] <= ids, (exp["includes"], ids)
    assert not (exp.get("excludes", set()) & ids)
    assert {b["product_id"] for b in rec["blocked"]} == exp["blocked"]
    for b in rec["blocked"]:
        assert b["unlock"] and not CODE.search(b["unlock"])
    if exp["gst"] != "Active":
        assert not any(catalogue[pid].requires_gstin for pid in ids | {pid for pid, _ in addons})
    assert rec["monthly_total_inr"] > 0
    for t in [rec["explanation"]] + [i["why"] for i in rec["items"] + rec["addons"]] + [i["what_it_does"] for i in rec["items"]]:
        assert not CODE.search(t), t
    assert f"{rec['monthly_total_inr']:,}" in rec["explanation"]
    sentences = [s for s in re.split(r"[.!?।]\s*", rec["explanation"]) if s.strip()]
    assert 1 <= len(sentences) <= 3


def test_profile_incomplete(client):
    h = login(client, "+919800000011", "en")
    cid = client.post("/api/v1/advisor/conversations", json={"language": "en"}, headers=h).json()["conversation_id"]
    r = client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "PROFILE_INCOMPLETE"


def test_invalid_gstin_is_reasked_not_accepted(client):
    h = login(client, "+919800000012", "en")
    cid = client.post("/api/v1/advisor/conversations", json={"language": "en"}, headers=h).json()["conversation_id"]
    for a in ["Shop or small service", "1-5 people", "Surat"]:
        client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": a}, headers=h)
    r = client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "24ABCDE1234F1Z9"}, headers=h).json()
    assert r["message"]["field"] == "gst" and "doesn't look right" in r["message"]["content"]
    assert r["failed_turns"] == 1 and r["escalation"] is None


def test_two_failed_turns_escalate_to_agent(client):
    h = login(client, "+919800000013", "en")
    cid = client.post("/api/v1/advisor/conversations", json={"language": "en"}, headers=h).json()["conversation_id"]
    client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "Shop or small service"}, headers=h)
    r1 = client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "hmm"}, headers=h).json()
    assert r1["escalation"] is None and r1["failed_turns"] == 1
    r2 = client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "not sure"}, headers=h).json()
    assert r2["escalation"] and r2["escalation"]["agent_name"] and r2["status"] == "escalated"


def test_asking_for_a_person_escalates_immediately(client):
    h = login(client, "+919800000014", "hi")
    cid = client.post("/api/v1/advisor/conversations", json={"language": "hi"}, headers=h).json()["conversation_id"]
    r = client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "I want to talk to a person"}, headers=h).json()
    assert r["escalation"] and r["status"] == "escalated"


class RogueLLM:
    name = "rogue"

    def phrase_question(self, field, lang, profile, default):
        return "Buy P15 now!"

    def extract(self, field, content, lang, profile):
        return None

    def choose(self, profile, eligible, suggested):
        return {"core": ["P15", "P03", "P11", "P99"] + suggested["core"], "addons": ["P10"]}

    def explain(self, context, lang, default):
        return "Get P15 WhatsApp and Managed SD-WAN for Rs 99 only."


def test_rules_engine_overrides_a_rogue_llm(client, catalogue, monkeypatch):
    from app.advisor import service
    from app.rules.engine import Profile, validate_bundle

    monkeypatch.setattr(service, "get_provider", lambda: RogueLLM())
    h = login(client, "+919800000015", "en")
    answers = ["Shop or small service", "1-5 people", "Lucknow", "No GST yet", "Mobile hotspot", "CCTV cameras"]
    cid, questions, last = run_conversation(client, h, "en", answers)
    assert all("P15" not in q["content"] for q in questions)
    rec = client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h).json()
    ids = {i["product_id"] for i in rec["items"] + rec["addons"]}
    assert not ids & {"P15", "P03", "P99", "P10"}
    prof = last["profile"]
    profile = Profile(segment=prof["segment"], city_tier=2, employees=prof["employees"], sites=prof["sites"])
    assert validate_bundle(profile, [(i["product_id"], i["qty"]) for i in rec["items"] + rec["addons"]], catalogue) == []
    assert not CODE.search(rec["explanation"]) and "Rs 99 " not in rec["explanation"]
    assert "SD-WAN" not in rec["explanation"]
    assert rec["source"] in ("rules", "rules_override", "llm")


def test_messages_are_stored_without_raw_gstin(client):
    from app.db import SessionLocal
    from app.models import Business, Conversation, Message

    h = login(client, "+919800000016", "en")
    answers = ["Clinic or office", "6-20 people", "Pune", "My GST is 32TTNXB7384T1ZW", "Business broadband", "Done"]
    cid, _, _ = run_conversation(client, h, "en", answers)
    client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h)
    with SessionLocal() as db:
        msgs = db.query(Message).filter(Message.conversation_id == cid).all()
        conv = db.get(Conversation, cid)
        biz = db.get(Business, conv.business_id)
        assert all("32TTNXB7384T1ZW" not in m.content for m in msgs)
        assert "32TTNXB7384T1ZW" not in conv.profile_json
        assert biz.gstin_masked.startswith("32") and "32TTNXB7384T1ZW" not in (biz.gstin_masked or "")
        assert biz.gstin_enc and b"32TTNXB7384T1ZW" not in biz.gstin_enc


def test_talk_to_person_label_escalates_in_every_language():
    from app.advisor.parse import parse_team, wants_human
    from tests.conftest import BACKEND

    for lang in ["en", "hi", "mr", "ta", "bn", "kn", "gu", "te"]:
        label = json.load(open(BACKEND.parent / "frontend" / "messages" / f"{lang}.json", encoding="utf-8"))["chat"]["talk_person"]
        assert wants_human(label), (lang, label)
    assert not wants_human("5 व्यक्ति काम करते हैं")
    assert parse_team("5 व्यक्ति काम करते हैं", "hi", "micro")[0] == 5


def test_switching_language_before_answering_restarts_in_new_language(client):
    h = login(client, "+919800000017", "hi")
    a = client.post("/api/v1/advisor/conversations", json={"language": "hi"}, headers=h).json()
    b = client.post("/api/v1/advisor/conversations", json={"language": "ta"}, headers=h).json()
    assert a["conversation_id"] == b["conversation_id"] and not b["resumed"]
    assert b["message"]["quick_replies"][0] == text("ta", "chips_type")[0]
    client.post("/api/v1/advisor/message", json={"conversation_id": b["conversation_id"], "content": text("ta", "chips_type")[0]}, headers=h)
    c = client.post("/api/v1/advisor/conversations", json={"language": "en"}, headers=h).json()
    assert c["resumed"] and c["conversation_id"] == a["conversation_id"]
