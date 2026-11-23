"""
Courier Service ORM Models: couriers.
Database: courier_db
Zero Cross-Database ForeignKeys: user_id is a pure scalar UUID logical reference.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.common.database import Base


class Courier(Base):
    __tablename__ = "couriers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Inter-database logical reference to user_db.users.id (SCALAR UUID, NO FOREIGN KEY)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    transport_type: Mapped[str] = mapped_column(String(30), nullable=False)
    vehicle_plate: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    max_payload_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    current_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="OFFLINE", index=True
    )
    current_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    current_lon: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("5.00")
    )
    total_deliveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Courier(id={self.id}, user_id={self.user_id}, status='{self.current_status}')>"


__all_models__ = [Courier]
