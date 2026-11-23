"""
Delivery Repository for database-per-service isolation on delivery_db.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from services.common.database import get_session_for_db
from services.delivery_service.models import Delivery, DeliveryCheckpoint


class DeliveryRepository:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("delivery_db")

    def get_by_id(self, delivery_id: UUID | str) -> Optional[Delivery]:
        if isinstance(delivery_id, str):
            delivery_id = UUID(delivery_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Delivery).where(Delivery.id == delivery_id).options(selectinload(Delivery.checkpoints))
            return sess.scalars(stmt).first()
        finally:
            if should_close:
                sess.close()

    def get_active_by_shipment_id(self, shipment_id: UUID | str) -> Optional[Delivery]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            active_statuses = ["PENDING_ASSIGNMENT", "ASSIGNED", "PICKED_UP"]
            stmt = (
                select(Delivery)
                .where(Delivery.shipment_id == shipment_id, Delivery.status.in_(active_statuses))
                .order_by(Delivery.created_at.desc())
                .options(selectinload(Delivery.checkpoints))
            )
            active = sess.scalars(stmt).first()
            if active:
                return active
            fallback_stmt = (
                select(Delivery)
                .where(Delivery.shipment_id == shipment_id)
                .order_by(Delivery.created_at.desc())
                .options(selectinload(Delivery.checkpoints))
            )
            return sess.scalars(fallback_stmt).first()
        finally:
            if should_close:
                sess.close()

    def list_by_shipment_id(self, shipment_id: UUID | str) -> List[Delivery]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(Delivery)
                .where(Delivery.shipment_id == shipment_id)
                .order_by(Delivery.created_at.asc())
                .options(selectinload(Delivery.checkpoints))
            )
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def list_by_courier_id(self, courier_id: UUID | str, status: Optional[str] = None) -> List[Delivery]:
        if isinstance(courier_id, str):
            courier_id = UUID(courier_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Delivery).where(Delivery.courier_id == courier_id)
            if status:
                stmt = stmt.where(Delivery.status == status.strip())
            stmt = stmt.order_by(Delivery.created_at.desc()).options(selectinload(Delivery.checkpoints))
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def get_checkpoints_by_delivery_id(self, delivery_id: UUID | str) -> List[DeliveryCheckpoint]:
        if isinstance(delivery_id, str):
            delivery_id = UUID(delivery_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(DeliveryCheckpoint)
                .where(DeliveryCheckpoint.delivery_id == delivery_id)
                .order_by(DeliveryCheckpoint.recorded_at.asc())
            )
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def get_checkpoints_for_shipment(self, shipment_id: UUID | str) -> List[DeliveryCheckpoint]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(DeliveryCheckpoint)
                .join(Delivery, DeliveryCheckpoint.delivery_id == Delivery.id)
                .where(Delivery.shipment_id == shipment_id)
                .order_by(DeliveryCheckpoint.recorded_at.asc())
            )
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def create_delivery(self, delivery: Delivery) -> Delivery:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(delivery)
            sess.commit()
            sess.refresh(delivery)
            return delivery
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def add_checkpoint(self, checkpoint: DeliveryCheckpoint) -> DeliveryCheckpoint:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(checkpoint)
            sess.commit()
            sess.refresh(checkpoint)
            return checkpoint
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def update_status(self, delivery_id: UUID | str, new_status: str, actual_delivered_at: Optional[datetime] = None) -> Optional[Delivery]:
        if isinstance(delivery_id, str):
            delivery_id = UUID(delivery_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            delivery = sess.scalars(select(Delivery).where(Delivery.id == delivery_id)).first()
            if not delivery:
                return None
            delivery.status = new_status
            if actual_delivered_at is not None:
                delivery.actual_delivered_at = actual_delivered_at
            sess.commit()
            sess.refresh(delivery)
            return delivery
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def assign_courier(self, delivery_id: UUID | str, courier_id: UUID | str) -> Optional[Delivery]:
        if isinstance(delivery_id, str):
            delivery_id = UUID(delivery_id)
        if isinstance(courier_id, str):
            courier_id = UUID(courier_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            delivery = sess.scalars(select(Delivery).where(Delivery.id == delivery_id)).first()
            if not delivery:
                return None
            delivery.courier_id = courier_id
            delivery.status = "ASSIGNED"
            sess.commit()
            sess.refresh(delivery)
            return delivery
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
