"""Build Phase 5: WhatsApp updates (DESIGN.md D3.9, D4.5). Mock outbox by default; the Twilio adapter is tested against a fake API."""
import json
import re

import httpx
import pytest

from tests.test_kyc import TYPES, consent, placed_order, upload
from tests.test_tracker import ADMIN, login, verify

LEFTOVER = re.compile(r"[{}]")


def opt_in(client, h, on=True):
    r = client.patch("/api/v1/me", json={"whatsapp_opt_in": on}, headers=h)
    assert r.status_code == 200 and r.json()["user"]["whatsapp_opt_in"] is on


def wa(order_id, template=None):
    from app.db import SessionLocal
    from app.models import Notification

    with SessionLocal() as db:
        q = db.query(Notification).filter(Notification.order_id == order_id, Notification.channel == "whatsapp")
        if template:
            q = q.filter(Notification.template == template)
        return [(n.template, n.status, n.provider_ref, json.loads(n.payload)["preview"]) for n in q.order_by(Notification.created_at)]


def opted_order(client, phone):
    """Log in with the WhatsApp box ticked (C2), then run the advisor and accept a quote."""
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    r = client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": r.json()["dev_code"], "language": "en",
                                                      "whatsapp_opt_in": True})
    assert r.json()["user"]["whatsapp_opt_in"] is True
    return placed_order(client, phone)


def test_every_template_renders_in_every_language():
    from app.config import get_settings
    from app.notifications.service import TEMPLATES, _strings, render

    params = {"display_id": "UD-2611-0001", "monthly_total_inr": 6055, "fix": "Upload a recent bill.", "message": "Priya will call you by 4 pm.",
              "date": "2026-11-12", "slot": "10:00-12:00", "text": "Technician visit on 12 Nov, 10-12 am"}
    for lang in get_settings().langs:
        assert set(_strings(lang)) == set(_strings("en")), lang
        for t in TEMPLATES:
            for state in ("QUOTE_ACCEPTED", "CONSENT_GIVEN", "KYC_FLAGGED"):
                out = render(t, lang, params | {"state": state})
                assert out.startswith("Accel Business: ") and not LEFTOVER.search(out) and len(out) < 400, (lang, t, out)
    assert "₹6,055" in render("quote_ready", "hi", params) and "हर महीने" in render("quote_ready", "hi", params)


def test_opted_in_owner_gets_quote_ready_in_the_mock_outbox(client):
    h, oid = opted_order(client, "+919844400001")
    rows = wa(oid, "quote_ready")
    assert len(rows) == 1
    _, status, ref, preview = rows[0]
    assert status == "sent" and ref.startswith("mock-wa-")
    assert re.search(r"UD-\d{4}-\d{4}", preview) and "a month" in preview and f"/order/{oid}/consent" in preview
    from app.db import SessionLocal
    from app.models import Notification

    with SessionLocal() as db:
        assert db.query(Notification).filter(Notification.order_id == oid, Notification.channel == "in_app", Notification.template == "quote_ready").count() == 1


def test_no_opt_in_means_skipped_but_in_app_still_shows(client):
    h, oid = placed_order(client, "+919844400002")
    assert [r[1] for r in wa(oid)] == ["skipped_no_optin"]
    items = client.get("/api/v1/notifications", headers=h).json()["items"]
    assert any(i["template"] == "quote_ready" and i["channel"] == "in_app" and i["preview"] for i in items)


def test_kyc_verified_then_install_booked(client):
    h, oid = opted_order(client, "+919844400003")
    c = consent(client, h, oid)
    for t in TYPES:
        assert upload(client, h, c["kyc_case_id"], "K02", t).status_code == 201
    client.post(f"/api/v1/kyc/{c['kyc_case_id']}/submit", headers=h)
    got = [r[0] for r in wa(oid) if r[1] == "sent"]
    assert got[-2:] == ["kyc_verified", "install_booked"]
    assert "Technician visit on" in wa(oid, "install_booked")[0][3]


def test_kyc_flag_tells_the_owner_the_exact_fix(client):
    h, oid = opted_order(client, "+919844400004")
    c = consent(client, h, oid)
    for t in TYPES:
        upload(client, h, c["kyc_case_id"], "K11", t)
    client.post(f"/api/v1/kyc/{c['kyc_case_id']}/submit", headers=h)
    (_, status, _, preview), = wa(oid, "kyc_fix_needed")
    assert status == "sent" and "bill" in preview.lower() and f"/order/{oid}/kyc" in preview


