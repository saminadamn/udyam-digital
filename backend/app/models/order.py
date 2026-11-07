from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col

ORDER_STATES = ("QUOTE_ACCEPTED", "CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_VERIFIED", "KYC_FLAGGED", "HUMAN_REVIEW",
                "INSTALL_BOOKED", "INSTALLED", "LIVE", "CANCELLED")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("state in (" + ",".join(f"'{s}'" for s in ORDER_STATES) + ")"),)
    id: Mapped[str] = id_col("ord")
    display_id: Mapped[str] = mapped_column(String, unique=True)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), unique=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String, index=True)
    state_entered_at: Mapped[str] = created_col()
    state_due_at: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    expected_install_date: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_live_date: Mapped[str | None] = mapped_column(String, nullable=True)
    install_slot: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    payment_status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[str] = created_col()
    updated_at: Mapped[str] = created_col()


class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = created_col()
