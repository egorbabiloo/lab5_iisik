"""
Tariff Service ORM Models: tariffs.
Database: tariff_db
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Text, Integer, Numeric, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.common.database import Base


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    urgency_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("1.00")
    )
    max_delivery_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Tariff(id={self.id}, code='{self.code}', base_price={self.base_price})>"


__all_models__ = [Tariff]
