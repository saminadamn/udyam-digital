import itertools
import json
import re
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd
import pytesseract
from PIL import Image, ImageFilter, ImageOps

root = Path(sys.argv[1])
docs = root / "data" / "kyc_documents"
outdir = root / "analysis" / "kyc"
outdir.mkdir(parents=True, exist_ok=True)
TODAY = date(2026, 7, 15)
GST = pd.read_csv(root / "data" / "mock_gstin_registry.csv", dtype=str).set_index("gstin")
UDY = pd.read_csv(root / "data" / "mock_udyam_registry.csv", dtype=str).set_index("udyam_number")
STATE_CODES = {"03": "Punjab", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "19": "West Bengal", "23": "Madhya Pradesh",
               "24": "Gujarat", "27": "Maharashtra", "29": "Karnataka", "32": "Kerala", "33": "Tamil Nadu", "36": "Telangana", "37": "Andhra Pradesh"}
UDY_STATE = {"PB": "Punjab", "DL": "Delhi", "RJ": "Rajasthan", "UP": "Uttar Pradesh", "BR": "Bihar", "WB": "West Bengal", "MP": "Madhya Pradesh",
             "GJ": "Gujarat", "MH": "Maharashtra", "KA": "Karnataka", "KL": "Kerala", "TN": "Tamil Nadu", "TS": "Telangana", "AP": "Andhra Pradesh"}
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_ok(g):
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g or ""):
        return False
    total = 0
    for i, ch in enumerate(g[:14]):
        v = CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return CHARS[(36 - total % 36) % 36] == g[14]


CONFUSE = {"6": "0G", "0": "OD6G", "O": "0D", "D": "0O", "1": "IL7", "I": "1LJ", "J": "I", "3": "98", "9": "3", "L": "1I", "7": "1/", "/": "71", "2": "Z", "Z": "2", "5": "S", "S": "5", "8": "B", "B": "8", "6": "G", "G": "60", "U": "V", "V": "U"}


def edit(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]


def repair_gstin(raw):
    s0 = re.sub(r"[^0-9A-Z/]", "", raw.upper().replace(" ", "")).replace("/", "7")
    variants = [s0] if len(s0) == 15 else ["".join(s0[i] for i in range(len(s0)) if i not in drop) for drop in itertools.combinations(range(len(s0)), len(s0) - 15)] if len(s0) > 15 else []
    for v in variants:
        fixed, _ = _repair15(v)
        if fixed:
            return fixed, s0
    return None, s0


def by_name(raw, legal_name):
    if not legal_name:
        return None, None
    cands = GST[GST.legal_name.apply(lambda n: sim(n, legal_name) > 0.9)]
    if not len(cands):
        return None, None
    s0 = re.sub(r"[^0-9A-Z]", "", raw.upper())
    best = min(cands.index, key=lambda g: edit(g, s0))
    return best, edit(best, s0)


def _repair15(s):
    if gstin_checksum_ok(s) and s in GST.index:
        return s, s
    slots = [[ch] + list(CONFUSE.get(ch, "")) for ch in s]
    best = None
    for k in (1, 2, 3):
        for pos in itertools.combinations(range(15), k):
            for subs in itertools.product(*[slots[i][1:] for i in pos]):
                cand = list(s)
                for i, ch in zip(pos, subs):
                    cand[i] = ch
                cand = "".join(cand)
                if gstin_checksum_ok(cand) and cand in GST.index:
                    return cand, s
        if best:
            break
    return None, s


def load(path):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(int)
    pink = (a[..., 0] - a[..., 1] > 25) & (a[..., 0] - a[..., 2] > 15)
    g = np.asarray(ImageOps.grayscale(img)).astype(int)
    g[pink] = 255
    return img, Image.fromarray(np.where(g < 150, 0, 255).astype(np.uint8))


def blur_score(img):
    g = np.asarray(ImageOps.grayscale(img)).astype(float)
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def deskew(bw):
    best = (0, -1)
    for ang in np.arange(-12, 12.5, 1.0):
        rot = bw.rotate(ang, expand=True, fillcolor=255)
        prof = (np.asarray(rot) < 128).sum(axis=1)
        score = float(np.var(prof))
        if score > best[1]:
            best = (ang, score)
    return bw.rotate(best[0], expand=True, fillcolor=255), best[0]


