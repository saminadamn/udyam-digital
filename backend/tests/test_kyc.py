import json
import logging
import re
from datetime import date
from pathlib import Path

import pytest

from tests.test_quotes import MICRO, make_quote

DOCS = Path(__file__).resolve().parents[2] / "data" / "kyc_documents"
RAW_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]")
TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]


def placed_order(client, phone):
    h, _, q = make_quote(client, phone, MICRO)
    r = client.post(f"/api/v1/quotes/{q['quote_id']}/accept", headers=h)
    assert r.status_code in (200, 201), r.text
    return h, r.json()["order_id"]


def consent(client, h, order_id):
    n = client.get("/api/v1/consent/notice", params={"language": "en"}).json()
    r = client.post("/api/v1/consent", json={"order_id": order_id, "notice_version": n["notice_version"], "granted": True}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, h, case_id, applicant, doc_type):
    data = (DOCS / f"{applicant}_{doc_type}.png").read_bytes()
    return client.post("/api/v1/kyc/upload", data={"case_id": case_id, "doc_type": doc_type},
                       files={"file": (f"{doc_type}.png", data, "image/png")}, headers=h)


def run_applicant(client, phone, applicant):
    h, order_id = placed_order(client, phone)
    c = consent(client, h, order_id)
    for t in TYPES:
        if (DOCS / f"{applicant}_{t}.png").exists():
            assert upload(client, h, c["kyc_case_id"], applicant, t).status_code == 201
    r = client.post(f"/api/v1/kyc/{c['kyc_case_id']}/submit", headers=h)
    assert r.status_code == 202, r.text
    res = client.get(f"/api/v1/kyc/{c['kyc_case_id']}/result", headers=h)
    assert res.status_code == 200
    return h, order_id, c, res.json()


@pytest.fixture(scope="module")
def batch():
    from app.kyc import checks, ocr
    from app.kyc.registry import CsvRegistry

    reg = CsvRegistry(DOCS.parent)
    out = {}
    for k in [f"K{i:02d}" for i in range(1, 13)]:
        docs = {t: (ocr.run(t, (DOCS / f"{k}_{t}.png").read_bytes()) if (DOCS / f"{k}_{t}.png").exists() else None) for t in TYPES}
        out[k] = checks.evaluate(docs, reg, "en", date(2026, 7, 15), 90)
    return out


EXPECTED = {"K01": ("blocked", {"GSTIN_ACTIVE", "UDYAM_EXISTS"}), "K04": ("reupload", {"DOCUMENT_READABLE"}),
            "K05": ("reupload", {"DOCUMENT_PRESENT"}), "K06": ("review", {"GSTIN_MATCHES_CERTIFICATE"}),
            "K07": ("review", {"NAMES_MATCH"}), "K11": ("reupload", {"ADDRESS_PROOF_DATE"})}


@pytest.mark.parametrize("k", [f"K{i:02d}" for i in range(1, 13)])
def test_planted_problems_are_flagged_with_reasons(batch, k):
    verdict, codes = EXPECTED.get(k, ("verified", set()))
    r = batch[k]
    fails = [c for c in r["checks"] if c["result"] == "fail"]
    assert r["verdict"] == verdict
    assert {c["code"] for c in fails} == codes
    for c in fails:
        assert len(c["reason"]) > 15 and len(c["customer"]) > 15
        assert not RAW_GSTIN.search(c["reason"] + c["customer"])


def test_k06_reason_names_the_digit_that_is_not_an_ocr_slip(batch):
    c = next(c for c in batch["K06"]["checks"] if c["code"] == "GSTIN_MATCHES_CERTIFICATE")
    assert "not an OCR look-alike" in c["reason"]


def test_notice_has_the_five_parts_in_every_language(client):
    for lang in ["hi", "en", "mr", "ta", "bn", "kn", "gu", "te"]:
        n = client.get("/api/v1/consent/notice", params={"language": lang}).json()
        assert n["notice_version"] == "kyc-v1.0" and n["language"] == lang
        assert [s["key"] for s in n["sections"]] == ["collect", "why", "retention", "access", "rights"]


def test_no_upload_without_consent(client):
    h, order_id = placed_order(client, "+919822200001")
    data = (DOCS / "K02_signatory_id.png").read_bytes()
    r = client.post("/api/v1/kyc/upload", data={"case_id": "kyc_none", "doc_type": "signatory_id"}, files={"file": ("a.png", data, "image/png")}, headers=h)
    assert r.status_code == 404
    c = consent(client, h, order_id)
    from app.db import SessionLocal
    from app.models import Consent, Order

    with SessionLocal() as db:
        row = db.get(Consent, c["consent_id"])
        assert row.purpose == "kyc_verification" and row.notice_version == "kyc-v1.0" and row.granted_at
        assert db.get(Order, order_id).state == "CONSENT_GIVEN"
    assert upload(client, h, c["kyc_case_id"], "K02", "signatory_id").status_code == 201
    w = client.delete(f"/api/v1/consent/{c['consent_id']}", headers=h)
    assert w.status_code == 200 and w.json()["documents_deleted"] == 1
    r = upload(client, h, c["kyc_case_id"], "K02", "signatory_id")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED"
    with SessionLocal() as db:
        assert db.get(Order, order_id).state == "CANCELLED"


