"""
Analytics Service Pydantic v2 Data Transfer Objects (DTOs).
Strict database isolation: only scalar types and primitives.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DateRangeInputDTO(BaseModel):
    """Input parameters for analytics aggregation queries."""
    model_config = ConfigDict(populate_by_name=True)

    start_date: datetime = Field(..., alias="startDate", description="Beginning of reporting period")
    end_date: datetime = Field(..., alias="endDate", description="End of reporting period")

    @model_validator(mode="after")
    def validate_range(self) -> "DateRangeInputDTO":
        if self.start_date > self.end_date:
            raise ValueError("startDate cannot be greater than endDate")
        return self


class AnalyticsSummaryDTO(BaseModel):
    """Aggregated operational summary metrics."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    period_start: datetime = Field(..., alias="periodStart")
    period_end: datetime = Field(..., alias="periodEnd")
    total_shipments: int = Field(..., alias="totalShipments", ge=0)
    delivered_shipments: int = Field(..., alias="deliveredShipments", ge=0)
    total_revenue: Decimal = Field(..., alias="totalRevenue", ge=Decimal("0.00"))
    average_delivery_duration_min: float = Field(..., alias="averageDeliveryDurationMin", ge=0.0)
    sla_compliance_rate: float = Field(..., alias="slaComplianceRate", ge=0.0, le=1.0)
    avg_delivery_duration_hours: Optional[float] = Field(None, alias="avgDeliveryDurationHours", ge=0.0)


class ShipmentStreamEventDTO(BaseModel):
    """DTO representing a single operational shipment lifecycle event."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    event_id: UUID = Field(..., alias="eventId")
    event_time: datetime = Field(..., alias="eventTime")
    event_type: str = Field(..., alias="eventType")
    shipment_id: UUID = Field(..., alias="shipmentId")
    client_id: UUID = Field(..., alias="clientId")
    tariff_id: UUID = Field(..., alias="tariffId")
    weight_kg: Decimal = Field(..., alias="weightKg")
    price: Decimal = Field(..., alias="price")
    origin_city: str = Field(..., alias="originCity")
    dest_city: str = Field(..., alias="destCity")
    total_distance_km: Decimal = Field(..., alias="totalDistanceKm")
    courier_id: Optional[UUID] = Field(None, alias="courierId")
    is_delayed: bool = Field(False, alias="isDelayed")


class DailyDeliveryStatsDTO(BaseModel):
    """DTO representing daily aggregated metrics per tariff code."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    report_date: date = Field(..., alias="reportDate")
    tariff_code: str = Field(..., alias="tariffCode")
    shipments_count: int = Field(..., alias="shipmentsCount", ge=0)
    delivered_count: int = Field(..., alias="deliveredCount", ge=0)
    total_revenue: Decimal = Field(..., alias="totalRevenue", ge=Decimal("0.00"))
    avg_delivery_time_min: Decimal = Field(..., alias="avgDeliveryTimeMin", ge=Decimal("0.00"))
    sla_compliance_rate: Decimal = Field(..., alias="slaComplianceRate", ge=Decimal("0.0000"), le=Decimal("1.0000"))