def ocr(bw):
    big = bw.resize((bw.width * 2, bw.height * 2), Image.LANCZOS)
    d = pytesseract.image_to_data(big, config="--psm 4", output_type=pytesseract.Output.DICT)
    conf = [int(c) for c, w in zip(d["conf"], d["text"]) if w.strip() and int(c) >= 0]
    return pytesseract.image_to_string(big, config="--psm 4"), (float(np.mean(conf)) if conf else 0.0)


def field(text, label, nxt=None):
    m = re.search(label + r"\s*[:.]?\s*(.+)", text, re.I)
    return m.group(1).strip() if m else None


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).replace(" llp", "").replace(" pvt ltd", "").strip()


def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio() if a and b else 0.0


def name_match(a, b):
    wa, wb = norm(a).split(), norm(b).split()
    if not wa or len(wa) != len(wb):
        return sim(a, b) > 0.95
    return all(x == y or (len(x) > 3 and SequenceMatcher(None, x, y).ratio() >= 0.8) for x, y in zip(wa, wb))


def read_gstin_line(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    pink = (a[..., 0] - a[..., 1] > 25) & (a[..., 0] - a[..., 2] > 15)
    g = np.asarray(ImageOps.grayscale(img)).astype(int)
    g[pink] = 255
    reads = []
    for thr, scale, mf in [(140, 3, 3), (170, 3, 0), (120, 4, 0), (200, 2, 0), (150, 5, 3)]:
        crop = Image.fromarray(np.where(g < thr, 0, 255).astype(np.uint8)).crop((505, 240, 1200, 292))
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        if mf:
            crop = crop.filter(ImageFilter.MinFilter(mf))
        for psm in (7, 8):
            t = pytesseract.image_to_string(crop, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ").strip()
            if t:
                reads.append(t)
    for t in reads:
        if repair_gstin(t)[0]:
            return t
    return min(reads, key=lambda t: abs(len(t) - 15)) if reads else ""


def unexplained_diffs(ocr, gstin):
    best = None
    s0 = re.sub(r"[^0-9A-Z]", "", ocr.upper())
    cands = [s0] if len(s0) == 15 else ["".join(s0[i] for i in range(len(s0)) if i not in d) for d in itertools.combinations(range(len(s0)), len(s0) - 15)] if len(s0) > 15 else []
    for c in cands:
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(c, gstin)) if a != b and b not in CONFUSE.get(a, "")]
        if best is None or len(diffs) < len(best):
            best = diffs
    return best


