from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[str] = id_col("quo")
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    monthly_total_inr: Mapped[int] = mapped_column(Integer, default=0)
    setup_total_inr: Mapped[int] = mapped_column(Integer, default=0)
    contract_months: Mapped[int] = mapped_column(Integer, default=0)
    max_install_days: Mapped[int] = mapped_column(Integer, default=0)
    pricing_rule: Mapped[str] = mapped_column(String)
    current_spend_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[str] = mapped_column(String)
    accepted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = created_col()


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (UniqueConstraint("quote_id", "product_id"),)
    id: Mapped[str] = id_col("qti")
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    qty: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String)
    selected: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_inr: Mapped[int] = mapped_column(Integer)
    line_monthly_inr: Mapped[int] = mapped_column(Integer)
    line_setup_inr: Mapped[int] = mapped_column(Integer)
    locked: Mapped[int] = mapped_column(Integer, default=0)
    lock_reason: Mapped[str | None] = mapped_column(String, nullable=True)
