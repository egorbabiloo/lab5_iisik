# -*- coding: utf-8 -*-
"""
Tier 1: Comprehensive Feature Coverage Tests (Opaque-Box E2E).
Covers all 9 root queries and 7 relationship field resolvers.
Minimum >=5 test cases per feature area (total 80 tests).
"""

import pytest
from conftest import (
    KNOWN_TRACKING_NUMBER,
    KNOWN_CLIENT_ID,
    KNOWN_TARIFF_ID,
    KNOWN_COURIER_ID,
    NON_EXISTENT_TRACKING,
)


# ==============================================================================
# Feature 1: Root Query `tariffs` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_tariffs_returns_list_of_active_tariffs(graphql_client):
    """Verify `tariffs` query returns non-empty list of tariffs without errors."""
    query = """
    query {
        tariffs {
            id
            code
            name
            basePrice
            pricePerKg
            pricePerKm
            urgencyMultiplier
            maxDeliveryDays
            isActive
        }
    }
    """
    res = await graphql_client.execute(query)
    assert "errors" not in res or res["errors"] is None
    tariffs = res.get("data", {}).get("tariffs")
    assert isinstance(tariffs, list)
    assert len(tariffs) >= 1


@pytest.mark.asyncio
async def test_tariffs_required_scalar_types(graphql_client):
    """Verify all tariffs have non-empty string identifier, code, and name."""
    query = """
    query {
        tariffs {
            id
            code
            name
        }
    }
    """
    res = await graphql_client.execute(query)
    tariffs = res.get("data", {}).get("tariffs", [])
    for t in tariffs:
        assert isinstance(t["id"], str) and len(t["id"]) > 0
        assert isinstance(t["code"], str) and len(t["code"]) > 0
        assert isinstance(t["name"], str) and len(t["name"]) > 0


@pytest.mark.asyncio
async def test_tariffs_numeric_pricing_fields_positive(graphql_client):
    """Verify basePrice, pricePerKg, and pricePerKm are positive numeric values."""
    query = """
    query {
        tariffs {
            basePrice
            pricePerKg
            pricePerKm
        }
    }
    """
    res = await graphql_client.execute(query)
    tariffs = res.get("data", {}).get("tariffs", [])
    for t in tariffs:
        assert float(t["basePrice"]) > 0.0
        assert float(t["pricePerKg"]) >= 0.0
        assert float(t["pricePerKm"]) >= 0.0


@pytest.mark.asyncio
async def test_tariffs_delivery_time_and_urgency(graphql_client):
    """Verify urgencyMultiplier >= 1.0 and maxDeliveryDays > 0."""
    query = """
    query {
        tariffs {
            urgencyMultiplier
            maxDeliveryDays
        }
    }
    """
    res = await graphql_client.execute(query)
    tariffs = res.get("data", {}).get("tariffs", [])
    for t in tariffs:
        assert float(t["urgencyMultiplier"]) >= 1.0
        assert int(t["maxDeliveryDays"]) > 0


@pytest.mark.asyncio
async def test_tariffs_all_returned_are_active(graphql_client):
    """Verify every item returned by `tariffs` has isActive == True."""
    query = """
    query {
        tariffs {
            code
            isActive
        }
    }
    """
    res = await graphql_client.execute(query)
    tariffs = res.get("data", {}).get("tariffs", [])
    for t in tariffs:
        assert t["isActive"] is True


# ==============================================================================
# Feature 2: Root Query `calculatePrice` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_calculate_price_standard_success(graphql_client, known_tariff_id):
    """Verify calculatePrice returns all expected fields for standard input."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            tariffId
            tariffName
            estimatedDistanceKm
            basePrice
            weightPrice
            distancePrice
            totalPrice
            estimatedDeliveryDays
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Брест",
            "distanceKm": 350.0,
            "weightKg": 2.5,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    data = res.get("data", {}).get("calculatePrice")
    assert data is not None
    assert data["tariffId"] == known_tariff_id
    assert float(data["totalPrice"]) > 0.0
    assert float(data["estimatedDistanceKm"]) == 350.0
    assert int(data["estimatedDeliveryDays"]) > 0


@pytest.mark.asyncio
async def test_calculate_price_breakdown_consistency(graphql_client, known_tariff_id):
    """Verify totalPrice matches sum of basePrice + weightPrice + distancePrice scaled by multiplier."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            basePrice
            weightPrice
            distancePrice
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Гродно",
            "distanceKm": 280.0,
            "weightKg": 5.0,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    data = res["data"]["calculatePrice"]
    base = float(data["basePrice"])
    weight = float(data["weightPrice"])
    dist = float(data["distancePrice"])
    total = float(data["totalPrice"])
    # Total price must be >= base + weight + dist (multiplier >= 1.0)
    assert total >= round(base + weight + dist, 1) - 0.5


