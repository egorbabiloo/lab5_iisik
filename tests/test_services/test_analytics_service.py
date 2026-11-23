"""
Unit tests for AnalyticsService and AnalyticsRepository in analytics_service.
Isolation: strictly analytics_db.
"""
from datetime import datetime, timezone, date
from decimal import Decimal
import pytest
from services.analytics_service.repository import AnalyticsRepository
from services.analytics_service.service import AnalyticsService
from services.analytics_service.schemas import DateRangeInputDTO, AnalyticsSummaryDTO


def test_analytics_summary_october_seeded_data(analytics_session):
    """
    Verifies aggregate metrics against the seeded October 2026 dataset:
    totalShipments = 15, deliveredShipments = 14, totalRevenue = 416.00,
    averageDeliveryDurationMin = 241.43, slaComplianceRate = 0.9733.
    """
    repo = AnalyticsRepository(analytics_session)
    service = AnalyticsService(repo)

    range_dto = DateRangeInputDTO(
        startDate=datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        endDate=datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    summary = service.get_analytics_summary(range_dto)

    assert isinstance(summary, AnalyticsSummaryDTO)
    assert summary.total_shipments == 15
    assert summary.delivered_shipments == 14
    assert summary.total_revenue == Decimal("416.00")
    assert summary.average_delivery_duration_min == pytest.approx(241.43, rel=1e-2)
    assert summary.sla_compliance_rate == pytest.approx(0.9733, rel=1e-2)
    assert summary.avg_delivery_duration_hours == pytest.approx(4.02, rel=1e-2)


def test_analytics_summary_future_range_zeroes(analytics_session):
    service = AnalyticsService(AnalyticsRepository(analytics_session))
    range_dto = DateRangeInputDTO(
        startDate=datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        endDate=datetime(2099, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    summary = service.get_analytics_summary(range_dto)

    assert summary.total_shipments == 0
    assert summary.delivered_shipments == 0
    assert summary.total_revenue == Decimal("0.00")
    assert summary.average_delivery_duration_min == 0.0
    assert summary.sla_compliance_rate == 1.0


def test_analytics_summary_reversed_range_raises():
    with pytest.raises(ValueError, match="startDate cannot be greater than endDate"):
        DateRangeInputDTO(
            startDate=datetime(2026, 10, 31, 0, 0, 0, tzinfo=timezone.utc),
            endDate=datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        )


def test_analytics_summary_instant_range(analytics_session):
    service = AnalyticsService(AnalyticsRepository(analytics_session))
    instant = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    range_dto = DateRangeInputDTO(startDate=instant, endDate=instant)
    summary = service.get_analytics_summary(range_dto)

    assert summary is not None
    assert summary.period_start == instant
    assert summary.period_end == instant


def test_list_stream_events(analytics_session):
    service = AnalyticsService(AnalyticsRepository(analytics_session))
    events = service.list_stream_events()
    assert len(events) >= 4
    event_types = {e.event_type for e in events}
    assert "CREATED" in event_types and "DELIVERED" in event_types


def test_get_daily_stats(analytics_session):
    service = AnalyticsService(analytics_session)
    stats = service.get_daily_stats(start_date=date(2026, 10, 11), end_date=date(2026, 10, 12))
    assert len(stats) == 3


def test_dual_lifecycle_auto_session():
    service = AnalyticsService()
    range_dto = DateRangeInputDTO(
        startDate=datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        endDate=datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    summary = service.get_analytics_summary(range_dto)
    assert summary.total_shipments == 15


def test_analytics_db_isolation(analytics_session):
    url = str(analytics_session.bind.url)
    assert "analytics_db" in url
