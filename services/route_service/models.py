"""
Route Service ORM Models: routes, route_stages.
Database: route_db
Zero Cross-Database ForeignKeys: shipment_id is a pure scalar UUID logical reference.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.common.database import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Inter-database logical reference to shipment_db.shipments.id (SCALAR UUID, NO FOREIGN KEY)
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    total_distance_km: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    estimated_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    current_stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Intra-database relationship
    stages: Mapped[List["RouteStage"]] = relationship(
        "RouteStage",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStage.stage_order.asc()"
    )

    def __repr__(self) -> str:
        return f"<Route(id={self.id}, shipment_id={self.shipment_id}, status='{self.status}')>"


class RouteStage(Base):
    __tablename__ = "route_stages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Intra-database foreign key
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    origin_point: Mapped[str] = mapped_column(String(150), nullable=False)
    dest_point: Mapped[str] = mapped_column(String(150), nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING", index=True
    )

    # Intra-database relationship
    route: Mapped["Route"] = relationship("Route", back_populates="stages")

    def __repr__(self) -> str:
        return f"<RouteStage(id={self.id}, route_id={self.route_id}, order={self.stage_order}, type='{self.stage_type}')>"


__all_models__ = [Route, RouteStage]
