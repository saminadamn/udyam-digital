"""Build Phase 5: admin lead dashboard (DESIGN.md D3.8, A2/A3): imported + app leads, propensity, filters, Call and outcome."""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_advisor import chips, login as login_lang
from tests.test_tracker import ADMIN, login

RAW_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]")
AGENT = "+919000000101"


@pytest.fixture(scope="module")
def scored(seeded):
    """The shared test DB is seeded without scores (fast); score the 5,000 imported leads once, as `python -m app.seed` does."""
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import CallLog, Lead
    from app.propensity import predict_many

    with SessionLocal() as db:
        if db.query(Lead).filter(Lead.origin == "import", Lead.propensity_bucket.is_not(None)).count() == 0:
            assert db.query(CallLog).count() == 0
            rows = db.query(Lead).filter(Lead.origin == "import").order_by(Lead.lead_id).all()
            from app.admin.lead_sync import model_input

            for lead, p in zip(rows, predict_many([model_input(r) for r in rows])):
                lead.propensity_score, lead.propensity_bucket, lead.propensity_reasons = p["score"], p["bucket"], json.dumps(p["top_3_reasons"])
            db.commit()
    return get_settings()


def leads(client, h, **params):
    r = client.get("/api/v1/admin/leads", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_scores_from_the_app_match_the_phase1_buckets(client, scored):
    out = leads(client, login(client, ADMIN), page_size=5)
    pct = out["bucket_conversion_pct"]
    assert abs(pct["High"] - 15.9) < 0.6 and abs(pct["Medium"] - 8.7) < 0.6 and abs(pct["Low"] - 1.8) < 0.6
    assert out["total"] >= 5000
    s = [i["propensity"]["score"] for i in out["items"]]
    assert s == sorted(s, reverse=True)


def test_table_columns_are_masked(client, scored):
    out = leads(client, login(client, AGENT), page_size=50)
    blob = json.dumps(out)
    assert not RAW_GSTIN.search(blob) and "UDYAM-" not in blob
    for i in out["items"]:
        assert {"contact", "segment", "stage_reached", "drop_reason", "propensity"} <= set(i)
        if i["origin"] == "import":
            assert re.fullmatch(r"\S+( \S\.)?", i["contact"]), i["contact"]
            assert len(i["propensity"]["reasons"]) <= 3 and i["propensity"]["bucket"] in ("High", "Medium", "Low")


def test_customers_cannot_see_leads(client):
    auth = login(client, '+919866600099')
    assert client.get("/api/v1/admin/leads", headers=auth).status_code == 403
    assert client.get("/api/v1/admin/metrics", headers=auth).status_code == 403


def test_high_propensity_not_contacted_then_call_and_outcome(client, scored):
    h = login(client, AGENT)
    hot = leads(client, h, preset="hot_uncontacted", page_size=10)
    assert hot["items"] and all(i["propensity"]["bucket"] == "High" and i["last_contacted_at"] is None and i["outcome"] != "Activated" for i in hot["items"])
    lead_id = hot["items"][0]["lead_id"]
    r = client.post(f"/api/v1/admin/leads/{lead_id}/call", json={"mode": "mock"}, headers=h)
    assert r.status_code == 201 and r.json()["status"] == "logged" and r.json()["provider"] == "mock"
    call_id = r.json()["call_id"]
    after = leads(client, h, preset="hot_uncontacted", page_size=200)
    assert lead_id not in {i["lead_id"] for i in after["items"]} and after["counts"]["hot_uncontacted"] == hot["counts"]["hot_uncontacted"] - 1
    r = client.post(f"/api/v1/admin/leads/{lead_id}/call", json={"mode": "mock"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RECENTLY_CALLED" and r.json()["error"]["details"]["by"] == "Priya"
    r = client.patch(f"/api/v1/admin/calls/{call_id}", json={"outcome": "interested", "duration_s": 140,
                                                             "note": "Owner +919812345678 wants Office Pro, GST 32TTNXB7384T1ZW"}, headers=h)
    assert r.status_code == 200 and r.json()["lead_status"] == "contacted" and r.json()["advisor_link_sent"] is False
    d = client.get(f"/api/v1/admin/leads/{lead_id}", headers=h).json()
    assert d["calls"][0]["outcome"] == "interested" and d["calls"][0]["agent"] == "Priya" and d["calls"][0]["duration_s"] == 140
    assert "9812345678" not in d["notes"][0]["body"] and not RAW_GSTIN.search(d["notes"][0]["body"])
    assert d["lead"]["gstin_masked"] is None or "•" in d["lead"]["gstin_masked"]
    assert d["lead"]["last_call"]["outcome"] == "interested"
    assert client.patch(f"/api/v1/admin/calls/{call_id}", json={"outcome": "maybe"}, headers=h).status_code == 400
    from app.db import SessionLocal
    from app.models import AuditLog

    with SessionLocal() as db:
        acts = {a.action for a in db.query(AuditLog).filter(AuditLog.entity_id == lead_id)}
    assert {"call_lead", "view_lead"} <= acts


def test_twilio_mode_without_a_number_falls_back_to_a_mock_call(client, scored):
    h = login(client, ADMIN)
    lead_id = leads(client, h, preset="hot_uncontacted", page_size=1)["items"][0]["lead_id"]
    r = client.post(f"/api/v1/admin/leads/{lead_id}/call", json={"mode": "twilio"}, headers=h)
    assert r.status_code == 201 and r.json()["provider"] == "mock" and r.json()["notice"]
    assert client.get(f"/api/v1/admin/leads/{lead_id}", headers=h).json()["calls"][0]["agent"] == "Admin"


def test_app_leads_are_scored_and_show_up_when_the_advisor_could_not_close(client, scored, monkeypatch):
    h = login_lang(client, "+919866600001", "en")
    r = client.post("/api/v1/advisor/conversations", json={"language": "en", "lead_source": "Referral"}, headers=h).json()
    cid = r["conversation_id"]
    for a in [chips("en", "chips_type", 1), chips("en", "chips_team", 1)]:
        client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": a}, headers=h)
    from app.db import SessionLocal
    from app.models import Conversation, Lead

    with SessionLocal() as db:
        lead_id = db.get(Conversation, cid).lead_id
        lead = db.get(Lead, lead_id)
        assert lead.segment == "Professional offices" and lead.propensity_bucket and lead.stage_reached == "Contacted"
    admin = login(client, ADMIN)
    assert lead_id not in {i["lead_id"] for i in leads(client, admin, preset="not_closed", page_size=200)["items"]}
    with SessionLocal() as db:
        c = db.get(Conversation, cid)
        c.updated_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(timespec="seconds")
        db.commit()
    row = next(i for i in leads(client, admin, preset="not_closed", origin="app", page_size=200)["items"] if i["lead_id"] == lead_id)
    assert row["advisor_outcome"] == "abandoned" and row["drop_reason"] == "Left the advisor at the city question"
    assert row["contact"] == "••••••0001" and row["propensity"]["reasons"]
    r = client.post("/api/v1/admin/leads/" + lead_id + "/call", json={"mode": "mock"}, headers=admin)
    client.patch(f"/api/v1/admin/calls/{r.json()['call_id']}", json={"outcome": "callback_requested"}, headers=admin)
    client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "Pune"}, headers=h)
    with SessionLocal() as db:
        assert db.get(Lead, lead_id).advisor_outcome == "not_started"


def test_interested_app_lead_gets_the_advisor_link_on_whatsapp(client, scored):
    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919866600002"})
    tok = client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": r.json()["dev_code"], "language": "en",
                                                        "whatsapp_opt_in": True}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    cid = client.post("/api/v1/advisor/conversations", json={"language": "en"}, headers=h).json()["conversation_id"]
    client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": "talk to a person"}, headers=h)
    admin = login(client, ADMIN)
    row = next(i for i in leads(client, admin, preset="not_closed", origin="app", page_size=200)["items"] if i["contact"] == "••••••0002")
    assert row["advisor_outcome"] == "escalated" and row["drop_reason"] == "Asked for a person in the advisor"
    call = client.post(f"/api/v1/admin/leads/{row['lead_id']}/call", json={"mode": "mock"}, headers=admin).json()
    r = client.patch(f"/api/v1/admin/calls/{call['call_id']}", json={"outcome": "interested"}, headers=admin).json()
    assert r["advisor_link_sent"] is True and r["advisor_link_status"] == "sent"
    out = client.get("/api/v1/notifications", headers=h).json()["items"]
    link = next(i for i in out if i["template"] == "advisor_link")
    assert link["channel"] == "whatsapp" and "/advisor" in link["preview"]


def test_filters(client, scored):
    h = login(client, AGENT)
    for params in ({"bucket": "Low"}, {"segment": "Small manufacturers"}, {"source": "Referral"}, {"origin": "import"}):
        out = leads(client, h, page_size=20, **params)
        key, val = next(iter(params.items()))
        field = {"bucket": lambda i: i["propensity"]["bucket"], "segment": lambda i: i["segment"], "source": lambda i: i["lead_source"],
                 "origin": lambda i: i["origin"]}[key]
        assert out["items"] and all(field(i) == val for i in out["items"])
    assert "L00001" in {i["lead_id"] for i in leads(client, h, q="Balaji Dental Care LLP", page_size=50)["items"]}
    assert [i["lead_id"] for i in leads(client, h, q="L00001")["items"]] == ["L00001"]
    assert leads(client, h, q="nothing-matches-this")["total"] == 0
