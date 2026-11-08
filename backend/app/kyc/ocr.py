"""OCR for the four KYC documents (ported from scripts/kyc_check.py, Phase 1 [K]).

Pipeline per image: remove the pink "SYNTHETIC SPECIMEN" watermark by colour, threshold, straighten a tilted scan,
measure sharpness, run Tesseract, then pull out the fields for that document type. The GSTIN line gets extra passes
because its monospace font and the watermark make it the hardest field to read.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import pytesseract
from PIL import Image, ImageFilter, ImageOps

from app.config import get_settings

BLUR_THRESHOLD = 50.0
DOC_TYPES = ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof")


@dataclass
class OcrResult:
    doc_type: str
    text: str
    confidence: float
    sharpness: float
    skew_deg: float
    readable: bool
    fields: dict = field(default_factory=dict)
    gstin_raw: str | None = None


def _rgb(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def _clean(img: Image.Image, threshold: int = 150) -> Image.Image:
    a = np.asarray(img).astype(np.int16)  # int16 is enough for these differences and uses 1/4 of int64's memory
    pink = (a[..., 0] - a[..., 1] > 25) & (a[..., 0] - a[..., 2] > 15)
    del a
    g = np.asarray(ImageOps.grayscale(img)).astype(np.int16)
    g[pink] = 255
    return Image.fromarray(np.where(g < threshold, 0, 255).astype(np.uint8))


def sharpness(img: Image.Image) -> float:
    g = np.asarray(ImageOps.grayscale(img)).astype(float)
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def _skew(bw: Image.Image) -> float:
    small = bw.copy()
    small.thumbnail((700, 700))

    def score(angle: float) -> float:
        rot = small.rotate(angle, expand=True, fillcolor=255)
        return float(np.var((np.asarray(rot) < 128).sum(axis=1)))

    coarse = max(np.arange(-12, 12.5, 2.0), key=score)
    return float(max(np.arange(coarse - 1.5, coarse + 1.6, 0.5), key=score))


def _ocr(bw: Image.Image) -> tuple[str, float]:
    big = bw.resize((bw.width * 2, bw.height * 2), Image.LANCZOS) if bw.width < 1600 else bw
    d = pytesseract.image_to_data(big, config="--psm 4", output_type=pytesseract.Output.DICT)
    conf = [int(c) for c, w in zip(d["conf"], d["text"]) if w.strip() and int(c) >= 0]
    return pytesseract.image_to_string(big, config="--psm 4"), (float(np.mean(conf)) if conf else 0.0)


def _gstin_line(img: Image.Image, angle: float) -> str | None:
    """Find the word 'GSTIN' on the page and re-read the text to its right with several clean-ups."""
    base = img.rotate(angle, expand=True, fillcolor=(255, 255, 255)) if abs(angle) > 0.4 else img
    bw = _clean(base)
    d = pytesseract.image_to_data(bw, config="--psm 4", output_type=pytesseract.Output.DICT)
    box = None
    for i, w in enumerate(d["text"]):
        if re.sub(r"[^A-Z]", "", w.upper()) in ("GSTIN", "GSTN", "GSTIN:"):
            box = (d["left"][i], d["top"][i], d["width"][i], d["height"][i])
            break
    if not box:
        return None
    x, y, w, h = box
    # work on the strip to the right of "GSTIN" only, not the whole page (same pixels, far less memory)
    left, top, right, bottom = x + int(w * 1.6), max(0, y - h // 2), min(base.width, x + w * 9), y + h + h // 2
    strip = base.crop((left, top, right, bottom))
    g = np.asarray(ImageOps.grayscale(strip)).astype(np.int16)
    a = np.asarray(strip).astype(np.int16)
    g[(a[..., 0] - a[..., 1] > 25) & (a[..., 0] - a[..., 2] > 15)] = 255
    del a
    reads = []
    for thr, scale, mf in [(140, 3, 3), (170, 3, 0), (120, 4, 0), (200, 2, 0), (150, 5, 3)]:
        crop = Image.fromarray(np.where(g < thr, 0, 255).astype(np.uint8))
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        if mf:
            crop = crop.filter(ImageFilter.MinFilter(mf))
        for psm in (7, 8):
            t = pytesseract.image_to_string(crop, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ").strip()
            if t:
                reads.append(t)
    return "|".join(reads) if reads else None


def _field(text: str, label: str) -> str | None:
    m = re.search(label + r"\s*[:.]?\s*(.+)", text, re.I)
    return m.group(1).strip() if m else None


def _after(lines: list[str], label: str) -> str | None:
    for i, line in enumerate(lines):
        if line.lower().startswith(label):
            rest = line[len(label):].strip(" :")
            if rest:
                return rest
            return lines[i + 1] if i + 1 < len(lines) else None
    return None


def extract(doc_type: str, text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if doc_type == "gst_certificate":
        m = re.search(r"GSTIN\s+([0-9A-Z/ ,]{12,22})", text)
        return {"gstin_text": m.group(1).strip() if m else None, "legal_name": _field(text, r"Legal [Nn]ame"),
                "trade_name": _field(text, r"Trade \S+"), "constitution": _field(text, r"[CcK“]?onstitution"),
                "address": _field(text, r"(?:Principal )?[Pp]lace of [Bb]usiness|Address")}
    if doc_type == "udyam_certificate":
        m = re.search(r"[UL][DO]YAM\s*-\s*([A-Z]{2})\s*-\s*[0O@]{1,2}\s*-\s*(\d{7})", text)
        return {"udyam_number": f"UDYAM-{m.group(1)}-00-{m.group(2)}" if m else None, "enterprise_name": _field(text, r"Enterprise name"),
                "city": _field(text, r"\nCity") or _field(text, r"^City"), "state": _field(text, r"\nState") or _field(text, r"^State"),
                "major_activity": _field(text, r"Major activity")}
    if doc_type == "signatory_id":
        return {"name": _after(lines, "name"), "designation": _after(lines, "designation"), "business": _after(lines, "for business"),
                "id_number": _after(lines, "id no"), "valid_till": _after(lines, "valid till")}
    if doc_type == "address_proof":
        m = re.search(r"Bill date\s+(\d{4}-\d{2}-\d{2})", text)
        addr = re.search(r"Supply \S+\s+(.+?)\n\s*\n?(.+?)\n", text, re.S)
        return {"billed_to": _field(text, r"Billed to"), "bill_date": m.group(1) if m else None,
                "address": (addr.group(1) + " " + addr.group(2)).replace("\n", " ").strip() if addr else None}
    raise ValueError(doc_type)


CACHE_PATH = Path(__file__).with_name("ocr_cache.json")


def cache_key(doc_type: str, data: bytes) -> str:
    return f"{hashlib.sha256(data).hexdigest()}:{doc_type}"


@lru_cache(maxsize=1)
def _cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError):
        return {}


def run(doc_type: str, data: bytes) -> OcrResult:
    """OCR one document. The case pack's sample images (byte-identical files only) reuse a result precomputed by
    scripts/build_ocr_cache.py with this same function, which keeps a small free-tier server from running Tesseract
    for the demo documents. Any other file, such as a phone photo, is read live."""
    if get_settings().ocr_cache:
        hit = _cache().get(cache_key(doc_type, data))
        if hit:
            return OcrResult(**hit)
    return run_live(doc_type, data)


def run_live(doc_type: str, data: bytes) -> OcrResult:
    if get_settings().ocr_engine != "tesseract":
        raise RuntimeError("Only the tesseract OCR engine is configured")
    img = _rgb(data)
    sharp = sharpness(img)
    bw = _clean(img)
    angle = _skew(bw) if doc_type != "signatory_id" else 0.0
    if abs(angle) > 0.4:
        bw = bw.rotate(angle, expand=True, fillcolor=255)
    text, conf = _ocr(bw)
    readable = sharp >= BLUR_THRESHOLD and conf >= 55
    fields = extract(doc_type, text) if readable else {}
    gline = _gstin_line(img, angle) if doc_type == "gst_certificate" and readable else None
    return OcrResult(doc_type, text, round(conf, 1), round(sharp, 1), round(angle, 1), readable, fields, gline)
