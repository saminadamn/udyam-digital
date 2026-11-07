"""Checks every LLM output before the owner sees it (DESIGN.md D1.4)."""
import re

from app.i18n import script_ratio

CODE_RE = re.compile(r"\bP\s?\d{2}\b", re.I)
AMOUNT_RE = re.compile(r"(?:Rs\.?|₹|INR)\s?([\d,]+)", re.I)


def problems(text: str, lang: str, allowed_names: set[str], all_names: set[str], allowed_amounts: set[int] | None = None,
             max_sentences: int | None = None) -> list[str]:
    out = []
    if not text or not text.strip():
        return ["empty"]
    if CODE_RE.search(text):
        out.append("product_code")
    low = text.lower()
    for name in all_names - allowed_names:
        if name.lower() in low:
            out.append(f"unlisted_product:{name}")
    if allowed_amounts is not None:
        for m in AMOUNT_RE.finditer(text):
            if int(m.group(1).replace(",", "")) not in allowed_amounts:
                out.append(f"amount:{m.group(1)}")
    if script_ratio(text, lang) < 0.5:
        out.append("wrong_language")
    if max_sentences:
        n = len([s for s in re.split(r"[.!?।]\s*", text.strip()) if s.strip()])
        if n > max_sentences:
            out.append("too_long")
    return out
