from datetime import date, timedelta



from tests.test_advisor import login, run_conversation

MICRO = ["Shop or small service", "1-5 people", "Lucknow", "No GST yet", "Mobile hotspot", "UPI and billing, CCTV cameras"]
PROF = ["Clinic or office", "6-20 people", "Pune", "32TTNXB7384T1ZW", "Business broadband", "Business email, Data backup"]
CHAIN = ["Chain with branches", "8+ branches, 60+ people", "Delhi", "32TTNXB7384T1ZW", "Business broadband", "Guest Wi-Fi"]


def make_quote(client, phone, answers, lang="en"):
    h = login(client, phone, lang)
    cid, _, _ = run_conversation(client, h, lang, answers)
    rec = client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h).json()
    r = client.post("/api/v1/quotes", json={"recommendation_id": rec["recommendation_id"]}, headers=h)
    assert r.status_code == 201, r.text
    return h, rec, r.json()


def item(q, pid):
    return next(i for i in q["items"] if i["product_id"] == pid)


def test_every_unit_price_is_inside_the_catalogue_range(catalogue):
    from app.pricing.service import unit_price

    for key in ("micro", "prof", "multi", "mfg"):
        for pid, p in catalogue.items():
            u = unit_price(pid, key, catalogue)
            assert p.price_min_inr <= u <= p.price_max_inr
            assert u == (p.price_min_inr if key == "micro" else round((p.price_min_inr + p.price_max_inr) / 2))


def test_quote_matches_recommendation_and_pricing_rule(client, catalogue):
    h, rec, q = make_quote(client, "+919811100001", MICRO)
    assert q["status"] == "draft" and q["pricing_rule"] == "micro_min_v1"
    assert q["monthly_total_inr"] == rec["monthly_total_inr"]
    core = [i for i in q["items"] if i["role"] == "core"]
    assert all(i["selected"] for i in core)
    assert all(not i["selected"] for i in q["items"] if i["role"] == "addon")
    assert q["monthly_total_inr"] == sum(i["line_monthly_inr"] for i in q["items"] if i["selected"])
    assert q["setup_total_inr"] == sum(i["line_setup_inr"] for i in q["items"] if i["selected"])
    assert q["contract_months"] == max(catalogue[i["product_id"]].min_contract_months for i in core)
    assert q["valid_until"] == (date.today() + timedelta(days=7)).isoformat()
    again = client.post("/api/v1/quotes", json={"recommendation_id": rec["recommendation_id"]}, headers=h).json()
    assert again["quote_id"] == q["quote_id"]


def test_toggle_addon_changes_price_and_setup(client):
    h, _, q = make_quote(client, "+919811100002", PROF)
    addon = next(i for i in q["items"] if i["role"] == "addon")
    on = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/{addon['product_id']}", json={"selected": True}, headers=h).json()
    assert on["monthly_total_inr"] == q["monthly_total_inr"] + addon["line_monthly_inr"]
    assert on["setup_total_inr"] == q["setup_total_inr"] + addon["line_setup_inr"]
    off = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/{addon['product_id']}", json={"selected": False}, headers=h).json()
    assert off["monthly_total_inr"] == q["monthly_total_inr"]


def test_connection_is_locked_with_a_reason(client):
    h, _, q = make_quote(client, "+919811100003", MICRO)
    link = item(q, "P01")
    assert link["locked"] and link["lock_reason"]
    r = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P01", json={"selected": False}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DEPENDENCY_LOCKED"
    assert r.json()["error"]["details"]["reason"] == link["lock_reason"]


def test_removing_a_base_needed_by_another_item_is_blocked_and_names_it(client):
    h, _, q = make_quote(client, "+919811100004", CHAIN)
    link = item(q, "P01")
    assert "Backup 4G/5G Failover" in link["lock_reason"]
    r = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P01", json={"selected": False}, headers=h)
    assert r.status_code == 409 and "Backup 4G/5G Failover" in r.json()["error"]["message"]


def test_dependency_lock_moves_when_a_second_base_exists(catalogue):
    from app.pricing.quote import locks

    lk = locks(["P01", "P04", "P23"], catalogue, "en")
    assert "P01" not in lk and "P04" not in lk
    lk = locks(["P01", "P23", "P22"], catalogue, "en")
    assert "Cloud CCTV" in lk["P01"] and "Secure Wi-Fi with Guest Network" in lk["P01"]
    assert locks(["P01", "P23"], catalogue, "hi")["P01"].endswith("के लिए ज़रूरी है।")


