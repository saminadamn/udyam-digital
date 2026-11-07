import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
CAT = pd.read_csv(ROOT / "data" / "product_catalogue.csv", dtype=str).set_index("product_id")


def rule_errors(profile, items):
    errs = []
    ids = {pid for pid, _ in items}
    for pid, qty in items:
        if pid not in CAT.index:
            errs.append(f"{pid}: not in catalogue")
            continue
        r = CAT.loc[pid]
        if qty < 1:
            errs.append(f"{pid}: quantity must be at least 1")
        if str(profile["city_tier"]) not in r.available_city_tiers.split(";"):
            errs.append(f"{pid}: not sold in tier {profile['city_tier']}")
        if profile["employees"] < int(r.min_employees):
            errs.append(f"{pid}: needs {r.min_employees}+ employees")
        if profile["sites"] < int(r.min_sites):
            errs.append(f"{pid}: needs {r.min_sites}+ sites")
        if r.requires_gstin == "Y" and profile.get("gst_status") != "Active":
            errs.append(f"{pid}: needs an active GSTIN")
        if isinstance(r.requires_one_of, str) and r.requires_one_of and not (set(r.requires_one_of.split("|")) & ids):
            errs.append(f"{pid}: needs one of {r.requires_one_of.replace('|', ', ')} in the bundle")
    return errs


def price(items, key):
    monthly = setup = 0
    for pid, qty in items:
        r = CAT.loc[pid]
        lo, hi = int(r.price_min_inr_per_month), int(r.price_max_inr_per_month)
        unit = lo if key == "micro" else round((lo + hi) / 2)
        assert lo <= unit <= hi
        monthly += unit * qty
        setup += int(r.one_time_setup_inr) * qty
    contract = max(int(CAT.loc[pid].min_contract_months) for pid, _ in items)
    install = max(int(CAT.loc[pid].typical_install_days) for pid, _ in items)
    return monthly, setup, contract, install


def scale(items, prof, per_site, per_user):
    out = []
    for pid, q in items:
        if pid in per_site:
            q = prof["sites"]
        elif pid in per_user:
            q = min(q, prof["employees"])
        out.append((pid, q))
    return out


def validate(spec):
    results = []
    for b in spec["bundles"]:
        for prof in b["profiles"]:
            per_site, per_user = set(b.get("per_site", [])), set(b.get("per_user", []))
            core = scale(b["core"], prof, per_site, per_user)
            addons = scale(b["addons"], prof, per_site, per_user)
            variants = [("core", core), ("core + add-ons", core + addons)]
            if b.get("gstin_only_addons"):
                g = scale(b["gstin_only_addons"], prof, per_site, per_user)
                variants.append(("core + GSTIN add-ons", core + g))
            if b.get("fallback"):
                old, new = b["fallback"]["swap"]
                variants.append((f"fallback ({b['fallback']['when']})", [(new if p == old else p, q) for p, q in core]))
            if b.get("tier1_upgrade"):
                old, new = b["tier1_upgrade"]["swap"]
                variants.append(("tier-1 upgrade", [(new if p == old else p, q) for p, q in core]))
            for name, items in variants:
                errs = rule_errors(prof, items)
                conditional = name in ("core + GSTIN add-ons", "tier-1 upgrade")
                m, s, ct, inst = price(items, b["key"]) if not errs else (0, 0, 0, 0)
                results.append({"bundle": b["name"], "profile": prof["label"], "variant": name, "items": items,
                                "monthly": m, "setup": s, "contract": ct, "install_days": inst, "conditional": conditional,
                                "ok": conditional or not errs, "offered": not errs, "errors": errs})
    return results


NEGATIVE = [
    ("WhatsApp API without a GSTIN", {"city_tier": 2, "employees": 3, "sites": 1, "gst_status": "None"}, [("P01", 1), ("P15", 1)]),
    ("Biz Fibre 1G in a tier 2 city", {"city_tier": 2, "employees": 8, "sites": 1, "gst_status": "Active"}, [("P03", 1)]),
    ("Cloud CCTV with no connection", {"city_tier": 1, "employees": 2, "sites": 1, "gst_status": "None"}, [("P23", 2)]),
    ("SD-WAN for only 2 sites", {"city_tier": 1, "employees": 15, "sites": 2, "gst_status": "Active"}, [("P02", 2), ("P10", 2)]),
    ("Leased line on a cancelled GSTIN", {"city_tier": 1, "employees": 40, "sites": 1, "gst_status": "Cancelled"}, [("P05", 1)]),
    ("Static IP on a leased line", {"city_tier": 1, "employees": 40, "sites": 1, "gst_status": "Active"}, [("P05", 1), ("P11", 1)]),
    ("Cloud Telephony for a 2-person office", {"city_tier": 1, "employees": 2, "sites": 1, "gst_status": "Active"}, [("P01", 1), ("P12", 1)]),
    ("Machine IoT for a 6-person unit", {"city_tier": 2, "employees": 6, "sites": 1, "gst_status": "Active"}, [("P01", 1), ("P24", 2)]),
    ("Toll-free on a suspended GSTIN", {"city_tier": 1, "employees": 5, "sites": 1, "gst_status": "Suspended"}, [("P13", 1)]),
]


def negative_tests():
    return [{"case": n, "errors": rule_errors(p, i), "ok": bool(rule_errors(p, i))} for n, p, i in NEGATIVE]


if __name__ == "__main__":
    spec = json.loads((ROOT / "analysis" / "bundles.json").read_text())
    res = validate(spec)
    neg = negative_tests()
    for r in res:
        status = "OK  " if r["ok"] else "FAIL"
        detail = f"Rs {r['monthly']:,}/mo, setup Rs {r['setup']:,}, {r['contract']} mo" if r["offered"] else f"blocked (conditional): {r['errors']}"
        print(f"[{status}] {r['bundle']:<14} | {r['profile']:<52} | {r['variant']:<38} | {detail}" + ("" if r["ok"] else f" | {r['errors']}"))
    for n in neg:
        print(f"[{'OK  ' if n['ok'] else 'FAIL'}] negative: {n['case']:<40} -> {n['errors']}")
    bad = sum(not r["ok"] for r in res) + sum(not n["ok"] for n in neg)
    print(f"\n{len(res)} bundle checks, {len(neg)} negative checks, {bad} failures")
    sys.exit(1 if bad else 0)
