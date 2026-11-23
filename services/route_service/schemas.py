"""
Pydantic v2 DTO schemas for Route Service.
Decoupled from SQLAlchemy ORM models.
"""
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RouteStageDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    stage_order: int = Field(..., alias="stageOrder")
    stage_type: str = Field(..., alias="stageType")
    origin_point: str = Field(..., alias="originPoint")
    dest_point: str = Field(..., alias="destPoint")
    planned_start: datetime = Field(..., alias="plannedStart")
    planned_end: datetime = Field(..., alias="plannedEnd")
    status: str


class RouteDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    shipment_id: UUID = Field(..., alias="shipmentId")
    total_distance_km: Decimal = Field(..., alias="totalDistanceKm")
    estimated_duration_min: int = Field(..., alias="estimatedDurationMin")
    current_stage_order: int = Field(..., alias="currentStageOrder")
    status: str
    created_at: datetime = Field(..., alias="createdAt")
    stages: List[RouteStageDTO] = Field(default_factory=list)

    @field_validator("total_distance_km", mode="before")
    @classmethod
    def convert_distance(cls, v: Any) -> Any:
        if v is not None and not isinstance(v, Decimal):
            return Decimal(str(v))
        return v


class CreateRouteInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    shipment_id: UUID = Field(..., alias="shipmentId")
    total_distance_km: Decimal = Field(..., alias="totalDistanceKm")
    estimated_duration_min: int = Field(..., alias="estimatedDurationMin")
    current_stage_order: int = Field(1, alias="currentStageOrder")
    status: str = "ACTIVE"

    @field_validator("total_distance_km", mode="before")
    @classmethod
    def convert_distance(cls, v: Any) -> Any:
        if v is not None and not isinstance(v, Decimal):
            return Decimal(str(v))
        return v


class CreateRouteStageInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    route_id: UUID = Field(..., alias="routeId")
    stage_order: int = Field(..., alias="stageOrder")
    stage_type: str = Field(..., alias="stageType")
    origin_point: str = Field(..., alias="originPoint")
    dest_point: str = Field(..., alias="destPoint")
    planned_start: datetime = Field(..., alias="plannedStart")
    planned_end: datetime = Field(..., alias="plannedEnd")
    status: str = "PENDING"
