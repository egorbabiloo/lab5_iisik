"""
Delivery Service implementing business logic and returning Pydantic v2 DTOs.
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Union
from uuid import UUID
from sqlalchemy.orm import Session
from services.common.database import session_scope
from services.common.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessRuleViolationError,
    InvalidOtpCodeError,
)
from services.delivery_service.models import Delivery, DeliveryCheckpoint
from services.delivery_service.repository import DeliveryRepository
from services.delivery_service.schemas import (
    DeliveryDTO,
    DeliveryCheckpointDTO,
    CreateDeliveryInputDTO,
    AddCheckpointInputDTO,
)


class DeliveryService:
    def __init__(
        self,
        repository_or_session: Optional[Union[DeliveryRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[DeliveryRepository] = None,
    ):
        if isinstance(repository_or_session, DeliveryRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = DeliveryRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = DeliveryRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    def _get_repo(self, session: Optional[Session] = None) -> DeliveryRepository:
        if session is not None:
            return DeliveryRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return DeliveryRepository(self._session)
        return DeliveryRepository()

    def get_by_id(self, delivery_id: UUID | str) -> Optional[DeliveryDTO]:
        if self.repository is not None or self._session is not None:
            model = self._get_repo().get_by_id(delivery_id)
            return DeliveryDTO.model_validate(model) if model else None
        with session_scope("delivery_db") as session:
            model = self._get_repo(session).get_by_id(delivery_id)
            return DeliveryDTO.model_validate(model) if model else None

    def get_delivery_by_id(self, delivery_id: UUID | str) -> Optional[DeliveryDTO]:
        return self.get_by_id(delivery_id)

    def get_active_by_shipment_id(self, shipment_id: UUID | str) -> Optional[DeliveryDTO]:
        if self.repository is not None or self._session is not None:
            model = self._get_repo().get_active_by_shipment_id(shipment_id)
            return DeliveryDTO.model_validate(model) if model else None
        with session_scope("delivery_db") as session:
            model = self._get_repo(session).get_active_by_shipment_id(shipment_id)
            return DeliveryDTO.model_validate(model) if model else None

    def get_active_delivery_by_shipment_id(self, shipment_id: UUID | str) -> Optional[DeliveryDTO]:
        return self.get_active_by_shipment_id(shipment_id)

    def list_by_courier_id(self, courier_id: UUID | str, status: Optional[str] = None) -> List[DeliveryDTO]:
        if self.repository is not None or self._session is not None:
            models = self._get_repo().list_by_courier_id(courier_id, status=status)
            return [DeliveryDTO.model_validate(m) for m in models]
        with session_scope("delivery_db") as session:
            models = self._get_repo(session).list_by_courier_id(courier_id, status=status)
            return [DeliveryDTO.model_validate(m) for m in models]

    def get_deliveries_by_courier(self, courier_id: UUID | str, status: Optional[str] = None) -> List[DeliveryDTO]:
        return self.list_by_courier_id(courier_id, status=status)

    def list_by_shipment_id(self, shipment_id: UUID | str) -> List[DeliveryDTO]:
        if self.repository is not None or self._session is not None:
            models = self._get_repo().list_by_shipment_id(shipment_id)
            return [DeliveryDTO.model_validate(m) for m in models]
        with session_scope("delivery_db") as session:
            models = self._get_repo(session).list_by_shipment_id(shipment_id)
            return [DeliveryDTO.model_validate(m) for m in models]

    def get_deliveries_by_shipment(self, shipment_id: UUID | str) -> List[DeliveryDTO]:
        return self.list_by_shipment_id(shipment_id)

    def get_checkpoints_by_delivery_id(self, delivery_id: UUID | str) -> List[DeliveryCheckpointDTO]:
        if self.repository is not None or self._session is not None:
            cps = self._get_repo().get_checkpoints_by_delivery_id(delivery_id)
            return [DeliveryCheckpointDTO.model_validate(cp) for cp in cps]
        with session_scope("delivery_db") as session:
            cps = self._get_repo(session).get_checkpoints_by_delivery_id(delivery_id)
            return [DeliveryCheckpointDTO.model_validate(cp) for cp in cps]

    def get_checkpoints_for_shipment(self, shipment_id: UUID | str) -> List[DeliveryCheckpointDTO]:
        if self.repository is not None or self._session is not None:
            cps = self._get_repo().get_checkpoints_for_shipment(shipment_id)
            return [DeliveryCheckpointDTO.model_validate(cp) for cp in cps]
        with session_scope("delivery_db") as session:
            cps = self._get_repo(session).get_checkpoints_for_shipment(shipment_id)
            return [DeliveryCheckpointDTO.model_validate(cp) for cp in cps]

    def create_delivery(self, data: CreateDeliveryInputDTO) -> DeliveryDTO:
        delivery = Delivery(
            shipment_id=data.shipment_id,
            route_stage_id=data.route_stage_id,
            courier_id=data.courier_id,
            delivery_type=data.delivery_type,
            status=data.status,
            window_start=data.window_start,
            window_end=data.window_end,
            otp_code_hash=data.otp_code_hash,
        )

        def _save(repo: DeliveryRepository) -> DeliveryDTO:
            saved = repo.create_delivery(delivery)
            loaded = repo.get_by_id(saved.id)
            return DeliveryDTO.model_validate(loaded)

        if self.repository is not None or self._session is not None:
            return _save(self._get_repo())
        with session_scope("delivery_db") as session:
            return _save(self._get_repo(session))

    def add_checkpoint(self, data: AddCheckpointInputDTO) -> DeliveryCheckpointDTO:
        checkpoint = DeliveryCheckpoint(
            delivery_id=data.delivery_id,
            status=data.status,
            location_name=data.location_name,
            notes=data.notes,
        )
        if data.recorded_at:
            checkpoint.recorded_at = data.recorded_at

        def _save(repo: DeliveryRepository) -> DeliveryCheckpointDTO:
            saved = repo.add_checkpoint(checkpoint)
            return DeliveryCheckpointDTO.model_validate(saved)

        if self.repository is not None or self._session is not None:
            return _save(self._get_repo())
        with session_scope("delivery_db") as session:
            return _save(self._get_repo(session))

    def assign_courier(self, delivery_id: UUID | str, courier_id: UUID | str) -> DeliveryDTO:
        def _assign(repo: DeliveryRepository) -> DeliveryDTO:
            deliv = repo.get_by_id(delivery_id)
            if not deliv:
                raise EntityNotFoundError(f"Delivery with id '{delivery_id}' not found")
            if deliv.status in ("DELIVERED", "FAILED"):
                raise BusinessRuleViolationError(
                    f"Cannot assign courier to delivery in finished status '{deliv.status}'"
                )
            updated = repo.assign_courier(delivery_id, courier_id)
            return DeliveryDTO.model_validate(updated)

        if self.repository is not None or self._session is not None:
            return _assign(self._get_repo())
        with session_scope("delivery_db") as session:
            return _assign(self._get_repo(session))

    def update_delivery_status(
        self, delivery_id: UUID | str, new_status: str, actual_delivered_at: Optional[datetime] = None
    ) -> Optional[DeliveryDTO]:
        if self.repository is not None or self._session is not None:
            updated = self._get_repo().update_status(delivery_id, new_status, actual_delivered_at)
            return DeliveryDTO.model_validate(updated) if updated else None
        with session_scope("delivery_db") as session:
            updated = self._get_repo(session).update_status(delivery_id, new_status, actual_delivered_at)
            return DeliveryDTO.model_validate(updated) if updated else None

    def verify_and_complete_delivery(
        self, delivery_id: UUID | str, plain_otp_code: str
    ) -> DeliveryDTO:
        """
        Business operation: Verifies recipient's one-time code and finalizes delivery.
        Rules:
        - Delivery must exist and be in active state (ASSIGNED or PICKED_UP).
        - plain_otp_code must match stored otp_code_hash (SHA-256 or plaintext fallback).
        - Sets actual_delivered_at to current UTC timestamp and status to DELIVERED.
        - Adds completion checkpoint.
        """
        code = plain_otp_code.strip() if plain_otp_code else ""
        if not code:
            raise ValidationError("OTP verification code is required")

        def _complete(repo: DeliveryRepository) -> DeliveryDTO:
            deliv = repo.get_by_id(delivery_id)
            if not deliv:
                raise EntityNotFoundError(f"Delivery with id '{delivery_id}' not found")

            if deliv.status == "DELIVERED":
                raise BusinessRuleViolationError("Delivery has already been completed")

            if deliv.status not in ("ASSIGNED", "PICKED_UP"):
                raise BusinessRuleViolationError(
                    f"Cannot complete delivery in status '{deliv.status}'. Must be ASSIGNED or PICKED_UP."
                )

            # OTP verification
            code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
            if deliv.otp_code_hash != code_hash and deliv.otp_code_hash != code:
                raise InvalidOtpCodeError(
                    f"Invalid delivery OTP verification code for delivery '{delivery_id}'"
                )

            now = datetime.now(timezone.utc)
            updated = repo.update_status(delivery_id, "DELIVERED", actual_delivered_at=now)

            # Add completion checkpoint
            repo.add_checkpoint(
                DeliveryCheckpoint(
                    delivery_id=deliv.id,
                    status="DELIVERED",
                    location_name="Recipient Address",
                    notes="Successfully handed over to recipient via verified OTP code",
                    recorded_at=now,
                )
            )

            loaded = repo.get_by_id(deliv.id)
            return DeliveryDTO.model_validate(loaded)

        if self.repository is not None or self._session is not None:
            return _complete(self._get_repo())
        with session_scope("delivery_db") as session:
            return _complete(self._get_repo(session))

    def cancel_delivery_for_shipment(self, shipment_id: UUID | str) -> Optional[DeliveryDTO]:
        def _cancel(repo: DeliveryRepository) -> Optional[DeliveryDTO]:
            active = repo.get_active_by_shipment_id(shipment_id)
            if not active:
                return None
            updated = repo.update_status(active.id, "FAILED")
            return DeliveryDTO.model_validate(updated) if updated else None

        if self.repository is not None or self._session is not None:
            return _cancel(self._get_repo())
        with session_scope("delivery_db") as session:
            return _cancel(self._get_repo(session))
