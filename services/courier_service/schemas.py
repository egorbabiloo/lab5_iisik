"""
Pydantic v2 DTO Schemas for Courier Service.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourierDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID = Field(..., alias="userId")
    transport_type: str = Field(..., alias="transportType")
    vehicle_plate: Optional[str] = Field(None, alias="vehiclePlate")
    max_payload_kg: Decimal = Field(..., alias="maxPayloadKg")
    current_status: str = Field(..., alias="currentStatus")
    current_lat: Optional[Decimal] = Field(None, alias="currentLat")
    current_lon: Optional[Decimal] = Field(None, alias="currentLon")
    rating: Decimal
    total_deliveries: int = Field(..., alias="totalDeliveries")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    @field_validator("max_payload_kg", "rating", mode="before")
    @classmethod
    def convert_to_decimal(cls, v):
        if v is not None and not isinstance(v, Decimal):
            return Decimal(str(v))
        return v

    @field_validator("current_lat", "current_lon", mode="before")
    @classmethod
    def convert_coords_to_decimal(cls, v):
        if v is not None and not isinstance(v, Decimal):
            return Decimal(str(v))
        return v


class CourierLocationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    courier_id: UUID = Field(..., alias="courierId")
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UpdateCourierStatusInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courier_id: UUID = Field(..., alias="courierId")
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"AVAILABLE", "BUSY", "OFFLINE"}
        norm = v.upper().strip()
        if norm not in valid_statuses:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {valid_statuses}")
        return norm


class UpdateCourierLocationInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courier_id: UUID = Field(..., alias="courierId")
    latitude: float
    longitude: float

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class CourierFilterDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Optional[str] = None
    transport_type: Optional[str] = Field(None, alias="transportType")
    min_payload_kg: Optional[float] = Field(None, alias="minPayloadKg")
    min_rating: Optional[float] = Field(None, alias="minRating")


class CourierSortDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str = "RATING"
    direction: str = "DESC"


class CourierPerformanceStatsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total_couriers: int = Field(..., alias="totalCouriers")
    available_couriers: int = Field(..., alias="availableCouriers")
    busy_couriers: int = Field(..., alias="busyCouriers")
    offline_couriers: int = Field(..., alias="offlineCouriers")
    average_rating: float = Field(..., alias="averageRating")
    total_delivered_count: int = Field(..., alias="totalDeliveredCount")
    top_performer: Optional[CourierDTO] = Field(None, alias="topPerformer")
