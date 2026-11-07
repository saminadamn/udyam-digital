import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import Product

router = APIRouter(prefix="/products", tags=["products"])
SEG_KEYS = {"micro", "prof", "multi", "mfg"}


def out(p: Product) -> dict:
    return {"product_id": p.product_id, "name": p.name, "category": p.category, "description": p.description, "unit": p.unit,
            "price_min_inr": p.price_min_inr, "price_max_inr": p.price_max_inr, "setup_fee_inr": p.setup_fee_inr,
            "min_contract_months": p.min_contract_months, "install_days": p.install_days, "requires_gstin": bool(p.requires_gstin),
            "requires_one_of": json.loads(p.requires_one_of), "city_tiers": json.loads(p.city_tiers), "min_employees": p.min_employees,
            "min_sites": p.min_sites, "target_segments": json.loads(p.target_segments)}


@router.get("")
def list_products(segment: str | None = None, city_tier: int | None = None, db: Session = Depends(get_db)):
    if segment and segment not in SEG_KEYS:
        raise ApiError(400, "VALIDATION_ERROR", "segment must be one of micro, prof, multi, mfg", {"field": "segment"})
    items = [out(p) for p in db.scalars(select(Product).order_by(Product.product_id))]
    if segment:
        items = [p for p in items if segment in p["target_segments"]]
    if city_tier:
        items = [p for p in items if city_tier in p["city_tiers"]]
    return {"products": items}


@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise ApiError(404, "NOT_FOUND", "Product not found.")
    return out(p)
