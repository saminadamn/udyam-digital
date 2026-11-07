from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = id_col("cnv")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.lead_id"), nullable=True)
    language: Mapped[str] = mapped_column(String, default="hi")
    channel: Mapped[str] = mapped_column(String, default="text")
    status: Mapped[str] = mapped_column(String, default="active")
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    questions_asked: Mapped[int] = mapped_column(Integer, default=0)
    failed_turns: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = created_col()
    updated_at: Mapped[str] = created_col()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = id_col("msg")
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    modality: Mapped[str] = mapped_column(String, default="text")
    audio_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="ok")
    created_at: Mapped[str] = created_col()
