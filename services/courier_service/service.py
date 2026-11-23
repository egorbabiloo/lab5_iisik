"""
Courier Service Domain Business Logic.
Returns decoupled Pydantic v2 DTOs.
"""
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from sqlalchemy.orm import Session
from services.common.database import session_scope
from services.common.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    ValidationError,
    ActiveDeliveriesPreventOfflineError,
    BusinessRuleViolationError,
)
from services.common.security import (
    AuthenticatedUser,
    ROLE_ADMIN,
    ROLE_COURIER,
    require_roles,
)
from services.courier_service.models import Courier
from services.courier_service.repository import CourierRepository
from services.courier_service.schemas import (
    CourierDTO,
    CourierLocationDTO,
    CourierFilterDTO,
    CourierSortDTO,
    CourierPerformanceStatsDTO,
    UpdateCourierStatusInputDTO,
    UpdateCourierLocationInputDTO,
)


class CourierService:
    def __init__(
        self,
        repository_or_session: Optional[Union[CourierRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[CourierRepository] = None,
    ):
        if isinstance(repository_or_session, CourierRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = CourierRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = CourierRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    def _get_repo(self, session: Optional[Session] = None) -> CourierRepository:
        if session is not None:
            return CourierRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return CourierRepository(self._session)
        return CourierRepository()

    def get_by_id(self, courier_id: UUID | str) -> Optional[CourierDTO]:
        if self.repository is not None or self._session is not None:
            courier = self._get_repo().get_by_id(courier_id)
            return CourierDTO.model_validate(courier) if courier else None
        with session_scope("courier_db") as session:
            courier = self._get_repo(session).get_by_id(courier_id)
            return CourierDTO.model_validate(courier) if courier else None

    def get_courier_by_id(self, courier_id: UUID | str) -> Optional[CourierDTO]:
        return self.get_by_id(courier_id)

    def get_by_user_id(self, user_id: UUID | str) -> Optional[CourierDTO]:
        if self.repository is not None or self._session is not None:
            courier = self._get_repo().get_by_user_id(user_id)
            return CourierDTO.model_validate(courier) if courier else None
        with session_scope("courier_db") as session:
            courier = self._get_repo(session).get_by_user_id(user_id)
            return CourierDTO.model_validate(courier) if courier else None

    def get_courier_by_user_id(self, user_id: UUID | str) -> Optional[CourierDTO]:
        return self.get_by_user_id(user_id)

    def list_by_status(self, status: str) -> List[CourierDTO]:
        if self.repository is not None or self._session is not None:
            couriers = self._get_repo().list_by_status(status)
            return [CourierDTO.model_validate(c) for c in couriers]
        with session_scope("courier_db") as session:
            couriers = self._get_repo(session).list_by_status(status)
            return [CourierDTO.model_validate(c) for c in couriers]

    def list_all(self, skip: int = 0, limit: int = 100) -> List[CourierDTO]:
        if self.repository is not None or self._session is not None:
            couriers = self._get_repo().list_all(skip=skip, limit=limit)
            return [CourierDTO.model_validate(c) for c in couriers]
        with session_scope("courier_db") as session:
            couriers = self._get_repo(session).list_all(skip=skip, limit=limit)
            return [CourierDTO.model_validate(c) for c in couriers]

    def list_couriers(self, skip: int = 0, limit: int = 100) -> List[CourierDTO]:
        return self.list_all(skip=skip, limit=limit)

    def filter_and_sort_couriers(
        self,
        filter_dto: Optional[CourierFilterDTO] = None,
        sort_dto: Optional[CourierSortDTO] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> List[CourierDTO]:
        if actor is not None:
            require_roles(actor, [ROLE_ADMIN], "couriers")
        if self.repository is not None or self._session is not None:
            couriers = self._get_repo().filter_and_sort(filter_dto=filter_dto, sort_dto=sort_dto)
            return [CourierDTO.model_validate(c) for c in couriers]
        with session_scope("courier_db") as session:
            couriers = self._get_repo(session).filter_and_sort(filter_dto=filter_dto, sort_dto=sort_dto)
            return [CourierDTO.model_validate(c) for c in couriers]

    def get_location(self, courier_id: UUID | str) -> Optional[CourierLocationDTO]:
        def _to_location(courier: Optional[Courier]) -> Optional[CourierLocationDTO]:
            if not courier:
                return None
            return CourierLocationDTO(
                courier_id=courier.id,
                latitude=float(courier.current_lat) if courier.current_lat is not None else None,
                longitude=float(courier.current_lon) if courier.current_lon is not None else None,
            )

        if self.repository is not None or self._session is not None:
            courier = self._get_repo().get_by_id(courier_id)
            return _to_location(courier)
        with session_scope("courier_db") as session:
            courier = self._get_repo(session).get_by_id(courier_id)
            return _to_location(courier)

    def update_status(
        self,
        courier_id: UUID | str,
        status: str,
        actor: Optional[AuthenticatedUser] = None,
    ) -> CourierDTO:
        if actor is not None:
            require_roles(actor, [ROLE_COURIER, ROLE_ADMIN], "updateCourierStatus")

        norm_status = status.upper().strip()
        if norm_status not in ("AVAILABLE", "BUSY", "OFFLINE"):
            raise ValidationError(f"Invalid courier status: '{status}'")

        def _update(repo: CourierRepository) -> CourierDTO:
            existing = repo.get_by_id(courier_id)
            if not existing:
                raise EntityNotFoundError(f"Courier with id '{courier_id}' not found")

            if actor is not None and actor.role == ROLE_COURIER and existing.user_id != actor.user_id:
                raise AuthorizationError(
                    "Access denied: courier can only update their own status"
                )

            if norm_status == "OFFLINE" and existing.current_status == "BUSY":
                raise ActiveDeliveriesPreventOfflineError(
                    f"Courier '{courier_id}' currently has active delivery tasks (BUSY) and cannot go OFFLINE."
                )

            courier = repo.update_status(courier_id, norm_status)
            return CourierDTO.model_validate(courier)

        if self.repository is not None or self._session is not None:
            return _update(self._get_repo())
        with session_scope("courier_db") as session:
            return _update(self._get_repo(session))

    def update_location(
        self,
        courier_id: UUID | str,
        lat: float,
        lon: float,
        actor: Optional[AuthenticatedUser] = None,
    ) -> bool:
        if actor is not None:
            require_roles(actor, [ROLE_COURIER, ROLE_ADMIN], "updateCourierLocation")

        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise ValidationError(f"Invalid coordinates: lat={lat}, lon={lon}")

        def _update(repo: CourierRepository) -> bool:
            existing = repo.get_by_id(courier_id)
            if not existing:
                raise EntityNotFoundError(f"Courier with id '{courier_id}' not found")
            if actor is not None and actor.role == ROLE_COURIER and existing.user_id != actor.user_id:
                raise AuthorizationError(
                    "Access denied: courier can only update their own location"
                )
            repo.update_location(courier_id, lat, lon)
            return True

        if self.repository is not None or self._session is not None:
            return _update(self._get_repo())
        with session_scope("courier_db") as session:
            return _update(self._get_repo(session))

    def increment_deliveries(self, courier_id: UUID | str) -> CourierDTO:
        def _inc(repo: CourierRepository) -> CourierDTO:
            courier = repo.increment_deliveries(courier_id)
            if not courier:
                raise EntityNotFoundError(f"Courier with id '{courier_id}' not found")
            return CourierDTO.model_validate(courier)

        if self.repository is not None or self._session is not None:
            return _inc(self._get_repo())
        with session_scope("courier_db") as session:
            return _inc(self._get_repo(session))

    def get_performance_stats(
        self, actor: Optional[AuthenticatedUser] = None
    ) -> CourierPerformanceStatsDTO:
        if actor is not None:
            require_roles(actor, [ROLE_ADMIN], "courierPerformanceStats")
        def _stats(repo: CourierRepository) -> CourierPerformanceStatsDTO:
            raw = repo.aggregate_performance_stats()
            top = CourierDTO.model_validate(raw["top_performer"]) if raw.get("top_performer") else None
            return CourierPerformanceStatsDTO(
                total_couriers=raw["total_couriers"],
                available_couriers=raw["available_couriers"],
                busy_couriers=raw["busy_couriers"],
                offline_couriers=raw["offline_couriers"],
                average_rating=raw["average_rating"],
                total_delivered_count=raw["total_delivered_count"],
                top_performer=top,
            )

        if self.repository is not None or self._session is not None:
            return _stats(self._get_repo())
        with session_scope("courier_db") as session:
            return _stats(self._get_repo(session))

    def check_availability(self, courier_id: UUID | str, parcel_weight_kg: float) -> Dict[str, Any]:
        def _check(repo: CourierRepository) -> Dict[str, Any]:
            courier = repo.get_by_id(courier_id)
            if not courier:
                raise EntityNotFoundError(f"Courier with id '{courier_id}' not found")
            is_available = (
                courier.current_status == "AVAILABLE"
                and float(courier.max_payload_kg) >= parcel_weight_kg
            )
            return {
                "courier_id": courier.id,
                "is_available": is_available,
                "current_status": courier.current_status,
                "max_payload_kg": float(courier.max_payload_kg),
            }

        if self.repository is not None or self._session is not None:
            return _check(self._get_repo())
        with session_scope("courier_db") as session:
            return _check(self._get_repo(session))
