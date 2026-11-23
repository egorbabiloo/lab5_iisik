# -*- coding: utf-8 -*-
"""
ShipmentClient: in-process client invoking ShipmentService, DeliveryService, and CourierService.
Orchestrates business actions across mock services adhering to clean boundaries.
"""

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Any
from uuid import UUID

from services.shipment_service.service import ShipmentService
from services.delivery_service.service import DeliveryService
from services.courier_service.service import CourierService
from services.tariff_service.service import TariffService
from services.route_service.service import RouteService
from services.user_service.service import UserService
from services.shipment_service.schemas import (
    ShipmentDTO,
    ShipmentConnectionDTO,
    TrackingTimelineDTO,
    TrackingEventDTO,
    CreateShipmentInputDTO,
    ShipmentFilterDTO,
    ShipmentSortDTO,
    ShipmentStatsDTO,
)
from services.route_service.schemas import CreateRouteInputDTO, CreateRouteStageInputDTO
from services.delivery_service.schemas import CreateDeliveryInputDTO
from services.tariff_service.schemas import CalculatePriceInputDTO
from services.common.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
    ValidationError,
)
from services.common.security import (
    AuthenticatedUser,
    ROLE_ADMIN,
    ROLE_CLIENT,
    ROLE_COURIER,
    require_authenticated,
    require_roles,
)
from gateway.clients.base import ShipmentClientProtocol


