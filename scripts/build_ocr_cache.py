"""Precompute OCR for the case pack's sample KYC images into backend/app/kyc/ocr_cache.json.

The server then skips Tesseract for these exact files (matched by SHA-256 + document type), which keeps OCR within a
512 MB free-tier instance during the demo. Any other upload still runs live OCR. Run it inside the backend image so the
results come from the same Linux Tesseract as the deployment:

    docker run --rm -v "$PWD/backend/app/kyc:/out" udyam-api-local python /srv/scripts/build_ocr_cache.py /out
    python scripts/build_ocr_cache.py            # or locally (Windows Tesseract gives the same verdicts)
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
for cand in (HERE.parent / "backend", Path("/srv/backend")):
    if (cand / "app").is_dir():
        sys.path.insert(0, str(cand))
        break
from app.kyc import ocr  # noqa: E402

DOCS = next(p for p in (HERE.parent / "data" / "kyc_documents", Path("/srv/data/kyc_documents")) if p.is_dir())
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(ocr.CACHE_PATH).parent

results = {}
for f in sorted(DOCS.glob("K*_*.png")):
    doc_type = f.stem.split("_", 1)[1]
    if doc_type not in ocr.DOC_TYPES:
        continue
    data = f.read_bytes()
    res = ocr.run_live(doc_type, data)
    results[ocr.cache_key(doc_type, data)] = asdict(res)
    print(f"{f.name}: readable={res.readable} conf={res.confidence}", flush=True)

(OUT / "ocr_cache.json").write_text(json.dumps({"note": "Precomputed by scripts/build_ocr_cache.py for the case-pack sample images only.",
                                                 "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(results)} entries -> {OUT / 'ocr_cache.json'}")
