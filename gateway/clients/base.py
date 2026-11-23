# -*- coding: utf-8 -*-
"""
Protocol interfaces for Gateway clients (future gRPC stubs).
Adheres strictly to Database-per-Service boundaries.
Only interacts with the domain service layer returning Pydantic v2 DTOs.
"""

from typing import Protocol, Optional, List, Dict, Any
from uuid import UUID

from services.common.security import AuthenticatedUser
from services.auth_service.schemas import (
    AuthTokenResponse,
    RegisterRequest,
    LoginRequest,
    VerifyTokenResponse,
    SessionInfoDTO,
)
from services.user_service.schemas import UserDTO
from services.tariff_service.schemas import (
    TariffDTO,
    CalculatePriceInputDTO,
    PriceCalculationResultDTO,
)
from services.courier_service.schemas import (
    CourierDTO,
    CourierFilterDTO,
    CourierSortDTO,
    CourierPerformanceStatsDTO,
)
from services.shipment_service.schemas import (
    ShipmentDTO,
    ShipmentConnectionDTO,
    TrackingTimelineDTO,
    ShipmentFilterDTO,
    ShipmentSortDTO,
    ShipmentStatsDTO,
)
from services.route_service.schemas import RouteDTO, RouteStageDTO
from services.delivery_service.schemas import DeliveryDTO, DeliveryCheckpointDTO
from services.analytics_service.schemas import (
    AnalyticsSummaryDTO,
    DateRangeInputDTO,
    ShipmentStreamEventDTO,
    DailyDeliveryStatsDTO,
)


class AuthClientProtocol(Protocol):
    def register(self, data: RegisterRequest) -> AuthTokenResponse:
        ...

    def login(self, data: LoginRequest) -> AuthTokenResponse:
        ...

    def verify_token(self, token: str) -> VerifyTokenResponse:
        ...

    def logout(self, token: str) -> bool:
        ...

    def refresh(self, refresh_token: str) -> AuthTokenResponse:
        ...

    def get_session(self, session_id: str) -> Optional[SessionInfoDTO]:
        ...


class UserClientProtocol(Protocol):
    def get_user_by_id(self, user_id: UUID | str) -> Optional[UserDTO]:
        ...

    def get_user_by_email(self, email: str) -> Optional[UserDTO]:
        ...

    def get_current_user(self) -> Optional[UserDTO]:
        ...

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserDTO]:
        ...


class TariffClientProtocol(Protocol):
    def get_tariff_by_id(self, tariff_id: UUID | str) -> Optional[TariffDTO]:
        ...

    def list_active_tariffs(self) -> List[TariffDTO]:
        ...

    def calculate_price(self, data: CalculatePriceInputDTO) -> PriceCalculationResultDTO:
        ...


class CourierClientProtocol(Protocol):
    def get_courier_by_id(self, courier_id: UUID | str) -> Optional[CourierDTO]:
        ...

    def get_courier_by_user_id(self, user_id: UUID | str) -> Optional[CourierDTO]:
        ...

    def list_couriers(self, status: Optional[str] = None) -> List[CourierDTO]:
        ...

    def filter_and_sort_couriers(
        self,
        filter_dto: Optional[CourierFilterDTO] = None,
        sort_dto: Optional[CourierSortDTO] = None,
    ) -> List[CourierDTO]:
        ...

    def check_availability(self, courier_id: UUID | str, weight_kg: float) -> Dict[str, Any]:
        ...

    def update_status(self, courier_id: UUID | str, status: str) -> CourierDTO:
        ...

    def update_location(self, courier_id: UUID | str, lat: float, lon: float) -> bool:
        ...

    def get_performance_stats(self) -> CourierPerformanceStatsDTO:
        ...


class ShipmentClientProtocol(Protocol):
    def get_shipment_by_id(self, shipment_id: UUID | str) -> Optional[ShipmentDTO]:
        ...

    def get_by_tracking_number(self, tracking_number: str) -> Optional[ShipmentDTO]:
        ...

    def list_shipments_by_client(
        self, client_id: UUID | str, limit: int = 50, offset: int = 0
    ) -> List[ShipmentDTO]:
        ...

    def get_client_shipments(
        self, client_id: UUID | str, limit: int = 50, offset: int = 0
    ) -> ShipmentConnectionDTO:
        ...

    def filter_and_sort_shipments(
        self,
        filter_dto: Optional[ShipmentFilterDTO] = None,
        sort_dto: Optional[ShipmentSortDTO] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ShipmentConnectionDTO:
        ...

    def get_shipment_stats(
        self, filter_dto: Optional[ShipmentFilterDTO] = None
    ) -> ShipmentStatsDTO:
        ...

    def get_tracking_timeline(self, tracking_number: str) -> Optional[TrackingTimelineDTO]:
        ...

    def create_shipment(self, input_data: dict) -> ShipmentDTO:
        ...

    def cancel_shipment(self, tracking_number: str, reason: Optional[str] = None) -> bool:
        ...


class RouteClientProtocol(Protocol):
    def get_route_by_id(self, route_id: UUID | str) -> Optional[RouteDTO]:
        ...

    def get_route_by_shipment_id(self, shipment_id: UUID | str) -> Optional[RouteDTO]:
        ...

    def get_stages_by_route_id(self, route_id: UUID | str) -> List[RouteStageDTO]:
        ...


class DeliveryClientProtocol(Protocol):
    def get_delivery_by_id(self, delivery_id: UUID | str) -> Optional[DeliveryDTO]:
        ...

    def get_active_delivery_by_shipment_id(
        self, shipment_id: UUID | str
    ) -> Optional[DeliveryDTO]:
        ...

    def get_deliveries_by_courier(
        self, courier_id: UUID | str, status: Optional[str] = None
    ) -> List[DeliveryDTO]:
        ...

    def get_checkpoints_by_delivery_id(
        self, delivery_id: UUID | str
    ) -> List[DeliveryCheckpointDTO]:
        ...

    def get_checkpoints_for_shipment(
        self, shipment_id: UUID | str
    ) -> List[DeliveryCheckpointDTO]:
        ...

    def assign_courier(
        self, delivery_id: UUID | str, courier_id: UUID | str
    ) -> DeliveryDTO:
        ...

    def update_checkpoint(
        self, delivery_id: UUID | str, status: str, location_name: str, notes: Optional[str] = None
    ) -> DeliveryCheckpointDTO:
        ...

    def verify_and_complete_delivery(
        self, delivery_id: UUID | str, plain_otp_code: str
    ) -> DeliveryDTO:
        ...


class AnalyticsClientProtocol(Protocol):
    def get_analytics_summary(self, range_dto: DateRangeInputDTO) -> AnalyticsSummaryDTO:
        ...

    def list_stream_events(
        self,
        event_type: Optional[str] = None,
        shipment_id: Optional[UUID | str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ShipmentStreamEventDTO]:
        ...

    def get_daily_stats(
        self, start_date: Any, end_date: Any
    ) -> List[DailyDeliveryStatsDTO]:
        ...
