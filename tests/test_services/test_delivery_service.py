"""
Unit tests for DeliveryService and DeliveryRepository in delivery_service.
Isolation: strictly delivery_db.
"""
from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import text
from services.delivery_service.repository import DeliveryRepository
from services.delivery_service.service import DeliveryService
from services.delivery_service.schemas import (
    DeliveryDTO,
    DeliveryCheckpointDTO,
    CreateDeliveryInputDTO,
    AddCheckpointInputDTO,
)
from tests.test_services.conftest import (
    KNOWN_DELIVERY_ID,
    KNOWN_SHIPMENT_ID,
    KNOWN_COURIER_ID,
    NON_EXISTENT_UUID,
)


def test_get_active_delivery_by_shipment_found(delivery_session):
    service = DeliveryService(DeliveryRepository(delivery_session))
    delivery = service.get_active_by_shipment_id(KNOWN_SHIPMENT_ID)

    assert delivery is not None
    assert isinstance(delivery, DeliveryDTO)
    assert delivery.id == KNOWN_DELIVERY_ID
    assert delivery.shipment_id == KNOWN_SHIPMENT_ID
    assert delivery.courier_id == KNOWN_COURIER_ID
    assert delivery.status == "PICKED_UP"
    assert delivery.delivery_type == "FIRST_MILE_PICKUP"
    assert len(delivery.checkpoints) == 3


def test_get_active_delivery_by_shipment_not_found(delivery_session):
    service = DeliveryService(DeliveryRepository(delivery_session))
    assert service.get_active_by_shipment_id(NON_EXISTENT_UUID) is None


def test_list_deliveries_by_courier_id(delivery_session):
    service = DeliveryService(DeliveryRepository(delivery_session))
    deliveries = service.list_by_courier_id(KNOWN_COURIER_ID)
    assert len(deliveries) >= 2


def test_get_delivery_checkpoints_chronological(delivery_session):
    service = DeliveryService(DeliveryRepository(delivery_session))
    cps = service.get_checkpoints_by_delivery_id(KNOWN_DELIVERY_ID)

    assert len(cps) == 3
    statuses = [cp.status for cp in cps]
    assert statuses == ["ACCEPTED", "PICKED_UP", "AT_HUB"]

    # Verify strictly ascending timestamps
    timestamps = [cp.recorded_at for cp in cps]
    assert timestamps == sorted(timestamps)


def test_get_checkpoints_for_shipment(delivery_session):
    service = DeliveryService(delivery_session)
    cps = service.get_checkpoints_for_shipment(KNOWN_SHIPMENT_ID)
    assert len(cps) == 3
    assert cps[0].status == "ACCEPTED"


def test_create_delivery_and_add_checkpoint(delivery_session):
    service = DeliveryService(delivery_session)
    mock_shipment = uuid.uuid4()
    mock_stage = uuid.uuid4()
    del_in = CreateDeliveryInputDTO(
        shipmentId=mock_shipment,
        routeStageId=mock_stage,
        deliveryType="LAST_MILE_DROPOFF",
        windowStart=datetime(2026, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
        windowEnd=datetime(2026, 10, 26, 16, 0, 0, tzinfo=timezone.utc),
        status="PENDING_ASSIGNMENT",
    )
    new_del = None
    try:
        new_del = service.create_delivery(del_in)
        assert new_del.shipment_id == mock_shipment
        assert new_del.status == "PENDING_ASSIGNMENT"

        assigned = service.assign_courier(new_del.id, KNOWN_COURIER_ID)
        assert assigned is not None
        assert assigned.courier_id == KNOWN_COURIER_ID
        assert assigned.status == "ASSIGNED"

        cp_in = AddCheckpointInputDTO(
            deliveryId=new_del.id,
            status="PICKED_UP",
            locationName="Центральный склад",
            notes="Заказ забран курьером",
        )
        cp = service.add_checkpoint(cp_in)
        assert cp.status == "PICKED_UP"
    finally:
        if new_del:
            delivery_session.execute(
                text("DELETE FROM delivery_checkpoints WHERE delivery_id = :did"),
                {"did": str(new_del.id)},
            )
            delivery_session.execute(
                text("DELETE FROM deliveries WHERE id = :did"),
                {"did": str(new_del.id)},
            )
            delivery_session.commit()


def test_dual_lifecycle_auto_session():
    service = DeliveryService()
    delivery = service.get_active_by_shipment_id(KNOWN_SHIPMENT_ID)
    assert delivery is not None
    assert delivery.id == KNOWN_DELIVERY_ID


def test_delivery_db_isolation(delivery_session):
    url = str(delivery_session.bind.url)
    assert "delivery_db" in url
