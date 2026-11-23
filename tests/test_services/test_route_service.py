"""
Unit tests for RouteService and RouteRepository in route_service.
Isolation: strictly route_db.
"""
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import text
from services.route_service.repository import RouteRepository
from services.route_service.service import RouteService
from services.route_service.schemas import (
    RouteDTO,
    RouteStageDTO,
    CreateRouteInputDTO,
    CreateRouteStageInputDTO,
)
from tests.test_services.conftest import KNOWN_ROUTE_ID, KNOWN_SHIPMENT_ID, NON_EXISTENT_UUID


def test_get_route_by_shipment_id_found(route_session):
    service = RouteService(RouteRepository(route_session))
    route = service.get_by_shipment_id(KNOWN_SHIPMENT_ID)

    assert route is not None
    assert isinstance(route, RouteDTO)
    assert route.id == KNOWN_ROUTE_ID
    assert route.shipment_id == KNOWN_SHIPMENT_ID
    assert route.total_distance_km == Decimal("352.40")
    assert route.estimated_duration_min == 360
    assert route.status == "ACTIVE"
    assert len(route.stages) == 3


def test_get_route_by_shipment_id_not_found(route_session):
    service = RouteService(RouteRepository(route_session))
    assert service.get_by_shipment_id(NON_EXISTENT_UUID) is None


def test_get_route_stages_ordering_and_content(route_session):
    service = RouteService(RouteRepository(route_session))
    stages = service.get_stages_by_route_id(KNOWN_ROUTE_ID)

    assert len(stages) == 3
    orders = [s.stage_order for s in stages]
    assert orders == [1, 2, 3]

    types = [s.stage_type for s in stages]
    assert types == ["PICKUP", "MAIN_TRANSIT", "LAST_MILE"]

    statuses = [s.status for s in stages]
    assert statuses == ["COMPLETED", "IN_PROGRESS", "PENDING"]


def test_create_route_and_add_stage(route_session):
    service = RouteService(route_session)
    mock_shipment_id = uuid.uuid4()
    route_in = CreateRouteInputDTO(
        shipmentId=mock_shipment_id,
        totalDistanceKm=Decimal("150.00"),
        estimatedDurationMin=120,
        currentStageOrder=1,
        status="ACTIVE",
    )
    new_route = None
    try:
        new_route = service.create_route(route_in)
        assert new_route.shipment_id == mock_shipment_id
        assert new_route.total_distance_km == Decimal("150.00")

        stage_in = CreateRouteStageInputDTO(
            routeId=new_route.id,
            stageOrder=1,
            stageType="PICKUP",
            originPoint="Точка А",
            destPoint="Точка Б",
            plannedStart=datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc),
            plannedEnd=datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc),
            status="PENDING",
        )
        new_stage = service.add_route_stage(stage_in)
        assert new_stage.stage_type == "PICKUP"
        assert new_stage.stage_order == 1
    finally:
        if new_route:
            route_session.execute(
                text("DELETE FROM route_stages WHERE route_id = :rid"),
                {"rid": str(new_route.id)},
            )
            route_session.execute(
                text("DELETE FROM routes WHERE id = :rid"),
                {"rid": str(new_route.id)},
            )
            route_session.commit()


def test_dual_lifecycle_auto_session():
    service = RouteService()
    route = service.get_by_shipment_id(KNOWN_SHIPMENT_ID)
    assert route is not None
    assert route.id == KNOWN_ROUTE_ID


def test_route_db_isolation(route_session):
    url = str(route_session.bind.url)
    assert "route_db" in url
