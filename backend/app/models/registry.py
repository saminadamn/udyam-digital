from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base


class GstinRecord(Base):
    __tablename__ = "gstin_registry"
    gstin: Mapped[str] = mapped_column(String, primary_key=True)
    legal_name: Mapped[str] = mapped_column(String)
    trade_name: Mapped[str] = mapped_column(String)
    constitution: Mapped[str] = mapped_column(String)
    principal_place_of_business: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    registration_date: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class UdyamRecord(Base):
    __tablename__ = "udyam_registry"
    udyam_number: Mapped[str] = mapped_column(String, primary_key=True)
    enterprise_name: Mapped[str] = mapped_column(String)
    enterprise_type: Mapped[str] = mapped_column(String)
    major_activity: Mapped[str] = mapped_column(String)
    nic_description: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    date_of_registration: Mapped[str] = mapped_column(String)


Index("ix_gstin_trade_name", func.lower(GstinRecord.trade_name))
Index("ix_udyam_name_city", func.lower(UdyamRecord.enterprise_name), func.lower(UdyamRecord.city))
