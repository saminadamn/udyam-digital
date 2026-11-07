import json
from datetime import datetime, timedelta

import pytest

from app.seed import AGENTS
from tests.test_kyc import placed_order

PHONE_OF = {name: phone for name, phone, _, _ in AGENTS}
ADMIN = "+919000000001"


_tokens: dict[str, dict] = {}


def login(client, phone, lang="en"):
    if phone in _tokens:
        return _tokens[phone]
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    r = client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": r.json()["dev_code"], "language": lang})
    _tokens[phone] = {"Authorization": f"Bearer {r.json()['token']}"}
    return _tokens[phone]


@pytest.fixture()
def admin(client):
    return login(client, ADMIN)


def verify(order_id):
    from app.db import SessionLocal
    from app.models import Order
    from app.orders import fulfilment, state_machine

    with SessionLocal() as db:
        o = db.get(Order, order_id)
        for s in ("CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_VERIFIED"):
            state_machine.transition(db, o, s, "test")
        fulfilment.on_verified(db, o)
        db.commit()


def booked(client, phone, lang="en"):
    h, oid = placed_order(client, phone) if lang == "en" else placed_hi(client, phone)
    verify(oid)
    return h, oid


def placed_hi(client, phone):
    h, oid = placed_order(client, phone)
    client.patch("/api/v1/me", json={"language": "hi"}, headers=h)
    return h, oid


def tracker(client, h, oid):
    r = client.get(f"/api/v1/orders/{oid}/tracker", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_verified_order_is_booked_with_expected_dates(client):
    from app.db import SessionLocal
    from app.escalations.service import IST
    from app.models import Order
    from app.orders.fulfilment import install_days

    h, oid = booked(client, "+919833300001")
    t = tracker(client, h, oid)
    with SessionLocal() as db:
        o = db.get(Order, oid)
        days = install_days(db, o)
    want = datetime.now(IST).date() + timedelta(days=days)
    if want.weekday() == 6:
        want += timedelta(days=1)
    assert t["state"] == "INSTALL_BOOKED" and t["expected_install_date"] == want.isoformat()
    assert t["expected_live_date"] == (want + timedelta(days=1)).isoformat()
    assert [s["status"] for s in t["steps"]] == ["done", "current", "upcoming", "upcoming"]
    assert t["steps"][0]["at"] and t["steps"][1]["detail"].startswith("Technician visit on ")
    assert t["steps"][2]["expected"] == want.isoformat() and t["steps"][2]["detail"].startswith("Expected by ")
    assert t["delayed"] is False and t["escalation"] is None


def test_tracker_before_verification_shows_days_not_dates(client):
    h, oid = placed_order(client, "+919833300002")
    t = tracker(client, h, oid)
    assert t["pre_verification"] and t["next_action"] == "consent"
    assert all(s["status"] == "upcoming" for s in t["steps"])
    assert "days after your documents are verified" in t["steps"][2]["detail"]


def test_delayed_order_auto_escalates_and_tracker_names_the_person(client, admin):
    h, oid = booked(client, "+919833300003")
    r = client.post(f"/api/v1/admin/orders/{oid}/advance", json={"delay_hours": 30}, headers=admin)
    assert r.status_code == 200 and r.json()["state"] == "INSTALL_BOOKED"
    assert tracker(client, h, oid)["delayed"] is True
    acts = client.post("/api/v1/admin/sla/scan", headers=admin).json()["actions"]
    mine = [a for a in acts if a["order_id"] == oid]
    assert mine and mine[0]["action"] == "escalated" and mine[0]["priority"] == "P1"
    t = tracker(client, h, oid)
    e = t["escalation"]
    assert t["delayed"] and t["delay_message"].startswith("Your installation is running late")
    assert e["trigger"] == "sla_breach" and e["agent_name"] in {"Arjun", "Sanjay"}
    assert e["message"].startswith(f"{e['agent_name']} from Accel will call you by ")
    assert not [a for a in client.post("/api/v1/admin/sla/scan", headers=admin).json()["actions"] if a["order_id"] == oid]
    from app.db import SessionLocal
    from app.models import Notification, Order

    with SessionLocal() as db:
        assert db.get(Order, oid).assigned_agent_id
        templates = {n.template for n in db.query(Notification).filter(Notification.order_id == oid)}
        assert {"install_booked", "agent_assigned", "delay_escalated"} <= templates


def test_assignment_spreads_load_and_matches_language(client, admin):
    from app.db import SessionLocal
    from app.escalations.service import assign_agent, open_counts
    from app.models import Agent

    with SessionLocal() as db:
        counts = open_counts(db)
        hi = assign_agent(db, "install", "hi")
        en = assign_agent(db, "install", "en")
        assert "hi" in json.loads(hi.languages) and "en" in json.loads(en.languages)
        installers = [a for a in db.query(Agent) if "install" in json.loads(a.skills) and "en" in json.loads(a.languages)]
        assert counts.get(en.id, 0) == min(counts.get(a.id, 0) for a in installers)


def test_simulator_moves_to_live_and_rejects_bad_jumps(client, admin):
    h, oid = booked(client, "+919833300004")
    bad = client.post(f"/api/v1/admin/orders/{oid}/advance", json={"to_state": "LIVE"}, headers=admin)
    assert bad.status_code == 409 and bad.json()["error"]["details"]["allowed"] == ["INSTALLED", "INSTALL_BOOKED"]
    assert client.post(f"/api/v1/admin/orders/{oid}/advance", json={"to_state": "INSTALLED"}, headers=h).status_code == 403
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"to_state": "INSTALLED"}, headers=admin)
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"to_state": "LIVE"}, headers=admin)
    t = tracker(client, h, oid)
    assert t["state"] == "LIVE" and [s["status"] for s in t["steps"]] == ["done"] * 4
    assert t["steps"][3]["detail"].startswith("Live since ") and t["payment_status"] == "paid"


