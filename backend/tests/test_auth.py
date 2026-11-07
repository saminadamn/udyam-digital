def test_otp_login_flow_and_me(client):
    r = client.post("/api/v1/auth/otp/request", json={"phone": "98765 43210"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["dev_code"]) == 6 and body["expires_in"] == 300
    bad = client.post("/api/v1/auth/otp/verify", json={"request_id": body["request_id"], "code": "000000" if body["dev_code"] != "000000" else "111111"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "OTP_INVALID"
    r = client.post("/api/v1/auth/otp/verify", json={"request_id": body["request_id"], "code": body["dev_code"], "language": "ta", "whatsapp_opt_in": True})
    assert r.status_code == 200
    user = r.json()["user"]
    assert user["phone_masked"] == "••••••3210" and user["language"] == "ta" and user["whatsapp_opt_in"] is True
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/v1/me", headers=h).json()["user"]["id"] == user["id"]
    assert client.patch("/api/v1/me", json={"language": "bn"}, headers=h).json()["user"]["language"] == "bn"
    again = client.post("/api/v1/auth/otp/verify", json={"request_id": body["request_id"], "code": body["dev_code"]})
    assert again.status_code == 400
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    assert client.get("/api/v1/me", headers=h).status_code == 401


def test_bad_phone_and_rate_limit(client):
    assert client.post("/api/v1/auth/otp/request", json={"phone": "12345"}).status_code in (400,)
    codes = [client.post("/api/v1/auth/otp/request", json={"phone": "+917000000001"}).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_requires_auth_and_error_shape(client):
    r = client.post("/api/v1/advisor/conversations", json={"language": "hi"})
    assert r.status_code == 401
    assert set(r.json()["error"]) == {"code", "message", "details"}


def test_phone_stored_encrypted(client):
    from app.db import SessionLocal
    from app.models import User

    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919123456789"})
    client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": r.json()["dev_code"]})
    with SessionLocal() as db:
        u = db.query(User).filter(User.phone_masked == "••••••6789").one()
        assert b"9123456789" not in u.phone_enc and "9123456789" not in u.phone_hash


def test_products_and_health(client):
    r = client.get("/api/v1/products")
    assert r.status_code == 200 and len(r.json()["products"]) == 25
    assert client.get("/api/v1/products/P11").json()["requires_one_of"] == ["P01", "P02", "P03"]
    assert client.get("/api/v1/products/P99").status_code == 404
    assert len(client.get("/api/v1/products?city_tier=2").json()["products"]) == 24
    assert client.get("/api/v1/health").json()["products"] == 25
