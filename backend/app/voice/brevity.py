"""Short, plain replies for the ear (build Phase 5: "responses stay short and simple when spoken").

The screen keeps the full text; text-to-speech reads this version: at most two sentences and about 180 characters, never dropping
the question the owner has to answer, with codes, links and masked numbers taken out."""
from __future__ import annotations

import re

SENT = re.compile(r"[^.!?।]+[.!?।]+|[^.!?।]+$")
QUESTION = ("?", "？")


def _clean(text: str) -> str:
    t = re.sub(r"https?://\S+", "", text)
    t = re.sub(r"\S*•+\S*", "", t)                      # masked GSTIN / phone
    t = re.sub(r"\b[A-Z]{2}-\d{4}-\d{4}\b", "", t)     # order display ids
    t = re.sub(r"\bP\d{2}\b", "", t)                   # product codes, in case any slipped through
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"[*_#`>\[\]]", "", t)
    t = re.sub(r"\bRs\.?\s?", "₹", t)
    return re.sub(r"\s+", " ", t).strip()


def _cut(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    head = s[:limit].rsplit(" ", 1)[0].rstrip(",;: ")
    return head + "…"


def spoken(text: str, max_chars: int = 180, max_sentences: int = 2) -> str:
    t = _clean(text or "")
    if not t:
        return ""
    sents = [s.strip() for s in SENT.findall(t) if s.strip()]
    if len(t) <= max_chars and len(sents) <= max_sentences:
        return t
    must = len(sents) - 1 if sents[-1].endswith(QUESTION) else 0
    keep = {must}
    budget = max_chars - len(sents[must])
    for i, s in enumerate(sents):
        if len(keep) >= max_sentences:
            break
        if i not in keep and len(s) + 1 <= budget:
            keep.add(i)
            budget -= len(s) + 1
    out = " ".join(sents[i] for i in sorted(keep))
    return _cut(out, max_chars)
