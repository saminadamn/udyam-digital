from sqlalchemy import CheckConstraint, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role in ('customer','agent','admin')"),)
    id: Mapped[str] = id_col("usr")
    phone_enc: Mapped[bytes] = mapped_column(LargeBinary)
    phone_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    phone_masked: Mapped[str] = mapped_column(String)
    display_name_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    role: Mapped[str] = mapped_column(String, default="customer")
    language: Mapped[str] = mapped_column(String, default="hi")
    whatsapp_opt_in: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = created_col()
    last_login_at: Mapped[str | None] = mapped_column(String, nullable=True)


class OtpRequest(Base):
    __tablename__ = "otp_requests"
    id: Mapped[str] = id_col("otp")
    phone_hash: Mapped[str] = mapped_column(String, index=True)
    code_hash: Mapped[str] = mapped_column(String)
    expires_at: Mapped[str] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = created_col()


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = id_col("agt")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String)
    languages: Mapped[str] = mapped_column(Text, default="[]")
    skills: Mapped[str] = mapped_column(Text, default="[]")
    max_open: Mapped[int] = mapped_column(Integer, default=8)
    active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = created_col()
