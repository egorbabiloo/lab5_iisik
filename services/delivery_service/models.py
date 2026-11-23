"""
Delivery Service ORM Models: deliveries, delivery_checkpoints.
Database: delivery_db
Zero Cross-Database ForeignKeys: shipment_id, route_stage_id, courier_id are pure scalar UUIDs.
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.common.database import Base


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Inter-database logical references (SCALAR UUIDs ONLY, NO FOREIGN KEYS)
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    route_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    courier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    delivery_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING_ASSIGNMENT", index=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    otp_code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Intra-database relationship
    checkpoints: Mapped[List["DeliveryCheckpoint"]] = relationship(
        "DeliveryCheckpoint",
        back_populates="delivery",
        cascade="all, delete-orphan",
        order_by="DeliveryCheckpoint.recorded_at.asc()"
    )

    def __repr__(self) -> str:
        return f"<Delivery(id={self.id}, shipment_id={self.shipment_id}, status='{self.status}')>"


class DeliveryCheckpoint(Base):
    __tablename__ = "delivery_checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Intra-database foreign key
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Intra-database relationship
    delivery: Mapped["Delivery"] = relationship("Delivery", back_populates="checkpoints")

    def __repr__(self) -> str:
        return f"<DeliveryCheckpoint(id={self.id}, delivery_id={self.delivery_id}, status='{self.status}')>"


__all_models__ = [Delivery, DeliveryCheckpoint]
