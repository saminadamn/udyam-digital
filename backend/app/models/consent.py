from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, id_col


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = id_col("cns")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id"), nullable=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    purpose: Mapped[str] = mapped_column(String)
    notice_version: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String)
    granted: Mapped[int] = mapped_column(Integer, default=1)
    granted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    withdrawn_at: Mapped[str | None] = mapped_column(String, nullable=True)
    client_hash: Mapped[str | None] = mapped_column(String, nullable=True)
