"""
Analytics Service ORM Models: events_shipment_stream, daily_delivery_stats.
Database: analytics_db (PostgreSQL 16)
Zero Cross-Database ForeignKeys: shipment_id, client_id, tariff_id, courier_id are pure scalar UUIDs.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.common.database import Base


class EventShipmentStream(Base):
    __tablename__ = "events_shipment_stream"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Inter-database logical references (SCALAR UUIDs ONLY, NO FOREIGN KEYS)
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tariff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    origin_city: Mapped[str] = mapped_column(String(100), nullable=False)
    dest_city: Mapped[str] = mapped_column(String(100), nullable=False)
    total_distance_km: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    courier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    is_delayed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<EventShipmentStream(id={self.event_id}, type='{self.event_type}', shipment_id={self.shipment_id})>"


class DailyDeliveryStats(Base):
    __tablename__ = "daily_delivery_stats"

    # Composite Primary Key
    report_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    tariff_code: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)

    shipments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    avg_delivery_time_min: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=Decimal("0.00")
    )
    sla_compliance_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("1.0000")
    )

    def __repr__(self) -> str:
        return f"<DailyDeliveryStats(date={self.report_date}, tariff='{self.tariff_code}', count={self.shipments_count})>"


__all_models__ = [EventShipmentStream, DailyDeliveryStats]
