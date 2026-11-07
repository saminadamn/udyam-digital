from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = id_col("ntf")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String)
    template: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String, default="queued")
    provider_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = created_col()
    sent_at: Mapped[str | None] = mapped_column(String, nullable=True)
