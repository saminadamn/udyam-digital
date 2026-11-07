"""Security pass (DESIGN.md D2.8, D6.1 test_privacy.py): no raw identifiers in logs, uploads encrypted outside the web root and
deleted after retention, rate limits on OTP and registry lookups, secrets required from the environment outside dev."""
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.test_kyc import RAW_GSTIN, run_applicant
from tests.test_tracker import login

REPO = Path(__file__).resolve().parents[2]
PHONE = re.compile(r"(?<!\d)(?:\+91)?[6-9]\d{9}(?!\d)")


def test_every_logger_is_scrubbed_including_children_and_access_log(caplog):
    from app.security import log_filter

    log_filter.install()
    with caplog.at_level(logging.INFO):
        logging.getLogger("udyam.notify.deep.child").warning("send to %s for %s", "+919812345678", "32TTNXB7384T1ZW")
        logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "1.2.3.4", "GET", "/api/v1/kyc/gstin/32TTNXB7384T1ZW", "1.1", 200)
        logging.getLogger("somelib").info("udyam UDYAM-KL-00-3078801 pan ABCDE1234F", extra={})
    text = caplog.text
    assert "200" in text, "numeric args still format"
    assert not RAW_GSTIN.search(text) and not PHONE.search(text) and "3078801" not in text.replace("•••8801", "") and "ABCDE1234F" not in text
    assert "32•••••••••1ZW" in text and "••••••5678" in text


def test_uploads_are_encrypted_outside_the_web_root_and_not_served(client):
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import KycDocument
    from app.security.crypto import decrypt

    h, oid, c, res = run_applicant(client, "+919888800001", "K02")
    upload_dir = Path(get_settings().upload_dir).resolve()
    assert not str(upload_dir).startswith(str((REPO / "frontend").resolve())), "uploads must not live under the frontend"
    with SessionLocal() as db:
        docs = db.query(KycDocument).filter(KycDocument.case_id == c["kyc_case_id"]).all()
        paths = [Path(decrypt(d.storage_path_enc)) for d in docs]
    assert paths and all(p.exists() and p.resolve().is_relative_to(upload_dir) for p in paths)
    for p in paths:
        raw = p.read_bytes()
        assert not raw.startswith((b"\x89PNG", b"\xff\xd8\xff", b"%PDF")) and re.fullmatch(r"[0-9a-f]{32}\.bin", p.name)
    rel = paths[0].relative_to(upload_dir)
    for url in (f"/storage/{rel}", f"/{rel}", f"/api/v1/storage/{rel}", f"/static/{rel}"):
        assert client.get(url).status_code == 404


def test_retention_deletes_files_and_ocr_text_but_spares_cases_in_progress(client):
    from app.db import SessionLocal
    from app.kyc.retention import purge
    from app.models import KycCase, KycDocument
    from app.security.crypto import decrypt

    _, _, done, _ = run_applicant(client, "+919888800002", "K02")
    _, _, review, _ = run_applicant(client, "+919888800003", "K06")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    with SessionLocal() as db:
        for cid in (done["kyc_case_id"], review["kyc_case_id"]):
            db.get(KycCase, cid).retention_until = past
        db.commit()
        out = purge(db)
        assert out["files_deleted"] >= 4
        kept = db.query(KycDocument).filter(KycDocument.case_id == review["kyc_case_id"]).all()
        gone = db.query(KycDocument).filter(KycDocument.case_id == done["kyc_case_id"]).all()
        assert db.get(KycCase, review["kyc_case_id"]).status in ("review", "human_review")
        assert all(d.status != "deleted" and Path(decrypt(d.storage_path_enc)).exists() for d in kept)
        assert all(d.status == "deleted" and d.deleted_at and d.ocr_text_enc is None and d.extracted == "{}" for d in gone)
        assert not any(Path(decrypt(d.storage_path_enc)).exists() for d in gone)
        assert purge(db)["documents"] == 0, "runs are idempotent"


@pytest.fixture()
def limits(monkeypatch):
    from app.config import get_settings
    from app.security import ratelimit

    ratelimit.reset()
    yield monkeypatch, get_settings()
    ratelimit.reset()


