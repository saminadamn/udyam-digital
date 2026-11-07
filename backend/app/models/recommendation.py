from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = id_col("rec")
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id"), nullable=True)
    bundle_key: Mapped[str] = mapped_column(String)
    items: Mapped[str] = mapped_column(Text)
    blocked: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str] = mapped_column(Text)
    rules_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = created_col()
