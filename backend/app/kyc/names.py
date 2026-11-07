"""Name matching for KYC (threshold documented in docs/KYC_CHECKS.md).

Two names match when, after lower-casing and dropping punctuation and the suffixes "LLP", "Pvt Ltd" and "Private Limited":
  - they have the same number of words, and every word pair is equal or (for words longer than 3 letters) at least 80% similar
    (difflib ratio), which tolerates one OCR slip per word ("Bental" ~ "Dental") but not a different word ("Shri" vs "Neelgiri"); or
  - the word counts differ and the whole strings are at least 95% similar.
"""
import re
from difflib import SequenceMatcher

WORD_THRESHOLD = 0.80
STRING_THRESHOLD = 0.95
_SUFFIX = re.compile(r"\b(private limited|pvt\.? ltd\.?|llp|limited)\b")


def norm(s: str | None) -> str:
    s = (s or "").lower()
    s = _SUFFIX.sub(" ", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio() if a and b else 0.0


def match(a: str | None, b: str | None) -> bool:
    wa, wb = norm(a).split(), norm(b).split()
    if not wa or not wb:
        return False
    if len(wa) == len(wb):
        return all(x == y or (len(x) > 3 and SequenceMatcher(None, x, y).ratio() >= WORD_THRESHOLD) for x, y in zip(wa, wb))
    return SequenceMatcher(None, " ".join(wa), " ".join(wb)).ratio() >= STRING_THRESHOLD


def proprietor_parts(legal_name: str | None) -> tuple[str | None, str | None]:
    """'Neha Banerjee (Prop. Neelgiri Physio Clinic)' -> ('Neha Banerjee', 'Neelgiri Physio Clinic')."""
    m = re.match(r"\s*(.+?)\s*\(\s*Prop\.?\s*(.+?)\s*\)\s*$", legal_name or "")
    return (m.group(1), m.group(2)) if m else (None, None)
