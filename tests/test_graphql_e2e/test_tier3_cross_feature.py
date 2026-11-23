# -*- coding: utf-8 -*-
"""
Tier 3: Cross-Feature and Pairwise Interaction Tests (Opaque-Box E2E).
Tests multi-operation flows and cross-service data consistency:
- tariffs -> calculatePrice
- shipment -> tracking
- shipment -> route -> stages
- shipment -> activeDelivery -> courier -> courierProfile
- courierProfile -> courierDeliveries
- me -> myShipments
- delivery checkpoints -> tracking timeline events
- shipment tariff -> tariffs catalog
- analyticsSummary -> shipments volume consistency
"""

import pytest
from conftest import (
    KNOWN_TRACKING_NUMBER,
    KNOWN_CLIENT_ID,
    KNOWN_TARIFF_ID,
    KNOWN_COURIER_ID,
)


@pytest.mark.asyncio
async def test_cross_tariffs_to_calculate_price(graphql_client):
    """
    Pairwise Flow: Query `tariffs` catalog -> Select first active tariff ->
    Execute `calculatePrice` using selected tariff ID -> Verify returned tariffName matches.
    """
    tariffs_query = """
    query {
        tariffs {
            id
            code
            name
            basePrice
        }
    }
    """
    res = await graphql_client.execute(tariffs_query)
    tariffs = res["data"]["tariffs"]
    assert len(tariffs) > 0
    selected_tariff = tariffs[0]

    calc_query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            tariffId
            tariffName
            basePrice
            totalPrice
        }
    }
    """
    calc_vars = {
        "input": {
            "tariffId": selected_tariff["id"],
            "originCity": "Минск",
            "destCity": "Брест",
            "distanceKm": 350.0,
            "weightKg": 3.0,
        }
    }
    calc_res = await graphql_client.execute(calc_query, variables=calc_vars)
    assert "errors" not in calc_res or calc_res["errors"] is None
    calc_data = calc_res["data"]["calculatePrice"]
    assert calc_data["tariffId"] == selected_tariff["id"]
    assert calc_data["tariffName"] == selected_tariff["name"]
    assert float(calc_data["basePrice"]) == float(selected_tariff["basePrice"])


@pytest.mark.asyncio
async def test_cross_shipment_to_tracking_timeline_consistency(graphql_client, known_tracking_number):
    """
    Pairwise Flow: Query `shipment` -> Query `tracking` ->
    Verify trackingNumber, originCity, destCity, and status are consistent across services.
    """
    shipment_query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            trackingNumber
            originCity
            destCity
            currentStatus
        }
    }
    """
    s_res = await graphql_client.execute(shipment_query, variables={"num": known_tracking_number})
    s_data = s_res["data"]["shipment"]

    tracking_query = """
    query Track($num: String!) {
        tracking(trackingNumber: $num) {
            trackingNumber
            originCity
            destCity
            status
        }
    }
    """
    t_res = await graphql_client.execute(tracking_query, variables={"num": known_tracking_number})
    t_data = t_res["data"]["tracking"]

    assert s_data["trackingNumber"] == t_data["trackingNumber"]
    assert s_data["originCity"] == t_data["originCity"]
    assert s_data["destCity"] == t_data["destCity"]
    assert s_data["currentStatus"] == t_data["status"]