def test_non_locked_core_item_can_be_removed(client):
    h, _, q = make_quote(client, "+919811100005", MICRO)
    pos = item(q, "P19")
    assert pos["selected"] and not pos["locked"]
    r = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P19", json={"selected": False}, headers=h).json()
    assert r["monthly_total_inr"] == q["monthly_total_inr"] - pos["line_monthly_inr"]


def test_quantity_steppers_only_for_per_site_and_per_user(client):
    h, _, q = make_quote(client, "+919811100006", CHAIN)
    link = item(q, "P01")
    assert link["qty_editable"] and link["qty_min"] == 1 and link["qty_max"] == 8
    r = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P01", json={"qty": 6}, headers=h).json()
    assert item(r, "P01")["qty"] == 6 and item(r, "P01")["line_monthly_inr"] == 6 * link["unit_price_inr"]
    assert client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P01", json={"qty": 9}, headers=h).json()["error"]["code"] == "QTY_OUT_OF_RANGE"
    assert client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P01", json={"qty": 0}, headers=h).status_code == 400
    assert r["items"][0]["product_id"] == "P01" and [i["role"] for i in r["items"]] == sorted([i["role"] for i in r["items"]], key=lambda x: x != "core")
    cam = item(r, "P23")
    assert not cam["qty_editable"]
    assert client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P23", json={"qty": 3}, headers=h).json()["error"]["code"] == "QTY_NOT_EDITABLE"


def test_compare_with_current_spend(client):
    h, _, q = make_quote(client, "+919811100007", MICRO)
    assert q["current_spend_inr"] is None and q["difference_inr"] is None
    r = client.patch(f"/api/v1/quotes/{q['quote_id']}", json={"current_spend_inr": 900}, headers=h).json()
    assert r["current_spend_inr"] == 900 and r["difference_inr"] == q["monthly_total_inr"] - 900
    assert client.patch(f"/api/v1/quotes/{q['quote_id']}", json={"current_spend_inr": -5}, headers=h).status_code == 400


def test_accept_creates_order_items_and_event(client):
    from app.db import SessionLocal
    from app.models import Notification, Order, OrderEvent, Quote, QuoteItem

    h, _, q = make_quote(client, "+919811100008", PROF)
    addon = next(i for i in q["items"] if i["role"] == "addon")
    q2 = client.patch(f"/api/v1/quotes/{q['quote_id']}/items/{addon['product_id']}", json={"selected": True}, headers=h).json()
    r = client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["state"] == "QUOTE_ACCEPTED" and out["display_id"].startswith("UD-") and out["next_step"] == "consent"
    with SessionLocal() as db:
        order = db.get(Order, out["order_id"])
        assert order.state == "QUOTE_ACCEPTED" and order.quote_id == q["quote_id"] and order.state_due_at
        quote = db.get(Quote, q["quote_id"])
        assert quote.status == "accepted" and quote.accepted_at and quote.monthly_total_inr == q2["monthly_total_inr"]
        saved = db.query(QuoteItem).filter(QuoteItem.quote_id == quote.id, QuoteItem.selected == 1).all()
        assert {i.product_id for i in saved} == {i["product_id"] for i in q2["items"] if i["selected"]}
        ev = db.query(OrderEvent).filter(OrderEvent.order_id == order.id).all()
        assert [(e.from_state, e.to_state, e.actor) for e in ev] == [(None, "QUOTE_ACCEPTED", "user")]
        assert db.query(Notification).filter(Notification.order_id == order.id, Notification.channel == "in_app").count() == 1
    again = client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "ORDER_EXISTS"
    assert client.patch(f"/api/v1/quotes/{q['quote_id']}/items/{addon['product_id']}", json={"selected": False}, headers=h).json()["error"]["code"] == "QUOTE_NOT_DRAFT"
    lst = client.get("/api/v1/orders", headers=h).json()["orders"]
    assert [o["order_id"] for o in lst] == [out["order_id"]]
    one = client.get(f"/api/v1/orders/{out['order_id']}", headers=h).json()
    assert one["state"] == "QUOTE_ACCEPTED" and len(one["items"]) == len(saved)