def test_human_review_is_announced_with_the_agent(client):
    h, oid = opted_order(client, "+919844400005")
    c = consent(client, h, oid)
    for t in TYPES:
        upload(client, h, c["kyc_case_id"], "K06", t)
    client.post(f"/api/v1/kyc/{c['kyc_case_id']}/submit", headers=h)
    (_, status, _, preview), = wa(oid, "kyc_review")
    assert status == "sent" and "will call you by" in preview


def test_delay_and_live_messages(client):
    admin = login(client, ADMIN)
    h, oid = opted_order(client, "+919844400006")
    verify(oid)
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"delay_hours": 30}, headers=admin)
    client.post("/api/v1/admin/sla/scan", headers=admin)
    (_, status, _, preview), = wa(oid, "delay_escalated")
    assert status == "sent" and "running late" in preview and "will call you by" in preview
    for st in ("INSTALLED", "LIVE"):
        assert client.post(f"/api/v1/admin/orders/{oid}/advance", json={"to_state": st}, headers=admin).status_code == 200
    (_, status, _, preview), = wa(oid, "live")
    assert status == "sent" and "is live" in preview


@pytest.mark.parametrize("state,words", [("QUOTE_ACCEPTED", "waiting for your documents"), ("CONSENT_GIVEN", "4 documents")])
def test_kyc_left_incomplete_for_24h_gets_one_reminder(client, state, words):
    admin = login(client, ADMIN)
    h, oid = opted_order(client, f"+91984440010{len(state) % 10}")
    if state == "CONSENT_GIVEN":
        consent(client, h, oid)
    client.post(f"/api/v1/admin/orders/{oid}/advance", json={"delay_hours": 1}, headers=admin)
    client.post("/api/v1/admin/sla/scan", headers=admin)
    client.post("/api/v1/admin/sla/scan", headers=admin)
    rows = wa(oid, "kyc_reminder_24h")
    assert len(rows) == 1 and rows[0][1] == "sent" and words in rows[0][3]


def test_hindi_owner_gets_hindi_whatsapp(client):
    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919844400007"})
    client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": r.json()["dev_code"], "language": "en", "whatsapp_opt_in": True})
    h, oid = placed_order(client, "+919844400007")
    client.patch("/api/v1/me", json={"language": "hi"}, headers=h)
    verify(oid)
    (_, status, _, preview), = wa(oid, "install_booked")
    assert status == "sent" and "ऑर्डर" in preview and "इंस्टॉलेशन" in preview


def test_outbox_scope_and_masking(client):
    h, oid = opted_order(client, "+919844400008")
    other = login(client, "+919844400009")
    assert all(i["order_id"] != oid for i in client.get("/api/v1/notifications", headers=other).json()["items"])
    assert client.get("/api/v1/notifications", params={"scope": "all"}, headers=other).json()["items"] == \
        client.get("/api/v1/notifications", headers=other).json()["items"]
    out = client.get("/api/v1/notifications", params={"scope": "all", "channel": "whatsapp"}, headers=login(client, ADMIN)).json()
    assert out["provider"] == "mock"
    mine = [i for i in out["items"] if i["order_id"] == oid]
    assert mine and mine[0]["to"] == "••••••0008" and "9844400008" not in json.dumps(out)


def test_admin_resend_and_validation(client):
    admin = login(client, ADMIN)
    h, oid = opted_order(client, "+919844400010")
    uid = client.get("/api/v1/me", headers=h).json()["user"]["id"]
    r = client.post("/api/v1/notifications/whatsapp", json={"user_id": uid, "order_id": oid, "template": "quote_ready",
                                                            "params": {"monthly_total_inr": 1597}}, headers=admin)
    assert r.status_code == 202 and r.json()["status"] == "sent" and "1,597" in r.json()["preview"]
    r = client.post("/api/v1/notifications/whatsapp", json={"user_id": uid, "order_id": oid, "template": "install_booked", "params": {}}, headers=admin)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PARAMS_MISSING"
    r = client.post("/api/v1/notifications/whatsapp", json={"user_id": uid, "template": "nope", "params": {}}, headers=admin)
    assert r.status_code == 404 and r.json()["error"]["code"] == "TEMPLATE_NOT_FOUND"
    assert client.post("/api/v1/notifications/whatsapp", json={"user_id": uid, "template": "live"}, headers=h).status_code == 403
    opt_in(client, h, False)
    r = client.post("/api/v1/notifications/whatsapp", json={"user_id": uid, "order_id": oid, "template": "live", "params": {}}, headers=admin)
    assert r.json()["status"] == "skipped_no_optin"


