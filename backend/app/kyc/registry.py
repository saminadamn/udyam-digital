"""Registry lookups used by the KYC checks: one backed by the database (the app), one by the CSVs (the batch script)."""
import csv
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.kyc import names
from app.models import GstinRecord, UdyamRecord

GST_COLS = ("gstin", "legal_name", "trade_name", "constitution", "principal_place_of_business", "state", "registration_date", "status")
UDY_COLS = ("udyam_number", "enterprise_name", "enterprise_type", "major_activity", "nic_description", "state", "city", "date_of_registration")


def _row(obj, cols) -> dict:
    return {c: getattr(obj, c) for c in cols}


class DbRegistry:
    def __init__(self, db: Session):
        self.db = db

    def gstin(self, g):
        r = self.db.get(GstinRecord, g)
        return _row(r, GST_COLS) if r else None

    def gstins_by_name(self, name):
        rows = self.db.scalars(select(GstinRecord)).all() if name else []
        return [_row(r, GST_COLS) for r in rows if names.match(name, r.trade_name) or names.match(name, r.legal_name)]

    def udyam(self, num):
        r = self.db.get(UdyamRecord, num)
        return _row(r, UDY_COLS) if r else None

    def udyams_by_name(self, name):
        if not name:
            return []
        rows = self.db.scalars(select(UdyamRecord).where(func.lower(UdyamRecord.enterprise_name) == name.lower())).all()
        return [_row(r, UDY_COLS) for r in rows]


class CsvRegistry:
    def __init__(self, data_dir: Path):
        with open(data_dir / "mock_gstin_registry.csv", newline="", encoding="utf-8") as f:
            self.g = {r["gstin"]: r for r in csv.DictReader(f)}
        with open(data_dir / "mock_udyam_registry.csv", newline="", encoding="utf-8") as f:
            self.u = {r["udyam_number"]: r for r in csv.DictReader(f)}

    def gstin(self, g):
        return self.g.get(g)

    def gstins_by_name(self, name):
        return [r for r in self.g.values() if name and (names.match(name, r["trade_name"]) or names.match(name, r["legal_name"]))]

    def udyam(self, num):
        return self.u.get(num)

    def udyams_by_name(self, name):
        return [r for r in self.u.values() if name and r["enterprise_name"].lower() == name.lower()]
