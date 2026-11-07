from sqlalchemy import Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, created_col, id_col


class KycCase(Base):
    __tablename__ = "kyc_cases"
    id: Mapped[str] = id_col("kyc")
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    consent_id: Mapped[str] = mapped_column(ForeignKey("consents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="open")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    gstin_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    gstin_masked: Mapped[str | None] = mapped_column(String, nullable=True)
    udyam_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    udyam_masked: Mapped[str | None] = mapped_column(String, nullable=True)
    registry_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_until: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = created_col()
    submitted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[str | None] = mapped_column(String, nullable=True)


class KycDocument(Base):
    __tablename__ = "kyc_documents"
    __table_args__ = (UniqueConstraint("case_id", "doc_type", "version"),)
    id: Mapped[str] = id_col("doc")
    case_id: Mapped[str] = mapped_column(ForeignKey("kyc_cases.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)
    storage_path_enc: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String)
    mime: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    ocr_text_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)
    skew_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String, default="uploaded")
    uploaded_at: Mapped[str] = created_col()
    deleted_at: Mapped[str | None] = mapped_column(String, nullable=True)


class KycCheck(Base):
    __tablename__ = "kyc_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("kyc_cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("kyc_documents.id"), nullable=True)
    check_code: Mapped[str] = mapped_column(String)
    result: Mapped[str] = mapped_column(String)
    severity: Mapped[str | None] = mapped_column(String, nullable=True)
    message_customer: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_internal: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = created_col()
