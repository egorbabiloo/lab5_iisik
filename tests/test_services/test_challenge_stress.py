"""
Empirical stress and edge-case challenge test suite for Milestone 2 internal services.
Adversarial coverage for:
1. Price calculation with zero, negative, extreme float values, non-existent tariffs, Unicode/empty cities.
2. Analytics with inverted date ranges, instant single-point ranges, future dates, past empty dates.
3. Non-existent tracking numbers, UUIDs, empty strings, Unicode characters, and boundaries.
4. Input validation and domain exceptions across all microservices.
"""
import math
import uuid
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
import pytest
from pydantic import ValidationError as PydanticValidationError

from services.common.exceptions import (
    EntityNotFoundError,
    ValidationError as DomainValidationError,
)
from services.tariff_service.schemas import CalculatePriceInputDTO
from services.tariff_service.service import TariffService
from services.analytics_service.schemas import DateRangeInputDTO
from services.analytics_service.service import AnalyticsService
from services.shipment_service.service import ShipmentService
from services.user_service.service import UserService
from services.courier_service.service import CourierService
from services.courier_service.schemas import (
    UpdateCourierLocationInputDTO,
    UpdateCourierStatusInputDTO,
)
from services.route_service.service import RouteService
from services.delivery_service.service import DeliveryService


# ==============================================================================
# 1. Price Calculation Stress & Edge Cases
# ==============================================================================

def test_price_calculation_zero_weight_raises():
    tariff = TariffService().list_active()[0]
    with pytest.raises((PydanticValidationError, DomainValidationError, ValueError)):
        dto = CalculatePriceInputDTO(
            tariff_id=tariff.id,
            origin_city="Minsk",
            dest_city="Brest",
            distance_km=100.0,
            weight_kg=0.0,
        )
        TariffService().calculate_price(dto)


def test_price_calculation_negative_weight_raises():
    tariff = TariffService().list_active()[0]
    for neg_w in [-0.0001, -1.0, -999.0]:
        with pytest.raises((PydanticValidationError, DomainValidationError, ValueError)):
            dto = CalculatePriceInputDTO(
                tariff_id=tariff.id,
                origin_city="Minsk",
                dest_city="Brest",
                distance_km=100.0,
                weight_kg=neg_w,
            )
            TariffService().calculate_price(dto)


def test_price_calculation_zero_distance_raises():
    tariff = TariffService().list_active()[0]
    with pytest.raises((PydanticValidationError, DomainValidationError, ValueError)):
        dto = CalculatePriceInputDTO(
            tariff_id=tariff.id,
            origin_city="Minsk",
            dest_city="Brest",
            distance_km=0.0,
            weight_kg=5.0,
        )
        TariffService().calculate_price(dto)


def test_price_calculation_negative_distance_raises():
    tariff = TariffService().list_active()[0]
    for neg_d in [-0.001, -10.0, -10000.0]:
        with pytest.raises((PydanticValidationError, DomainValidationError, ValueError)):
            dto = CalculatePriceInputDTO(
                tariff_id=tariff.id,
                origin_city="Minsk",
                dest_city="Brest",
                distance_km=neg_d,
                weight_kg=5.0,
            )
            TariffService().calculate_price(dto)


def test_price_calculation_extreme_large_floats():
    """Stress-test with very large distances and weights (millions/billions)."""
    tariff = TariffService().list_active()[0]
    service = TariffService()

    # 1. Millions
    dto1 = CalculatePriceInputDTO(
        tariff_id=tariff.id,
        origin_city="Minsk",
        dest_city="Vladivostok",
        distance_km=1_000_000.0,
        weight_kg=100_000.0,
    )
    res1 = service.calculate_price(dto1)
    assert res1.total_price > Decimal("100000.00")
    assert res1.base_price == tariff.base_price
    assert res1.weight_price > 0
    assert res1.distance_price > 0

    # 2. Billions
    dto2 = CalculatePriceInputDTO(
        tariff_id=tariff.id,
        origin_city="Minsk",
        dest_city="Vladivostok",
        distance_km=1_000_000_000.0,
        weight_kg=1_000_000.0,
    )
    res2 = service.calculate_price(dto2)
    assert res2.total_price > Decimal("10000000.00")