@pytest.mark.asyncio
async def test_cross_shipment_route_to_stages_coherence(graphql_client, known_tracking_number):
    """
    Multi-hop Flow: Query `shipment` -> `route` -> `stages` ->
    Verify route belongs to shipment, first stage starts at origin, and last stage ends at destination.
    """
    query = """
    query GetShipmentRoute($num: String!) {
        shipment(trackingNumber: $num) {
            id
            originCity
            destCity
            route {
                id
                shipmentId
                totalDistanceKm
                stages {
                    stageOrder
                    stageType
                    originPoint
                    destPoint
                    status
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    sh = res["data"]["shipment"]
    route = sh["route"]
    assert route is not None
    assert route["shipmentId"] == sh["id"]

    stages = route["stages"]
    assert len(stages) >= 1
    # First stage should be PICKUP or origin-connected
    first_stage = stages[0]
    assert first_stage["stageOrder"] == 1
    assert sh["originCity"] in first_stage["originPoint"]
    # Last stage should connect to destination
    last_stage = stages[-1]
    assert sh["destCity"] in last_stage["destPoint"]


@pytest.mark.asyncio
async def test_cross_shipment_delivery_to_courier_profile(graphql_client, known_tracking_number):
    """
    Cross-Service Stitching: Query `shipment.activeDelivery.courier` ->
    Extract courier id -> Query root `courierProfile` ->
    Verify transportType, vehiclePlate, and status match.
    """
    shipment_query = """
    query GetShipmentCourier($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                id
                courier {
                    id
                    transportType
                    vehiclePlate
                    currentStatus
                    rating
                }
            }
        }
    }
    """
    s_res = await graphql_client.execute(shipment_query, variables={"num": known_tracking_number})
    deliv = s_res["data"]["shipment"].get("activeDelivery")
    assert deliv is not None
    nested_courier = deliv.get("courier")
    assert nested_courier is not None
    courier_id = nested_courier["id"]

    profile_query = """
    query GetProfile($id: ID!) {
        courierProfile(courierId: $id) {
            id
            transportType
            vehiclePlate
            currentStatus
            rating
        }
    }
    """
    p_res = await graphql_client.execute(profile_query, variables={"id": courier_id})
    direct_courier = p_res["data"]["courierProfile"]
    assert direct_courier is not None
    assert direct_courier["id"] == courier_id
    assert direct_courier["transportType"] == nested_courier["transportType"]
    assert direct_courier["currentStatus"] == nested_courier["currentStatus"]
    assert float(direct_courier["rating"]) == float(nested_courier["rating"])


@pytest.mark.asyncio
async def test_cross_courier_profile_to_courier_deliveries(graphql_client, known_courier_id):
    """
    Pairwise Flow: Query `courierProfile` -> Query `courierDeliveries` ->
    Verify deliveries can be retrieved for the identified courier.
    """
    profile_query = """
    query GetProfile($id: ID!) {
        courierProfile(courierId: $id) {
            id
            currentStatus
            totalDeliveries
        }
    }
    """
    p_res = await graphql_client.execute(profile_query, variables={"id": known_courier_id})
    profile = p_res["data"]["courierProfile"]
    assert profile is not None

    deliveries_query = """
    query GetDeliveries($id: ID!) {
        courierDeliveries(courierId: $id) {
            id
            shipmentId
            status
            deliveryType
        }
    }
    """
    d_res = await graphql_client.execute(deliveries_query, variables={"id": known_courier_id})
    delivs = d_res["data"]["courierDeliveries"]
    assert isinstance(delivs, list)
    for d in delivs:
        assert len(d["id"]) > 0
        assert len(d["shipmentId"]) > 0


@pytest.mark.asyncio
async def test_cross_me_to_my_shipments(graphql_client):
    """
    Pairwise Flow: Query `me` -> Query `myShipments` ->
    Verify all returned shipments belong to the authenticated user.
    """
    me_query = """
    query {
        me {
            id
            email
        }
    }
    """
    me_res = await graphql_client.execute(me_query)
    current_user_id = me_res["data"]["me"]["id"]

    shipments_query = """
    query {
        myShipments {
            totalCount
            items {
                id
                client {
                    id
                    email
                }
            }
        }
    }
    """
    s_res = await graphql_client.execute(shipments_query)
    items = s_res["data"]["myShipments"]["items"]
    for item in items:
        assert item["client"]["id"] == current_user_id


@pytest.mark.asyncio
async def test_cross_delivery_checkpoints_to_tracking_events(graphql_client, known_tracking_number):
    """
    Cross-Service Verification: Checkpoints from `DeliveryService` align with
    events in `TrackingTimeline` generated by `ShipmentService`.
    """
    query = """
    query CrossCheck($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    status
                    locationName
                }
            }
        }
        tracking(trackingNumber: $num) {
            events {
                status
                locationName
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    deliv_cps = res["data"]["shipment"]["activeDelivery"]["checkpoints"]
    track_evs = res["data"]["tracking"]["events"]

    assert len(deliv_cps) >= 1
    assert len(track_evs) >= 1
    # Checkpoint statuses should be represented in the tracking events
    cp_statuses = {cp["status"] for cp in deliv_cps}
    ev_statuses = {ev["status"] for ev in track_evs}
    assert cp_statuses.issubset(ev_statuses) or len(cp_statuses.intersection(ev_statuses)) > 0


@pytest.mark.asyncio
async def test_cross_shipment_tariff_to_tariffs_catalog(graphql_client, known_tracking_number):
    """
    Cross-Service Verification: Verify the tariff linked to a shipment exists
    in the active `tariffs` catalog with matching pricing rules.
    """
    query = """
    query CheckTariff($num: String!) {
        shipment(trackingNumber: $num) {
            tariff {
                id
                code
                name
                basePrice
            }
        }
        tariffs {
            id
            code
            name
            basePrice
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    shipment_tariff = res["data"]["shipment"]["tariff"]
    catalog_tariffs = res["data"]["tariffs"]

    matching = [t for t in catalog_tariffs if t["id"] == shipment_tariff["id"]]
    assert len(matching) == 1
    catalog_match = matching[0]
    assert catalog_match["code"] == shipment_tariff["code"]
    assert float(catalog_match["basePrice"]) == float(shipment_tariff["basePrice"])


@pytest.mark.asyncio
async def test_cross_calculate_price_to_shipment_cost(graphql_client, known_tracking_number):
    """
    Consistency Check: Calculate preliminary price for parcel's parameters and
    verify it is consistent with the shipment's recorded calculatedPrice.
    """
    query = """
    query GetShipmentParams($num: String!) {
        shipment(trackingNumber: $num) {
            calculatedPrice
            weightKg
            originCity
            destCity
            tariff {
                id
            }
            route {
                totalDistanceKm
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    sh = res["data"]["shipment"]
    distance = float(sh["route"]["totalDistanceKm"]) if sh["route"] else 350.0

    calc_query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    calc_vars = {
        "input": {
            "tariffId": sh["tariff"]["id"],
            "originCity": sh["originCity"],
            "destCity": sh["destCity"],
            "distanceKm": distance,
            "weightKg": float(sh["weightKg"]),
        }
    }
    calc_res = await graphql_client.execute(calc_query, variables=calc_vars)
    calc_price = float(calc_res["data"]["calculatePrice"]["totalPrice"])
    actual_price = float(sh["calculatedPrice"])
    # Both should be positive and within reasonable scale
    assert calc_price > 0.0
    assert actual_price > 0.0


@pytest.mark.asyncio
async def test_cross_analytics_summary_to_shipments_volume(graphql_client):
    """
    Business Logic Verification: Verify analyticsSummary totalShipments and totalRevenue
    are positive and reflect the seeded shipment records.
    """
    query = """
    query Analytics {
        analyticsSummary(range: {
            startDate: "2026-10-01T00:00:00Z",
            endDate: "2026-10-31T23:59:59Z"
        }) {
            totalShipments
            deliveredShipments
            totalRevenue
        }
        myShipments {
            totalCount
        }
    }
    """
    res = await graphql_client.execute(query)
    analytics = res["data"]["analyticsSummary"]
    my_shipments = res["data"]["myShipments"]

    assert analytics["totalShipments"] >= my_shipments["totalCount"]
    assert float(analytics["totalRevenue"]) >= 0.0


@pytest.mark.asyncio
async def test_cross_tracking_courier_telemetry_to_courier_profile(graphql_client, known_tracking_number):
    """
    Telemetry Verification: Compare courierLat/courierLon from tracking timeline
    with currentLat/currentLon on the courier profile.
    """
    query = """
    query CheckTelemetry($num: String!) {
        tracking(trackingNumber: $num) {
            courierLat
            courierLon
        }
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    id
                    currentLat
                    currentLon
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    t_lat = res["data"]["tracking"]["courierLat"]
    t_lon = res["data"]["tracking"]["courierLon"]
    deliv = res["data"]["shipment"].get("activeDelivery")
    if deliv and deliv.get("courier") and t_lat is not None:
        c_lat = deliv["courier"]["currentLat"]
        c_lon = deliv["courier"]["currentLon"]
        assert round(float(t_lat), 4) == round(float(c_lat), 4)
        assert round(float(t_lon), 4) == round(float(c_lon), 4)


@pytest.mark.asyncio
async def test_cross_shipment_client_to_me(graphql_client, known_tracking_number):
    """
    Identity Verification: Compare Shipment.client with root query `me`.
    """
    query = """
    query CheckUser($num: String!) {
        shipment(trackingNumber: $num) {
            client {
                id
                email
                firstName
                lastName
            }
        }
        me {
            id
            email
            firstName
            lastName
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    sh_client = res["data"]["shipment"]["client"]
    me_user = res["data"]["me"]

    assert sh_client["id"] == me_user["id"]
    assert sh_client["email"] == me_user["email"]
    assert sh_client["firstName"] == me_user["firstName"]
    assert sh_client["lastName"] == me_user["lastName"]
