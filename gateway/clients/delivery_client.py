# -*- coding: utf-8 -*-
"""
DeliveryClient: in-process client invoking DeliveryService, CourierService, and ShipmentService.
Coordinates cross-service business flows for dispatch, assignment, tracking checkpoints, and completion.
"""

from typing import Optional, List
from uuid import UUID

from services.delivery_service.service import DeliveryService
from services.courier_service.service import CourierService
from services.shipment_service.service import ShipmentService
from services.delivery_service.schemas import (
    DeliveryDTO,
    DeliveryCheckpointDTO,
    AddCheckpointInputDTO,
)
from services.common.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
    CourierBusyError,
    PayloadCapacityExceededError,
)
from services.common.security import (
    AuthenticatedUser,
    ROLE_ADMIN,
    ROLE_COURIER,
    require_roles,
)
from gateway.clients.base import DeliveryClientProtocol


class DeliveryClient(DeliveryClientProtocol):
    def __init__(
        self,
        delivery_service: Optional[DeliveryService] = None,
        courier_service: Optional[CourierService] = None,
        shipment_service: Optional[ShipmentService] = None,
    ) -> None:
        self._delivery_service = delivery_service or DeliveryService()
        self._courier_service = courier_service or CourierService()
        self._shipment_service = shipment_service or ShipmentService()

    def get_delivery_by_id(self, delivery_id: UUID | str) -> Optional[DeliveryDTO]:
        return self._delivery_service.get_by_id(delivery_id)

    def get_active_delivery_by_shipment_id(
        self, shipment_id: UUID | str
    ) -> Optional[DeliveryDTO]:
        return self._delivery_service.get_active_by_shipment_id(shipment_id)

    def _verify_courier_ownership(
        self, delivery_courier_id: Optional[UUID], actor: Optional[AuthenticatedUser], operation: str
    ) -> None:
        if actor is None:
            return
        require_roles(actor, [ROLE_COURIER, ROLE_ADMIN], operation)
        if actor.role == ROLE_ADMIN:
            return
        courier = self._courier_service.get_by_user_id(actor.user_id)
        if not courier or delivery_courier_id != courier.id:
            raise AuthorizationError(
                f"Access denied: courier '{actor.email}' cannot execute '{operation}' for another courier's delivery"
            )

    def get_deliveries_by_courier(
        self,
        courier_id: UUID | str,
        status: Optional[str] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> List[DeliveryDTO]:
        if actor is not None:
            require_roles(actor, [ROLE_COURIER, ROLE_ADMIN], "courierDeliveries")
            if actor.role == ROLE_COURIER:
                own_courier = self._courier_service.get_by_user_id(actor.user_id)
                if not own_courier or str(own_courier.id) != str(courier_id):
                    raise AuthorizationError(
                        "Access denied: courier can only inspect their own deliveries"
                    )
        return self._delivery_service.list_by_courier_id(courier_id, status=status)

    def get_checkpoints_by_delivery_id(
        self, delivery_id: UUID | str
    ) -> List[DeliveryCheckpointDTO]:
        return self._delivery_service.get_checkpoints_by_delivery_id(delivery_id)

    def get_checkpoints_for_shipment(
        self, shipment_id: UUID | str
    ) -> List[DeliveryCheckpointDTO]:
        return self._delivery_service.get_checkpoints_for_shipment(shipment_id)

    def assign_courier(
        self,
        delivery_id: UUID | str,
        courier_id: UUID | str,
        actor: Optional[AuthenticatedUser] = None,
    ) -> DeliveryDTO:
        """
        Business operation: Assigns courier to delivery stage with invariant checks:
        1. Actor must hold ROLE_ADMIN (if security context provided).
        2. Courier must exist and be in AVAILABLE status.
        3. Parcel weight must not exceed courier's payload capacity.
        4. Delivery status transitions to ASSIGNED.
        5. Courier transitions to BUSY.
        6. Shipment status transitions to ASSIGNED.
        """
        if actor is not None:
            require_roles(actor, [ROLE_ADMIN], "assignCourier")
        deliv = self._delivery_service.get_by_id(delivery_id)
        if not deliv:
            raise EntityNotFoundError(f"Delivery with id '{delivery_id}' not found")

        courier = self._courier_service.get_by_id(courier_id)
        if not courier:
            raise EntityNotFoundError(f"Courier with id '{courier_id}' not found")

        # Invariant 1: Courier payload capacity check
        shipment = self._shipment_service.get_by_id(deliv.shipment_id)
        if shipment and float(courier.max_payload_kg) < float(shipment.weight_kg):
            raise PayloadCapacityExceededError(
                f"Parcel weight {shipment.weight_kg} kg exceeds courier payload capacity {courier.max_payload_kg} kg"
            )

        # Invariant 2: Courier status check
        if courier.current_status != "AVAILABLE":
            raise CourierBusyError(
                f"Courier '{courier_id}' is currently '{courier.current_status}' and cannot accept deliveries"
            )

        # Perform assignment in DeliveryService
        updated_delivery = self._delivery_service.assign_courier(delivery_id, courier_id)

        # Transition courier status to BUSY
        self._courier_service.update_status(courier_id, "BUSY")

        # Synchronize shipment status to ASSIGNED
        if shipment:
            self._shipment_service.update_shipment_status(
                shipment.id, "ASSIGNED", comment=f"Assigned to courier {courier_id}"
            )

        return updated_delivery

    def update_checkpoint(
        self,
        delivery_id: UUID | str,
        status: str,
        location_name: str,
        notes: Optional[str] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> DeliveryCheckpointDTO:
        """
        Business operation: Logs telemetry checkpoint and updates delivery and shipment status.
        """
        if actor is not None:
            require_roles(actor, [ROLE_COURIER, ROLE_ADMIN], "updateDeliveryCheckpoint")

        deliv = self._delivery_service.get_by_id(delivery_id)
        if not deliv:
            raise EntityNotFoundError(f"Delivery with id '{delivery_id}' not found")

        self._verify_courier_ownership(deliv.courier_id, actor, "updateDeliveryCheckpoint")

        cp_dto = AddCheckpointInputDTO(
            delivery_id=deliv.id,
            status=status.upper().strip(),
            location_name=location_name,
            notes=notes,
        )
        checkpoint = self._delivery_service.add_checkpoint(cp_dto)

        # Synchronize status transitions
        norm_status = status.upper().strip()
        if norm_status in ("PICKED_UP", "IN_TRANSIT"):
            self._delivery_service.update_delivery_status(deliv.id, "PICKED_UP")
            self._shipment_service.update_shipment_status(
                deliv.shipment_id, norm_status, comment=f"Checkpoint recorded at {location_name}"
            )

        return checkpoint

    def verify_and_complete_delivery(
        self,
        delivery_id: UUID | str,
        plain_otp_code: str,
        actor: Optional[AuthenticatedUser] = None,
    ) -> DeliveryDTO:
        """
        Business operation: Verifies recipient code, completes delivery, and frees courier.
        """
        if actor is not None:
            require_roles(actor, [ROLE_COURIER, ROLE_ADMIN], "verifyAndCompleteDelivery")
            deliv = self._delivery_service.get_by_id(delivery_id)
            if not deliv:
                raise EntityNotFoundError(f"Delivery with id '{delivery_id}' not found")
            self._verify_courier_ownership(deliv.courier_id, actor, "verifyAndCompleteDelivery")

        delivery = self._delivery_service.verify_and_complete_delivery(delivery_id, plain_otp_code)

        # Synchronize shipment status to DELIVERED
        self._shipment_service.update_shipment_status(
            delivery.shipment_id, "DELIVERED", comment="Successfully delivered to recipient"
        )

        # Free courier back to AVAILABLE and increment delivery count
        if delivery.courier_id:
            try:
                self._courier_service.update_status(delivery.courier_id, "AVAILABLE")
                self._courier_service.increment_deliveries(delivery.courier_id)
            except Exception:
                pass

        return delivery
