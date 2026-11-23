"""
Pydantic v2 DTO Schemas for Tariff Service.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TariffDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    base_price: Decimal = Field(..., alias="basePrice")
    price_per_kg: Decimal = Field(..., alias="pricePerKg")
    price_per_km: Decimal = Field(..., alias="pricePerKm")
    urgency_multiplier: Decimal = Field(..., alias="urgencyMultiplier")
    max_delivery_days: int = Field(..., alias="maxDeliveryDays")
    is_active: bool = Field(..., alias="isActive")


class CalculatePriceInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tariff_id: UUID = Field(..., alias="tariffId")
    origin_city: str = Field(..., alias="originCity")
    dest_city: str = Field(..., alias="destCity")
    distance_km: float = Field(..., alias="distanceKm")
    weight_kg: float = Field(..., alias="weightKg")

    @field_validator("distance_km")
    @classmethod
    def validate_distance(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError("distance_km must be strictly greater than 0")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError("weight_kg must be strictly greater than 0")
        return v

    @field_validator("origin_city", "dest_city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("city name cannot be empty")
        return v.strip()


class PriceCalculationResultDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    tariff_id: UUID = Field(..., alias="tariffId")
    tariff_name: str = Field(..., alias="tariffName")
    estimated_distance_km: float = Field(..., alias="estimatedDistanceKm")
    base_price: Decimal = Field(..., alias="basePrice")
    weight_price: Decimal = Field(..., alias="weightPrice")
    distance_price: Decimal = Field(..., alias="distancePrice")
    total_price: Decimal = Field(..., alias="totalPrice")
    estimated_delivery_days: int = Field(..., alias="estimatedDeliveryDays")