def fake_twilio(seen, status_code=201, body=None):
    def handler(req: httpx.Request):
        seen.append(req)
        return httpx.Response(status_code, json=body or {"sid": "SM123", "status": "queued"})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_twilio_adapter_sends_the_sandbox_message():
    from app.config import Settings
    from app.notifications.providers.twilio import TwilioProvider

    s = Settings(twilio_account_sid="AC1", twilio_auth_token="tok", twilio_whatsapp_from="whatsapp:+14155238886")
    seen = []
    res = TwilioProvider(s, fake_twilio(seen)).send_whatsapp("+919876543210", "hello", "https://x.example/cb")
    assert res.ok and res.ref == "SM123" and res.status == "queued"
    req = seen[0]
    form = dict(httpx.QueryParams(req.content.decode()))
    assert str(req.url) == "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages.json"
    assert form == {"From": "whatsapp:+14155238886", "To": "whatsapp:+919876543210", "Body": "hello", "StatusCallback": "https://x.example/cb"}
    assert req.headers["authorization"].startswith("Basic ")
    bad = TwilioProvider(s, fake_twilio([], 400, {"code": 63007, "message": "not joined"})).send_whatsapp("+91", "x")
    assert not bad.ok and bad.status == "failed" and "63007" in bad.error


def test_twilio_path_queues_then_dispatches_and_failures_are_kept(client, monkeypatch):
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Notification
    from app.notifications import providers, service

    s = get_settings()
    monkeypatch.setattr(s, "notify_provider", "twilio")
    monkeypatch.setattr(s, "twilio_account_sid", "AC1")
    monkeypatch.setattr(s, "twilio_auth_token", "tok")
    h, oid = opted_order(client, "+919844400011")
    assert [r[1] for r in wa(oid, "quote_ready")] == ["queued"]
    seen = []
    monkeypatch.setattr(providers, "get_provider", lambda: providers.TwilioProvider(s, fake_twilio(seen)))
    with SessionLocal() as db:
        assert service.dispatch_pending(db) >= 1
    assert wa(oid, "quote_ready")[0][1:3] == ("queued", "SM123")
    assert "whatsapp:+919844400011" in seen[-1].content.decode().replace("%3A", ":").replace("%2B", "+")
    with SessionLocal() as db:
        service.webhook(db, {"MessageSid": "SM123", "MessageStatus": "delivered"})
        assert db.query(Notification).filter(Notification.provider_ref == "SM123").first().status == "delivered"
    monkeypatch.setattr(providers, "get_provider", lambda: providers.TwilioProvider(s, fake_twilio([], 401, {"code": 20003, "message": "auth"})))
    h2, oid2 = opted_order(client, "+919844400012")
    with SessionLocal() as db:
        service.dispatch_pending(db)
    (_, status, _, _), = wa(oid2, "quote_ready")
    assert status == "failed"
    with SessionLocal() as db:
        assert "20003" in db.query(Notification).filter(Notification.order_id == oid2, Notification.channel == "whatsapp").one().error
    assert client.get("/api/v1/health").json()["providers"]["messaging"] == "twilio"


def test_twilio_webhook_checks_the_signature(client, monkeypatch):
    from app.config import get_settings
    from app.notifications.providers.twilio import signature

    s = get_settings()
    monkeypatch.setattr(s, "twilio_auth_token", "tok")
    url = "http://testserver/api/v1/notifications/webhook/twilio"
    params = {"MessageSid": "SMnone", "MessageStatus": "delivered"}
    assert client.post(url, data=params, headers={"X-Twilio-Signature": "bad"}).status_code == 403
    assert client.post(url, data=params, headers={"X-Twilio-Signature": signature("tok", url, params)}).status_code == 204
