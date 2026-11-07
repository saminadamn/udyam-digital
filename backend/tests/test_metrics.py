"""Build Phase 5: the 5 pilot metrics on the dashboard, computed live from the DB (analysis/bundles_and_metrics.md section 3)."""
from tests.test_kyc import placed_order
from tests.test_tracker import ADMIN, login, verify


def get(client):
    r = client.get("/api/v1/admin/metrics", headers=login(client, ADMIN))
    assert r.status_code == 200, r.text
    return {m["key"]: m for m in r.json()["metrics"]}, r.json()


def test_baselines_are_recomputed_from_the_imported_leads(client):
    m, body = get(client)
    assert [k for k, v in m.items() if v["strip"]] == ["lead_to_activation", "days_to_activate", "cac_per_activation", "churn_6m",
                                                       "chase_calls_per_customer"]
    want = {"lead_to_activation": (0.074, 0.11), "days_to_activate": (17.6, 8), "cac_per_activation": (15053, 8000), "churn_6m": (0.152, 0.11),
            "chase_calls_per_customer": (3.0, 0.5), "kyc_completion": (0.683, 0.85)}
    for k, (base, target) in want.items():
        assert round(m[k]["baseline"], 1 if k == "chase_calls_per_customer" else 3) == base, (k, m[k]["baseline"])
        assert m[k]["target"] == target
    assert body["baseline_leads"] == 5000


def test_an_app_customer_going_live_moves_the_current_numbers(client):
    m0, b0 = get(client)
    h, oid = placed_order(client, "+919877700001")
    verify(oid)
    admin = login(client, ADMIN)
    assert client.post("/api/v1/escalations", json={"order_id": oid, "reason": "When is the technician coming?"}, headers=h).status_code == 201
    for st in ("INSTALLED", "LIVE"):
        assert client.post(f"/api/v1/admin/orders/{oid}/advance", json={"to_state": st}, headers=admin).status_code == 200
    m1, b1 = get(client)
    assert b1["app_leads"] == b0["app_leads"] + 1 and b1["app_orders"] == b0["app_orders"] + 1
    conv, days, cac, chase = (m1[k]["current"] for k in ("lead_to_activation", "days_to_activate", "cac_per_activation", "chase_calls_per_customer"))
    assert conv and conv > (m0["lead_to_activation"]["current"] or 0)
    assert days is not None and 0 <= days < 1
    assert cac and cac > 0
    assert chase and chase > (m0["chase_calls_per_customer"]["current"] or 0)
    assert m1["churn_6m"]["current"] is None and "reach 6 months on" in m1["churn_6m"]["note"]
    assert m1["kyc_completion"]["current"] is not None
    from app.db import SessionLocal
    from app.models import Lead, Order

    with SessionLocal() as db:
        lead = db.query(Lead).filter(Lead.business_id == db.get(Order, oid).business_id).one()
        assert (lead.outcome, lead.stage_reached, lead.lead_status) == ("Activated", "Activated", "converted") and lead.monthly_bundle_value_inr


def test_filters_narrow_the_current_column(client):
    admin = login(client, ADMIN)
    r = client.get("/api/v1/admin/metrics", params={"segment": "Small manufacturers", "channel": "assisted", "from": "2026-01-01"}, headers=admin)
    assert r.status_code == 200 and r.json()["filters"] == {"from": "2026-01-01", "to": None, "segment": "Small manufacturers", "channel": "assisted"}
    assert client.get("/api/v1/admin/metrics", params={"channel": "phone"}, headers=admin).status_code in (400, 422)
