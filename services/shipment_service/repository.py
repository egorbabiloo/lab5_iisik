"""
Shipment Repository for database-per-service isolation on shipment_db.
"""
from typing import Optional, List, Tuple, Any
from uuid import UUID
from decimal import Decimal
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session, selectinload
from services.common.database import get_session_for_db
from services.shipment_service.models import Shipment, ShipmentStatusHistory


class ShipmentRepository:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("shipment_db")

    def get_by_id(self, shipment_id: UUID | str) -> Optional[Shipment]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Shipment).where(Shipment.id == shipment_id).options(selectinload(Shipment.status_history))
            return sess.scalars(stmt).first()
        finally:
            if should_close:
                sess.close()

    def get_by_tracking_number(self, tracking_number: str) -> Optional[Shipment]:
        clean_num = tracking_number.strip() if tracking_number else ""
        if not clean_num:
            return None
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Shipment).where(Shipment.tracking_number == clean_num).options(selectinload(Shipment.status_history))
            return sess.scalars(stmt).first()
        finally:
            if should_close:
                sess.close()

    def list_by_client(self, client_id: UUID | str, limit: int = 50, offset: int = 0) -> Tuple[List[Shipment], int]:
        if isinstance(client_id, str):
            client_id = UUID(client_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            count_stmt = select(func.count(Shipment.id)).where(Shipment.client_id == client_id)
            total = sess.scalar(count_stmt) or 0

            stmt = (
                select(Shipment)
                .where(Shipment.client_id == client_id)
                .order_by(Shipment.created_at.desc())
                .limit(limit)
                .offset(offset)
                .options(selectinload(Shipment.status_history))
            )
            items = list(sess.scalars(stmt).all())
            return items, total
        finally:
            if should_close:
                sess.close()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Shipment]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Shipment).order_by(Shipment.created_at.desc()).limit(limit).offset(offset).options(selectinload(Shipment.status_history))
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def create(self, shipment: Shipment) -> Shipment:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(shipment)
            sess.commit()
            sess.refresh(shipment)
            return shipment
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def add_status_history(self, history: ShipmentStatusHistory) -> ShipmentStatusHistory:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(history)
            sess.commit()
            sess.refresh(history)
            return history
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def get_status_history(self, shipment_id: UUID | str) -> List[ShipmentStatusHistory]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(ShipmentStatusHistory).where(ShipmentStatusHistory.shipment_id == shipment_id).order_by(ShipmentStatusHistory.changed_at.asc())
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def update_status(self, shipment_id: UUID | str, new_status: str, comment: Optional[str] = None) -> Optional[Shipment]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            shipment = sess.scalars(select(Shipment).where(Shipment.id == shipment_id)).first()
            if not shipment:
                return None
            shipment.current_status = new_status
            history = ShipmentStatusHistory(
                shipment_id=shipment.id,
                status=new_status,
                comment=comment,
            )
            sess.add(history)
            sess.commit()
            sess.refresh(shipment)
            return shipment
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def _build_filter_conditions(self, filter_dto: Optional[Any] = None) -> list:
        conditions = []
        if not filter_dto:
            return conditions
        if getattr(filter_dto, "status", None):
            conditions.append(Shipment.current_status.in_(filter_dto.status))
        if getattr(filter_dto, "origin_city", None):
            conditions.append(Shipment.origin_city.ilike(f"%{filter_dto.origin_city}%"))
        if getattr(filter_dto, "dest_city", None):
            conditions.append(Shipment.dest_city.ilike(f"%{filter_dto.dest_city}%"))
        if getattr(filter_dto, "tariff_id", None):
            conditions.append(Shipment.tariff_id == filter_dto.tariff_id)
        if getattr(filter_dto, "date_from", None):
            conditions.append(Shipment.created_at >= filter_dto.date_from)
        if getattr(filter_dto, "date_to", None):
            conditions.append(Shipment.created_at <= filter_dto.date_to)
        if getattr(filter_dto, "min_price", None) is not None:
            conditions.append(Shipment.calculated_price >= filter_dto.min_price)
        if getattr(filter_dto, "max_price", None) is not None:
            conditions.append(Shipment.calculated_price <= filter_dto.max_price)
        if getattr(filter_dto, "min_weight", None) is not None:
            conditions.append(Shipment.weight_kg >= filter_dto.min_weight)
        if getattr(filter_dto, "max_weight", None) is not None:
            conditions.append(Shipment.weight_kg <= filter_dto.max_weight)
        if getattr(filter_dto, "search_query", None):
            q = filter_dto.search_query.strip()
            if q:
                conditions.append(
                    or_(
                        Shipment.tracking_number.ilike(f"%{q}%"),
                        Shipment.recipient_name.ilike(f"%{q}%"),
                        Shipment.recipient_phone.ilike(f"%{q}%"),
                    )
                )
        return conditions

    def filter_and_sort(
        self,
        filter_dto: Optional[Any] = None,
        sort_dto: Optional[Any] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Shipment], int]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            conditions = self._build_filter_conditions(filter_dto)
            base_count = select(func.count(Shipment.id))
            if conditions:
                base_count = base_count.where(and_(*conditions))
            total = sess.scalar(base_count) or 0

            stmt = select(Shipment).options(selectinload(Shipment.status_history))
            if conditions:
                stmt = stmt.where(and_(*conditions))

            sort_field = getattr(sort_dto, "field", "CREATED_AT") if sort_dto else "CREATED_AT"
            direction = getattr(sort_dto, "direction", "DESC") if sort_dto else "DESC"

            field_map = {
                "CREATED_AT": Shipment.created_at,
                "CALCULATED_PRICE": Shipment.calculated_price,
                "WEIGHT_KG": Shipment.weight_kg,
                "TRACKING_NUMBER": Shipment.tracking_number,
            }
            order_col = field_map.get(sort_field, Shipment.created_at)
            stmt = stmt.order_by(order_col.asc() if str(direction).upper() == "ASC" else order_col.desc())
            stmt = stmt.limit(limit).offset(offset)

            items = list(sess.scalars(stmt).all())
            return items, total
        finally:
            if should_close:
                sess.close()

    def aggregate_stats(self, filter_dto: Optional[Any] = None) -> dict:
        sess = self._get_session()
        should_close = self._session is None
        try:
            conditions = self._build_filter_conditions(filter_dto)
            agg_stmt = select(
                func.count(Shipment.id).label("total_count"),
                func.coalesce(func.sum(Shipment.calculated_price), 0).label("total_revenue"),
                func.coalesce(func.avg(Shipment.calculated_price), 0).label("avg_price"),
                func.coalesce(func.min(Shipment.calculated_price), 0).label("min_price"),
                func.coalesce(func.max(Shipment.calculated_price), 0).label("max_price"),
                func.coalesce(func.avg(Shipment.weight_kg), 0).label("avg_weight"),
            )
            if conditions:
                agg_stmt = agg_stmt.where(and_(*conditions))
            row = sess.execute(agg_stmt).one()

            status_stmt = select(
                Shipment.current_status,
                func.count(Shipment.id)
            )
            if conditions:
                status_stmt = status_stmt.where(and_(*conditions))
            status_stmt = status_stmt.group_by(Shipment.current_status)
            status_rows = sess.execute(status_stmt).all()
            status_breakdown = [{"status": r[0], "count": r[1]} for r in status_rows]

            city_stmt = select(
                Shipment.origin_city,
                func.count(Shipment.id),
                func.coalesce(func.sum(Shipment.calculated_price), 0)
            )
            if conditions:
                city_stmt = city_stmt.where(and_(*conditions))
            city_stmt = city_stmt.group_by(Shipment.origin_city)
            city_rows = sess.execute(city_stmt).all()
            city_breakdown = [
                {"city": r[0], "shipment_count": r[1], "total_revenue": Decimal(str(round(r[2], 2)))}
                for r in city_rows
            ]

            return {
                "total_count": int(row.total_count),
                "total_revenue": Decimal(str(round(row.total_revenue, 2))),
                "average_price": Decimal(str(round(row.avg_price, 2))),
                "min_price": Decimal(str(round(row.min_price, 2))),
                "max_price": Decimal(str(round(row.max_price, 2))),
                "average_weight": float(round(row.avg_weight, 2)),
                "status_breakdown": status_breakdown,
                "city_breakdown": city_breakdown,
                "tariff_breakdown": [],
            }
        finally:
            if should_close:
                sess.close()
