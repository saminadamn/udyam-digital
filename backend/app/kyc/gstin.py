import re

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
UDYAM_PATTERN = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")


def normalise(raw: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", raw or "").upper()


def format_ok(g: str) -> bool:
    return bool(GSTIN_PATTERN.match(g or ""))


def check_digit(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return CHARS[(36 - total % 36) % 36]


def checksum_ok(g: str) -> bool:
    """Official GSTIN check digit. Accepts 'X' as the 4th PAN character (dataset README)."""
    return format_ok(g) and check_digit(g[:14]) == g[14]


def find_in_text(text: str) -> str | None:
    """First GSTIN-shaped 15-character run in free text ("My GST is 27AB CDE..."), ignoring spaces and dashes inside it."""
    flat = re.sub(r"[\s\-./]", "", (text or "").upper())
    m = re.search(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]", flat)
    if m:
        return m.group()
    for tok in re.findall(r"[0-9A-Z]{15,}", re.sub(r"[\-./]", "", (text or "").upper())):
        m = re.search(r"\d{2}[A-Z0-9]{13}", tok)
        if m:
            return m.group()
    return None


def udyam_format_ok(num: str) -> bool:
    return bool(UDYAM_PATTERN.match(num or ""))


CONFUSE = {"6": "0G", "0": "OD6G", "O": "0D", "D": "0O", "1": "IL7", "I": "1LJ", "J": "I", "L": "1I", "7": "1", "2": "Z", "Z": "2",
           "5": "S", "S": "5", "8": "B", "B": "8", "G": "60", "U": "V", "V": "U", "3": "98", "9": "3"}


def _variants(raw: str) -> list[str]:
    import itertools

    s0 = re.sub(r"[^0-9A-Z/]", "", (raw or "").upper()).replace("/", "7")
    if len(s0) == 15:
        return [s0]
    if 15 < len(s0) <= 18:
        return ["".join(s0[i] for i in range(len(s0)) if i not in drop) for drop in itertools.combinations(range(len(s0)), len(s0) - 15)]
    return []


def repair(raw: str, exists) -> str | None:
    """Turn an OCR read into a real GSTIN: fix look-alike characters (0/O, 1/I, 5/S, ...) and keep a candidate only if it
    passes the checksum AND exists(candidate) is true (registry lookup). Up to 3 substitutions."""
    import itertools

    for s in _variants(raw):
        if checksum_ok(s) and exists(s):
            return s
        slots = [CONFUSE.get(ch, "") for ch in s]
        for k in (1, 2, 3):
            for pos in itertools.combinations([i for i in range(15) if slots[i]], k):
                for subs in itertools.product(*[slots[i] for i in pos]):
                    cand = list(s)
                    for i, ch in zip(pos, subs):
                        cand[i] = ch
                    cand = "".join(cand)
                    if checksum_ok(cand) and exists(cand):
                        return cand
    return None


def explained_by_ocr(raw: str, gstin: str) -> bool:
    """True if every difference between the OCR text and gstin is an OCR look-alike (so the certificate really shows gstin)."""
    for s in _variants(raw):
        if all(a == b or b in CONFUSE.get(a, "") for a, b in zip(s, gstin)):
            return True
    return False


STATE_CODES = {"01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
               "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "18": "Assam", "19": "West Bengal", "20": "Jharkhand",
               "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "27": "Maharashtra", "29": "Karnataka", "30": "Goa",
               "32": "Kerala", "33": "Tamil Nadu", "36": "Telangana", "37": "Andhra Pradesh"}
UDYAM_STATES = {"PB": "Punjab", "DL": "Delhi", "RJ": "Rajasthan", "UP": "Uttar Pradesh", "BR": "Bihar", "WB": "West Bengal", "MP": "Madhya Pradesh",
                "GJ": "Gujarat", "MH": "Maharashtra", "KA": "Karnataka", "KL": "Kerala", "TN": "Tamil Nadu", "TS": "Telangana", "AP": "Andhra Pradesh",
                "HR": "Haryana", "JH": "Jharkhand", "OD": "Odisha", "CG": "Chhattisgarh", "UK": "Uttarakhand", "GA": "Goa", "AS": "Assam"}