@pytest.mark.asyncio
async def test_calculate_price_weight_scaling(graphql_client, known_tariff_id):
    """Verify weightPrice scales proportionally when weight increases."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            weightPrice
            totalPrice
        }
    }
    """
    v1 = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Витебск",
            "distanceKm": 290.0,
            "weightKg": 2.0,
        }
    }
    v2 = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Витебск",
            "distanceKm": 290.0,
            "weightKg": 10.0,
        }
    }
    r1 = await graphql_client.execute(query, variables=v1)
    r2 = await graphql_client.execute(query, variables=v2)
    wp1 = float(r1["data"]["calculatePrice"]["weightPrice"])
    wp2 = float(r2["data"]["calculatePrice"]["weightPrice"])
    assert wp2 > wp1
    # Weight 10kg is 5x 2kg, so wp2 should be approximately 5x wp1
    assert abs((wp2 / wp1) - 5.0) < 0.2


@pytest.mark.asyncio
async def test_calculate_price_distance_scaling(graphql_client, known_tariff_id):
    """Verify distancePrice scales proportionally when distance increases."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            distancePrice
            totalPrice
        }
    }
    """
    v1 = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Борисов",
            "distanceKm": 75.0,
            "weightKg": 3.0,
        }
    }
    v2 = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Гомель",
            "distanceKm": 310.0,
            "weightKg": 3.0,
        }
    }
    r1 = await graphql_client.execute(query, variables=v1)
    r2 = await graphql_client.execute(query, variables=v2)
    dp1 = float(r1["data"]["calculatePrice"]["distancePrice"])
    dp2 = float(r2["data"]["calculatePrice"]["distancePrice"])
    assert dp2 > dp1


