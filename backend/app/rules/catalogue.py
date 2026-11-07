import csv
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rules.engine import Catalogue, Product

PER_SITE = {"per site", "per counter"}
PER_USER = {"per user", "per line", "per device"}


def from_csv(path: Path) -> Catalogue:
    out: Catalogue = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["product_id"]] = Product(
                product_id=r["product_id"], name=r["product_name"], unit=r["unit"],
                price_min_inr=int(r["price_min_inr_per_month"]), price_max_inr=int(r["price_max_inr_per_month"]),
                setup_fee_inr=int(r["one_time_setup_inr"]), min_contract_months=int(r["min_contract_months"]),
                city_tiers=tuple(int(t) for t in r["available_city_tiers"].split(";")),
                min_employees=int(r["min_employees"]), min_sites=int(r["min_sites"]), requires_gstin=r["requires_gstin"] == "Y",
                requires_one_of=tuple(p for p in r["requires_one_of"].split("|") if p), install_days=int(r["typical_install_days"]),
                quantity_basis="per_site" if r["unit"] in PER_SITE else "per_user" if r["unit"] in PER_USER else "fixed",
            )
    return out


def from_db(db: Session) -> Catalogue:
    from app.models import Product as P

    out: Catalogue = {}
    for r in db.scalars(select(P)):
        out[r.product_id] = Product(
            product_id=r.product_id, name=r.name, unit=r.unit, price_min_inr=r.price_min_inr, price_max_inr=r.price_max_inr,
            setup_fee_inr=r.setup_fee_inr, min_contract_months=r.min_contract_months, city_tiers=tuple(json.loads(r.city_tiers)),
            min_employees=r.min_employees, min_sites=r.min_sites, requires_gstin=bool(r.requires_gstin),
            requires_one_of=tuple(json.loads(r.requires_one_of)), install_days=r.install_days, quantity_basis=r.quantity_basis,
        )
    return out


@lru_cache(maxsize=1)
def cached_from_db() -> Catalogue:
    from app.db import SessionLocal

    with SessionLocal() as db:
        return from_db(db)
