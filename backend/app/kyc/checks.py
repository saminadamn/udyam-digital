"""KYC cross-checks. Every rule is its own function-sized block that adds one Check with a pass/fail, a severity and a reason.

Thresholds live in docs/KYC_CHECKS.md. The verdict comes only from the severities of the failed checks:
blocking -> Blocked, missing/unreadable/stale -> Re-upload needed, mismatch/needs_review -> Human review, nothing failed -> Verified.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.kyc import gstin as G
from app.kyc import names
from app.kyc.ocr import DOC_TYPES, OcrResult
from app.security.masking import mask_gstin, mask_udyam, scrub

VERDICTS = ("blocked", "reupload", "review", "verified")
REUPLOAD = {"missing_document", "unreadable", "stale"}


@dataclass
class Check:
    code: str
    result: str
    severity: str | None
    reason: str
    customer: str
    doc_type: str | None = None


class Registry(Protocol):
    def gstin(self, g: str) -> dict | None: ...
    def gstins_by_name(self, name: str) -> list[dict]: ...
    def udyam(self, num: str) -> dict | None: ...
    def udyams_by_name(self, name: str) -> list[dict]: ...


@lru_cache
def _messages() -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "i18n" / "kyc_messages.json").read_text(encoding="utf-8"))


def text(lang: str, key: str, **kw) -> str:
    m = _messages()
    s = m.get(lang, {}).get(key) or m["en"][key]
    return s.format(**kw)


def doc_name(lang: str, doc_type: str) -> str:
    return text(lang, f"doc.{doc_type}")


def place(addr: str | None) -> tuple[str, str]:
    """'Shop/Unit 164, Station Road, Kochi, Kerala - 289398' -> ('Kochi', 'Kerala')."""
    parts = [p.strip() for p in re.sub(r"\s*-\s*\d{6}\s*$", "", addr or "").split(",")]
    return (parts[-2], parts[-1]) if len(parts) >= 2 else ("", "")


def _squash(s: str | None) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def verdict(checks: list[Check]) -> str:
    failed = {c.severity for c in checks if c.result == "fail"}
    if "blocking" in failed:
        return "blocked"
    if failed & REUPLOAD:
        return "reupload"
    if failed:
        return "review"
    return "verified"


class Run:
    def __init__(self, docs: dict[str, OcrResult | None], reg: Registry, lang: str, today: date, max_days: int, declared_gstin: str | None):
        self.docs, self.reg, self.lang, self.today, self.max_days = docs, reg, lang, today, max_days
        self.declared = G.normalise(declared_gstin) if declared_gstin else None
        self.checks: list[Check] = []
        self.gstin: str | None = None
        self.gst: dict | None = None
        self.udyam_num: str | None = None
        self.udy: dict | None = None

    def add(self, code: str, ok: bool, severity: str, reason: str, msg_key: str | None = None, doc_type: str | None = None, **kw):
        customer = text(self.lang, f"pass.{code}", **kw) if ok else text(self.lang, msg_key or f"fail.{code}", **kw)
        self.checks.append(Check(code, "pass" if ok else "fail", None if ok else severity, scrub(reason), customer, doc_type))

    def ok(self, doc_type: str) -> OcrResult | None:
        d = self.docs.get(doc_type)
        return d if d is not None and d.readable else None

    def f(self, doc_type: str, key: str) -> str | None:
        d = self.ok(doc_type)
        return (d.fields or {}).get(key) if d else None

    def documents(self):
        for t in DOC_TYPES:
            d = self.docs.get(t)
            name = doc_name(self.lang, t)
            self.add("DOCUMENT_PRESENT", d is not None, "missing_document", f"{t}: " + ("uploaded" if d is not None else "not uploaded"),
                     doc_type=t, doc=name)
            if d is not None:
                self.add("DOCUMENT_READABLE", d.readable, "unreadable",
                         f"{t}: sharpness {d.sharpness} (min 50), OCR confidence {d.confidence}% (min 55), straightened {d.skew_deg:+.0f} deg",
                         doc_type=t, doc=name)

    def _gst_reads(self) -> list[str]:
        d = self.ok("gst_certificate")
        if not d:
            return []
        reads = [r for r in (d.gstin_raw or "").split("|") if r]
        if (d.fields or {}).get("gstin_text"):
            reads.insert(0, d.fields["gstin_text"])
        return reads

    def resolve_gstin(self):
        """Work out which GSTIN the certificate shows, then run the four GSTIN rules against the registry."""
        reads = self._gst_reads()
        exists = lambda g: self.reg.gstin(g) is not None
        found, how = None, None
        for r in reads:
            found = G.repair(r, exists)
            if found:
                how = "read" if G.normalise(r)[-15:] == found else "read with look-alike characters fixed"
                self.add("GSTIN_MATCHES_CERTIFICATE", True, "mismatch", f"certificate shows {mask_gstin(found)} ({how}), checksum valid and in registry")
                break
        cert_name = self.f("gst_certificate", "trade_name") or names.proprietor_parts(self.f("gst_certificate", "legal_name"))[1]
        if not found and reads and cert_name:
            cands = self.reg.gstins_by_name(cert_name)
            if cands:
                flat = max(reads, key=lambda r: -abs(len(G.normalise(r)) - 15))
                best = min(cands, key=lambda c: sum(a != b for a, b in zip(G.normalise(flat)[-15:], c["gstin"])))
                explained = any(G.explained_by_ocr(r, best["gstin"]) for r in reads)
                self.add("GSTIN_MATCHES_CERTIFICATE", explained, "mismatch",
                         f"certificate GSTIN reads {mask_gstin(G.normalise(flat))}; registry GSTIN for '{best['trade_name']}' is {mask_gstin(best['gstin'])}"
                         + ("" if explained else "; the difference is not an OCR look-alike, so the number on the certificate is not this business's GSTIN"))
                found, how = best["gstin"], "matched by business name"
        if found and self.declared and self.declared != found:
            self.add("GSTIN_MATCHES_CERTIFICATE", False, "mismatch",
                     f"typed GSTIN {mask_gstin(self.declared)} differs from the certificate {mask_gstin(found)}")
        if not found and self.declared and not self.ok("gst_certificate"):
            found, how = self.declared, "typed by the customer (certificate not readable)"
        if not found and not self.ok("gst_certificate"):
            bill = self.f("address_proof", "billed_to") or self.f("udyam_certificate", "enterprise_name")
            hits = self.reg.gstins_by_name(bill) if bill else []
            if len(hits) == 1:
                found, how = hits[0]["gstin"], "looked up by business name (certificate not readable)"
        if not found:
            if self.ok("gst_certificate") or self.declared:
                self.add("GSTIN_FORMAT", False, "needs_review", f"no valid GSTIN found; OCR saw {[mask_gstin(G.normalise(r)) for r in reads][:3]}")
            return
        self.gstin = found
        self.add("GSTIN_FORMAT", G.checksum_ok(found), "needs_review",
                 f"{mask_gstin(found)}: 15 characters, PAN block and check digit valid ({how})")
        self.gst = self.reg.gstin(found)
        self.add("GSTIN_EXISTS", self.gst is not None, "mismatch", f"{mask_gstin(found)} " + ("found in GST registry" if self.gst else "not in GST registry"))
        if not self.gst:
            return
        status = self.gst["status"]
        self.add("GSTIN_ACTIVE", status == "Active", "blocking", f"registry status {status}", status=text(self.lang, f"status.{status}") if f"status.{status}" in _messages()["en"] else status)
        code_state = G.STATE_CODES.get(found[:2])
        self.add("GSTIN_STATE_CODE", code_state == self.gst["state"], "mismatch",
                 f"state code {found[:2]} = {code_state}; registry state {self.gst['state']}")

    def udyam(self):
        if not self.ok("udyam_certificate"):
            return
        num = self.f("udyam_certificate", "udyam_number")
        name, city = self.f("udyam_certificate", "enterprise_name"), self.f("udyam_certificate", "city")
        if not num:
            same = [u for u in self.reg.udyams_by_name(name or "") if _squash(u["city"]) == _squash(city)]
            elsewhere = [u for u in self.reg.udyams_by_name(name or "") if _squash(u["city"]) != _squash(city)]
            reason = "registration number is blank on the certificate"
            if same:
                reason += f"; registry has {mask_udyam(same[0]['udyam_number'])} for this name in {city}, ask the customer to confirm"
            elif elsewhere:
                reason += f"; no record for this name in {city}, same name exists in {', '.join(u['city'] for u in elsewhere)} (different business)"
            self.add("UDYAM_EXISTS", False, "mismatch", reason, msg_key="fail.UDYAM_BLANK")
            return
        self.udyam_num = num
        fmt = G.udyam_format_ok(num) and num[6:8] in G.UDYAM_STATES
        self.udy = self.reg.udyam(num) if fmt else None
        self.add("UDYAM_EXISTS", self.udy is not None, "mismatch",
                 f"{mask_udyam(num)} " + ("found in Udyam registry" if self.udy else "not in Udyam registry" if fmt else "has an invalid format"))
        if self.udy:
            self.add("UDYAM_NAME_MATCH", names.match(name, self.udy["enterprise_name"]), "mismatch",
                     f"certificate '{name}' vs Udyam registry '{self.udy['enterprise_name']}'")

    def names_consistent(self):
        """GST cert (trade name, and the business inside 'Owner (Prop. X)'), Udyam cert and registry must all name one business."""
        seen = []
        trade = self.f("gst_certificate", "trade_name")
        owner, prop = names.proprietor_parts(self.f("gst_certificate", "legal_name"))
        if trade:
            seen.append(("GST certificate trade name", trade))
        if prop:
            seen.append(("GST certificate legal name", prop))
        if self.f("udyam_certificate", "enterprise_name"):
            seen.append(("Udyam certificate", self.f("udyam_certificate", "enterprise_name")))
        ref = None
        if self.gst:
            ref = ("GST registry", self.gst["trade_name"])
        elif self.udy:
            ref = ("Udyam registry", self.udy["enterprise_name"])
        if not ref or not seen:
            return
        bad = [(where, n) for where, n in seen if not names.match(n, ref[1])]
        if self.gst and owner:
            reg_owner = names.proprietor_parts(self.gst["legal_name"])[0]
            if reg_owner and not names.match(owner, reg_owner):
                bad.append(("GST certificate proprietor", owner))
        reason = "; ".join(f"{w} '{n}'" for w, n in seen) + f" vs {ref[0]} '{ref[1]}'"
        if bad:
            reason = "differs: " + "; ".join(f"{w} '{n}'" for w, n in bad) + f" vs {ref[0]} '{ref[1]}'"
        self.add("NAMES_MATCH", not bad, "mismatch", reason, business=ref[1])

    def signatory(self):
        biz = self.f("signatory_id", "business")
        if not biz or not (self.gst or self.udy):
            return
        ref = [self.gst["trade_name"], self.gst["legal_name"]] if self.gst else [self.udy["enterprise_name"]]
        self.add("SIGNATORY_FOR_BUSINESS", any(names.match(biz, r) for r in ref), "mismatch",
                 f"ID card is for '{biz}', registry business '{ref[0]}'")

    def address(self):
        addr = self.f("address_proof", "address")
        if not self.ok("address_proof"):
            return
        if self.gst:
            city, state = place(self.gst["principal_place_of_business"])
            src = "GST registry"
        elif self.udy:
            city, state, src = self.udy["city"], self.udy["state"], "Udyam registry"
        else:
            return
        a = _squash(addr)
        self.add("ADDRESS_MATCH", bool(a) and _squash(city) in a and _squash(state) in a, "mismatch",
                 f"bill address '{addr}' vs {src} {city}, {state}", city=city, state=state)

    def address_date(self):
        if not self.ok("address_proof"):
            return
        raw = self.f("address_proof", "bill_date")
        try:
            d = date.fromisoformat(raw or "")
        except ValueError:
            self.add("ADDRESS_PROOF_DATE", False, "unreadable", f"bill date not readable ('{raw}')", msg_key="fail.ADDRESS_PROOF_DATE_UNREADABLE", doc_type="address_proof")
            return
        age = (self.today - d).days
        self.add("ADDRESS_PROOF_DATE", 0 <= age <= self.max_days, "stale",
                 f"bill dated {d.isoformat()}, {age} days before {self.today.isoformat()} (limit {self.max_days})", doc_type="address_proof", date=d.isoformat(), days=age)

    def run(self):
        self.documents()
        self.resolve_gstin()
        self.udyam()
        self.names_consistent()
        self.signatory()
        self.address()
        self.address_date()
        return self


def evaluate(docs: dict[str, OcrResult | None], reg: Registry, lang: str = "en", today: date = date(2026, 7, 15),
             max_days: int = 90, declared_gstin: str | None = None) -> dict:
    r = Run(docs, reg, lang, today, max_days, declared_gstin).run()
    return {"verdict": verdict(r.checks), "checks": [asdict(c) for c in r.checks], "gstin": r.gstin, "gst": r.gst,
            "udyam": r.udyam_num, "udyam_record": r.udy}


def fix_list(checks: list[dict]) -> list[dict]:
    """What the customer has to do, one line per failed check, re-uploads first."""
    fails = [c for c in checks if c["result"] == "fail"]
    return sorted(({"code": c["code"], "doc_type": c["doc_type"], "message": c["customer"], "reupload": c["severity"] in REUPLOAD}
                   for c in fails), key=lambda x: not x["reupload"])
