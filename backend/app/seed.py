import csv
import json
import sys
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import Agent, GstinRecord, Lead, Product, UdyamRecord, User
from app.security.crypto import encrypt, pii_hash
from app.security.masking import mask_phone

PER_SITE = {"per site", "per counter"}
PER_USER = {"per user", "per line", "per device"}

AGENTS = [
    ("Priya Sharma", "+919000000101", ["hi", "en"], ["kyc", "sales"]),
    ("Arjun Iyer", "+919000000102", ["ta", "en", "te"], ["sales", "install"]),
    ("Meera Kulkarni", "+919000000103", ["mr", "hi", "gu"], ["kyc", "install"]),
    ("Sanjay Das", "+919000000104", ["bn", "hi", "en"], ["install", "account_manager"]),
    ("Kavya Rao", "+919000000105", ["kn", "te", "en"], ["account_manager", "sales", "kyc"]),
]
DEMO_USERS = [("+919000000001", "admin"), ("+919000000002", "customer")]


def _int(v):
    if v in (None, ""):
        return None
    return int(float(v))


def _rows(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def seed_products(db: Session, data: Path) -> int:
    db.execute(delete(Product))
    n = 0
    for r in _rows(data / "product_catalogue.csv"):
        db.add(Product(
            product_id=r["product_id"], category=r["category"], name=r["product_name"], description=r["description"], unit=r["unit"],
            price_min_inr=int(r["price_min_inr_per_month"]), price_max_inr=int(r["price_max_inr_per_month"]),
            setup_fee_inr=int(r["one_time_setup_inr"]), min_contract_months=int(r["min_contract_months"]),
            min_employees=int(r["min_employees"]), min_sites=int(r["min_sites"]), install_days=int(r["typical_install_days"]),
            city_tiers=json.dumps([int(t) for t in r["available_city_tiers"].split(";")]),
            requires_gstin=1 if r["requires_gstin"] == "Y" else 0,
            requires_one_of=json.dumps([p for p in r["requires_one_of"].split("|") if p]),
            target_segments=json.dumps(r["target_segments"].split(";")),
            quantity_basis="per_site" if r["unit"] in PER_SITE else "per_user" if r["unit"] in PER_USER else "fixed",
        ))
        n += 1
    return n


def seed_registries(db: Session, data: Path) -> tuple[int, int]:
    db.execute(delete(GstinRecord))
    db.execute(delete(UdyamRecord))
    g = [GstinRecord(**{k: r[k] for k in ("gstin", "legal_name", "trade_name", "constitution", "principal_place_of_business", "state", "registration_date", "status")})
         for r in _rows(data / "mock_gstin_registry.csv")]
    u = [UdyamRecord(**{k: r[k] for k in ("udyam_number", "enterprise_name", "enterprise_type", "major_activity", "nic_description", "state", "city", "date_of_registration")})
         for r in _rows(data / "mock_udyam_registry.csv")]
    db.add_all(g)
    db.add_all(u)
    return len(g), len(u)


def seed_leads(db: Session, data: Path, score: bool = True) -> int:
    db.execute(delete(Lead).where(Lead.origin == "import"))
    rows = list(_rows(data / "smb_leads.csv"))
    scores = [None] * len(rows)
    if score:
        try:
            from app.propensity import predict_many
            scores = predict_many([r | {"city_tier": int(r["city_tier"]), "employee_count": int(r["employee_count"]), "num_sites": int(r["num_sites"]),
                                        "monthly_telecom_spend_inr": float(r["monthly_telecom_spend_inr"] or 0)} for r in rows])
        except Exception as e:
            print(f"propensity model unavailable, skipping scores: {e}", file=sys.stderr)
    ints = {"city_tier", "employee_count", "num_sites", "monthly_telecom_spend_inr", "days_lead_to_activation", "customer_follow_up_calls",
            "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months", "nps_score", "acquisition_cost_inr"}
    cols = {c.name for c in Lead.__table__.columns}
    n = 0
    for r, p in zip(rows, scores):
        rec = {k: (_int(v) if k in ints else (v or None)) for k, v in r.items() if k in cols}
        if p:
            rec.update(propensity_score=p["score"], propensity_bucket=p["bucket"], propensity_reasons=json.dumps(p["top_3_reasons"]))
        db.add(Lead(origin="import", **rec))
        n += 1
    return n


def _user(db: Session, phone: str, role: str) -> User:
    h = pii_hash(phone)
    u = db.scalar(select(User).where(User.phone_hash == h))
    if not u:
        u = User(phone_enc=encrypt(phone), phone_hash=h, phone_masked=mask_phone(phone), role=role, language="en")
        db.add(u)
        db.flush()
    return u


def seed_people(db: Session) -> int:
    for phone, role in DEMO_USERS:
        _user(db, phone, role)
    for name, phone, langs, skills in AGENTS:
        u = _user(db, phone, "agent")
        if not db.scalar(select(Agent).where(Agent.user_id == u.id)):
            db.add(Agent(user_id=u.id, name=name, languages=json.dumps(langs), skills=json.dumps(skills)))
    return len(AGENTS)


def run(data_dir: Path | None = None, score: bool = True, verbose: bool = True) -> dict:
    data = Path(data_dir or get_settings().data_dir)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        out = {"products": seed_products(db, data)}
        out["gstin_registry"], out["udyam_registry"] = seed_registries(db, data)
        out["leads"] = seed_leads(db, data, score)
        out["agents"] = seed_people(db)
        db.commit()
    if verbose:
        print(json.dumps(out))
    return out


if __name__ == "__main__":
    run(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