applicants = sorted({p.name[:3] for p in docs.glob("K*.png")})
report = []
for k in applicants:
    rec = {"applicant": k, "documents": {}, "checks": []}
    texts = {}
    for kind in ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]:
        p = docs / f"{k}_{kind}.png"
        if not p.exists():
            rec["documents"][kind] = {"present": False}
            continue
        img, bw = load(p)
        bs = blur_score(img)
        skew = 0.0
        if img.size != (1240, 1754) and kind != "signatory_id":
            bw, skew = deskew(bw)
        txt, conf = ocr(bw)
        texts[kind] = txt
        rec["documents"][kind] = {"present": True, "size": list(img.size), "blur_score": round(bs, 1), "skew_corrected_deg": float(skew), "ocr_conf": round(conf, 1)}
        if kind == "gst_certificate":
            line = read_gstin_line(img) if img.size == (1240, 1754) else (field(txt, r"GSTIN") or "")
            rec["documents"][kind]["gstin_ocr"] = line
    g_txt, u_txt, s_txt, a_txt = (texts.get(x, "") for x in ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"])
    ex = {}
    gd = rec["documents"].get("gst_certificate", {})
    if gd.get("present"):
        gst_fixed, gst_seen = repair_gstin(gd.get("gstin_ocr", ""))
        if not gst_fixed:
            m = re.search(r"GSTIN\s+([0-9A-Z/ ,]{12,20})", g_txt)
            if m:
                gst_fixed, _ = repair_gstin(m.group(1))
        ex["gstin_method"] = "OCR + checksum repair" if gst_fixed else None
        ex["gst_legal_name"] = field(g_txt, r"Legal [Nn]ame")
        if not gst_fixed:
            gst_fixed, dist = by_name(gst_seen, ex["gst_legal_name"])
            if gst_fixed:
                ex["gstin_method"] = f"registry match on legal name, closest GSTIN to OCR text (edit distance {dist})"
                ex["gstin_unexplained"] = unexplained_diffs(gst_seen, gst_fixed)
        ex["gstin_read_as"] = gst_seen
        ex["gstin"] = gst_fixed
        ex["gst_trade_name"] = field(g_txt, r"Trade \S+")
        ex["gst_constitution"] = field(g_txt, r"[CcK“]?onstitution")
    if rec["documents"].get("udyam_certificate", {}).get("present"):
        m = re.search(r"[UL][DO]YAM\s*-\s*([A-Z]{2})\s*-\s*[0O@]{1,2}\s*-\s*(\d{7})", u_txt)
        ex["udyam_number"] = f"UDYAM-{m.group(1)}-00-{m.group(2)}" if m else None
        ex["udyam_name"] = field(u_txt, r"Enterprise name")
        ex["udyam_city"] = field(u_txt, r"\nCity")
        ex["udyam_state"] = field(u_txt, r"\nState")
        ex["udyam_activity"] = field(u_txt, r"Major activity")
    if rec["documents"].get("signatory_id", {}).get("present"):
        lines = [l.strip() for l in s_txt.splitlines() if l.strip()]
        def after(lbl):
            for i, l in enumerate(lines):
                if l.lower().startswith(lbl):
                    return lines[i + 1] if i + 1 < len(lines) else None
        ex["sig_name"], ex["sig_role"], ex["sig_business"], ex["sig_id"], ex["sig_valid_till"] = after("name"), after("designation"), after("for business"), after("id no"), after("valid till")
    if rec["documents"].get("address_proof", {}).get("present"):
        ex["bill_name"] = field(a_txt, r"Billed to")
        m = re.search(r"Bill date\s+(\d{4}-\d{2}-\d{2})", a_txt)
        ex["bill_date"] = m.group(1) if m else None
        m = re.search(r"Supply \S+\s+(.+?)\n\s*\n?(.+?)\n", a_txt, re.S)
        ex["bill_address"] = (m.group(1) + m.group(2)).replace("\n", " ").strip() if m else None
    rec["extracted"] = ex

    def add(check, ok, detail, severity):
        rec["checks"].append({"check": check, "result": "pass" if ok else "FAIL", "detail": detail, "severity": None if ok else severity})

    for kind in ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]:
        d = rec["documents"][kind]
        if not d["present"]:
            add(f"{kind} present", False, "document not uploaded", "missing_document")
        else:
            if d["blur_score"] < 50:
                add(f"{kind} readable", False, f"image too blurry (sharpness {d['blur_score']}, OCR confidence {d['ocr_conf']}%)", "unreadable")
            if abs(d["skew_corrected_deg"]) > 0:
                add(f"{kind} alignment", True, f"scan tilted; auto-straightened by {d['skew_corrected_deg']:+.0f} degrees", None)
    reg = None
    if gd.get("present") and rec["documents"]["gst_certificate"]["blur_score"] >= 50:
        if not ex.get("gstin"):
            add("GSTIN format and checksum", False, f"could not read a valid GSTIN (OCR saw '{ex.get('gstin_read_as')}')", "needs_review")
        else:
            corrected = ex["gstin"] != ex.get("gstin_read_as")
            needs_confirm = "legal name" in (ex.get("gstin_method") or "")
            unexplained = ex.get("gstin_unexplained")
            if needs_confirm and (unexplained is None or len(unexplained) > 0):
                ocr_cs = gstin_checksum_ok(re.sub(r"[^0-9A-Z]", "", ex["gstin_read_as"])[-15:])
                add("GSTIN on certificate matches registry", False, f"certificate GSTIN reads '{ex['gstin_read_as']}', which fails the checksum and differs from the registry GSTIN for this business ({ex['gstin']}) at characters that are not OCR look-alikes {[(i + 1, a, b) for i, a, b in (unexplained or [])]}", "mismatch")
                needs_confirm = True
            add("GSTIN read from certificate", not needs_confirm, f"{ex['gstin']}" + (f" (OCR read '{ex['gstin_read_as']}'; resolved by {ex['gstin_method']})" if corrected else " (read cleanly)") + ("; ask the applicant to confirm the number" if needs_confirm else ""), "confirm")
            reg = GST.loc[ex["gstin"]]
            add("GSTIN found in registry", True, reg.legal_name, None)
            add("GSTIN status Active", reg.status == "Active", f"registry status: {reg.status}", "blocking")
            add("Legal name matches registry", name_match(ex.get("gst_legal_name"), reg.legal_name), f"certificate '{ex.get('gst_legal_name')}' vs registry '{reg.legal_name}'", "mismatch")
            add("Trade name matches registry", name_match(ex.get("gst_trade_name"), reg.trade_name), f"certificate '{ex.get('gst_trade_name')}' vs registry '{reg.trade_name}'", "mismatch")
            if "(Prop." in (ex.get("gst_legal_name") or ""):
                inner = re.search(r"\(Prop\.?\s*(.+?)\)", ex["gst_legal_name"])
                if inner:
                    add("Proprietor's business = trade name", name_match(inner.group(1), ex.get("gst_trade_name")),
                        f"legal name says '{inner.group(1)}', trade name says '{ex.get('gst_trade_name')}'", "mismatch")
            add("GSTIN state code matches registry state", STATE_CODES.get(ex["gstin"][:2]) == reg.state, f"code {ex['gstin'][:2]} = {STATE_CODES.get(ex['gstin'][:2])}, registry state {reg.state}", "mismatch")
    elif not gd.get("present"):
        pass
    else:
        best = GST[GST.legal_name.str.lower() == (ex.get("bill_name") or "").lower()]
        if len(best):
            reg = best.iloc[0]
            add("GSTIN status Active (looked up by name, certificate unreadable)", reg.status == "Active", f"registry status: {reg.status} for {best.index[0]}", "blocking")
    ud = rec["documents"]["udyam_certificate"]
    if ud["present"]:
        if not ex.get("udyam_number"):
            add("Udyam number present", False, "Udyam registration number field is blank on the certificate", "mismatch")
            hit = UDY[(UDY.enterprise_name.str.lower() == (ex.get("udyam_name") or "").lower()) & (UDY.city.str.lower() == (ex.get("udyam_city") or "").lower())]
            other = UDY[(UDY.enterprise_name.str.lower() == (ex.get("udyam_name") or "").lower()) & (UDY.city.str.lower() != (ex.get("udyam_city") or "").lower())]
            if len(hit):
                add("Udyam record found by name + city", True, f"registry has {hit.index[0]}; ask applicant to confirm", None)
            else:
                add("Udyam record found by name + city", False, f"no Udyam record for this name in {ex.get('udyam_city')}" + (f" (same name exists elsewhere: {', '.join(other.index + ' in ' + other.city)}, so a name-only lookup would pick the wrong business)" if len(other) else ""), "mismatch")
        elif ex["udyam_number"] not in UDY.index:
            add("Udyam number found in registry", False, f"{ex['udyam_number']} not in registry", "mismatch")
        else:
            u = UDY.loc[ex["udyam_number"]]
            add("Udyam number found in registry", True, ex["udyam_number"], None)
            add("Udyam name matches registry", sim(ex.get("udyam_name"), u.enterprise_name) > 0.85, f"certificate '{ex.get('udyam_name')}' vs registry '{u.enterprise_name}'", "mismatch")
            add("Udyam city/state match registry", norm(ex.get("udyam_city")) == norm(u.city) and norm(ex.get("udyam_state")) == norm(u.state), f"certificate {ex.get('udyam_city')}, {ex.get('udyam_state')} vs registry {u.city}, {u.state}", "mismatch")
            add("Udyam state code matches state", UDY_STATE.get(ex["udyam_number"][6:8]) == u.state, f"{ex['udyam_number'][6:8]} vs {u.state}", "mismatch")
            if reg is not None:
                add("Udyam name matches GST trade name", sim(u.enterprise_name, reg.trade_name) > 0.85, f"Udyam '{u.enterprise_name}' vs GST trade name '{reg.trade_name}'", "mismatch")
                add("Udyam state matches GST state", u.state == reg.state, f"Udyam {u.state} vs GST {reg.state}", "mismatch")
    if ex.get("bill_date"):
        age = (TODAY - date.fromisoformat(ex["bill_date"])).days
        add("Address proof no older than 90 days", 0 <= age <= 90, f"bill dated {ex['bill_date']}, {age} days before 2026-07-15", "stale")
    if ex.get("bill_name") and reg is not None:
        add("Bill name matches business", max(sim(ex["bill_name"], reg.trade_name), sim(ex["bill_name"], reg.legal_name)) > 0.85, f"bill '{ex['bill_name']}' vs GST '{reg.trade_name}'", "mismatch")
    if ex.get("bill_address") and reg is not None:
        city = reg.principal_place_of_business.split(",")[-2].strip() if "," in reg.principal_place_of_business else ""
        pin_bill = re.findall(r"\d{6}", ex["bill_address"].replace(" ", ""))
        pin_reg = re.findall(r"\d{6}", reg.principal_place_of_business)
        add("Bill address matches registered address", bool(pin_bill and pin_reg and pin_bill[-1] == pin_reg[-1]) and city.lower() in ex["bill_address"].lower(),
            f"bill '{ex['bill_address']}' vs registry '{reg.principal_place_of_business}'", "mismatch")
    if ex.get("sig_business") and reg is not None:
        add("Signatory ID is for this business", max(sim(ex["sig_business"], reg.trade_name), sim(ex["sig_business"], reg.legal_name)) > 0.85, f"ID says '{ex['sig_business']}'", "mismatch")
    if ex.get("sig_valid_till"):
        try:
            ok = date.fromisoformat(ex["sig_valid_till"]) >= TODAY
            add("Signatory ID not expired", ok, f"valid till {ex['sig_valid_till']}", "stale")
        except ValueError:
            add("Signatory ID not expired", False, f"could not read date '{ex['sig_valid_till']}'", "needs_review")
    if reg is not None and ex.get("sig_name"):
        if reg.constitution == "Proprietorship":
            owner = reg.legal_name.split("(")[0].strip()
            add("Signatory is the proprietor", sim(ex["sig_name"], owner) > 0.85, f"signatory '{ex['sig_name']}' ({ex.get('sig_role')}) vs proprietor '{owner}'", "mismatch")
        else:
            add("Signatory authority (company/LLP)", True, f"'{ex['sig_name']}' ({ex.get('sig_role')}); registry has no director list, so a board resolution / partner letter is needed to confirm authority", None)
    fails = [c for c in rec["checks"] if c["result"] == "FAIL"]
    sev = {c["severity"] for c in fails}
    rec["verdict"] = ("Blocked" if "blocking" in sev else "Re-upload needed" if sev & {"missing_document", "unreadable", "stale"} else
                      "Human review" if sev & {"mismatch", "needs_review"} else "Verified (confirm GSTIN)" if sev == {"confirm"} else "Verified")
    report.append(rec)