class ShipmentClient(ShipmentClientProtocol):
    def __init__(
        self,
        shipment_service: Optional[ShipmentService] = None,
        delivery_service: Optional[DeliveryService] = None,
        courier_service: Optional[CourierService] = None,
        tariff_service: Optional[TariffService] = None,
        route_service: Optional[RouteService] = None,
        user_service: Optional[UserService] = None,
    ) -> None:
        self._shipment_service = shipment_service or ShipmentService()
        self._delivery_service = delivery_service or DeliveryService()
        self._courier_service = courier_service or CourierService()
        self._tariff_service = tariff_service or TariffService()
        self._route_service = route_service or RouteService()
        self._user_service = user_service or UserService()

    def _authorize_shipment_access(self, shipment: ShipmentDTO, actor: Optional[AuthenticatedUser]) -> None:
        if actor is None:
            return
        require_authenticated(actor)
        if actor.role == ROLE_ADMIN:
            return
        if actor.role == ROLE_CLIENT:
            if shipment.client_id != actor.user_id:
                raise AuthorizationError(
                    f"Access denied: client '{actor.email}' cannot access shipment '{shipment.tracking_number}'"
                )
            return
        if actor.role == ROLE_COURIER:
            courier = self._courier_service.get_by_user_id(actor.user_id)
            active_delivery = self._delivery_service.get_active_by_shipment_id(shipment.id)
            if not courier or not active_delivery or active_delivery.courier_id != courier.id:
                raise AuthorizationError(
                    f"Access denied: shipment '{shipment.tracking_number}' is not assigned to courier '{actor.email}'"
                )
            return
        raise AuthorizationError(f"Access denied for role '{actor.role}'")

    def get_shipment_by_id(
        self, shipment_id: UUID | str, actor: Optional[AuthenticatedUser] = None
    ) -> Optional[ShipmentDTO]:
        shipment = self._shipment_service.get_by_id(shipment_id)
        if shipment and actor is not None:
            self._authorize_shipment_access(shipment, actor)
        return shipment

    def get_by_tracking_number(
        self, tracking_number: str, actor: Optional[AuthenticatedUser] = None
    ) -> Optional[ShipmentDTO]:
        clean_num = (tracking_number or "").strip()
        if not clean_num:
            return None
        shipment = self._shipment_service.get_by_tracking_number(clean_num)
        if shipment and actor is not None:
            self._authorize_shipment_access(shipment, actor)
        return shipment

    def list_shipments_by_client(
        self, client_id: UUID | str, limit: int = 50, offset: int = 0
    ) -> List[ShipmentDTO]:
        return self._shipment_service.list_by_client_id(client_id, limit=limit, offset=offset)

    def get_client_shipments(
        self, client_id: UUID | str, limit: int = 50, offset: int = 0
    ) -> ShipmentConnectionDTO:
        return self._shipment_service.get_client_shipments(client_id, limit=limit, offset=offset)

    def filter_and_sort_shipments(
        self,
        filter_dto: Optional[ShipmentFilterDTO] = None,
        sort_dto: Optional[ShipmentSortDTO] = None,
        limit: int = 50,
        offset: int = 0,
        actor: Optional[AuthenticatedUser] = None,
    ) -> ShipmentConnectionDTO:
        return self._shipment_service.filter_and_sort_shipments(
            filter_dto=filter_dto, sort_dto=sort_dto, limit=limit, offset=offset, actor=actor
        )

    def get_shipment_stats(
        self,
        filter_dto: Optional[ShipmentFilterDTO] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> ShipmentStatsDTO:
        return self._shipment_service.get_shipment_stats(filter_dto=filter_dto, actor=actor)

    def get_tracking_timeline(
        self, tracking_number: str, actor: Optional[AuthenticatedUser] = None
    ) -> Optional[TrackingTimelineDTO]:
        clean_num = (tracking_number or "").strip()
        if not clean_num:
            return None

        shipment = self._shipment_service.get_by_tracking_number(clean_num)
        if not shipment:
            return None

        if actor is not None:
            self._authorize_shipment_access(shipment, actor)

        courier_lat: Optional[float] = None
        courier_lon: Optional[float] = None
        active_delivery = self._delivery_service.get_active_by_shipment_id(shipment.id)
        if active_delivery and active_delivery.courier_id:
            courier = self._courier_service.get_by_id(active_delivery.courier_id)
            if courier:
                courier_lat = float(courier.current_lat) if courier.current_lat is not None else None
                courier_lon = float(courier.current_lon) if courier.current_lon is not None else None

        checkpoints = self._delivery_service.get_checkpoints_for_shipment(shipment.id)
        events: List[TrackingEventDTO] = [
            TrackingEventDTO(
                timestamp=cp.recorded_at,
                status=cp.status,
                location_name=cp.location_name,
                description=cp.notes,
            )
            for cp in checkpoints
        ]

        if not events:
            history = self._shipment_service.get_status_history(shipment.id)
            for h in history:
                events.append(
                    TrackingEventDTO(
                        timestamp=h.changed_at,
                        status=h.status,
                        location_name=shipment.origin_city,
                        description=h.comment,
                    )
                )

        events.sort(key=lambda ev: ev.timestamp)

        return TrackingTimelineDTO(
            tracking_number=shipment.tracking_number,
            status=shipment.current_status,
            origin_city=shipment.origin_city,
            dest_city=shipment.dest_city,
            courier_lat=courier_lat,
            courier_lon=courier_lon,
            events=events,
        )

    def cancel_shipment(
        self,
        tracking_number: str,
        reason: Optional[str] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> bool:
        """
        Business operation: Cancels shipment and orchestrates release of courier and cancellation of delivery.
        """
        shipment = self._shipment_service.get_by_tracking_number(tracking_number)
        if not shipment:
            raise EntityNotFoundError(f"Shipment with tracking number '{tracking_number}' not found")

        # Invariant & RBAC checks in ShipmentService will reject unauthorized or invalid-state cancellations
        self._shipment_service.cancel_shipment(tracking_number, reason=reason, actor=actor)

        # Synchronize Delivery Service & Courier Service
        active_delivery = self._delivery_service.get_active_by_shipment_id(shipment.id)
        if active_delivery:
            # Free assigned courier back to AVAILABLE
            if active_delivery.courier_id:
                try:
                    self._courier_service.update_status(active_delivery.courier_id, "AVAILABLE")
                except Exception:
                    pass
            # Mark delivery as FAILED / cancelled
            self._delivery_service.update_delivery_status(active_delivery.id, "FAILED")

        return True

    def create_shipment(
        self, input_data: dict, actor: Optional[AuthenticatedUser] = None
    ) -> ShipmentDTO:
        """
        Business operation: Registers a new shipment, calculates price from tariff,
        generates tracking number, and initializes delivery and route structures.
        """
        if actor is not None:
            require_roles(actor, [ROLE_CLIENT, ROLE_ADMIN], "createShipment")

        tariff_id = input_data.get("tariff_id") or input_data.get("tariffId")
        if not tariff_id:
            raise ValidationError("tariffId is required")

        tariff = self._tariff_service.get_by_id(tariff_id)
        if not tariff:
            raise EntityNotFoundError(f"Tariff with id '{tariff_id}' not found")

        weight_kg = float(input_data.get("weight_kg") or input_data.get("weightKg", 1.0))
        if weight_kg <= 0:
            raise ValidationError("Parcel weight must be strictly positive")

        dims = input_data.get("dimensions", {})
        length_cm = float(dims.get("length_cm") or dims.get("lengthCm", 10.0))
        width_cm = float(dims.get("width_cm") or dims.get("widthCm", 10.0))
        height_cm = float(dims.get("height_cm") or dims.get("heightCm", 10.0))
        if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
            raise ValidationError("Parcel dimensions must be strictly positive")

        origin_city = input_data.get("origin_city") or input_data.get("originCity", "Минск")
        origin_address = input_data.get("origin_address") or input_data.get("originAddress", "ул. Ленина, 1")
        dest_city = input_data.get("dest_city") or input_data.get("destCity", "Брест")
        dest_address = input_data.get("dest_address") or input_data.get("destAddress", "ул. Советская, 10")
        recipient_name = input_data.get("recipient_name") or input_data.get("recipientName", "Получатель")
        recipient_phone = input_data.get("recipient_phone") or input_data.get("recipientPhone", "+375291234567")

        # Resolve client strictly from verified actor identity when provided
        if actor is not None:
            client_id = actor.user_id
        else:
            curr_user = self._user_service.get_current_user()
            client_id = curr_user.id if curr_user else uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")

        # Estimate distance and calculate exact price via TariffService
        est_distance = 350.0 if origin_city.lower() != dest_city.lower() else 25.0
        calc_dto = CalculatePriceInputDTO(
            tariff_id=tariff.id,
            origin_city=origin_city,
            dest_city=dest_city,
            distance_km=est_distance,
            weight_kg=weight_kg,
        )
        calc_res = self._tariff_service.calculate_price(calc_dto)
        calculated_price = calc_res.total_price

        # Unique tracking number
        tracking_number = f"PKG-BY-2026-{uuid.uuid4().hex[:6].upper()}"

        create_dto = CreateShipmentInputDTO(
            client_id=client_id,
            tariff_id=tariff.id,
            weight_kg=weight_kg,
            length_cm=length_cm,
            width_cm=width_cm,
            height_cm=height_cm,
            calculated_price=calculated_price,
            origin_city=origin_city,
            origin_address=origin_address,
            origin_lat=input_data.get("origin_lat") or input_data.get("originLat", 53.9006),
            origin_lon=input_data.get("origin_lon") or input_data.get("originLon", 27.5590),
            dest_city=dest_city,
            dest_address=dest_address,
            dest_lat=input_data.get("dest_lat") or input_data.get("destLat", 52.0976),
            dest_lon=input_data.get("dest_lon") or input_data.get("destLon", 23.7341),
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
        )

        shipment = self._shipment_service.create_shipment(create_dto, tracking_number=tracking_number)

        # Initialize Route
        now = datetime.now(timezone.utc)
        route_dto = CreateRouteInputDTO(
            shipment_id=shipment.id,
            total_distance_km=Decimal(str(est_distance)),
            estimated_duration_min=int(est_distance * 1.2),
            current_stage_order=1,
            status="ACTIVE",
        )
        route = self._route_service.create_route(route_dto)

        # Add initial RouteStage
        stage_dto = CreateRouteStageInputDTO(
            route_id=route.id,
            stage_order=1,
            stage_type="PICKUP",
            origin_point=f"{origin_city}, {origin_address}",
            dest_point=f"Хаб {origin_city}",
            planned_start=now + timedelta(minutes=30),
            planned_end=now + timedelta(hours=2),
            status="PENDING",
        )
        stage = self._route_service.add_route_stage(stage_dto)

        # Initialize Delivery with OTP code
        # Default security code 123456
        default_otp = "123456"
        otp_hash = hashlib.sha256(default_otp.encode("utf-8")).hexdigest()
        deliv_dto = CreateDeliveryInputDTO(
            shipment_id=shipment.id,
            route_stage_id=stage.id,
            delivery_type="FIRST_MILE_PICKUP",
            status="PENDING_ASSIGNMENT",
            window_start=stage.planned_start,
            window_end=stage.planned_end,
            otp_code_hash=otp_hash,
        )
        self._delivery_service.create_delivery(deliv_dto)

        return shipment
