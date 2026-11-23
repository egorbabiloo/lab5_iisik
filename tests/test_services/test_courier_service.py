"""
Unit tests for CourierService and CourierRepository in courier_service.
Isolation: strictly courier_db.
"""
from decimal import Decimal
import pytest
from services.courier_service.repository import CourierRepository
from services.courier_service.service import CourierService
from services.courier_service.schemas import CourierDTO
from tests.test_services.conftest import KNOWN_COURIER_ID, KNOWN_COURIER_USER_ID, NON_EXISTENT_UUID


def test_get_courier_by_id_found(courier_session):
    service = CourierService(CourierRepository(courier_session))
    courier = service.get_courier_by_id(KNOWN_COURIER_ID)

    assert courier is not None
    assert isinstance(courier, CourierDTO)
    assert courier.id == KNOWN_COURIER_ID
    assert courier.user_id == KNOWN_COURIER_USER_ID
    assert courier.transport_type == "CAR"
    assert courier.vehicle_plate == "1234-AB-7"
    assert courier.max_payload_kg == Decimal("250.00")
    assert courier.current_status == "AVAILABLE"
    assert courier.rating == Decimal("4.95")
    assert courier.total_deliveries == 142


def test_get_courier_by_id_not_found(courier_session):
    service = CourierService(CourierRepository(courier_session))
    assert service.get_courier_by_id(NON_EXISTENT_UUID) is None


def test_get_courier_by_user_id(courier_session):
    service = CourierService(CourierRepository(courier_session))
    courier = service.get_courier_by_user_id(KNOWN_COURIER_USER_ID)
    assert courier is not None
    assert courier.id == KNOWN_COURIER_ID


def test_courier_coordinates_precision(courier_session):
    service = CourierService(CourierRepository(courier_session))
    courier = service.get_courier_by_id(KNOWN_COURIER_ID)
    assert courier.current_lat is not None and courier.current_lon is not None
    assert float(courier.current_lat) == pytest.approx(52.09811, rel=1e-3)
    assert float(courier.current_lon) == pytest.approx(23.68902, rel=1e-3)


def test_list_by_status(courier_session):
    service = CourierService(courier_session)
    available = service.list_by_status("AVAILABLE")
    assert len(available) >= 2


def test_check_availability(courier_session):
    service = CourierService(courier_session)
    res_ok = service.check_availability(KNOWN_COURIER_ID, parcel_weight_kg=50.0)
    assert res_ok["is_available"] is True
    res_heavy = service.check_availability(KNOWN_COURIER_ID, parcel_weight_kg=300.0)
    assert res_heavy["is_available"] is False


def test_dual_lifecycle_auto_session():
    service = CourierService()
    courier = service.get_by_id(KNOWN_COURIER_ID)
    assert courier is not None
    assert courier.id == KNOWN_COURIER_ID


def test_courier_db_isolation(courier_session):
    url = str(courier_session.bind.url)
    assert "courier_db" in url