(outdir / "kyc_results.json").write_text(json.dumps(report, indent=1, default=str))
md = ["# KYC results: applicants K01-K12\n", "Generated by scripts/kyc_check.py from the 47 images in data/kyc_documents. 'Today' = 2026-07-15.\n",
      "| applicant | business (registry) | verdict | failed checks |", "|---|---|---|---|"]
for r in report:
    g = r["extracted"].get("gstin")
    nm = GST.loc[g].trade_name if g else (r["extracted"].get("bill_name") or "")
    fails = [f"{c['check']}: {c['detail']}" for c in r["checks"] if c["result"] == "FAIL"]
    md.append(f"| {r['applicant']} | {nm} | **{r['verdict']}** | {'<br>'.join(fails) if fails else 'none'} |")
md.append("\n## OCR quality per document\n")
md.append("| applicant | document | OCR confidence | sharpness | skew fixed | note |")
md.append("|---|---|---|---|---|---|")
for r in report:
    for kind, d in r["documents"].items():
        if d["present"]:
            note = []
            if kind == "gst_certificate":
                note.append(f"GSTIN OCR '{d.get('gstin_ocr', '')}' -> {r['extracted'].get('gstin')}")
            md.append(f"| {r['applicant']} | {kind} | {d['ocr_conf']}% | {d['blur_score']} | {d['skew_corrected_deg']:+.0f} deg | {'; '.join(note)} |")
        else:
            md.append(f"| {r['applicant']} | {kind} | - | - | - | MISSING |")
md.append("\n## Every check\n")
for r in report:
    md.append(f"### {r['applicant']}: {r['verdict']}\n")
    for c in r["checks"]:
        md.append(f"- [{c['result']}] {c['check']}: {c['detail']}")
    md.append("")
(outdir / "kyc_results.md").write_text("\n".join(md))
print("\n".join(md[:20]))