def test_price_calculation_tiny_positive_values():
    """Sub-gram weights and sub-meter distances should calculate without underflow."""
    tariff = TariffService().list_active()[0]
    service = TariffService()

    dto = CalculatePriceInputDTO(
        tariff_id=tariff.id,
        origin_city="Minsk",
        dest_city="Brest",
        distance_km=0.0001,
        weight_kg=0.0001,
    )
    res = service.calculate_price(dto)
    assert res.total_price >= tariff.base_price
    assert res.total_price == tariff.base_price


def test_price_calculation_nan_and_inf_rejected():
    tariff = TariffService().list_active()[0]
    service = TariffService()

    for invalid_val in [float("nan"), float("inf"), float("-inf")]:
        try:
            dto = CalculatePriceInputDTO(
                tariff_id=tariff.id,
                origin_city="Minsk",
                dest_city="Brest",
                distance_km=invalid_val,
                weight_kg=5.0,
            )
            # If DTO creation didn't raise, calculation must raise
            with pytest.raises(Exception):
                service.calculate_price(dto)
        except Exception:
            pass  # Successfully rejected


def test_price_calculation_nonexistent_tariff_raises_entity_not_found():
    fake_id = uuid.uuid4()
    dto = CalculatePriceInputDTO(
        tariff_id=fake_id,
        origin_city="Minsk",
        dest_city="Grodno",
        distance_km=280.0,
        weight_kg=3.5,
    )
    with pytest.raises(EntityNotFoundError) as exc_info:
        TariffService().calculate_price(dto)
    assert str(fake_id) in str(exc_info.value)


def test_price_calculation_empty_and_whitespace_cities_rejected():
    tariff = TariffService().list_active()[0]
    for bad_city in ["", "   ", "\t\n"]:
        with pytest.raises(PydanticValidationError):
            CalculatePriceInputDTO(
                tariff_id=tariff.id,
                origin_city=bad_city,
                dest_city="Brest",
                distance_km=100.0,
                weight_kg=1.0,
            )
        with pytest.raises(PydanticValidationError):
            CalculatePriceInputDTO(
                tariff_id=tariff.id,
                origin_city="Minsk",
                dest_city=bad_city,
                distance_km=100.0,
                weight_kg=1.0,
            )


def test_price_calculation_unicode_cities_accepted():
    tariff = TariffService().list_active()[0]
    dto = CalculatePriceInputDTO(
        tariff_id=tariff.id,
        origin_city="Мінск - Цэнтральны 🚀",
        dest_city="Гродна - Вакзал 📦",
        distance_km=280.0,
        weight_kg=2.5,
    )
    res = TariffService().calculate_price(dto)
    assert res.total_price > tariff.base_price
    assert res.tariff_name == tariff.name


# ==============================================================================
# 2. Analytics Stress & Edge Cases
# ==============================================================================

def test_analytics_inverted_date_range_raises():
    start = datetime(2026, 10, 25, 12, 0, 0)
    end = datetime(2026, 10, 20, 12, 0, 0)
    with pytest.raises((ValueError, PydanticValidationError)):
        dto = DateRangeInputDTO(startDate=start, endDate=end)
        AnalyticsService().get_analytics_summary(dto)


def test_analytics_instant_single_point_range_graceful():
    instant = datetime(2026, 10, 15, 10, 0, 0)
    dto = DateRangeInputDTO(startDate=instant, endDate=instant)
    summary = AnalyticsService().get_analytics_summary(dto)
    assert summary.total_shipments >= 0
    assert summary.delivered_shipments >= 0
    assert summary.total_revenue >= Decimal("0.00")
    assert summary.average_delivery_duration_min >= 0.0
    assert 0.0 <= summary.sla_compliance_rate <= 1.0


