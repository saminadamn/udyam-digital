from sqlalchemy import CheckConstraint, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col

SEGMENTS = ("Micro retail & services", "Professional offices", "Small multi-site businesses", "Small manufacturers")


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint("city_tier in (1,2)"),
        CheckConstraint("employees >= 1"),
        CheckConstraint("sites >= 1"),
    )
    id: Mapped[str] = id_col("biz")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    business_type: Mapped[str | None] = mapped_column(String, nullable=True)
    segment: Mapped[str] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    city_tier: Mapped[int] = mapped_column(Integer)
    employees: Mapped[int] = mapped_column(Integer)
    sites: Mapped[int] = mapped_column(Integer)
    turnover_band: Mapped[str | None] = mapped_column(String, nullable=True)
    current_internet: Mapped[str | None] = mapped_column(String, nullable=True)
    current_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    monthly_spend_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_gstin: Mapped[int] = mapped_column(Integer, default=0)
    gstin_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    gstin_masked: Mapped[str | None] = mapped_column(String, nullable=True)
    gst_status: Mapped[str] = mapped_column(String, default="None")
    has_udyam: Mapped[int] = mapped_column(Integer, default=0)
    udyam_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    udyam_masked: Mapped[str | None] = mapped_column(String, nullable=True)
    products_of_interest: Mapped[str] = mapped_column(Text, default="[]")
    lead_source: Mapped[str | None] = mapped_column(String, nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = created_col()
    updated_at: Mapped[str] = created_col()
