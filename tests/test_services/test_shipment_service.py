"""
Unit tests for ShipmentService and ShipmentRepository in shipment_service.
Isolation: strictly shipment_db.
"""
from decimal import Decimal
import pytest
from sqlalchemy import text
from services.shipment_service.repository import ShipmentRepository
from services.shipment_service.service import ShipmentService
from services.shipment_service.schemas import ShipmentDTO, CreateShipmentInputDTO
from tests.test_services.conftest import (
    KNOWN_SHIPMENT_ID,
    KNOWN_TRACKING_NUMBER,
    KNOWN_CLIENT_ID,
    KNOWN_TARIFF_ID,
    NON_EXISTENT_UUID,
)


def test_get_shipment_by_tracking_found(shipment_session):
    service = ShipmentService(ShipmentRepository(shipment_session))
    shipment = service.get_by_tracking_number(KNOWN_TRACKING_NUMBER)

    assert shipment is not None
    assert isinstance(shipment, ShipmentDTO)
    assert shipment.id == KNOWN_SHIPMENT_ID
    assert shipment.tracking_number == KNOWN_TRACKING_NUMBER
    assert shipment.client_id == KNOWN_CLIENT_ID
    assert shipment.tariff_id == KNOWN_TARIFF_ID
    assert shipment.calculated_price == Decimal("24.50")
    assert shipment.current_status == "IN_TRANSIT"
    assert shipment.origin_city == "Минск"
    assert shipment.dest_city == "Брест"
    assert shipment.dimensions.length_cm == 30.0
    assert shipment.dimensions.width_cm == 20.0
    assert shipment.dimensions.height_cm == 15.0


def test_get_shipment_by_tracking_not_found(shipment_session):
    service = ShipmentService(ShipmentRepository(shipment_session))
    assert service.get_by_tracking_number("PKG-NON-EXISTENT") is None


def test_list_shipments_by_client(shipment_session):
    service = ShipmentService(ShipmentRepository(shipment_session))
    shipments = service.list_by_client_id(KNOWN_CLIENT_ID)
    assert len(shipments) >= 2
    trackings = [s.tracking_number for s in shipments]
    assert KNOWN_TRACKING_NUMBER in trackings


def test_get_shipment_status_history(shipment_session):
    service = ShipmentService(ShipmentRepository(shipment_session))
    history = service.get_status_history(KNOWN_SHIPMENT_ID)
    assert len(history) == 4
    statuses = [h.status for h in history]
    assert statuses == ["CREATED", "ASSIGNED", "PICKED_UP", "IN_TRANSIT"]


def test_create_and_update_shipment(shipment_session):
    service = ShipmentService(shipment_session)
    input_dto = CreateShipmentInputDTO(
        clientId=KNOWN_CLIENT_ID,
        tariffId=KNOWN_TARIFF_ID,
        weightKg=1.5,
        lengthCm=10.0,
        widthCm=10.0,
        heightCm=10.0,
        calculatedPrice=Decimal("15.00"),
        originCity="Минск",
        originAddress="ул. Ленина, 1",
        originLat=53.90,
        originLon=27.56,
        destCity="Гродно",
        destAddress="ул. Мира, 2",
        destLat=53.68,
        destLon=23.83,
        recipientName="Тестовый Получатель",
        recipientPhone="+375291112233",
    )
    test_tracking = "PKG-BY-TEST-0001"
    new_shipment = None
    try:
        new_shipment = service.create_shipment(input_dto, tracking_number=test_tracking)
        assert new_shipment.tracking_number == test_tracking
        assert new_shipment.current_status == "CREATED"

        updated = service.update_shipment_status(new_shipment.id, "DELIVERED", comment="Delivered to customer")
        assert updated is not None
        assert updated.current_status == "DELIVERED"
    finally:
        if new_shipment:
            shipment_session.execute(
                text("DELETE FROM shipment_status_history WHERE shipment_id = :sid"),
                {"sid": str(new_shipment.id)},
            )
            shipment_session.execute(
                text("DELETE FROM shipments WHERE id = :sid"),
                {"sid": str(new_shipment.id)},
            )
            shipment_session.commit()


def test_dual_lifecycle_auto_session():
    service = ShipmentService()
    shipment = service.get_by_tracking_number(KNOWN_TRACKING_NUMBER)
    assert shipment is not None
    assert shipment.id == KNOWN_SHIPMENT_ID


def test_shipment_db_isolation(shipment_session):
    url = str(shipment_session.bind.url)
    assert "shipment_db" in url
