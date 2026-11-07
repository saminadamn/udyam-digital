import re

GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
UDYAM_RE = re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return "••••••" + digits[-4:]


def mask_gstin(g: str | None) -> str | None:
    return None if not g else f"{g[:2]}{'•' * 9}{g[-3:]}"


def mask_udyam(u: str | None) -> str | None:
    return None if not u else f"{u[:12]}•••{u[-4:]}"


def scrub(text: str) -> str:
    text = GSTIN_RE.sub(lambda m: mask_gstin(m.group()), text)
    text = UDYAM_RE.sub(lambda m: mask_udyam(m.group()), text)
    text = PAN_RE.sub(lambda m: m.group()[:2] + "•••••" + m.group()[-3:], text)
    return PHONE_RE.sub(lambda m: mask_phone(m.group()), text)