def test_talk_to_a_person_once(client):
    h, oid = booked(client, "+919833300005")
    r = client.post("/api/v1/escalations", json={"order_id": oid, "reason": "Want to change installation date", "preferred_time": "after 4 pm"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["agent"]["name"] in body["message"] and "from Accel will call you by" in body["message"]
    again = client.post("/api/v1/escalations", json={"order_id": oid}, headers=h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "ESCALATION_EXISTS"
    assert tracker(client, h, oid)["escalation"]["escalation_id"] == body["escalation_id"]


def test_agent_sees_full_context_and_resolves(client, admin):
    h, oid = booked(client, "+919833300006")
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"delay_hours": 48}, headers=admin)
    client.post("/api/v1/admin/sla/scan", headers=admin)
    e = tracker(client, h, oid)["escalation"]
    full = next(n for n in PHONE_OF if n.startswith(e["agent_name"]))
    agent_h = login(client, PHONE_OF[full])
    mine = client.get("/api/v1/escalations", params={"mine": "true"}, headers=agent_h).json()
    assert e["escalation_id"] in [i["escalation_id"] for i in mine["items"]]
    d = client.get(f"/api/v1/escalations/{e['escalation_id']}", headers=agent_h).json()
    assert d["business"]["segment"] == "Micro retail & services" and d["customer"]["phone_masked"].endswith("0006")
    assert d["chat"]["summary"] and len(d["chat"]["messages"]) > 4
    assert d["quote"]["items"] and d["order"]["events"][-1]["to"] == "INSTALL_BOOKED"
    assert "Late by" in d["escalation"]["reason"] and d["escalation"]["customer_was_told"] == e["message"]
    other = next(p for n, p in PHONE_OF.items() if not n.startswith(e["agent_name"]))
    nope = client.patch(f"/api/v1/escalations/{e['escalation_id']}", json={"action": "resolve", "resolution": "rebooked", "note": "Called"}, headers=login(client, other))
    assert nope.status_code == 403
    r = client.patch(f"/api/v1/escalations/{e['escalation_id']}", json={"action": "resolve", "resolution": "rebooked", "note": "Technician fell ill; rebooked for tomorrow"}, headers=agent_h)
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    t = tracker(client, h, oid)
    assert t["delayed"] is False and t["escalation"] is None
    from app.db import SessionLocal
    from app.escalations.service import IST
    from app.models import AuditLog

    tomorrow = datetime.now(IST).date() + timedelta(days=1)
    assert t["expected_install_date"] == (tomorrow + timedelta(days=1 if tomorrow.weekday() == 6 else 0)).isoformat()
    with SessionLocal() as db:
        assert db.query(AuditLog).filter(AuditLog.entity_id == e["escalation_id"], AuditLog.action == "view_escalation").count() == 1


def test_agent_approval_clears_kyc_review(client, admin):
    from app.db import SessionLocal
    from app.escalations.service import create
    from app.models import Order
    from app.orders import state_machine

    h, oid = placed_order(client, "+919833300007")
    with SessionLocal() as db:
        o = db.get(Order, oid)
        for s in ("CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_FLAGGED", "HUMAN_REVIEW"):
            state_machine.transition(db, o, s, "test")
        e = create(db, trigger="kyc_flag", priority="P1", skill="kyc", reason="GSTIN on certificate differs from registry", lang="en", order=o, sla_hours=4)
        db.commit()
        eid = e.id
    r = client.patch(f"/api/v1/escalations/{eid}", json={"action": "resolve", "resolution": "approved", "note": "Confirmed GSTIN with owner"}, headers=admin)
    assert r.status_code == 200
    assert tracker(client, h, oid)["state"] == "INSTALL_BOOKED"


def test_waiting_for_documents_gets_a_reminder_then_a_person(client, admin):
    h, oid = placed_order(client, "+919833300008")
    from app.db import SessionLocal
    from app.models import Order
    from app.orders import state_machine

    with SessionLocal() as db:
        state_machine.transition(db, db.get(Order, oid), "CONSENT_GIVEN", "test")
        db.commit()
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"delay_hours": 6}, headers=admin)
    acts = [a for a in client.post("/api/v1/admin/sla/scan", headers=admin).json()["actions"] if a["order_id"] == oid]
    assert acts == [{"order_id": oid, "state": "CONSENT_GIVEN", "action": "reminder"}]
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"delay_hours": 60}, headers=admin)
    acts = [a for a in client.post("/api/v1/admin/sla/scan", headers=admin).json()["actions"] if a["order_id"] == oid]
    assert acts[0]["action"] == "escalated" and acts[0]["priority"] == "P3"


def test_customers_cannot_open_the_agent_queue(client, auth):
    assert client.get("/api/v1/escalations", headers=auth).status_code == 403
    assert client.get("/api/v1/admin/agents", headers=auth).status_code == 403


def test_callbacks_are_promised_inside_working_hours():
    from app.escalations.service import IST, callback_due

    sat_evening = datetime(2026, 11, 7, 18, 50, tzinfo=IST)
    assert callback_due(sat_evening, 2).astimezone(IST) == datetime(2026, 11, 9, 11, 0, tzinfo=IST)
    weekday = datetime(2026, 11, 10, 10, 7, tzinfo=IST)
    assert callback_due(weekday, 2).astimezone(IST) == datetime(2026, 11, 10, 12, 15, tzinfo=IST)
