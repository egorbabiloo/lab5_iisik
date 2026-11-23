"""
Analytics Service Repository: SQLAlchemy 2.0 query and aggregation layer.
Database: analytics_db (PostgreSQL 16)
Zero Cross-Database ForeignKeys: Operates strictly on analytics_db models.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session
from services.common.database import get_session_for_db
from services.analytics_service.models import EventShipmentStream, DailyDeliveryStats


class AnalyticsRepository:
    """Repository accessing events_shipment_stream and daily_delivery_stats."""

    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("analytics_db")

    def aggregate_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """
        Calculates operational summary metrics for the given period.
        Primary source: daily_delivery_stats for daily roll-ups.
        Fallback/supplement: events_shipment_stream for fine-grained intervals.
        """
        sess = self._get_session()
        should_close = self._session is None
        try:
            s_date: date = start_time.date()
            e_date: date = end_time.date()

            # Step 1: Query pre-aggregated daily_delivery_stats
            daily_stmt = (
                select(
                    func.coalesce(func.sum(DailyDeliveryStats.shipments_count), 0).label("total_shipments"),
                    func.coalesce(func.sum(DailyDeliveryStats.delivered_count), 0).label("delivered_shipments"),
                    func.coalesce(func.sum(DailyDeliveryStats.total_revenue), Decimal("0.00")).label("total_revenue"),
                    func.sum(DailyDeliveryStats.avg_delivery_time_min * DailyDeliveryStats.delivered_count).label("weighted_time_sum"),
                    func.sum(DailyDeliveryStats.sla_compliance_rate * DailyDeliveryStats.shipments_count).label("weighted_sla_sum"),
                    func.count().label("row_count"),
                )
                .where(DailyDeliveryStats.report_date >= s_date)
                .where(DailyDeliveryStats.report_date <= e_date)
            )
            row = sess.execute(daily_stmt).one()

            if row.row_count > 0 and row.total_shipments > 0:
                total_shipments = int(row.total_shipments)
                delivered_shipments = int(row.delivered_shipments)
                total_revenue = Decimal(str(row.total_revenue)).quantize(Decimal("0.01"))

                avg_time = (
                    float(row.weighted_time_sum / delivered_shipments)
                    if delivered_shipments > 0 and row.weighted_time_sum is not None
                    else 0.0
                )
                sla_rate = (
                    float(row.weighted_sla_sum / total_shipments)
                    if total_shipments > 0 and row.weighted_sla_sum is not None
                    else 1.0
                )
                sla_rate = max(0.0, min(1.0, sla_rate))

                return {
                    "total_shipments": total_shipments,
                    "delivered_shipments": delivered_shipments,
                    "total_revenue": total_revenue,
                    "average_delivery_duration_min": round(avg_time, 2),
                    "sla_compliance_rate": round(sla_rate, 4),
                }

            # Step 2: Fallback to events_shipment_stream
            stream_stmt = (
                select(
                    func.count(func.distinct(EventShipmentStream.shipment_id)).label("total_shipments"),
                    func.count(
                        func.distinct(
                            case(
                                (EventShipmentStream.event_type == "DELIVERED", EventShipmentStream.shipment_id),
                                else_=None,
                            )
                        )
                    ).label("delivered_shipments"),
                    func.coalesce(
                        func.sum(
                            case(
                                (EventShipmentStream.event_type == "CREATED", EventShipmentStream.price),
                                else_=Decimal("0.00"),
                            )
                        ),
                        Decimal("0.00"),
                    ).label("total_revenue"),
                    func.count().label("event_count"),
                    func.count(
                        case((EventShipmentStream.is_delayed.is_(True), 1), else_=None)
                    ).label("delayed_count"),
                )
                .where(EventShipmentStream.event_time >= start_time)
                .where(EventShipmentStream.event_time <= end_time)
            )
            s_row = sess.execute(stream_stmt).one()

            if s_row.event_count > 0:
                total_shipments = int(s_row.total_shipments)
                delivered_shipments = int(s_row.delivered_shipments)
                total_revenue = Decimal(str(s_row.total_revenue)).quantize(Decimal("0.01"))
                delayed_count = int(s_row.delayed_count)
                sla_rate = (
                    1.0 - (float(delayed_count) / float(s_row.event_count))
                    if s_row.event_count > 0
                    else 1.0
                )

                return {
                    "total_shipments": total_shipments,
                    "delivered_shipments": delivered_shipments,
                    "total_revenue": total_revenue,
                    "average_delivery_duration_min": 0.0,
                    "sla_compliance_rate": round(max(0.0, min(1.0, sla_rate)), 4),
                }

            # Step 3: Default zero metrics for future or empty ranges
            return {
                "total_shipments": 0,
                "delivered_shipments": 0,
                "total_revenue": Decimal("0.00"),
                "average_delivery_duration_min": 0.0,
                "sla_compliance_rate": 1.0,
            }
        finally:
            if should_close:
                sess.close()

    def get_daily_stats(self, start_date: date, end_date: date) -> List[DailyDeliveryStats]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(DailyDeliveryStats)
                .where(DailyDeliveryStats.report_date >= start_date)
                .where(DailyDeliveryStats.report_date <= end_date)
                .order_by(DailyDeliveryStats.report_date.asc(), DailyDeliveryStats.tariff_code.asc())
            )
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def list_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        shipment_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[EventShipmentStream]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(EventShipmentStream)
            if start_time is not None:
                stmt = stmt.where(EventShipmentStream.event_time >= start_time)
            if end_time is not None:
                stmt = stmt.where(EventShipmentStream.event_time <= end_time)
            if shipment_id is not None:
                stmt = stmt.where(EventShipmentStream.shipment_id == shipment_id)
            if event_type is not None:
                stmt = stmt.where(EventShipmentStream.event_type == event_type)

            stmt = stmt.order_by(EventShipmentStream.event_time.asc()).limit(limit)
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def record_stream_event(self, event: EventShipmentStream) -> EventShipmentStream:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(event)
            sess.commit()
            sess.refresh(event)
            return event
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
