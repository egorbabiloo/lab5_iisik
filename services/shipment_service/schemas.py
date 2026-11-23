"""
Pydantic v2 DTO schemas for Shipment Service.
Decoupled from SQLAlchemy ORM models.
"""
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class DimensionsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    length_cm: float = Field(..., alias="lengthCm")
    width_cm: float = Field(..., alias="widthCm")
    height_cm: float = Field(..., alias="heightCm")


class ShipmentStatusHistoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    shipment_id: UUID = Field(..., alias="shipmentId")
    status: str
    comment: Optional[str] = None
    changed_at: datetime = Field(..., alias="changedAt")


class ShipmentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    tracking_number: str = Field(..., alias="trackingNumber")
    client_id: UUID = Field(..., alias="clientId")
    tariff_id: UUID = Field(..., alias="tariffId")
    weight_kg: float = Field(..., alias="weightKg")
    length_cm: float = Field(..., alias="lengthCm")
    width_cm: float = Field(..., alias="widthCm")
    height_cm: float = Field(..., alias="heightCm")
    calculated_price: Decimal = Field(..., alias="calculatedPrice")
    current_status: str = Field(..., alias="currentStatus")
    origin_city: str = Field(..., alias="originCity")
    origin_address: str = Field(..., alias="originAddress")
    origin_lat: float = Field(..., alias="originLat")
    origin_lon: float = Field(..., alias="originLon")
    dest_city: str = Field(..., alias="destCity")
    dest_address: str = Field(..., alias="destAddress")
    dest_lat: float = Field(..., alias="destLat")
    dest_lon: float = Field(..., alias="destLon")
    recipient_name: str = Field(..., alias="recipientName")
    recipient_phone: str = Field(..., alias="recipientPhone")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    @field_validator(
        "weight_kg",
        "length_cm",
        "width_cm",
        "height_cm",
        "origin_lat",
        "origin_lon",
        "dest_lat",
        "dest_lon",
        mode="before",
    )
    @classmethod
    def convert_decimal_to_float(cls, v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v)
        return v

    @computed_field
    @property
    def dimensions(self) -> DimensionsDTO:
        return DimensionsDTO(
            length_cm=self.length_cm,
            width_cm=self.width_cm,
            height_cm=self.height_cm,
        )


class ShipmentConnectionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    items: List[ShipmentDTO]
    total_count: int = Field(..., alias="totalCount")


class TrackingEventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    timestamp: datetime
    status: str
    location_name: str = Field(..., alias="locationName")
    description: Optional[str] = None


class TrackingTimelineDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    tracking_number: str = Field(..., alias="trackingNumber")
    status: str
    origin_city: str = Field(..., alias="originCity")
    dest_city: str = Field(..., alias="destCity")
    courier_lat: Optional[float] = Field(None, alias="courierLat")
    courier_lon: Optional[float] = Field(None, alias="courierLon")
    events: List[TrackingEventDTO] = Field(default_factory=list)


class CreateShipmentInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: UUID = Field(..., alias="clientId")
    tariff_id: UUID = Field(..., alias="tariffId")
    weight_kg: float = Field(..., alias="weightKg")
    length_cm: float = Field(..., alias="lengthCm")
    width_cm: float = Field(..., alias="widthCm")
    height_cm: float = Field(..., alias="heightCm")
    calculated_price: Decimal = Field(..., alias="calculatedPrice")
    origin_city: str = Field(..., alias="originCity")
    origin_address: str = Field(..., alias="originAddress")
    origin_lat: float = Field(..., alias="originLat")
    origin_lon: float = Field(..., alias="originLon")
    dest_city: str = Field(..., alias="destCity")
    dest_address: str = Field(..., alias="destAddress")
    dest_lat: float = Field(..., alias="destLat")
    dest_lon: float = Field(..., alias="destLon")
    recipient_name: str = Field(..., alias="recipientName")
    recipient_phone: str = Field(..., alias="recipientPhone")


class ShipmentFilterDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Optional[List[str]] = None
    origin_city: Optional[str] = Field(None, alias="originCity")
    dest_city: Optional[str] = Field(None, alias="destCity")
    tariff_id: Optional[UUID] = Field(None, alias="tariffId")
    date_from: Optional[datetime] = Field(None, alias="dateFrom")
    date_to: Optional[datetime] = Field(None, alias="dateTo")
    min_price: Optional[Decimal] = Field(None, alias="minPrice")
    max_price: Optional[Decimal] = Field(None, alias="maxPrice")
    min_weight: Optional[float] = Field(None, alias="minWeight")
    max_weight: Optional[float] = Field(None, alias="maxWeight")
    search_query: Optional[str] = Field(None, alias="searchQuery")


class ShipmentSortDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str = "CREATED_AT"
    direction: str = "DESC"


class PaginationDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    limit: int = 50
    offset: int = 0


class StatusCountDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    status: str
    count: int


class CityRevenueStatsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    city: str
    shipment_count: int = Field(..., alias="shipmentCount")
    total_revenue: Decimal = Field(..., alias="totalRevenue")


class TariffUsageStatsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    tariff_name: str = Field(..., alias="tariffName")
    count: int
    revenue: Decimal


class ShipmentStatsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total_count: int = Field(..., alias="totalCount")
    total_revenue: Decimal = Field(..., alias="totalRevenue")
    average_price: Decimal = Field(..., alias="averagePrice")
    min_price: Decimal = Field(..., alias="minPrice")
    max_price: Decimal = Field(..., alias="maxPrice")
    average_weight: float = Field(..., alias="averageWeight")
    status_breakdown: List[StatusCountDTO] = Field(default_factory=list, alias="statusBreakdown")
    city_breakdown: List[CityRevenueStatsDTO] = Field(default_factory=list, alias="cityBreakdown")
    tariff_breakdown: List[TariffUsageStatsDTO] = Field(default_factory=list, alias="tariffBreakdown")
