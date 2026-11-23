"""
Courier Service Repository for courier_db.
Strict database isolation: queries only couriers table.
Inter-service user reference is handled as pure scalar UUID (zero cross-DB FK).
"""
from decimal import Decimal
from typing import Optional, List, Any
from uuid import UUID
from sqlalchemy import select, func, case, and_
from sqlalchemy.orm import Session
from services.common.database import get_session_for_db
from services.courier_service.models import Courier


class CourierRepository:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("courier_db")

    def get_by_id(self, courier_id: UUID | str) -> Optional[Courier]:
        if isinstance(courier_id, str):
            courier_id = UUID(courier_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Courier).where(Courier.id == courier_id)
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def get_by_user_id(self, user_id: UUID | str) -> Optional[Courier]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Courier).where(Courier.user_id == user_id)
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def list_by_status(self, status: str) -> List[Courier]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(Courier)
                .where(Courier.current_status == status.upper().strip())
                .order_by(Courier.rating.desc())
            )
            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[Courier]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(Courier)
                .order_by(Courier.rating.desc())
                .offset(skip)
                .limit(limit)
            )
            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def filter_and_sort(
        self, filter_dto: Optional[Any] = None, sort_dto: Optional[Any] = None
    ) -> List[Courier]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Courier)
            conditions = []
            if filter_dto:
                if getattr(filter_dto, "status", None):
                    conditions.append(Courier.current_status == filter_dto.status.upper().strip())
                if getattr(filter_dto, "transport_type", None):
                    conditions.append(Courier.transport_type == filter_dto.transport_type.upper().strip())
                if getattr(filter_dto, "min_payload_kg", None) is not None:
                    conditions.append(Courier.max_payload_kg >= Decimal(str(filter_dto.min_payload_kg)))
                if getattr(filter_dto, "min_rating", None) is not None:
                    conditions.append(Courier.rating >= Decimal(str(filter_dto.min_rating)))

            if conditions:
                stmt = stmt.where(and_(*conditions))

            sort_field = getattr(sort_dto, "field", "RATING") if sort_dto else "RATING"
            direction = getattr(sort_dto, "direction", "DESC") if sort_dto else "DESC"

            field_map = {
                "RATING": Courier.rating,
                "TOTAL_DELIVERIES": Courier.total_deliveries,
                "MAX_PAYLOAD_KG": Courier.max_payload_kg,
            }
            order_col = field_map.get(sort_field, Courier.rating)
            stmt = stmt.order_by(order_col.asc() if str(direction).upper() == "ASC" else order_col.desc())

            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def update_status(self, courier_id: UUID | str, status: str) -> Optional[Courier]:
        if isinstance(courier_id, str):
            courier_id = UUID(courier_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            courier = sess.execute(select(Courier).where(Courier.id == courier_id)).scalar_one_or_none()
            if courier:
                courier.current_status = status.upper().strip()
                sess.commit()
                sess.refresh(courier)
            return courier
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def update_location(self, courier_id: UUID | str, lat: float, lon: float) -> Optional[Courier]:
        if isinstance(courier_id, str):
            courier_id = UUID(courier_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            courier = sess.execute(select(Courier).where(Courier.id == courier_id)).scalar_one_or_none()
            if courier:
                courier.current_lat = Decimal(str(lat))
                courier.current_lon = Decimal(str(lon))
                sess.commit()
                sess.refresh(courier)
            return courier
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def increment_deliveries(self, courier_id: UUID | str) -> Optional[Courier]:
        if isinstance(courier_id, str):
            courier_id = UUID(courier_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            courier = sess.execute(select(Courier).where(Courier.id == courier_id)).scalar_one_or_none()
            if courier:
                courier.total_deliveries += 1
                sess.commit()
                sess.refresh(courier)
            return courier
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def aggregate_performance_stats(self) -> dict:
        sess = self._get_session()
        should_close = self._session is None
        try:
            total_stmt = select(
                func.count(Courier.id).label("total_couriers"),
                func.count(case((Courier.current_status == 'AVAILABLE', 1))).label("available_couriers"),
                func.count(case((Courier.current_status == 'BUSY', 1))).label("busy_couriers"),
                func.count(case((Courier.current_status == 'OFFLINE', 1))).label("offline_couriers"),
                func.coalesce(func.avg(Courier.rating), 0).label("average_rating"),
                func.coalesce(func.sum(Courier.total_deliveries), 0).label("total_delivered_count"),
            )
            row = sess.execute(total_stmt).one()

            # Top performer
            top_stmt = select(Courier).order_by(Courier.total_deliveries.desc(), Courier.rating.desc()).limit(1)
            top = sess.execute(top_stmt).scalar_one_or_none()

            return {
                "total_couriers": int(row.total_couriers),
                "available_couriers": int(row.available_couriers),
                "busy_couriers": int(row.busy_couriers),
                "offline_couriers": int(row.offline_couriers),
                "average_rating": float(round(row.average_rating, 2)),
                "total_delivered_count": int(row.total_delivered_count),
                "top_performer": top,
            }
        finally:
            if should_close:
                sess.close()

    def create(self, courier: Courier) -> Courier:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(courier)
            sess.commit()
            sess.refresh(courier)
            return courier
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
