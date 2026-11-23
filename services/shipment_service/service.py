"""
Shipment Service implementing business logic and returning Pydantic v2 DTOs.
"""
from typing import Optional, List, Union, Any
from uuid import UUID
import uuid
from sqlalchemy.orm import Session
from services.common.database import session_scope
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
    require_roles,
)
from services.shipment_service.models import Shipment, ShipmentStatusHistory
from services.shipment_service.repository import ShipmentRepository
from services.shipment_service.schemas import (
    ShipmentDTO,
    ShipmentStatusHistoryDTO,
    ShipmentConnectionDTO,
    CreateShipmentInputDTO,
    ShipmentFilterDTO,
    ShipmentSortDTO,
    ShipmentStatsDTO,
    StatusCountDTO,
    CityRevenueStatsDTO,
)


class ShipmentService:
    def __init__(
        self,
        repository_or_session: Optional[Union[ShipmentRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[ShipmentRepository] = None,
    ):
        if isinstance(repository_or_session, ShipmentRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = ShipmentRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = ShipmentRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    def _get_repo(self, session: Optional[Session] = None) -> ShipmentRepository:
        if session is not None:
            return ShipmentRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return ShipmentRepository(self._session)
        return ShipmentRepository()

    def get_by_id(self, shipment_id: UUID | str) -> Optional[ShipmentDTO]:
        if self.repository is not None or self._session is not None:
            model = self._get_repo().get_by_id(shipment_id)
            return ShipmentDTO.model_validate(model) if model else None
        with session_scope("shipment_db") as session:
            model = self._get_repo(session).get_by_id(shipment_id)
            return ShipmentDTO.model_validate(model) if model else None

    def get_shipment_by_id(self, shipment_id: UUID | str) -> Optional[ShipmentDTO]:
        return self.get_by_id(shipment_id)

    def get_by_tracking_number(self, tracking_number: str) -> Optional[ShipmentDTO]:
        clean_num = tracking_number.strip() if tracking_number else ""
        if not clean_num:
            return None
        if self.repository is not None or self._session is not None:
            model = self._get_repo().get_by_tracking_number(clean_num)
            return ShipmentDTO.model_validate(model) if model else None
        with session_scope("shipment_db") as session:
            model = self._get_repo(session).get_by_tracking_number(clean_num)
            return ShipmentDTO.model_validate(model) if model else None

    def get_shipment_by_tracking_number(self, tracking_number: str) -> Optional[ShipmentDTO]:
        return self.get_by_tracking_number(tracking_number)

    def list_by_client_id(self, client_id: UUID | str, limit: int = 50, offset: int = 0) -> List[ShipmentDTO]:
        if self.repository is not None or self._session is not None:
            items, _ = self._get_repo().list_by_client(client_id=client_id, limit=limit, offset=offset)
            return [ShipmentDTO.model_validate(s) for s in items]
        with session_scope("shipment_db") as session:
            items, _ = self._get_repo(session).list_by_client(client_id=client_id, limit=limit, offset=offset)
            return [ShipmentDTO.model_validate(s) for s in items]

    def get_client_shipments(self, client_id: UUID | str, limit: int = 50, offset: int = 0) -> ShipmentConnectionDTO:
        if self.repository is not None or self._session is not None:
            items, total = self._get_repo().list_by_client(client_id=client_id, limit=limit, offset=offset)
            return ShipmentConnectionDTO(
                items=[ShipmentDTO.model_validate(s) for s in items],
                total_count=total,
            )
        with session_scope("shipment_db") as session:
            items, total = self._get_repo(session).list_by_client(client_id=client_id, limit=limit, offset=offset)
            return ShipmentConnectionDTO(
                items=[ShipmentDTO.model_validate(s) for s in items],
                total_count=total,
            )

    def filter_and_sort_shipments(
        self,
        filter_dto: Optional[ShipmentFilterDTO] = None,
        sort_dto: Optional[ShipmentSortDTO] = None,
        limit: int = 50,
        offset: int = 0,
        actor: Optional[AuthenticatedUser] = None,
    ) -> ShipmentConnectionDTO:
        """Query shipments with rich multi-criteria filtering, sorting, and pagination."""
        if actor is not None:
            require_roles(actor, [ROLE_ADMIN], "shipments")
        if self.repository is not None or self._session is not None:
            items, total = self._get_repo().filter_and_sort(
                filter_dto=filter_dto, sort_dto=sort_dto, limit=limit, offset=offset
            )
            return ShipmentConnectionDTO(
                items=[ShipmentDTO.model_validate(s) for s in items],
                total_count=total,
            )
        with session_scope("shipment_db") as session:
            items, total = self._get_repo(session).filter_and_sort(
                filter_dto=filter_dto, sort_dto=sort_dto, limit=limit, offset=offset
            )
            return ShipmentConnectionDTO(
                items=[ShipmentDTO.model_validate(s) for s in items],
                total_count=total,
            )

    def get_shipment_stats(
        self,
        filter_dto: Optional[ShipmentFilterDTO] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> ShipmentStatsDTO:
        """Calculates aggregated KPIs: count, sum, average, min, max, and breakdown distributions."""
        if actor is not None:
            require_roles(actor, [ROLE_ADMIN], "shipmentStats")
        if self.repository is not None or self._session is not None:
            data = self._get_repo().aggregate_stats(filter_dto)
            return ShipmentStatsDTO.model_validate(data)
        with session_scope("shipment_db") as session:
            data = self._get_repo(session).aggregate_stats(filter_dto)
            return ShipmentStatsDTO.model_validate(data)

    def get_status_history(self, shipment_id: UUID | str) -> List[ShipmentStatusHistoryDTO]:
        if self.repository is not None or self._session is not None:
            histories = self._get_repo().get_status_history(shipment_id)
            return [ShipmentStatusHistoryDTO.model_validate(h) for h in histories]
        with session_scope("shipment_db") as session:
            histories = self._get_repo(session).get_status_history(shipment_id)
            return [ShipmentStatusHistoryDTO.model_validate(h) for h in histories]

    def create_shipment(self, data: CreateShipmentInputDTO, tracking_number: Optional[str] = None) -> ShipmentDTO:
        if not tracking_number:
            tracking_number = f"PKG-BY-2026-{uuid.uuid4().hex[:6].upper()}"

        shipment = Shipment(
            tracking_number=tracking_number,
            client_id=data.client_id,
            tariff_id=data.tariff_id,
            weight_kg=data.weight_kg,
            length_cm=data.length_cm,
            width_cm=data.width_cm,
            height_cm=data.height_cm,
            calculated_price=data.calculated_price,
            current_status="CREATED",
            origin_city=data.origin_city,
            origin_address=data.origin_address,
            origin_lat=data.origin_lat,
            origin_lon=data.origin_lon,
            dest_city=data.dest_city,
            dest_address=data.dest_address,
            dest_lat=data.dest_lat,
            dest_lon=data.dest_lon,
            recipient_name=data.recipient_name,
            recipient_phone=data.recipient_phone,
        )

        def _save(repo: ShipmentRepository) -> ShipmentDTO:
            saved = repo.create(shipment)
            repo.add_status_history(
                ShipmentStatusHistory(shipment_id=saved.id, status="CREATED", comment="Shipment registered")
            )
            loaded = repo.get_by_id(saved.id)
            return ShipmentDTO.model_validate(loaded)

        if self.repository is not None or self._session is not None:
            return _save(self._get_repo())
        with session_scope("shipment_db") as session:
            return _save(self._get_repo(session))

    def update_shipment_status(
        self, shipment_id: UUID | str, new_status: str, comment: Optional[str] = None
    ) -> Optional[ShipmentDTO]:
        if self.repository is not None or self._session is not None:
            updated = self._get_repo().update_status(shipment_id, new_status, comment)
            return ShipmentDTO.model_validate(updated) if updated else None
        with session_scope("shipment_db") as session:
            updated = self._get_repo(session).update_status(shipment_id, new_status, comment)
            return ShipmentDTO.model_validate(updated) if updated else None

    def cancel_shipment(
        self,
        tracking_number: str,
        reason: Optional[str] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> ShipmentDTO:
        """
        Business operation: Cancels a shipment if lifecycle invariants and RBAC allow it.
        Rules:
        - Allowed roles: ROLE_CLIENT (own shipments only), ROLE_ADMIN (any shipment).
        - Allowed statuses: CREATED, ASSIGNED.
        - Forbidden statuses: PICKED_UP, IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED, CANCELLED.
        """
        if actor is not None:
            require_roles(actor, [ROLE_CLIENT, ROLE_ADMIN], "cancelShipment")

        clean_num = tracking_number.strip() if tracking_number else ""
        if not clean_num:
            raise ValidationError("trackingNumber is required")

        shipment = self.get_by_tracking_number(clean_num)
        if not shipment:
            raise EntityNotFoundError(f"Shipment with tracking number '{clean_num}' not found")

        if actor is not None and actor.role == ROLE_CLIENT and shipment.client_id != actor.user_id:
            raise AuthorizationError(
                f"Access denied: client '{actor.email}' cannot cancel shipment '{clean_num}' owned by another user"
            )

        current = shipment.current_status
        if current == "CANCELLED":
            raise BusinessRuleViolationError(
                f"Shipment '{clean_num}' is already in CANCELLED status"
            )

        if current in ("PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"):
            raise BusinessRuleViolationError(
                f"Cannot cancel shipment '{clean_num}' with status '{current}'. "
                f"Shipment is already dispatched, in transit, or delivered."
            )

        if current not in ("CREATED", "ASSIGNED"):
            raise BusinessRuleViolationError(
                f"Shipment '{clean_num}' with status '{current}' cannot be cancelled."
            )

        comment = reason or "Cancelled by user/dispatcher request"
        updated = self.update_shipment_status(shipment.id, "CANCELLED", comment=comment)
        if not updated:
            raise BusinessRuleViolationError(f"Failed to cancel shipment '{clean_num}'")
        return updated