def test_consent_needs_the_current_notice(client):
    h, order_id = placed_order(client, "+919822200002")
    r = client.post("/api/v1/consent", json={"order_id": order_id, "notice_version": "kyc-v0.9", "granted": True}, headers=h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "NOTICE_VERSION_OUTDATED"


def test_gstin_api(client, auth):
    ok = client.get("/api/v1/kyc/gstin/32TTNXB7384T1ZW", headers=auth).json()
    assert ok["gstin_masked"] == "32•••••••••1ZW" and ok["status"] == "Active" and ok["state"] == "Kerala"
    assert "32TTNXB7384T1ZW" not in json.dumps(ok)
    assert client.get("/api/v1/kyc/gstin/32TTNXB7384T1Z", headers=auth).json()["error"]["code"] == "GSTIN_FORMAT"
    assert client.get("/api/v1/kyc/gstin/32TTNXB7384T1ZA", headers=auth).json()["error"]["code"] == "GSTIN_CHECKSUM"
    gone = client.get("/api/v1/kyc/gstin/37IHKXV5167L1ZS", headers=auth).json()
    assert gone["status"] == "Cancelled"


def test_udyam_api_accepts_district_00(client, auth):
    r = client.get("/api/v1/kyc/udyam/UDYAM-KL-00-3078801", headers=auth)
    assert r.status_code == 200 and r.json()["enterprise_name"] == "Balaji Dental Care LLP" and r.json()["udyam_masked"] == "UDYAM-KL-00-•••8801"
    assert client.get("/api/v1/kyc/udyam/UDYAM-KL-0-3078801", headers=auth).json()["error"]["code"] == "UDYAM_FORMAT"


def test_clean_applicant_is_verified(client):
    h, order_id, c, res = run_applicant(client, "+919822200003", "K02")
    assert res["verdict"] == "verified" and res["order_state"] == "INSTALL_BOOKED" and res["fix"] == [] and res["escalation"] is None
    from app.db import SessionLocal
    from app.models import OrderEvent

    with SessionLocal() as db:
        states = [e.to_state for e in db.query(OrderEvent).filter(OrderEvent.order_id == order_id).order_by(OrderEvent.id)]
    assert states[-2:] == ["KYC_VERIFIED", "INSTALL_BOOKED"]
    assert all(x["result"] == "pass" for x in res["checks"])


def test_stale_bill_flags_the_order_and_asks_for_a_reupload(client):
    h, order_id, c, res = run_applicant(client, "+919822200004", "K11")
    assert res["verdict"] == "reupload" and res["order_state"] == "KYC_FLAGGED"
    assert res["fix"] == [x for x in res["checks"] if x["result"] == "fail"]
    assert res["fix"][0]["action"] == {"type": "reupload", "doc_type": "address_proof"}
    assert res["escalation"] and res["escalation"]["priority"] == "P3"
    assert upload(client, h, c["kyc_case_id"], "K02", "address_proof").status_code == 201


def test_mismatch_goes_to_a_person(client):
    h, order_id, c, res = run_applicant(client, "+919822200005", "K06")
    assert res["verdict"] == "review" and res["order_state"] == "HUMAN_REVIEW"
    assert res["escalation"]["priority"] == "P1"
    from app.db import SessionLocal
    from app.models import Escalation, KycCheck, OrderEvent

    with SessionLocal() as db:
        states = [e.to_state for e in db.query(OrderEvent).filter(OrderEvent.order_id == order_id).order_by(OrderEvent.id)]
        assert states[-4:] == ["CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_FLAGGED", "HUMAN_REVIEW"]
        esc = db.query(Escalation).filter(Escalation.kyc_case_id == c["kyc_case_id"]).one()
        assert esc.trigger == "kyc_flag" and esc.required_skill == "kyc" and not RAW_GSTIN.search(esc.reason)
        assert not any(RAW_GSTIN.search(x.detail_internal or "") for x in db.query(KycCheck).filter(KycCheck.case_id == c["kyc_case_id"]))


def test_logs_never_show_a_raw_gstin(caplog):
    from app.security.log_filter import PIIFilter

    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "lookup 32TTNXB7384T1ZW for UDYAM-KL-00-3078801", None, None)
    PIIFilter().filter(rec)
    assert rec.getMessage() == "lookup 32•••••••••1ZW for UDYAM-KL-00-•••8801"
