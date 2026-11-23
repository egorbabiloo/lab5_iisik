"""
Pydantic v2 DTO schemas for Delivery Service.
Decoupled from SQLAlchemy ORM models.
"""
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class DeliveryCheckpointDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    status: str
    recorded_at: datetime = Field(..., alias="recordedAt")
    location_name: str = Field(..., alias="locationName")
    notes: Optional[str] = None


class DeliveryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    shipment_id: UUID = Field(..., alias="shipmentId")
    route_stage_id: UUID = Field(..., alias="routeStageId")
    courier_id: Optional[UUID] = Field(None, alias="courierId")
    delivery_type: str = Field(..., alias="deliveryType")
    status: str
    window_start: datetime = Field(..., alias="windowStart")
    window_end: datetime = Field(..., alias="windowEnd")
    actual_delivered_at: Optional[datetime] = Field(None, alias="actualDeliveredAt")
    checkpoints: List[DeliveryCheckpointDTO] = Field(default_factory=list)


class CreateDeliveryInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    shipment_id: UUID = Field(..., alias="shipmentId")
    route_stage_id: UUID = Field(..., alias="routeStageId")
    delivery_type: str = Field(..., alias="deliveryType")
    window_start: datetime = Field(..., alias="windowStart")
    window_end: datetime = Field(..., alias="windowEnd")
    courier_id: Optional[UUID] = Field(None, alias="courierId")
    status: str = "PENDING_ASSIGNMENT"
    otp_code_hash: str = "seeded_mock_hash"


class AddCheckpointInputDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    delivery_id: UUID = Field(..., alias="deliveryId")
    status: str
    location_name: str = Field(..., alias="locationName")
    notes: Optional[str] = None
    recorded_at: Optional[datetime] = Field(None, alias="recordedAt")
