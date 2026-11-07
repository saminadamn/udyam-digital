"""Deterministic extraction of profile fields from what the owner typed or tapped."""
import re

from app.i18n import ascii_digits, bundle, text

FIELDS = ["type", "team", "city", "gst", "internet", "needs"]
TYPE_VALUES = ["micro", "prof", "multi", "mfg"]
SEGMENT_NAME = {"micro": "Micro retail & services", "prof": "Professional offices", "multi": "Small multi-site businesses", "mfg": "Small manufacturers"}
TEAM_CHIPS = [(3, 1), (12, 1), (30, 1), (75, 1)]
TEAM_CHAIN_CHIPS = [(15, 3), (40, 5), (75, 8)]
INTERNET_VALUES = ["Mobile hotspot", "Home broadband", "Business broadband", "Leased line", "None"]
NEED_CODES = ["pos", "whatsapp", "cctv", "email", "wifi", "backup", "website", "calls", "tollfree", "security"]
EN_NEED_WORDS = {"pos": ["upi", "billing", "pos", "payment", "card"], "whatsapp": ["whatsapp"], "cctv": ["cctv", "camera"],
                 "email": ["email", "e-mail", "mail"], "wifi": ["wifi", "wi-fi"], "backup": ["backup", "back up"], "website": ["website", "site"],
                 "calls": ["phone line", "ivr", "telephony", "landline"], "tollfree": ["toll", "1800"], "security": ["virus", "antivirus", "security"],
                 "sms": ["sms"], "fleet": ["vehicle", "fleet", "gps"], "machines": ["machine", "sensor"], "failover": ["failover", "backup internet"],
                 "sdwan": ["sd-wan", "sdwan"], "firewall": ["firewall"], "static_ip": ["static ip"]}
INTERNET_WORDS = {"Mobile hotspot": ["hotspot", "mobile data", "phone"], "Home broadband": ["home"], "Business broadband": ["business broadband", "fibre", "fiber", "broadband"],
                  "Leased line": ["leased", "ill"], "None": ["nothing", "none", "no internet"]}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", ascii_digits(s or "")).strip().lower()


def chip_index(content: str, labels: list[str]) -> int | None:
    c = _norm(content)
    for i, label in enumerate(labels):
        if c == _norm(label):
            return i
    return None


def any_kw(content: str, words: list[str]) -> bool:
    c = f" {_norm(content)} "
    return any(w.lower() in c for w in words)


def all_lang_kw(key: str) -> list[str]:
    out = []
    for lang in bundle().values():
        out += lang["keywords"].get(key, [])
    return out


def wants_human(content: str) -> bool:
    return any_kw(content, all_lang_kw("human"))


def parse_type(content: str, lang: str):
    i = chip_index(content, text(lang, "chips_type"))
    if i is not None:
        return TYPE_VALUES[i]
    for key in ("multi", "mfg", "prof", "micro"):
        if any_kw(content, all_lang_kw(key)):
            return key
    return None


NUMBER_WORDS = {w: i + 1 for i, w in enumerate(
    "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
NUMBER_WORDS |= {w: i + 1 for i, w in enumerate("एक दो तीन चार पांच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस".split())}
NUMBER_WORDS |= {"पाँच": 5, "छः": 6, "छे": 6, "alone": 1, "only me": 1, "just me": 1, "अकेला": 1, "अकेले": 1}


def _words_to_digits(content: str) -> str:
    """Voice transcripts often spell small numbers out ("three people", "तीन लोग"); turn them into digits first."""
    out = content
    for w, n in sorted(NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(rf"(?<![\w\u0900-\u097F]){re.escape(w)}(?![\w\u0900-\u097F])", str(n), out, flags=re.IGNORECASE)
    return out


def _numbers(content: str) -> list[tuple[int, int, int]]:
    c = ascii_digits(_words_to_digits(content))
    return [(int(m.group()), m.start(), m.end()) for m in re.finditer(r"\d{1,4}", c)]


def parse_team(content: str, lang: str, seg: str | None):
    chips = text(lang, "chips_team_chain") if seg == "multi" else text(lang, "chips_team")
    i = chip_index(content, chips)
    if i is not None:
        return (TEAM_CHAIN_CHIPS if seg == "multi" else TEAM_CHIPS)[i]
    nums = _numbers(content)
    if not nums:
        return None
    c = ascii_digits(_words_to_digits(content)).lower()
    site_words = all_lang_kw("sites")
    people_words = all_lang_kw("people")
    employees = sites = None
    for n, s, e in nums:
        window = c[e:e + 14] + " " + c[max(0, s - 14):s]
        after = c[e:e + 14]
        if any(w.lower() in after for w in site_words) or (sites is None and employees is not None and not any(w.lower() in after for w in people_words)):
            sites = sites or n
        elif any(w.lower() in window for w in people_words) or employees is None:
            employees = employees or n
    employees = employees or (nums[0][0] if nums else None)
    if not employees or employees < 1:
        return None
    sites = sites or (2 if seg == "multi" else 1)
    return (min(employees, 5000), max(1, min(sites, 500)))


def parse_city(content: str, lang: str, cities: dict[str, dict]):
    i = chip_index(content, text(lang, "chips_city_other"))
    if i is not None:
        return {"city": None, "city_tier": 1 if i == 0 else 2, "state": None, "assumed": False}
    c = _norm(content)
    for name, info in cities.items():
        if name.lower() in c:
            return {"city": name, "city_tier": info["tier"], "state": info["state"], "assumed": False}
    cleaned = content.strip().strip(".").title()
    if cleaned:
        return {"city": cleaned[:60], "city_tier": 2, "state": None, "assumed": True}
    return None


def parse_gst(content: str, lang: str):
    from app.kyc import gstin

    i = chip_index(content, text(lang, "chips_gst"))
    if i == 0:
        return {"answer": "no"}
    if i == 1:
        return {"answer": "later"}
    found = gstin.find_in_text(content)
    if found:
        return {"answer": "number", "gstin": found, "format_ok": gstin.format_ok(found), "checksum_ok": gstin.checksum_ok(found)}
    if any_kw(content, all_lang_kw("later")):
        return {"answer": "later"}
    if any_kw(content, all_lang_kw("no")):
        return {"answer": "no"}
    tokens = re.findall(r"[0-9A-Za-z]{10,}", content or "")
    if tokens:
        tok = max(tokens, key=len).upper()[:15]
        return {"answer": "number", "gstin": tok, "format_ok": False, "checksum_ok": False}
    return None


def parse_internet(content: str, lang: str):
    i = chip_index(content, text(lang, "chips_internet"))
    if i is not None:
        return INTERNET_VALUES[i]
    for value, words in INTERNET_WORDS.items():
        if any_kw(content, words):
            return value
    return "Unknown"


def parse_needs(content: str, lang: str) -> list[str]:
    labels = text(lang, "chips_needs")
    c = _norm(content)
    found = []
    for code, label in zip(NEED_CODES, labels):
        if _norm(label) in c:
            found.append(code)
    for code, words in EN_NEED_WORDS.items():
        if code not in found and any_kw(content, words):
            found.append(code)
    return found
