from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (
        CheckConstraint("coalesce(order_id, kyc_case_id, conversation_id, lead_id) is not null"),
        CheckConstraint("trigger in ('sla_breach','kyc_flag','advisor_failed','user_request','assisted_deal')"),
    )
    id: Mapped[str] = id_col("esc")
    trigger: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String, default="P2")
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    kyc_case_id: Mapped[str | None] = mapped_column(ForeignKey("kyc_cases.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.lead_id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open", index=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    required_skill: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    sla_due_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = created_col()
    assigned_at: Mapped[str | None] = mapped_column(String, nullable=True)
    first_response_at: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