def test_analytics_future_date_range_graceful_zeroes():
    start = datetime(2099, 1, 1, 0, 0, 0)
    end = datetime(2099, 12, 31, 23, 59, 59)
    dto = DateRangeInputDTO(startDate=start, endDate=end)
    summary = AnalyticsService().get_analytics_summary(dto)
    assert summary.total_shipments == 0
    assert summary.delivered_shipments == 0
    assert summary.total_revenue == Decimal("0.00")
    assert summary.average_delivery_duration_min == 0.0
    assert summary.sla_compliance_rate == 1.0


def test_analytics_past_empty_date_range_graceful_zeroes():
    start = datetime(1995, 1, 1, 0, 0, 0)
    end = datetime(1995, 12, 31, 23, 59, 59)
    dto = DateRangeInputDTO(startDate=start, endDate=end)
    summary = AnalyticsService().get_analytics_summary(dto)
    assert summary.total_shipments == 0
    assert summary.delivered_shipments == 0
    assert summary.total_revenue == Decimal("0.00")


def test_analytics_events_listing_extreme_limits_and_filters():
    service = AnalyticsService()
    # Negative / zero limit
    events_0 = service.list_stream_events(limit=0)
    assert isinstance(events_0, list)

    events_large = service.list_stream_events(limit=1000)
    assert isinstance(events_large, list)

    # Filter with random non-existent shipment_id
    events_none = service.list_stream_events(shipment_id=uuid.uuid4())
    assert events_none == []

    # Filter with non-existent event_type
    events_bad_type = service.list_stream_events(event_type="NON_EXISTENT_TYPE")
    assert events_bad_type == []


# ==============================================================================
# 3. Tracking Numbers & Identifier Edge Cases
# ==============================================================================

def test_shipment_get_by_tracking_number_nonexistent():
    svc = ShipmentService()
    assert svc.get_by_tracking_number("PKG-NONEXISTENT-999999") is None
    assert svc.get_by_tracking_number("invalid_tracking") is None


def test_shipment_get_by_tracking_number_empty_and_whitespace():
    svc = ShipmentService()
    assert svc.get_by_tracking_number("") is None
    assert svc.get_by_tracking_number("   ") is None
    assert svc.get_by_tracking_number("\t\n\r ") is None
    assert svc.get_by_tracking_number(None) is None


def test_shipment_get_by_tracking_number_unicode_and_emojis():
    svc = ShipmentService()
    assert svc.get_by_tracking_number("📦🚀🚚🔥") is None
    assert svc.get_by_tracking_number("МИНСК-ПОСЫЛКА-001") is None
    assert svc.get_by_tracking_number("北京快递-12345") is None


def test_shipment_get_by_tracking_number_long_strings():
    svc = ShipmentService()
    assert svc.get_by_tracking_number("A" * 1000) is None
    assert svc.get_by_tracking_number("PKG-" + "9" * 500) is None


# ==============================================================================
# 4. Non-Existent UUIDs across all 7 microservices
# ==============================================================================

