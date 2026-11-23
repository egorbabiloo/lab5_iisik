"""
Analytics Service: Business logic for operational metrics aggregation and SLA tracking.
Encapsulates repository operations, enforces date range validation, and converts to Pydantic v2 DTOs.
"""
from datetime import datetime, date
from typing import List, Optional, Union
from uuid import UUID
from sqlalchemy.orm import Session

from services.common.database import session_scope
from services.common.security import AuthenticatedUser, ROLE_ADMIN, require_roles
from services.analytics_service.models import EventShipmentStream, DailyDeliveryStats
from services.analytics_service.repository import AnalyticsRepository
from services.analytics_service.schemas import (
    DateRangeInputDTO,
    AnalyticsSummaryDTO,
    ShipmentStreamEventDTO,
    DailyDeliveryStatsDTO,
)


class AnalyticsService:
    """Service layer for analytics_db operational metrics."""

    def __init__(
        self,
        repository_or_session: Optional[Union[AnalyticsRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[AnalyticsRepository] = None,
    ):
        if isinstance(repository_or_session, AnalyticsRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = AnalyticsRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = AnalyticsRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    @classmethod
    def create(cls, session: Optional[Session] = None) -> "AnalyticsService":
        """Factory method instantiating the service with a managed session."""
        return cls(session=session)

    def _get_repo(self, session: Optional[Session] = None) -> AnalyticsRepository:
        if session is not None:
            return AnalyticsRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return AnalyticsRepository(self._session)
        return AnalyticsRepository()

    def get_analytics_summary(
        self,
        date_range: DateRangeInputDTO,
        actor: Optional[AuthenticatedUser] = None,
    ) -> AnalyticsSummaryDTO:
        """
        Validates date interval and calculates total shipments, delivered count,
        total revenue, SLA compliance rate, and average delivery duration.
        """
        if actor is not None:
            require_roles(actor, [ROLE_ADMIN], "analyticsSummary")
        if date_range.start_date > date_range.end_date:
            raise ValueError("startDate cannot be greater than endDate")

        if self.repository is not None or self._session is not None:
            raw_data = self._get_repo().aggregate_summary(date_range.start_date, date_range.end_date)
        else:
            with session_scope("analytics_db") as session:
                raw_data = self._get_repo(session).aggregate_summary(date_range.start_date, date_range.end_date)

        avg_minutes = float(raw_data["average_delivery_duration_min"])
        avg_hours = round(avg_minutes / 60.0, 2)

        return AnalyticsSummaryDTO(
            period_start=date_range.start_date,
            period_end=date_range.end_date,
            total_shipments=raw_data["total_shipments"],
            delivered_shipments=raw_data["delivered_shipments"],
            total_revenue=raw_data["total_revenue"],
            average_delivery_duration_min=avg_minutes,
            sla_compliance_rate=raw_data["sla_compliance_rate"],
            avg_delivery_duration_hours=avg_hours,
        )

    def list_stream_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        shipment_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ShipmentStreamEventDTO]:
        """Fetches and maps stream events to Pydantic DTOs."""
        if self.repository is not None or self._session is not None:
            events = self._get_repo().list_events(
                start_time=start_time,
                end_time=end_time,
                shipment_id=shipment_id,
                event_type=event_type,
                limit=limit,
            )
            return [ShipmentStreamEventDTO.model_validate(e) for e in events]
        with session_scope("analytics_db") as session:
            events = self._get_repo(session).list_events(
                start_time=start_time,
                end_time=end_time,
                shipment_id=shipment_id,
                event_type=event_type,
                limit=limit,
            )
            return [ShipmentStreamEventDTO.model_validate(e) for e in events]

    def get_daily_stats(self, start_date: date, end_date: date) -> List[DailyDeliveryStatsDTO]:
        """Fetches and maps daily delivery stats to Pydantic DTOs."""
        if self.repository is not None or self._session is not None:
            stats = self._get_repo().get_daily_stats(start_date, end_date)
            return [DailyDeliveryStatsDTO.model_validate(s) for s in stats]
        with session_scope("analytics_db") as session:
            stats = self._get_repo(session).get_daily_stats(start_date, end_date)
            return [DailyDeliveryStatsDTO.model_validate(s) for s in stats]