def test_registry_lookups_are_rate_limited_per_user(client, limits):
    mp, s = limits
    mp.setattr(s, "lookup_rate_limit", 3)
    h = login(client, "+919888800004")
    codes = [client.get("/api/v1/kyc/gstin/32TTNXB7384T1ZW", headers=h).status_code for _ in range(3)]
    codes.append(client.get("/api/v1/kyc/udyam/UDYAM-KL-00-3078801", headers=h).status_code)
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    r = client.get("/api/v1/kyc/gstin/32TTNXB7384T1ZW", headers=h)
    assert r.json()["error"]["code"] == "RATE_LIMITED" and r.json()["error"]["details"]["retry_after_s"] > 0
    assert client.get("/api/v1/kyc/gstin/32TTNXB7384T1ZW", headers=login(client, "+919888800005")).status_code == 200


def test_otp_is_rate_limited_per_phone_and_per_ip(client, limits):
    mp, s = limits
    codes = [client.post("/api/v1/auth/otp/request", json={"phone": "+919888800006"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429], "3 per phone per 10 minutes"
    mp.setattr(s, "otp_ip_rate_limit", 2)
    from app.security import ratelimit

    ratelimit.reset()
    ip = {"X-Forwarded-For": "203.0.113.9"}
    codes = [client.post("/api/v1/auth/otp/request", json={"phone": f"+91988880001{i}"}, headers=ip).status_code for i in range(3)]
    assert codes == [200, 200, 429], "one IP can't spray codes at many numbers"
    assert client.post("/api/v1/auth/otp/request", json={"phone": "+919888800019"}, headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200


def test_wrong_otp_attempts_are_capped(client):
    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919888800020"}).json()
    codes = [client.post("/api/v1/auth/otp/verify", json={"request_id": r["request_id"], "code": "000000" if r["dev_code"] != "000000" else "111111"}).status_code
             for _ in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429


def test_secrets_must_come_from_the_environment_outside_dev():
    from cryptography.fernet import Fernet

    from app.config import Settings

    Settings(app_env="dev").check_secrets()
    with pytest.raises(RuntimeError) as e:
        Settings(app_env="demo").check_secrets()
    assert "JWT_SECRET" in str(e.value) and "APP_ENCRYPTION_KEY" in str(e.value) and "PII_HASH_KEY" in str(e.value)
    with pytest.raises(RuntimeError):
        Settings(app_env="prod", jwt_secret="x" * 40, pii_hash_key="y" * 40, app_encryption_key="too-short").check_secrets()
    Settings(app_env="prod", jwt_secret="x" * 40, pii_hash_key="y" * 40, app_encryption_key=Fernet.generate_key().decode()).check_secrets()
    Settings(app_env="demo", jwt_secret="x" * 40, pii_hash_key="y" * 40, app_encryption_key="z" * 48).check_secrets()
    from app.security.crypto import fernet_key

    key = Fernet.generate_key()
    assert fernet_key(key.decode()) == key and Fernet(fernet_key("a dashboard-generated random string of any shape"))


def test_no_secrets_or_env_files_in_the_repo():
    ignored = (REPO / ".gitignore").read_text()
    assert ".env" in ignored and "*.db" in ignored and "backend/storage/" in ignored
    leak = re.compile(r"(sk-[A-Za-z0-9]{20,}|AC[0-9a-f]{32}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
    for p in list((REPO / "backend" / "app").rglob("*.py")) + list((REPO / "frontend" / "src").rglob("*.ts*")) + list(REPO.glob("*.y*ml")):
        assert not leak.search(p.read_text(encoding="utf-8", errors="ignore")), p
    for f in (REPO / "backend" / ".env.example", REPO / "frontend" / ".env.example"):
        for line in f.read_text().splitlines():
            if re.match(r"^(JWT_SECRET|APP_ENCRYPTION_KEY|PII_HASH_KEY|TWILIO_AUTH_TOKEN|VOICE_API_KEY|LLM_API_KEY)=", line):
                assert line.split("=", 1)[1].split("#")[0].strip() in ("", "change-me", "change-me-to-32-plus-random-bytes"), line


def test_api_responses_carry_masked_ids_only(client):
    h, oid, c, res = run_applicant(client, "+919888800021", "K02")
    blob = "".join(client.get(u, headers=h).text for u in (f"/api/v1/kyc/{c['kyc_case_id']}/result", f"/api/v1/orders/{oid}", "/api/v1/me",
                                                             f"/api/v1/orders/{oid}/tracker", "/api/v1/notifications"))
    assert not RAW_GSTIN.search(blob) and not PHONE.search(blob)
