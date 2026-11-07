from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class CallLog(Base):
    __tablename__ = "call_logs"
    id: Mapped[str] = id_col("call")
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.lead_id"), index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String, default="mock")
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = created_col()


class LeadNote(Base):
    __tablename__ = "lead_notes"
    id: Mapped[str] = id_col("note")
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.lead_id"), index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = created_col()
