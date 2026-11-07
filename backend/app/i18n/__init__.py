import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent
LANG_NAMES = {"hi": "Hindi", "en": "English", "mr": "Marathi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "gu": "Gujarati"}
SCRIPTS = {"hi": (0x0900, 0x097F), "mr": (0x0900, 0x097F), "bn": (0x0980, 0x09FF), "gu": (0x0A80, 0x0AFF), "ta": (0x0B80, 0x0BFF),
           "te": (0x0C00, 0x0C7F), "kn": (0x0C80, 0x0CFF)}
DIGITS = {0x0966: "hi", 0x09E6: "bn", 0x0AE6: "gu", 0x0BE6: "ta", 0x0C66: "te", 0x0CE6: "kn"}


@lru_cache(maxsize=1)
def bundle() -> dict:
    out = {}
    for f in sorted(DIR.glob("advisor_*.json")):
        out.update(json.loads(f.read_text(encoding="utf-8")))
    return out


def langs() -> list[str]:
    return list(bundle())


def text(lang: str, key: str, **kw):
    b = bundle()
    node = b.get(lang, b["en"])
    for part in key.split("."):
        node = node[part]
    if isinstance(node, str) and kw:
        return node.format(**kw)
    return node


def ascii_digits(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        for zero in DIGITS:
            if zero <= o <= zero + 9:
                ch = str(o - zero)
                break
        out.append(ch)
    return "".join(out)


def script_ratio(s: str, lang: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    if lang == "en":
        return sum(c.isascii() for c in letters) / len(letters)
    lo, hi = SCRIPTS[lang]
    return sum(lo <= ord(c) <= hi for c in letters) / len(letters)