def test_invalid_bundle_cannot_be_accepted(client):
    from app.db import SessionLocal
    from app.models import Business, Quote, QuoteItem

    h, _, q = make_quote(client, "+919811100009", PROF)
    with SessionLocal() as db:
        db.query(QuoteItem).filter(QuoteItem.quote_id == q["quote_id"], QuoteItem.product_id == "P02").update({"selected": 0})
        db.commit()
    r = client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INELIGIBLE"

    h2, _, q2 = make_quote(client, "+919811100010", PROF)
    with SessionLocal() as db:
        biz = db.get(Business, db.get(Quote, q2["quote_id"]).business_id)
        biz.gst_status = "Cancelled"
        db.query(QuoteItem).filter(QuoteItem.quote_id == q2["quote_id"]).update({"selected": 1})
        db.commit()
    r = client.post(f"/api/v1/quotes/{q2['quote_id']}/accept", headers=h2)
    assert r.status_code == 422 and any("GSTIN" in x for x in r.json()["error"]["details"]["reasons"])


def test_expired_quote_cannot_be_accepted(client):
    from app.db import SessionLocal
    from app.models import Quote

    h, _, q = make_quote(client, "+919811100011", MICRO)
    with SessionLocal() as db:
        db.get(Quote, q["quote_id"]).valid_until = (date.today() - timedelta(days=1)).isoformat()
        db.commit()
    r = client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "QUOTE_EXPIRED"


def test_assisted_deal_gets_an_account_manager(client):
    from app.db import SessionLocal
    from app.models import Escalation

    h, _, q = make_quote(client, "+919811100012", CHAIN)
    assert q["assisted"] is True
    out = client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=h).json()
    with SessionLocal() as db:
        esc = db.query(Escalation).filter(Escalation.order_id == out["order_id"]).one()
        assert esc.trigger == "assisted_deal" and esc.assigned_agent_id and esc.required_skill == "account_manager"
    assert client.get(f"/api/v1/orders/{out['order_id']}", headers=h).json()["account_manager"]


def test_other_users_cannot_see_or_change_a_quote(client):
    h, _, q = make_quote(client, "+919811100013", MICRO)
    other = login(client, "+919811100014", "en")
    assert client.get(f"/api/v1/quotes/{q['quote_id']}", headers=other).status_code == 404
    assert client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=other).status_code == 404


def test_single_site_connection_has_no_stepper(client):
    h, _, q = make_quote(client, "+919811100015", PROF)
    assert item(q, "P02")["qty_editable"] is False
    assert client.patch(f"/api/v1/quotes/{q['quote_id']}/items/P02", json={"qty": 1}, headers=h).json()["error"]["code"] == "QTY_NOT_EDITABLE"
    assert item(q, "P16")["qty_editable"] is True


def test_recommend_offers_plan_options_and_any_option_opens_a_matching_quote(client):
    h = login(client, "+919811100077", "en")
    cid, _, _ = run_conversation(client, h, "en", PROF)
    rec = client.post("/api/v1/advisor/recommend", json={"conversation_id": cid}, headers=h).json()
    opts = {o["key"]: o for o in rec["options"]}
    assert opts["recommended"]["recommendation_id"] == rec["recommendation_id"]
    assert opts["recommended"]["monthly_total_inr"] == rec["monthly_total_inr"]
    assert len(opts) >= 4 and len({o["recommendation_id"] for o in opts.values()}) == len(opts)
    for key in ("essential", "complete"):
        o = opts[key]
        q = client.post("/api/v1/quotes", json={"recommendation_id": o["recommendation_id"]}, headers=h)
        assert q.status_code == 201, q.text
        q = q.json()
        assert q["monthly_total_inr"] == o["monthly_total_inr"]
        assert {i["product_id"] for i in q["items"] if i["selected"]} == {i["product_id"] for i in o["items"]}
    # reloading the conversation still shows the main recommendation, not an alternative
    conv = client.get(f"/api/v1/advisor/conversations/{cid}", headers=h)
    if conv.status_code == 200 and conv.json().get("recommendation"):
        assert conv.json()["recommendation"]["recommendation_id"] == rec["recommendation_id"]
