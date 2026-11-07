from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base


class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String)
    price_min_inr: Mapped[int] = mapped_column(Integer)
    price_max_inr: Mapped[int] = mapped_column(Integer)
    setup_fee_inr: Mapped[int] = mapped_column(Integer)
    min_contract_months: Mapped[int] = mapped_column(Integer)
    min_employees: Mapped[int] = mapped_column(Integer)
    min_sites: Mapped[int] = mapped_column(Integer)
    install_days: Mapped[int] = mapped_column(Integer)
    city_tiers: Mapped[str] = mapped_column(Text)
    requires_gstin: Mapped[int] = mapped_column(Integer)
    requires_one_of: Mapped[str] = mapped_column(Text, default="[]")
    target_segments: Mapped[str] = mapped_column(Text, default="[]")
    quantity_basis: Mapped[str] = mapped_column(String, default="fixed")