def test_nonexistent_uuids_all_services():
    fake_id = uuid.uuid4()
    fake_str_id = str(uuid.uuid4())

    # Shipment Service
    ship_svc = ShipmentService()
    assert ship_svc.get_by_id(fake_id) is None
    assert ship_svc.get_by_id(fake_str_id) is None
    assert ship_svc.list_by_client_id(fake_id) == []
    conn = ship_svc.get_client_shipments(fake_id)
    assert conn.items == []
    assert conn.total_count == 0
    assert ship_svc.get_status_history(fake_id) == []

    # Tariff Service
    tariff_svc = TariffService()
    assert tariff_svc.get_by_id(fake_id) is None
    assert tariff_svc.get_by_id(fake_str_id) is None
    assert tariff_svc.get_by_code("NON_EXISTENT_CODE") is None
    assert tariff_svc.get_by_code("") is None
    assert tariff_svc.get_by_code("🚀ТАРИФ") is None

    # User Service
    user_svc = UserService()
    assert user_svc.get_by_id(fake_id) is None
    assert user_svc.get_by_id(fake_str_id) is None
    assert user_svc.get_by_email("nobody@example.com") is None
    assert user_svc.get_by_email("") is None
    assert user_svc.get_by_email("тест@логистика.бел") is None
    assert user_svc.get_role_by_code("NON_EXISTENT_ROLE") is None

    # Courier Service
    courier_svc = CourierService()
    assert courier_svc.get_by_id(fake_id) is None
    assert courier_svc.get_by_id(fake_str_id) is None
    assert courier_svc.get_by_user_id(fake_id) is None
    assert courier_svc.list_by_status("NON_EXISTENT_STATUS") == []
    assert courier_svc.get_location(fake_id) is None

    # Route Service
    route_svc = RouteService()
    assert route_svc.get_by_id(fake_id) is None
    assert route_svc.get_by_id(fake_str_id) is None
    assert route_svc.get_by_shipment_id(fake_id) is None
    assert route_svc.get_stages_by_route_id(fake_id) == []
    assert route_svc.get_stage_by_id(fake_id) is None

    # Delivery Service
    delivery_svc = DeliveryService()
    assert delivery_svc.get_by_id(fake_id) is None
    assert delivery_svc.get_by_id(fake_str_id) is None
    assert delivery_svc.get_active_by_shipment_id(fake_id) is None
    assert delivery_svc.list_by_courier_id(fake_id) == []
    assert delivery_svc.list_by_shipment_id(fake_id) == []
    assert delivery_svc.get_checkpoints_for_shipment(fake_id) == []
    assert delivery_svc.get_checkpoints_by_delivery_id(fake_id) == []


# ==============================================================================
# 5. Courier availability and input validation
# ==============================================================================

def test_courier_check_availability_detached_instance_bug_exposure():
    """
    CRITICAL CHALLENGE TEST:
    Verifies CourierService.check_availability under default auto-session lifecycle.
    Exposes DetachedInstanceError when courier ORM entity attributes are accessed
    outside session_scope.
    """
    courier_svc = CourierService()
    fake_id = uuid.uuid4()

    # Non-existent courier raises EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        courier_svc.check_availability(fake_id, 10.0)

    # Existing courier under auto-session lifecycle
    active_couriers = courier_svc.list_all()
    if active_couriers:
        c = active_couriers[0]
        # This call exposes DetachedInstanceError on unpatched code:
        res = courier_svc.check_availability(c.id, 10.0)
        assert "is_available" in res
        assert "courier_id" in res


def test_courier_input_dto_validation():
    fake_id = uuid.uuid4()

    # Status validation: only AVAILABLE, BUSY, OFFLINE permitted
    with pytest.raises(PydanticValidationError):
        UpdateCourierStatusInputDTO(courier_id=fake_id, status="FLYING")

    valid_dto = UpdateCourierStatusInputDTO(courier_id=fake_id, status=" available ")
    assert valid_dto.status == "AVAILABLE"

    # Latitude validation [-90, 90]
    with pytest.raises(PydanticValidationError):
        UpdateCourierLocationInputDTO(courier_id=fake_id, latitude=91.0, longitude=27.5)
    with pytest.raises(PydanticValidationError):
        UpdateCourierLocationInputDTO(courier_id=fake_id, latitude=-90.1, longitude=27.5)

    # Longitude validation [-180, 180]
    with pytest.raises(PydanticValidationError):
        UpdateCourierLocationInputDTO(courier_id=fake_id, latitude=53.9, longitude=180.1)
    with pytest.raises(PydanticValidationError):
        UpdateCourierLocationInputDTO(courier_id=fake_id, latitude=53.9, longitude=-181.0)

    # Valid boundary coords
    loc_dto = UpdateCourierLocationInputDTO(courier_id=fake_id, latitude=90.0, longitude=-180.0)
    assert loc_dto.latitude == 90.0
    assert loc_dto.longitude == -180.0
