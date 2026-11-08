"""The precomputed OCR cache for the case pack's sample KYC images (scripts/build_ocr_cache.py)."""
from pathlib import Path

import pytest

from app.config import get_settings
from app.kyc import ocr

DOCS = Path(__file__).resolve().parents[2] / "data" / "kyc_documents"
SAMPLES = [(f, f.stem.split("_", 1)[1]) for f in sorted(DOCS.glob("K*_*.png")) if f.stem.split("_", 1)[1] in ocr.DOC_TYPES]


@pytest.fixture
def cache_on(monkeypatch):
    monkeypatch.setenv("OCR_CACHE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_every_sample_image_has_a_cached_result():
    keys = ocr._cache()
    assert len(SAMPLES) == 47
    missing = [f.name for f, t in SAMPLES if ocr.cache_key(t, f.read_bytes()) not in keys]
    assert not missing, f"rebuild with scripts/build_ocr_cache.py: {missing}"


def test_sample_file_uses_the_cache_without_tesseract(cache_on, monkeypatch):
    monkeypatch.setattr(ocr, "run_live", lambda *a: pytest.fail("Tesseract ran for a cached sample"))
    f = DOCS / "K02_gst_certificate.png"
    res = ocr.run("gst_certificate", f.read_bytes())
    assert res.readable and res.fields.get("gstin_text") and res.gstin_raw and res.doc_type == "gst_certificate"


def test_other_files_and_wrong_doc_type_run_live_ocr(cache_on, monkeypatch):
    calls = []
    monkeypatch.setattr(ocr, "run_live", lambda t, d: calls.append(t) or ocr.OcrResult(t, "", 0.0, 0.0, 0.0, False))
    data = (DOCS / "K02_gst_certificate.png").read_bytes()
    ocr.run("gst_certificate", data + b"\0")  # any change to the bytes: not a sample file
    ocr.run("address_proof", data)  # right file, wrong document type
    assert calls == ["gst_certificate", "address_proof"]


def test_cache_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("OCR_CACHE", "false")
    get_settings.cache_clear()
    calls = []
    monkeypatch.setattr(ocr, "run_live", lambda t, d: calls.append(t) or ocr.OcrResult(t, "", 0.0, 0.0, 0.0, False))
    ocr.run("gst_certificate", (DOCS / "K02_gst_certificate.png").read_bytes())
    get_settings.cache_clear()
    assert calls == ["gst_certificate"]
