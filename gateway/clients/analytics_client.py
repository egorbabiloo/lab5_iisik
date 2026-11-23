# -*- coding: utf-8 -*-
"""
AnalyticsClient: in-process client invoking AnalyticsService.
"""

from typing import Optional, List, Any
from uuid import UUID

from services.analytics_service.service import AnalyticsService
from services.analytics_service.schemas import (
    AnalyticsSummaryDTO,
    DateRangeInputDTO,
    ShipmentStreamEventDTO,
    DailyDeliveryStatsDTO,
)
from services.common.security import AuthenticatedUser
from gateway.clients.base import AnalyticsClientProtocol


class AnalyticsClient(AnalyticsClientProtocol):
    def __init__(self, service: Optional[AnalyticsService] = None) -> None:
        self._service = service or AnalyticsService()

    def get_analytics_summary(
        self, range_dto: DateRangeInputDTO, actor: Optional[AuthenticatedUser] = None
    ) -> AnalyticsSummaryDTO:
        return self._service.get_analytics_summary(range_dto, actor=actor)

    def list_stream_events(
        self,
        event_type: Optional[str] = None,
        shipment_id: Optional[UUID | str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ShipmentStreamEventDTO]:
        return self._service.list_stream_events(
            event_type=event_type, shipment_id=shipment_id, limit=limit, offset=offset
        )

    def get_daily_stats(
        self, start_date: Any, end_date: Any
    ) -> List[DailyDeliveryStatsDTO]:
        return self._service.get_daily_stats(start_date=start_date, end_date=end_date)
