"""
Shipment Service ORM Models: shipments, shipment_status_history.
Database: shipment_db
Zero Cross-Database ForeignKeys: client_id and tariff_id are pure scalar UUIDs.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Text, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.common.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tracking_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )

    # Inter-database logical references (SCALAR UUIDs ONLY, NO FOREIGN KEYS)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tariff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    length_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    width_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    calculated_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    current_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="CREATED", index=True
    )

    origin_city: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_address: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    origin_lon: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)

    dest_city: Mapped[str] = mapped_column(String(100), nullable=False)
    dest_address: Mapped[str] = mapped_column(String(255), nullable=False)
    dest_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    dest_lon: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)

    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Intra-database relationship
    status_history: Mapped[List["ShipmentStatusHistory"]] = relationship(
        "ShipmentStatusHistory",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentStatusHistory.changed_at.asc()"
    )

    def __repr__(self) -> str:
        return f"<Shipment(id={self.id}, tracking='{self.tracking_number}', status='{self.current_status}')>"


class ShipmentStatusHistory(Base):
    __tablename__ = "shipment_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Intra-database foreign key
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Intra-database relationship
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="status_history")

    def __repr__(self) -> str:
        return f"<ShipmentStatusHistory(id={self.id}, shipment_id={self.shipment_id}, status='{self.status}')>"


__all_models__ = [Shipment, ShipmentStatusHistory]