@pytest.mark.asyncio
async def test_calculate_price_estimated_delivery_days(graphql_client, known_tariff_id):
    """Verify estimatedDeliveryDays is returned as positive integer."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            estimatedDeliveryDays
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Могилев",
            "distanceKm": 200.0,
            "weightKg": 1.0,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    days = res["data"]["calculatePrice"]["estimatedDeliveryDays"]
    assert isinstance(days, int) and days > 0


# ==============================================================================
# Feature 3: Root Query `shipment` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_shipment_by_tracking_number_returns_object(graphql_client, known_tracking_number):
    """Verify shipment query by valid trackingNumber returns non-null shipment."""
    query = """
    query GetShipment($trackingNumber: String!) {
        shipment(trackingNumber: $trackingNumber) {
            id
            trackingNumber
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    shipment = res.get("data", {}).get("shipment")
    assert shipment is not None
    assert shipment["trackingNumber"] == known_tracking_number


@pytest.mark.asyncio
async def test_shipment_core_scalar_attributes(graphql_client, known_tracking_number):
    """Verify shipment returns core addresses, recipient, and timestamps."""
    query = """
    query GetShipment($trackingNumber: String!) {
        shipment(trackingNumber: $trackingNumber) {
            originCity
            originAddress
            destCity
            destAddress
            recipientName
            recipientPhone
            createdAt
            updatedAt
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    shipment = res["data"]["shipment"]
    assert len(shipment["originCity"]) > 0
    assert len(shipment["destCity"]) > 0
    assert len(shipment["recipientName"]) > 0
    assert len(shipment["recipientPhone"]) > 0
    assert "T" in shipment["createdAt"]


@pytest.mark.asyncio
async def test_shipment_status_valid_enum(graphql_client, known_tracking_number):
    """Verify currentStatus is a member of ShipmentStatus enum."""
    valid_statuses = {
        "CREATED", "ASSIGNED", "PICKED_UP", "IN_TRANSIT",
        "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"
    }
    query = """
    query GetShipment($trackingNumber: String!) {
        shipment(trackingNumber: $trackingNumber) {
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    status = res["data"]["shipment"]["currentStatus"]
    assert status in valid_statuses


@pytest.mark.asyncio
async def test_shipment_dimensions_field_resolver(graphql_client, known_tracking_number):
    """Verify dimensions field resolver returns length, width, height."""
    query = """
    query GetShipment($trackingNumber: String!) {
        shipment(trackingNumber: $trackingNumber) {
            weightKg
            dimensions {
                lengthCm
                widthCm
                heightCm
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    shipment = res["data"]["shipment"]
    assert float(shipment["weightKg"]) > 0.0
    dims = shipment["dimensions"]
    assert float(dims["lengthCm"]) > 0.0
    assert float(dims["widthCm"]) > 0.0
    assert float(dims["heightCm"]) > 0.0


@pytest.mark.asyncio
async def test_shipment_unknown_tracking_returns_null(graphql_client, non_existent_tracking):
    """Verify non-existent trackingNumber returns null without raising 500 error."""
    query = """
    query GetShipment($trackingNumber: String!) {
        shipment(trackingNumber: $trackingNumber) {
            id
            trackingNumber
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": non_existent_tracking})
    assert res.get("data", {}).get("shipment") is None


# ==============================================================================
# Feature 4: Root Query `myShipments` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_my_shipments_returns_connection_structure(graphql_client):
    """Verify myShipments returns items list and totalCount."""
    query = """
    query {
        myShipments {
            totalCount
            items {
                id
                trackingNumber
                currentStatus
            }
        }
    }
    """
    res = await graphql_client.execute(query)
    assert "errors" not in res or res["errors"] is None
    conn = res.get("data", {}).get("myShipments")
    assert conn is not None
    assert isinstance(conn["totalCount"], int)
    assert isinstance(conn["items"], list)


@pytest.mark.asyncio
async def test_my_shipments_total_count_matches_items(graphql_client):
    """Verify totalCount is greater than or equal to items list length."""
    query = """
    query {
        myShipments {
            totalCount
            items {
                id
            }
        }
    }
    """
    res = await graphql_client.execute(query)
    conn = res["data"]["myShipments"]
    assert conn["totalCount"] >= len(conn["items"])


@pytest.mark.asyncio
async def test_my_shipments_items_have_valid_identifiers(graphql_client):
    """Verify all items in myShipments have non-empty trackingNumber."""
    query = """
    query {
        myShipments {
            items {
                id
                trackingNumber
            }
        }
    }
    """
    res = await graphql_client.execute(query)
    items = res["data"]["myShipments"]["items"]
    for item in items:
        assert isinstance(item["id"], str) and len(item["id"]) > 0
        assert isinstance(item["trackingNumber"], str) and len(item["trackingNumber"]) > 0


@pytest.mark.asyncio
async def test_my_shipments_items_have_pricing_and_dates(graphql_client):
    """Verify items in myShipments have calculatedPrice and createdAt."""
    query = """
    query {
        myShipments {
            items {
                calculatedPrice
                createdAt
            }
        }
    }
    """
    res = await graphql_client.execute(query)
    items = res["data"]["myShipments"]["items"]
    for item in items:
        assert float(item["calculatedPrice"]) > 0.0
        assert "T" in item["createdAt"]


@pytest.mark.asyncio
async def test_my_shipments_nested_destinations(graphql_client):
    """Verify originCity and destCity in myShipments items."""
    query = """
    query {
        myShipments {
            items {
                originCity
                destCity
                recipientName
            }
        }
    }
    """
    res = await graphql_client.execute(query)
    items = res["data"]["myShipments"]["items"]
    for item in items:
        assert len(item["originCity"]) > 0
        assert len(item["destCity"]) > 0


# ==============================================================================
# Feature 5: Root Query `tracking` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_tracking_by_valid_tracking_number(graphql_client, known_tracking_number):
    """Verify tracking returns timeline with matching trackingNumber."""
    query = """
    query Track($trackingNumber: String!) {
        tracking(trackingNumber: $trackingNumber) {
            trackingNumber
            status
            originCity
            destCity
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    timeline = res.get("data", {}).get("tracking")
    assert timeline is not None
    assert timeline["trackingNumber"] == known_tracking_number
    assert len(timeline["originCity"]) > 0
    assert len(timeline["destCity"]) > 0


@pytest.mark.asyncio
async def test_tracking_events_timeline_present(graphql_client, known_tracking_number):
    """Verify tracking events list is populated."""
    query = """
    query Track($trackingNumber: String!) {
        tracking(trackingNumber: $trackingNumber) {
            events {
                timestamp
                status
                locationName
                description
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    events = res["data"]["tracking"]["events"]
    assert isinstance(events, list)
    assert len(events) >= 1
    for ev in events:
        assert len(ev["status"]) > 0
        assert len(ev["locationName"]) > 0


@pytest.mark.asyncio
async def test_tracking_events_chronological_order(graphql_client, known_tracking_number):
    """Verify tracking events are ordered chronologically by timestamp."""
    query = """
    query Track($trackingNumber: String!) {
        tracking(trackingNumber: $trackingNumber) {
            events {
                timestamp
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    events = res["data"]["tracking"]["events"]
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_tracking_courier_gps_telemetry(graphql_client, known_tracking_number):
    """Verify courierLat and courierLon are valid floats or null."""
    query = """
    query Track($trackingNumber: String!) {
        tracking(trackingNumber: $trackingNumber) {
            courierLat
            courierLon
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    tl = res["data"]["tracking"]
    lat = tl["courierLat"]
    lon = tl["courierLon"]
    if lat is not None:
        assert -90.0 <= float(lat) <= 90.0
    if lon is not None:
        assert -180.0 <= float(lon) <= 180.0


@pytest.mark.asyncio
async def test_tracking_timeline_status_consistency(graphql_client, known_tracking_number):
    """Verify tracking status is valid ShipmentStatus enum."""
    valid_statuses = {
        "CREATED", "ASSIGNED", "PICKED_UP", "IN_TRANSIT",
        "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"
    }
    query = """
    query Track($trackingNumber: String!) {
        tracking(trackingNumber: $trackingNumber) {
            status
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    status = res["data"]["tracking"]["status"]
    assert status in valid_statuses


# ==============================================================================
# Feature 6: Root Query `courierProfile` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_courier_profile_by_id_returns_object(graphql_client, known_courier_id):
    """Verify courierProfile by known courierId returns courier details."""
    query = """
    query GetCourier($id: ID!) {
        courierProfile(courierId: $id) {
            id
            userId
            transportType
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": known_courier_id})
    assert "errors" not in res or res["errors"] is None
    courier = res.get("data", {}).get("courierProfile")
    assert courier is not None
    assert courier["id"] == known_courier_id


@pytest.mark.asyncio
async def test_courier_profile_transport_type(graphql_client, known_courier_id):
    """Verify courier transportType is member of TransportType enum."""
    valid_transports = {"FOOT", "BICYCLE", "CAR", "VAN"}
    query = """
    query GetCourier($id: ID!) {
        courierProfile(courierId: $id) {
            transportType
            vehiclePlate
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": known_courier_id})
    t_type = res["data"]["courierProfile"]["transportType"]
    assert t_type in valid_transports


@pytest.mark.asyncio
async def test_courier_profile_status_enum(graphql_client, known_courier_id):
    """Verify courier currentStatus is member of CourierStatus enum."""
    valid_statuses = {"AVAILABLE", "BUSY", "OFFLINE"}
    query = """
    query GetCourier($id: ID!) {
        courierProfile(courierId: $id) {
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": known_courier_id})
    status = res["data"]["courierProfile"]["currentStatus"]
    assert status in valid_statuses


@pytest.mark.asyncio
async def test_courier_profile_metrics(graphql_client, known_courier_id):
    """Verify courier rating, maxPayloadKg, and totalDeliveries."""
    query = """
    query GetCourier($id: ID!) {
        courierProfile(courierId: $id) {
            rating
            totalDeliveries
            maxPayloadKg
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": known_courier_id})
    cp = res["data"]["courierProfile"]
    assert 0.0 <= float(cp["rating"]) <= 5.0
    assert int(cp["totalDeliveries"]) >= 0
    assert float(cp["maxPayloadKg"]) > 0.0


@pytest.mark.asyncio
async def test_courier_profile_default_omitted_id(graphql_client):
    """Verify courierProfile with omitted courierId returns courier or null gracefully."""
    query = """
    query {
        courierProfile {
            id
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query)
    assert "data" in res


# ==============================================================================
# Feature 7: Root Query `courierDeliveries` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_courier_deliveries_by_courier_id(graphql_client, known_courier_id):
    """Verify courierDeliveries returns list for valid courier."""
    query = """
    query GetDeliveries($courierId: ID!) {
        courierDeliveries(courierId: $courierId) {
            id
            shipmentId
            deliveryType
            status
            windowStart
            windowEnd
        }
    }
    """
    res = await graphql_client.execute(query, variables={"courierId": known_courier_id})
    assert "errors" not in res or res["errors"] is None
    delivs = res.get("data", {}).get("courierDeliveries")
    assert isinstance(delivs, list)


@pytest.mark.asyncio
async def test_courier_deliveries_filter_assigned(graphql_client, known_courier_id):
    """Verify filtering courier deliveries by ASSIGNED status."""
    query = """
    query GetDeliveries($courierId: ID!) {
        courierDeliveries(courierId: $courierId, status: ASSIGNED) {
            id
            status
        }
    }
    """
    res = await graphql_client.execute(query, variables={"courierId": known_courier_id})
    delivs = res.get("data", {}).get("courierDeliveries", [])
    for d in delivs:
        assert d["status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_courier_deliveries_filter_delivered(graphql_client, known_courier_id):
    """Verify filtering courier deliveries by DELIVERED status."""
    query = """
    query GetDeliveries($courierId: ID!) {
        courierDeliveries(courierId: $courierId, status: DELIVERED) {
            id
            status
        }
    }
    """
    res = await graphql_client.execute(query, variables={"courierId": known_courier_id})
    delivs = res.get("data", {}).get("courierDeliveries", [])
    for d in delivs:
        assert d["status"] == "DELIVERED"


@pytest.mark.asyncio
async def test_courier_deliveries_time_windows(graphql_client, known_courier_id):
    """Verify delivery windowStart is before or equal to windowEnd."""
    query = """
    query GetDeliveries($courierId: ID!) {
        courierDeliveries(courierId: $courierId) {
            windowStart
            windowEnd
        }
    }
    """
    res = await graphql_client.execute(query, variables={"courierId": known_courier_id})
    delivs = res.get("data", {}).get("courierDeliveries", [])
    for d in delivs:
        assert d["windowStart"] <= d["windowEnd"]


@pytest.mark.asyncio
async def test_courier_deliveries_delivery_type_enum(graphql_client, known_courier_id):
    """Verify deliveryType is member of DeliveryType enum."""
    valid_types = {"FIRST_MILE_PICKUP", "LAST_MILE_DROPOFF"}
    query = """
    query GetDeliveries($courierId: ID!) {
        courierDeliveries(courierId: $courierId) {
            deliveryType
        }
    }
    """
    res = await graphql_client.execute(query, variables={"courierId": known_courier_id})
    delivs = res.get("data", {}).get("courierDeliveries", [])
    for d in delivs:
        assert d["deliveryType"] in valid_types


# ==============================================================================
# Feature 8: Root Query `analyticsSummary` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_analytics_summary_valid_date_range(graphql_client):
    """Verify analyticsSummary returns summary object for valid date range."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            periodStart
            periodEnd
            totalShipments
            deliveredShipments
            totalRevenue
            averageDeliveryDurationMin
            slaComplianceRate
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-01T00:00:00Z",
            "endDate": "2026-10-31T23:59:59Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    summary = res.get("data", {}).get("analyticsSummary")
    assert summary is not None


@pytest.mark.asyncio
async def test_analytics_summary_volume_metrics(graphql_client):
    """Verify totalShipments and deliveredShipments are non-negative and consistent."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            totalShipments
            deliveredShipments
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-01T00:00:00Z",
            "endDate": "2026-10-31T23:59:59Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    s = res["data"]["analyticsSummary"]
    assert s["totalShipments"] >= 0
    assert s["deliveredShipments"] >= 0
    assert s["totalShipments"] >= s["deliveredShipments"]


@pytest.mark.asyncio
async def test_analytics_summary_financial_metrics(graphql_client):
    """Verify totalRevenue is non-negative Decimal value."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            totalRevenue
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-01T00:00:00Z",
            "endDate": "2026-10-31T23:59:59Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    rev = float(res["data"]["analyticsSummary"]["totalRevenue"])
    assert rev >= 0.0


@pytest.mark.asyncio
async def test_analytics_summary_sla_compliance_rate(graphql_client):
    """Verify slaComplianceRate is between 0.0 and 1.0."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            slaComplianceRate
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-01T00:00:00Z",
            "endDate": "2026-10-31T23:59:59Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    sla = float(res["data"]["analyticsSummary"]["slaComplianceRate"])
    assert 0.0 <= sla <= 1.0


@pytest.mark.asyncio
async def test_analytics_summary_duration_metric(graphql_client):
    """Verify averageDeliveryDurationMin is non-negative float."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            averageDeliveryDurationMin
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-01T00:00:00Z",
            "endDate": "2026-10-31T23:59:59Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    avg_dur = float(res["data"]["analyticsSummary"]["averageDeliveryDurationMin"])
    assert avg_dur >= 0.0


# ==============================================================================
# Feature 9: Root Query `me` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_me_authenticated_user_profile(graphql_client):
    """Verify `me` query returns profile of current authenticated user."""
    query = """
    query {
        me {
            id
            email
            phone
            firstName
            lastName
            role
            accountStatus
            createdAt
        }
    }
    """
    res = await graphql_client.execute(query)
    assert "errors" not in res or res["errors"] is None
    me = res.get("data", {}).get("me")
    assert me is not None
    assert len(me["id"]) > 0


@pytest.mark.asyncio
async def test_me_role_is_valid_enum(graphql_client):
    """Verify `me` returns valid RoleType enum."""
    valid_roles = {"ROLE_CLIENT", "ROLE_COURIER", "ROLE_ADMIN"}
    query = """
    query {
        me {
            role
        }
    }
    """
    res = await graphql_client.execute(query)
    role = res["data"]["me"]["role"]
    assert role in valid_roles


@pytest.mark.asyncio
async def test_me_account_status_active(graphql_client):
    """Verify `me` accountStatus is ACTIVE."""
    query = """
    query {
        me {
            accountStatus
        }
    }
    """
    res = await graphql_client.execute(query)
    status = res["data"]["me"]["accountStatus"]
    assert status == "ACTIVE"


@pytest.mark.asyncio
async def test_me_contact_info_format(graphql_client):
    """Verify email contains @ and phone is non-empty."""
    query = """
    query {
        me {
            email
            phone
        }
    }
    """
    res = await graphql_client.execute(query)
    me = res["data"]["me"]
    assert "@" in me["email"]
    assert len(me["phone"]) >= 7


@pytest.mark.asyncio
async def test_me_name_fields_populated(graphql_client):
    """Verify firstName and lastName are non-empty strings."""
    query = """
    query {
        me {
            firstName
            lastName
        }
    }
    """
    res = await graphql_client.execute(query)
    me = res["data"]["me"]
    assert len(me["firstName"]) > 0
    assert len(me["lastName"]) > 0


# ==============================================================================
# Feature 10: Field Resolver `Shipment.client` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_shipment_client_resolver_returns_user(graphql_client, known_tracking_number):
    """Verify Shipment.client resolves to client User object."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            client {
                id
                email
                firstName
                lastName
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    client = res["data"]["shipment"]["client"]
    assert client is not None


@pytest.mark.asyncio
async def test_shipment_client_id_matches_client(graphql_client, known_tracking_number, known_client_id):
    """Verify resolved client id matches known client UUID."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            client {
                id
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    client_id = res["data"]["shipment"]["client"]["id"]
    assert client_id == known_client_id


@pytest.mark.asyncio
async def test_shipment_client_name_fields(graphql_client, known_tracking_number):
    """Verify client firstName and lastName are non-empty strings."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            client {
                firstName
                lastName
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    client = res["data"]["shipment"]["client"]
    assert len(client["firstName"]) > 0
    assert len(client["lastName"]) > 0


@pytest.mark.asyncio
async def test_shipment_client_role(graphql_client, known_tracking_number):
    """Verify resolved client role is ROLE_CLIENT."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            client {
                role
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    role = res["data"]["shipment"]["client"]["role"]
    assert role == "ROLE_CLIENT"


@pytest.mark.asyncio
async def test_shipment_client_account_status(graphql_client, known_tracking_number):
    """Verify resolved client accountStatus is ACTIVE."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            client {
                accountStatus
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    status = res["data"]["shipment"]["client"]["accountStatus"]
    assert status == "ACTIVE"


# ==============================================================================
# Feature 11: Field Resolver `Shipment.tariff` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_shipment_tariff_resolver_returns_tariff(graphql_client, known_tracking_number):
    """Verify Shipment.tariff resolves associated Tariff object."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            tariff {
                id
                code
                name
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    tariff = res["data"]["shipment"]["tariff"]
    assert tariff is not None


@pytest.mark.asyncio
async def test_shipment_tariff_id_matches_seed(graphql_client, known_tracking_number, known_tariff_id):
    """Verify resolved tariff id matches known tariff UUID."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            tariff {
                id
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    tariff_id = res["data"]["shipment"]["tariff"]["id"]
    assert tariff_id == known_tariff_id


@pytest.mark.asyncio
async def test_shipment_tariff_code_and_name(graphql_client, known_tracking_number):
    """Verify tariff code and name are populated."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            tariff {
                code
                name
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    tariff = res["data"]["shipment"]["tariff"]
    assert len(tariff["code"]) > 0
    assert len(tariff["name"]) > 0


@pytest.mark.asyncio
async def test_shipment_tariff_base_price_positive(graphql_client, known_tracking_number):
    """Verify tariff basePrice is positive."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            tariff {
                basePrice
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    base_price = float(res["data"]["shipment"]["tariff"]["basePrice"])
    assert base_price > 0.0


@pytest.mark.asyncio
async def test_shipment_tariff_multipliers(graphql_client, known_tracking_number):
    """Verify tariff urgencyMultiplier >= 1.0 and maxDeliveryDays > 0."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            tariff {
                urgencyMultiplier
                maxDeliveryDays
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    t = res["data"]["shipment"]["tariff"]
    assert float(t["urgencyMultiplier"]) >= 1.0
    assert int(t["maxDeliveryDays"]) > 0


# ==============================================================================
# Feature 12: Field Resolver `Shipment.route` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_shipment_route_resolver_returns_route(graphql_client, known_tracking_number):
    """Verify Shipment.route resolves Route object."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                id
                shipmentId
                totalDistanceKm
                estimatedDurationMin
                status
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    route = res["data"]["shipment"]["route"]
    assert route is not None


@pytest.mark.asyncio
async def test_shipment_route_shipment_id_link(graphql_client, known_tracking_number):
    """Verify route shipmentId matches parent shipment id."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            route {
                shipmentId
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    sh = res["data"]["shipment"]
    assert sh["route"]["shipmentId"] == sh["id"]


@pytest.mark.asyncio
async def test_shipment_route_distance_positive(graphql_client, known_tracking_number):
    """Verify route totalDistanceKm is positive float."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                totalDistanceKm
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    dist = float(res["data"]["shipment"]["route"]["totalDistanceKm"])
    assert dist > 0.0


@pytest.mark.asyncio
async def test_shipment_route_duration_positive(graphql_client, known_tracking_number):
    """Verify route estimatedDurationMin is positive integer."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                estimatedDurationMin
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    dur = int(res["data"]["shipment"]["route"]["estimatedDurationMin"])
    assert dur > 0


@pytest.mark.asyncio
async def test_shipment_route_status_non_empty(graphql_client, known_tracking_number):
    """Verify route status is non-empty string."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                status
                currentStageOrder
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    route = res["data"]["shipment"]["route"]
    assert len(route["status"]) > 0
    assert route["currentStageOrder"] >= 1


# ==============================================================================
# Feature 13: Field Resolver `Shipment.activeDelivery` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_shipment_active_delivery_resolver(graphql_client, known_tracking_number):
    """Verify Shipment.activeDelivery resolves Delivery object for active parcel."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                id
                shipmentId
                deliveryType
                status
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    deliv = res["data"]["shipment"]["activeDelivery"]
    assert deliv is not None


@pytest.mark.asyncio
async def test_shipment_active_delivery_shipment_link(graphql_client, known_tracking_number):
    """Verify activeDelivery shipmentId matches shipment id."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            activeDelivery {
                shipmentId
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    sh = res["data"]["shipment"]
    assert sh["activeDelivery"]["shipmentId"] == sh["id"]


@pytest.mark.asyncio
async def test_shipment_active_delivery_type_enum(graphql_client, known_tracking_number):
    """Verify deliveryType is member of DeliveryType enum."""
    valid_types = {"FIRST_MILE_PICKUP", "LAST_MILE_DROPOFF"}
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                deliveryType
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    d_type = res["data"]["shipment"]["activeDelivery"]["deliveryType"]
    assert d_type in valid_types


@pytest.mark.asyncio
async def test_shipment_active_delivery_status_enum(graphql_client, known_tracking_number):
    """Verify status is member of DeliveryStatus enum."""
    valid_statuses = {"PENDING_ASSIGNMENT", "ASSIGNED", "PICKED_UP", "DELIVERED", "FAILED"}
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                status
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    status = res["data"]["shipment"]["activeDelivery"]["status"]
    assert status in valid_statuses


@pytest.mark.asyncio
async def test_shipment_active_delivery_time_window_valid(graphql_client, known_tracking_number):
    """Verify delivery windowStart <= windowEnd."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                windowStart
                windowEnd
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    deliv = res["data"]["shipment"]["activeDelivery"]
    assert deliv["windowStart"] <= deliv["windowEnd"]


# ==============================================================================
# Feature 14: Field Resolver `Route.stages` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_route_stages_resolver_returns_list(graphql_client, known_tracking_number):
    """Verify Route.stages resolves non-empty stages list."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                stages {
                    id
                    stageOrder
                    stageType
                    status
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    stages = res["data"]["shipment"]["route"]["stages"]
    assert isinstance(stages, list)
    assert len(stages) >= 1


@pytest.mark.asyncio
async def test_route_stages_strictly_ordered(graphql_client, known_tracking_number):
    """Verify stages are ordered by stageOrder ascending starting from 1."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                stages {
                    stageOrder
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    stages = res["data"]["shipment"]["route"]["stages"]
    orders = [s["stageOrder"] for s in stages]
    assert orders == sorted(orders)
    assert orders[0] == 1


@pytest.mark.asyncio
async def test_route_stages_type_enum(graphql_client, known_tracking_number):
    """Verify each stage stageType is member of StageType enum."""
    valid_types = {"PICKUP", "MAIN_TRANSIT", "LAST_MILE"}
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                stages {
                    stageType
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    stages = res["data"]["shipment"]["route"]["stages"]
    for s in stages:
        assert s["stageType"] in valid_types


@pytest.mark.asyncio
async def test_route_stages_status_enum(graphql_client, known_tracking_number):
    """Verify each stage status is member of StageStatus enum."""
    valid_statuses = {"PENDING", "IN_PROGRESS", "COMPLETED"}
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                stages {
                    status
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    stages = res["data"]["shipment"]["route"]["stages"]
    for s in stages:
        assert s["status"] in valid_statuses


@pytest.mark.asyncio
async def test_route_stages_origin_and_dest_non_empty(graphql_client, known_tracking_number):
    """Verify stage originPoint and destPoint are non-empty strings."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                stages {
                    originPoint
                    destPoint
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    stages = res["data"]["shipment"]["route"]["stages"]
    for s in stages:
        assert len(s["originPoint"]) > 0
        assert len(s["destPoint"]) > 0


# ==============================================================================
# Feature 15: Field Resolver `Delivery.courier` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_delivery_courier_resolver_returns_courier(graphql_client, known_tracking_number):
    """Verify Delivery.courier resolves assigned Courier object."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    id
                    transportType
                    vehiclePlate
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    courier = res["data"]["shipment"]["activeDelivery"]["courier"]
    assert courier is not None


@pytest.mark.asyncio
async def test_delivery_courier_id_matches_assigned(graphql_client, known_tracking_number, known_courier_id):
    """Verify resolved courier id matches known assigned courier UUID."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    id
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    c_id = res["data"]["shipment"]["activeDelivery"]["courier"]["id"]
    assert c_id == known_courier_id


@pytest.mark.asyncio
async def test_delivery_courier_transport_type(graphql_client, known_tracking_number):
    """Verify courier transportType is member of TransportType enum."""
    valid_transports = {"FOOT", "BICYCLE", "CAR", "VAN"}
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    transportType
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    tt = res["data"]["shipment"]["activeDelivery"]["courier"]["transportType"]
    assert tt in valid_transports


@pytest.mark.asyncio
async def test_delivery_courier_rating_bounds(graphql_client, known_tracking_number):
    """Verify courier rating is between 0.0 and 5.0."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    rating
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    rating = float(res["data"]["shipment"]["activeDelivery"]["courier"]["rating"])
    assert 0.0 <= rating <= 5.0


@pytest.mark.asyncio
async def test_delivery_courier_payload_positive(graphql_client, known_tracking_number):
    """Verify courier maxPayloadKg is positive float."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    maxPayloadKg
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    payload = float(res["data"]["shipment"]["activeDelivery"]["courier"]["maxPayloadKg"])
    assert payload > 0.0


# ==============================================================================
# Feature 16: Field Resolver `Delivery.checkpoints` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_delivery_checkpoints_returns_list(graphql_client, known_tracking_number):
    """Verify Delivery.checkpoints resolves list of checkpoints."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    id
                    status
                    recordedAt
                    locationName
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    cps = res["data"]["shipment"]["activeDelivery"]["checkpoints"]
    assert isinstance(cps, list)


@pytest.mark.asyncio
async def test_delivery_checkpoints_chronological_order(graphql_client, known_tracking_number):
    """Verify checkpoints are chronologically sorted by recordedAt."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    recordedAt
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    cps = res["data"]["shipment"]["activeDelivery"]["checkpoints"]
    times = [cp["recordedAt"] for cp in cps]
    assert times == sorted(times)


@pytest.mark.asyncio
async def test_delivery_checkpoints_status_non_empty(graphql_client, known_tracking_number):
    """Verify every checkpoint has non-empty status string."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    status
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    cps = res["data"]["shipment"]["activeDelivery"]["checkpoints"]
    for cp in cps:
        assert len(cp["status"]) > 0


@pytest.mark.asyncio
async def test_delivery_checkpoints_location_non_empty(graphql_client, known_tracking_number):
    """Verify every checkpoint has non-empty locationName string."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    locationName
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    cps = res["data"]["shipment"]["activeDelivery"]["checkpoints"]
    for cp in cps:
        assert len(cp["locationName"]) > 0


@pytest.mark.asyncio
async def test_delivery_checkpoints_notes_field_accessible(graphql_client, known_tracking_number):
    """Verify notes field is nullable string and does not produce GraphQL errors."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    notes
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    cps = res["data"]["shipment"]["activeDelivery"]["checkpoints"]
    for cp in cps:
        assert cp["notes"] is None or isinstance(cp["notes"], str)
