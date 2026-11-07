"""Consent and KYC flow: consent opens a case, uploads are OCR'd on arrival, submit runs every check and moves the order."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.kyc import checks, ocr, storage
from app.kyc import gstin as G
from app.kyc.registry import DbRegistry
from app.models import (Business, Consent, Escalation, KycCase, KycCheck, KycDocument, Order, Product, Quote,
                        QuoteItem, User, now_iso)
from app.orders import state_machine
from app.security.crypto import decrypt, encrypt
from app.security.masking import mask_gstin, mask_udyam

PURPOSE = "kyc_verification"
INSTANT = {"gst_certificate": {"DOCUMENT_READABLE", "GSTIN_FORMAT", "GSTIN_MATCHES_CERTIFICATE", "GSTIN_EXISTS", "GSTIN_ACTIVE", "GSTIN_STATE_CODE"},
           "udyam_certificate": {"DOCUMENT_READABLE", "UDYAM_EXISTS", "UDYAM_NAME_MATCH"},
           "signatory_id": {"DOCUMENT_READABLE"},
           "address_proof": {"DOCUMENT_READABLE", "ADDRESS_PROOF_DATE"}}
PRIORITY = {"blocked": ("P1", 4), "review": ("P1", 4), "reupload": ("P3", 24)}
LABEL = {"blocked": "Blocked", "reupload": "Re-upload needed", "review": "Human review", "verified": "Verified"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


@lru_cache
def _notice() -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "i18n" / "consent_notice.json").read_text(encoding="utf-8"))


def notice(purpose: str, language: str) -> dict:
    if purpose != PURPOSE:
        raise ApiError(404, "NOTICE_NOT_FOUND", "There is no notice for that purpose.")
    n = _notice()
    body = n["languages"].get(language) or n["languages"]["en"]
    s = get_settings()
    return {"notice_version": n["version"], "purpose": purpose, "language": language if language in n["languages"] else "en",
            "retention_days": s.doc_retention_days, "retention_abandoned_days": s.doc_retention_abandoned_days, **body}


def _owned_order(db: Session, user: User, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if not order or (order.user_id != user.id and user.role == "customer"):
        raise ApiError(404, "ORDER_NOT_FOUND", "We couldn't find that order.")
    return order


def _owned_case(db: Session, user: User, case_id: str) -> tuple[KycCase, Order]:
    case = db.get(KycCase, case_id)
    order = db.get(Order, case.order_id) if case else None
    if not case or (order.user_id != user.id and user.role == "customer"):
        raise ApiError(404, "CASE_NOT_FOUND", "We couldn't find that KYC case.")
    return case, order


def _active_consent(db: Session, case: KycCase) -> Consent | None:
    c = db.get(Consent, case.consent_id)
    return c if c and c.granted and not c.withdrawn_at else None


def give_consent(db: Session, user: User, order_id: str, notice_version: str, granted: bool, language: str | None, client: str | None) -> dict:
    order = _owned_order(db, user, order_id)
    if notice_version != _notice()["version"]:
        raise ApiError(400, "NOTICE_VERSION_OUTDATED", "The privacy notice has changed. Please read it again.", {"current": _notice()["version"]})
    if not granted:
        raise ApiError(400, "CONSENT_NOT_GRANTED", "We can only check documents after you agree.")
    if order.state != "QUOTE_ACCEPTED":
        existing = db.scalar(select(KycCase).where(KycCase.order_id == order.id))
        if existing and order.state != "CANCELLED":
            return {"consent_id": existing.consent_id, "kyc_case_id": existing.id, "order_state": order.state}
        raise ApiError(409, "INVALID_STATE", "This order isn't waiting for consent.", {"state": order.state})
    now = _now()
    consent = Consent(user_id=user.id, business_id=order.business_id, order_id=order.id, purpose=PURPOSE, notice_version=notice_version,
                      language=language or user.language, granted=1, granted_at=_iso(now),
                      client_hash=hashlib.sha256(client.encode()).hexdigest()[:16] if client else None)
    db.add(consent)
    db.flush()
    case = KycCase(order_id=order.id, business_id=order.business_id, consent_id=consent.id, status="open",
                   retention_until=_iso(now + timedelta(days=get_settings().doc_retention_abandoned_days)))
    biz = db.get(Business, order.business_id)
    if biz and biz.gstin_enc:
        case.gstin_enc, case.gstin_masked = biz.gstin_enc, biz.gstin_masked
    db.add(case)
    state_machine.transition(db, order, "CONSENT_GIVEN", f"customer:{user.id}", f"consent {notice_version}")
    db.commit()
    return {"consent_id": consent.id, "kyc_case_id": case.id, "order_state": order.state, "granted_at": consent.granted_at,
            "notice_version": notice_version, "purpose": PURPOSE}


def withdraw(db: Session, user: User, consent_id: str) -> dict:
    c = db.get(Consent, consent_id)
    if not c or c.user_id != user.id:
        raise ApiError(404, "CONSENT_NOT_FOUND", "We couldn't find that consent.")
    if c.withdrawn_at:
        raise ApiError(409, "ALREADY_WITHDRAWN", "This consent was already withdrawn.")
    c.withdrawn_at, c.granted = now_iso(), 0
    case = db.scalar(select(KycCase).where(KycCase.consent_id == c.id))
    deleted = 0
    if case:
        case.status, case.retention_until = "rejected", now_iso()
        for d in db.scalars(select(KycDocument).where(KycDocument.case_id == case.id, KycDocument.deleted_at.is_(None))):
            storage.delete(decrypt(d.storage_path_enc))
            d.ocr_text_enc, d.status, d.deleted_at, d.extracted = None, "deleted", now_iso(), "{}"
            deleted += 1
        for e in db.scalars(select(Escalation).where(Escalation.kyc_case_id == case.id, Escalation.status.in_(("open", "assigned", "in_progress")))):
            e.status, e.resolution, e.resolved_at = "resolved", "consent_withdrawn", now_iso()
        order = db.get(Order, case.order_id)
        if order and "CANCELLED" in state_machine.TRANSITIONS.get(order.state, set()):
            state_machine.transition(db, order, "CANCELLED", f"customer:{user.id}", "consent withdrawn")
    db.commit()
    return {"withdrawn_at": c.withdrawn_at, "kyc_case_status": case.status if case else None, "documents_scheduled_for_deletion": deleted,
            "documents_deleted": deleted}


def _gst_only_items(db: Session, order: Order) -> list[dict]:
    q = db.get(Quote, order.quote_id)
    if not q:
        return []
    rows = db.execute(select(QuoteItem, Product).join(Product, Product.product_id == QuoteItem.product_id)
                      .where(QuoteItem.quote_id == q.id, QuoteItem.selected == 1, Product.requires_gstin == 1)).all()
    return [{"product_id": p.product_id, "name": p.name} for _, p in rows]


def gstin_lookup(db: Session, user: User, raw: str, order_id: str | None) -> dict:
    g = G.normalise(raw)
    if not G.format_ok(g):
        raise ApiError(400, "GSTIN_FORMAT", "A GSTIN has 15 characters: 2 digits, 10-character PAN, then 3 more.")
    if not G.checksum_ok(g):
        raise ApiError(400, "GSTIN_CHECKSUM", "That GSTIN's last character doesn't add up. Please check for a typo.")
    rec = DbRegistry(db).gstin(g)
    if not rec:
        raise ApiError(404, "GSTIN_NOT_FOUND", "This GSTIN isn't in the GST registry. Check the number or upload your certificate.",
                       {"gstin_masked": mask_gstin(g)})
    active = rec["status"] == "Active"
    effects = {"removed_products": [], "quote_repriced": False, "action": None}
    if order_id:
        order = _owned_order(db, user, order_id)
        biz = db.get(Business, order.business_id)
        if biz:
            biz.gstin_enc, biz.gstin_masked, biz.gst_status, biz.has_gstin = encrypt(g), mask_gstin(g), rec["status"], 1
        case = db.scalar(select(KycCase).where(KycCase.order_id == order.id))
        if case:
            case.gstin_enc, case.gstin_masked = encrypt(g), mask_gstin(g)
        if not active:
            effects = {"removed_products": _gst_only_items(db, order), "quote_repriced": False, "action": "change_bundle"}
        db.commit()
    code_state = G.STATE_CODES.get(g[:2])
    return {"gstin_masked": mask_gstin(g), "valid_format": True, "checksum_ok": True, "found": True, "legal_name": rec["legal_name"],
            "trade_name": rec["trade_name"], "constitution": rec["constitution"], "state": rec["state"], "status": rec["status"],
            "address_city": checks.place(rec["principal_place_of_business"])[0], "state_code_matches": code_state == rec["state"],
            "effects": effects}


def udyam_lookup(db: Session, user: User, raw: str, order_id: str | None) -> dict:
    num = (raw or "").strip().upper()
    if not G.udyam_format_ok(num) or num[6:8] not in G.UDYAM_STATES:
        raise ApiError(400, "UDYAM_FORMAT", "A Udyam number looks like UDYAM-XX-00-1234567.")
    rec = DbRegistry(db).udyam(num)
    if not rec:
        raise ApiError(404, "UDYAM_NOT_FOUND", "This Udyam number isn't in the Udyam registry.", {"udyam_masked": mask_udyam(num)})
    out = {"udyam_masked": mask_udyam(num), "found": True, "enterprise_name": rec["enterprise_name"], "enterprise_type": rec["enterprise_type"],
           "city": rec["city"], "state": rec["state"], "matches_gst_trade_name": None, "matches_gst_state": None}
    if order_id:
        order = _owned_order(db, user, order_id)
        biz = db.get(Business, order.business_id)
        g = decrypt(biz.gstin_enc) if biz and biz.gstin_enc else None
        gst = DbRegistry(db).gstin(g) if g else None
        if gst:
            from app.kyc import names

            out["matches_gst_trade_name"] = names.match(rec["enterprise_name"], gst["trade_name"])
            out["matches_gst_state"] = rec["state"] == gst["state"]
        if biz:
            biz.udyam_enc, biz.udyam_masked, biz.has_udyam = encrypt(num), mask_udyam(num), 1
        db.commit()
    return out


def _latest_docs(db: Session, case_id: str) -> dict[str, KycDocument]:
    out: dict[str, KycDocument] = {}
    for d in db.scalars(select(KycDocument).where(KycDocument.case_id == case_id, KycDocument.deleted_at.is_(None)).order_by(KycDocument.version)):
        out[d.doc_type] = d
    return out


def _as_ocr(d: KycDocument) -> ocr.OcrResult:
    ex = json.loads(d.extracted or "{}")
    return ocr.OcrResult(d.doc_type, "", d.ocr_confidence or 0, d.sharpness or 0, d.skew_deg or 0, bool(ex.get("readable")),
                         ex.get("fields") or {}, ex.get("gstin_raw"))


def _evaluate(db: Session, case: KycCase, lang: str) -> dict:
    s = get_settings()
    docs = {t: _as_ocr(d) for t, d in _latest_docs(db, case.id).items()}
    full = {t: docs.get(t) for t in ocr.DOC_TYPES}
    declared = decrypt(case.gstin_enc) if case.gstin_enc else None
    return checks.evaluate(full, DbRegistry(db), lang, date.fromisoformat(s.kyc_today), s.kyc_address_proof_max_days, declared)


def _public_fields(doc_type: str, fields: dict) -> dict:
    """What the customer sees of the OCR output: identifiers masked, nothing extra."""
    f = dict(fields)
    f.pop("gstin_text", None)
    if doc_type == "udyam_certificate" and f.get("udyam_number"):
        f["udyam_number"] = mask_udyam(f["udyam_number"])
    if doc_type == "signatory_id" and f.get("id_number"):
        n = f["id_number"]
        f["id_number"] = ("•" * max(0, len(n) - 4)) + n[-4:] if len(n) > 4 else "••••"
    return f


def upload(db: Session, user: User, case_id: str, doc_type: str, filename: str | None, data: bytes, lang: str | None) -> dict:
    case, order = _owned_case(db, user, case_id)
    if not _active_consent(db, case):
        raise ApiError(403, "CONSENT_REQUIRED", "Please agree to the privacy notice before uploading documents.")
    if case.status not in ("open", "flagged"):
        raise ApiError(409, "CASE_NOT_OPEN", "This KYC case isn't taking new documents right now.", {"status": case.status})
    if doc_type not in ocr.DOC_TYPES:
        raise ApiError(422, "BAD_DOC_TYPE", "Unknown document type.", {"allowed": list(ocr.DOC_TYPES)})
    if len(data) > get_settings().upload_max_mb * 1024 * 1024:
        raise ApiError(413, "FILE_TOO_LARGE", f"Files must be under {get_settings().upload_max_mb} MB.")
    mime = storage.sniff(data)
    if mime not in ("image/png", "image/jpeg"):
        raise ApiError(415, "UNSUPPORTED_TYPE", "Please upload a photo (JPG or PNG).")
    res = ocr.run(doc_type, data)
    path, sha = storage.save(case.id, data)
    prev = _latest_docs(db, case.id).get(doc_type)
    doc = KycDocument(case_id=case.id, doc_type=doc_type, version=(prev.version + 1) if prev else 1, storage_path_enc=encrypt(path), sha256=sha,
                      mime=mime, size_bytes=len(data), ocr_text_enc=encrypt(res.text), ocr_confidence=res.confidence, sharpness=res.sharpness,
                      skew_deg=res.skew_deg, extracted=json.dumps({"fields": res.fields, "gstin_raw": res.gstin_raw, "readable": res.readable}),
                      status="processed" if res.readable else "unreadable")
    db.add(doc)
    if prev:
        prev.status = "superseded"
    db.flush()
    result = _evaluate(db, case, lang or user.language)
    instant = [c for c in result["checks"] if c["code"] in INSTANT[doc_type] and (c["doc_type"] in (None, doc_type))]
    if result.get("gstin") and not case.gstin_enc:
        case.gstin_enc, case.gstin_masked = encrypt(result["gstin"]), mask_gstin(result["gstin"])
    if result.get("udyam"):
        case.udyam_enc, case.udyam_masked = encrypt(result["udyam"]), mask_udyam(result["udyam"])
    db.commit()
    return {"document_id": doc.id, "doc_type": doc_type, "version": doc.version,
            "quality": {"sharpness": res.sharpness, "skew_corrected_deg": res.skew_deg, "ocr_confidence": res.confidence, "readable": res.readable},
            "extracted": _public_fields(doc_type, res.fields),
            "instant_checks": [{"check_code": c["code"], "result": c["result"], "severity": c["severity"], "message": c["customer"]} for c in instant]}


def submit(db: Session, user: User, case_id: str) -> dict:
    case, order = _owned_case(db, user, case_id)
    if not _active_consent(db, case):
        raise ApiError(403, "CONSENT_REQUIRED", "Please agree to the privacy notice first.")
    if case.status not in ("open", "flagged"):
        raise ApiError(409, "CASE_NOT_OPEN", "This KYC case was already submitted.", {"status": case.status})
    if not _latest_docs(db, case.id):
        raise ApiError(409, "DOCUMENTS_MISSING", "Please upload your documents first.", {"missing": list(ocr.DOC_TYPES)})
    state_machine.transition(db, order, "KYC_SUBMITTED", f"customer:{user.id}")
    case.status, case.submitted_at, case.verdict = "submitted", now_iso(), None
    db.commit()
    return {"case_id": case.id, "status": "submitted", "order_state": order.state}


def _escalate(db: Session, case: KycCase, order: Order, verdict: str, fails: list[dict], lang: str) -> Escalation:
    from app.escalations.service import create

    for e in db.scalars(select(Escalation).where(Escalation.kyc_case_id == case.id, Escalation.status.in_(("open", "assigned", "in_progress")))):
        e.status, e.resolution, e.resolved_at = "resolved", "superseded_by_resubmission", now_iso()
    prio, hours = PRIORITY[verdict]
    reason = f"KYC {LABEL[verdict]}: " + "; ".join(f"{c['code']}: {c['reason']}" for c in fails)
    return create(db, trigger="kyc_flag", priority=prio, skill="kyc", reason=reason, lang=lang, order=order, kyc_case_id=case.id,
                  sla_hours=hours, notify_customer=verdict != "reupload")


def run_checks(db: Session, case_id: str) -> str:
    from app.notifications.service import notify

    """The background step after submit: every rule, then the order moves. Any fail -> KYC_FLAGGED and an escalation."""
    case = db.get(KycCase, case_id)
    order = db.get(Order, case.order_id)
    user = db.get(User, order.user_id)
    lang = user.language if user else "en"
    result = _evaluate(db, case, lang)
    v = result["verdict"]
    for old in db.scalars(select(KycCheck).where(KycCheck.case_id == case.id)):
        db.delete(old)
    for c in result["checks"]:
        doc = _latest_docs(db, case.id).get(c["doc_type"]) if c["doc_type"] else None
        db.add(KycCheck(case_id=case.id, document_id=doc.id if doc else None, check_code=c["code"], result=c["result"], severity=c["severity"],
                        message_customer=c["customer"], detail_internal=c["reason"]))
    if result["gst"]:
        snap = {k: result["gst"][k] for k in ("trade_name", "constitution", "state", "status")}
        snap["udyam"] = {k: result["udyam_record"][k] for k in ("enterprise_name", "city", "state")} if result["udyam_record"] else None
        case.registry_snapshot = json.dumps(snap)
    if result["gstin"]:
        case.gstin_enc, case.gstin_masked = encrypt(result["gstin"]), mask_gstin(result["gstin"])
    case.verdict = v
    if v == "verified":
        case.status, case.verified_at = "verified", now_iso()
        case.retention_until = _iso(_now() + timedelta(days=get_settings().doc_retention_days))
        state_machine.transition(db, order, "KYC_VERIFIED", "system:kyc", "all checks passed")
        from app.orders.fulfilment import on_verified

        notify(db, order.user_id, order.id, "kyc_verified", lang, {"display_id": order.display_id, "verdict": v})
        on_verified(db, order)
    else:
        fails = [c for c in result["checks"] if c["result"] == "fail"]
        case.status = "review" if v == "review" else "flagged"
        state_machine.transition(db, order, "KYC_FLAGGED", "system:kyc", f"{LABEL[v]}: " + ", ".join(c["code"] for c in fails))
        e = _escalate(db, case, order, v, fails, lang)
        if v == "review":
            state_machine.transition(db, order, "HUMAN_REVIEW", "system:kyc", "sent to a KYC specialist")
            from app.escalations.service import customer_message

            notify(db, order.user_id, order.id, "kyc_review", lang, {"display_id": order.display_id, "verdict": v,
                                                                    "message": customer_message(db, e, lang)})
        else:
            first = next((c for c in fails if c.get("customer")), None)
            notify(db, order.user_id, order.id, "kyc_fix_needed", lang, {"display_id": order.display_id, "verdict": v,
                                                                        "fix": first["customer"] if first else "", "checks": [c["code"] for c in fails]})
    db.commit()
    return v


def run_checks_task(case_id: str) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        run_checks(db, case_id)
    finally:
        db.close()


def _code_doc(c: KycCheck) -> str | None:
    if c.check_code == "DOCUMENT_PRESENT" and c.detail_internal:
        return c.detail_internal.split(":")[0]
    return None


def result(db: Session, user: User, case_id: str) -> dict:
    case, order = _owned_case(db, user, case_id)
    docs = _latest_docs(db, case.id)
    out = {"case_id": case.id, "status": case.status, "order_id": order.id, "order_state": order.state, "gstin_masked": case.gstin_masked,
           "udyam_masked": case.udyam_masked, "consent_id": case.consent_id,
           "documents": [{"document_id": d.id, "doc_type": t, "version": d.version, "readable": d.status != "unreadable"} for t, d in docs.items()]}
    if case.status in ("open", "submitted"):
        return out | {"verdict": None, "verdict_label": None, "checks": [], "fix": [], "escalation": None}
    rows = db.scalars(select(KycCheck).where(KycCheck.case_id == case.id).order_by(KycCheck.id)).all()
    by_id = {d.id: t for t, d in docs.items()}
    by_any = {d.id: d.doc_type for d in db.scalars(select(KycDocument).where(KycDocument.case_id == case.id))}
    lst = [{"check_code": c.check_code, "result": c.result, "severity": c.severity, "message": c.message_customer,
            "doc_type": by_id.get(c.document_id) or by_any.get(c.document_id) or _code_doc(c)} for c in rows]
    for c in lst:
        c["action"] = ({"type": "change_bundle"} if c["severity"] == "blocking" else
                       {"type": "reupload", "doc_type": c["doc_type"]} if c["severity"] in checks.REUPLOAD and c["doc_type"] else
                       {"type": "wait_for_call"} if c["result"] == "fail" else None)
    esc = db.scalar(select(Escalation).where(Escalation.kyc_case_id == case.id).order_by(Escalation.created_at.desc()))
    esc_out = None
    if esc and esc.status in ("open", "assigned", "in_progress"):
        from app.models import Agent

        agent = db.get(Agent, esc.assigned_agent_id) if esc.assigned_agent_id else None
        esc_out = {"escalation_id": esc.id, "priority": esc.priority, "status": esc.status, "agent_name": agent.name.split()[0] if agent else None,
                   "sla_due_at": esc.sla_due_at}
    return out | {"verdict": case.verdict, "verdict_label": LABEL.get(case.verdict), "checks": lst,
                  "fix": [c for c in lst if c["result"] == "fail"], "escalation": esc_out,
                  "blocked_items": _gst_only_items(db, order) if case.verdict == "blocked" else []}
