"""Deterministic eligibility rules. No I/O, no LLM: the catalogue is passed in.

The rules come from product_catalogue.csv:
  CITY_TIER        product sold only in available_city_tiers
  MIN_EMPLOYEES    business must have at least min_employees
  MIN_SITES        business must have at least min_sites
  GSTIN_REQUIRED   requires_gstin = Y needs a GSTIN that is valid AND Active in the registry
  DEPENDENCY       requires_one_of needs at least one of those products in the same bundle
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

BUNDLES_PATH = Path(__file__).with_name("bundles.json")
SEGMENT_KEY = {"Micro retail & services": "micro", "Professional offices": "prof", "Small multi-site businesses": "multi", "Small manufacturers": "mfg"}
CONNECTIVITY_PREFERENCE = {
    "micro": ["P01", "P04", "P02"],
    "prof": ["P02", "P01", "P04", "P03"],
    "multi": ["P01", "P02", "P04"],
    "mfg": ["P05", "P03", "P02", "P01", "P04"],
}
BASE_LINKS = {"P01", "P02", "P03", "P04", "P05", "P06"}
NEED_PRODUCTS = {
    "pos": ["P19"], "upi": ["P19"], "whatsapp": ["P15"], "cctv": ["P23"], "email": ["P16"], "wifi": ["P22"], "backup": ["P17"],
    "website": ["P18"], "calls": ["P12"], "tollfree": ["P13"], "sms": ["P14"], "security": ["P20"], "failover": ["P09"],
    "static_ip": ["P11"], "fleet": ["P25"], "machines": ["P24"], "sdwan": ["P10"], "firewall": ["P21"], "mobile": ["P07"],
}


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    unit: str
    price_min_inr: int
    price_max_inr: int
    setup_fee_inr: int
    min_contract_months: int
    city_tiers: tuple[int, ...]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]
    install_days: int
    quantity_basis: str = "fixed"


@dataclass
class Profile:
    segment: str
    city_tier: int
    employees: int
    sites: int
    gst_status: str = "None"
    gstin_valid: bool = False
    needs: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return SEGMENT_KEY[self.segment]

    @property
    def gst_ok(self) -> bool:
        return self.gstin_valid and self.gst_status == "Active"


@dataclass(frozen=True)
class Violation:
    product_id: str
    rule: str
    message: str
    params: dict = field(default_factory=dict, hash=False, compare=False)

    def as_dict(self) -> dict:
        return asdict(self)


Catalogue = dict[str, Product]
Items = list[tuple[str, int]]


def product_rules(profile: Profile, p: Product) -> list[Violation]:
    out = []
    if profile.city_tier not in p.city_tiers:
        out.append(Violation(p.product_id, "CITY_TIER", f"{p.name} is not sold in tier {profile.city_tier} cities",
                             {"city_tier": profile.city_tier, "allowed": list(p.city_tiers)}))
    if profile.employees < p.min_employees:
        out.append(Violation(p.product_id, "MIN_EMPLOYEES", f"{p.name} needs at least {p.min_employees} employees",
                             {"min": p.min_employees, "have": profile.employees}))
    if profile.sites < p.min_sites:
        out.append(Violation(p.product_id, "MIN_SITES", f"{p.name} needs at least {p.min_sites} sites", {"min": p.min_sites, "have": profile.sites}))
    if p.requires_gstin and not profile.gst_ok:
        why = "no GSTIN" if not profile.gstin_valid and profile.gst_status in ("None", "", None) else (
            "GSTIN not verified" if not profile.gstin_valid else f"GSTIN is {profile.gst_status}")
        out.append(Violation(p.product_id, "GSTIN_REQUIRED", f"{p.name} needs an active, verified GSTIN ({why})",
                             {"gst_status": profile.gst_status, "gstin_valid": profile.gstin_valid}))
    return out


def eligible_products(profile: Profile, catalogue: Catalogue) -> dict:
    """Which products this business may buy on its own merits.

    Dependencies (requires_one_of) are bundle-level, so eligible products that need a base
    product are returned with the list of acceptable bases that are themselves eligible.
    """
    eligible, ineligible = {}, {}
    for pid, p in catalogue.items():
        v = product_rules(profile, p)
        if v:
            ineligible[pid] = v
    for pid, p in catalogue.items():
        if pid in ineligible:
            continue
        bases = [b for b in p.requires_one_of if b in catalogue and b not in ineligible]
        if p.requires_one_of and not bases:
            ineligible[pid] = [Violation(pid, "DEPENDENCY", f"{p.name} needs one of {', '.join(p.requires_one_of)}, none of which this business can buy",
                                         {"requires_one_of": list(p.requires_one_of)})]
        else:
            eligible[pid] = {"requires_one_of": bases}
    return {"eligible": eligible, "ineligible": ineligible}


def validate_bundle(profile: Profile, items: Items, catalogue: Catalogue) -> list[Violation]:
    out: list[Violation] = []
    seen = set()
    ids = {pid for pid, _ in items}
    for pid, qty in items:
        if pid in seen:
            out.append(Violation(pid, "DUPLICATE", f"{pid} appears more than once"))
            continue
        seen.add(pid)
        p = catalogue.get(pid)
        if p is None:
            out.append(Violation(pid, "UNKNOWN_PRODUCT", f"{pid} is not in the catalogue"))
            continue
        if not isinstance(qty, int) or qty < 1:
            out.append(Violation(pid, "BAD_QUANTITY", f"{p.name} quantity must be at least 1", {"qty": qty}))
        out.extend(product_rules(profile, p))
        if p.requires_one_of and not (set(p.requires_one_of) & ids):
            names = [catalogue[b].name for b in p.requires_one_of if b in catalogue]
            out.append(Violation(pid, "DEPENDENCY", f"{p.name} needs one of: {', '.join(names)}", {"requires_one_of": list(p.requires_one_of)}))
    return out


def _bundles() -> dict:
    return {b["key"]: b for b in json.loads(BUNDLES_PATH.read_text())["bundles"]}


def _qty(pid: str, q: int, profile: Profile, spec: dict, catalogue: Catalogue) -> int:
    if pid in spec.get("per_site", []):
        return profile.sites
    if pid in spec.get("per_user", []):
        return max(1, min(q, profile.employees))
    basis = catalogue[pid].quantity_basis
    if basis == "per_site":
        return profile.sites
    if basis == "per_user":
        return max(1, min(q, profile.employees))
    return q


def default_bundle(profile: Profile, catalogue: Catalogue) -> dict:
    spec = _bundles()[profile.key]
    core = [(pid, _qty(pid, q, profile, spec, catalogue)) for pid, q in spec["core"]]
    addons = [(pid, _qty(pid, q, profile, spec, catalogue)) for pid, q in spec["addons"] + spec.get("gstin_only_addons", [])]
    return {"key": profile.key, "name": spec["name"], "core": core, "addons": addons}


def _need_qty(pid: str, profile: Profile, catalogue: Catalogue) -> int:
    if pid == "P23":
        return 2 * profile.sites
    if pid == "P24":
        return max(1, min(10, profile.employees // 7))
    basis = catalogue[pid].quantity_basis
    if basis == "per_site":
        return profile.sites
    if basis == "per_user":
        return max(1, min(profile.employees, 25))
    return 1


def build_bundle(profile: Profile, catalogue: Catalogue, wanted: list[str] | None = None) -> dict:
    """Default bundle for the segment + products for the stated needs, filtered by the rules.

    Returns core/addons that pass validate_bundle, and `blocked` for anything asked for or
    suggested that this business cannot have, each with its violations.
    """
    elig = eligible_products(profile, catalogue)
    ok, bad = elig["eligible"], elig["ineligible"]
    base = default_bundle(profile, catalogue)
    blocked: dict[str, list[Violation]] = {}

    core = list(base["core"])
    if not any(pid in BASE_LINKS for pid, _ in core) or any(pid in BASE_LINKS and pid in bad for pid, _ in core):
        link = next((c for c in CONNECTIVITY_PREFERENCE[profile.key] if c in ok), None)
        core = [(pid, q) for pid, q in core if pid not in BASE_LINKS]
        if link:
            core.insert(0, (link, profile.sites if catalogue[link].quantity_basis == "per_site" else 1))

    wanted_ids: list[str] = []
    for need in (wanted or []) + profile.needs:
        for pid in NEED_PRODUCTS.get(need, [need] if need in catalogue else []):
            if pid not in wanted_ids:
                wanted_ids.append(pid)

    addons = [(pid, q) for pid, q in base["addons"]]
    have = {pid for pid, _ in core}
    for pid in wanted_ids:
        if pid in have:
            continue
        if pid in {a for a, _ in addons}:
            core.append(next((a, q) for a, q in addons if a == pid))
            addons = [(a, q) for a, q in addons if a != pid]
        else:
            core.append((pid, _need_qty(pid, profile, catalogue)))
        have.add(pid)

    def keep(group: Items) -> Items:
        kept = []
        for pid, q in group:
            if pid in bad:
                blocked.setdefault(pid, bad[pid])
            else:
                kept.append((pid, q))
        return kept

    core, addons = keep(core), keep(addons)
    for _ in range(3):
        ids = {pid for pid, _ in core}
        dropped = False
        for group_name in ("core", "addons"):
            group = core if group_name == "core" else addons
            pool = ids | ({pid for pid, _ in addons} if group_name == "addons" else set())
            for pid, q in list(group):
                req = catalogue[pid].requires_one_of
                if req and not (set(req) & (ids if group_name == "core" else pool)):
                    group.remove((pid, q))
                    blocked.setdefault(pid, [Violation(pid, "DEPENDENCY", f"{catalogue[pid].name} needs one of: " +
                                                       ", ".join(catalogue[b].name for b in req), {"requires_one_of": list(req)})])
                    dropped = True
        if not dropped:
            break

    core_ids = {p for p, _ in core}
    addons = [(p, q) for p, q in addons if p not in core_ids]
    wanted_blocked = {pid: v for pid, v in blocked.items() if pid in wanted_ids}
    return {
        "key": base["key"], "name": base["name"], "core": core, "addons": addons,
        "blocked": {pid: [x.as_dict() for x in v] for pid, v in blocked.items()},
        "wanted_blocked": sorted(wanted_blocked),
        "violations": [v.as_dict() for v in validate_bundle(profile, core, catalogue) + validate_bundle(profile, core + addons, catalogue)],
    }


MOBILE_LINES = {"P07", "P08"}
QUICK_LINK = "P04"  # 5G AirFiber: no trenching, the fastest install
OPTION_EXTRAS = {
    "grow": ["P18", "P15", "P14"],                # website, WhatsApp Business API, business SMS
    "secure": ["P09", "P20", "P17", "P22", "P21"],  # failover, endpoint security, backup, secure Wi-Fi, firewall
}
OPTION_ORDER = ["essential", "recommended", "quick", "grow", "secure", "complete"]


def plan_options(profile: Profile, catalogue: Catalogue, bundle: dict) -> list[dict]:
    """Alternative plans around the recommended bundle, so the owner can choose by price, speed, growth or safety.

    Every option is built only from products this business is eligible for, dependencies are re-checked,
    and an option is dropped if it fails validate_bundle or duplicates another option's core.
    Returns [{"key", "core", "addons"}] in OPTION_ORDER, always including "recommended".
    """
    elig = eligible_products(profile, catalogue)["eligible"]
    core, addons = list(bundle["core"]), list(bundle["addons"])
    qty = {p: q for p, q in core + addons}
    wanted = {pid for need in profile.needs for pid in NEED_PRODUCTS.get(need, [])}
    link = next((p for p, _ in core if p in BASE_LINKS), None)

    def q(pid: str) -> int:
        return qty.get(pid) or _need_qty(pid, profile, catalogue)

    def with_extras(base: Items, extras: list[str]) -> Items:
        ids = {p for p, _ in base}
        return base + [(p, q(p)) for p in extras if p in elig and p not in ids]

    raw: dict[str, Items] = {"recommended": core}
    raw["essential"] = [(p, n) for p, n in core if p in BASE_LINKS or p in MOBILE_LINES or p in wanted]
    # quick start swaps fibre for 5G AirFiber; a dedicated leased line (P05/P06) is a different class of service, so no swap there
    if link and link not in (QUICK_LINK, "P05", "P06") and QUICK_LINK in elig:
        n = profile.sites if catalogue[QUICK_LINK].quantity_basis == "per_site" else 1
        raw["quick"] = [(QUICK_LINK, n) if p == link else (p, m) for p, m in core]
    for key, extras in OPTION_EXTRAS.items():
        raw[key] = with_extras(core, extras)
    raw["complete"] = with_extras(core, [p for p, _ in addons])

    out, seen = [], {frozenset(core)}
    for key in OPTION_ORDER:
        if key not in raw:
            continue
        opt_core = list(raw[key])
        for _ in range(3):  # drop anything whose base product is no longer in the plan
            ids = {p for p, _ in opt_core}
            keep = [(p, n) for p, n in opt_core if not catalogue[p].requires_one_of or set(catalogue[p].requires_one_of) & ids]
            if len(keep) == len(opt_core):
                break
            opt_core = keep
        ids = {p for p, _ in opt_core}
        pool = [(p, q(p)) for p in dict.fromkeys([p for p, _ in core + addons]) if p not in ids and p in elig]
        opt_addons = [(p, n) for p, n in pool if not catalogue[p].requires_one_of or set(catalogue[p].requires_one_of) & ids]
        sig = frozenset(opt_core)
        if not ids & BASE_LINKS or validate_bundle(profile, opt_core, catalogue) or validate_bundle(profile, opt_core + opt_addons, catalogue):
            continue
        if key != "recommended" and sig in seen:
            continue
        seen.add(sig)
        out.append({"key": key, "core": opt_core, "addons": opt_addons})
    return out


def rules_version() -> str:
    h = hashlib.sha256(Path(__file__).read_bytes() + BUNDLES_PATH.read_bytes())
    return h.hexdigest()[:10]
