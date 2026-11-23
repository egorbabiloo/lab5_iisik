# -*- coding: utf-8 -*-
"""
Tier 2: Boundaries, Corners, and Error Handling Tests (Opaque-Box E2E).
Covers null handling for unknown entities, boundary conditions, zero/negative inputs,
empty filters, and special character robustness.
Minimum >=5 test cases per boundary area (total 27 tests across 5 areas).
"""

import pytest
from conftest import (
    KNOWN_TRACKING_NUMBER,
    KNOWN_TARIFF_ID,
    KNOWN_COURIER_ID,
    NON_EXISTENT_TRACKING,
    NON_EXISTENT_UUID,
)


# ==============================================================================
# Area 1: Null Returns on Non-Existent Entities (No 500 crashes) (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_unknown_tracking_number_returns_null_shipment(graphql_client, non_existent_tracking):
    """Verify non-existent tracking number returns null data for shipment without server error."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            trackingNumber
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": non_existent_tracking})
    assert "errors" not in res or res["errors"] is None
    assert res.get("data", {}).get("shipment") is None


@pytest.mark.asyncio
async def test_unknown_courier_id_returns_null_profile(graphql_client, non_existent_uuid):
    """Verify non-existent courierId returns null courierProfile without server error."""
    query = """
    query GetCourier($id: ID!) {
        courierProfile(courierId: $id) {
            id
            transportType
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": non_existent_uuid})
    assert "errors" not in res or res["errors"] is None
    assert res.get("data", {}).get("courierProfile") is None


@pytest.mark.asyncio
async def test_unknown_courier_id_random_uuid(graphql_client):
    """Verify random unused UUID returns null courierProfile."""
    random_uuid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    query = """
    query GetCourier($id: ID!) {
        courierProfile(courierId: $id) {
            id
            currentStatus
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": random_uuid})
    assert res.get("data", {}).get("courierProfile") is None


@pytest.mark.asyncio
async def test_unknown_tracking_number_for_timeline(graphql_client, non_existent_tracking):
    """Verify tracking query with unknown tracking number returns null or user error, not 500."""
    query = """
    query Track($num: String!) {
        tracking(trackingNumber: $num) {
            trackingNumber
            status
            events {
                status
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": non_existent_tracking})
    # Either data.tracking is null or a descriptive GraphQL error is returned
    tracking_data = res.get("data", {}).get("tracking") if res.get("data") else None
    assert tracking_data is None or "errors" in res


@pytest.mark.asyncio
async def test_malformed_tracking_number_empty_string(graphql_client):
    """Verify empty string tracking number returns null or error without crashing."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": ""})
    assert res.get("data", {}).get("shipment") is None or "errors" in res


@pytest.mark.asyncio
async def test_tracking_number_sql_injection_attempt(graphql_client):
    """Verify SQL injection strings in tracking number do not cause crash."""
    injection_strings = [
        "' OR 1=1; --",
        "'; DROP TABLE shipments; --",
        "PKG' UNION SELECT * FROM users --",
    ]
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            trackingNumber
        }
    }
    """
    for sqli in injection_strings:
        res = await graphql_client.execute(query, variables={"num": sqli})
        assert res.get("data", {}).get("shipment") is None


# ==============================================================================
# Area 2: Input Boundary & Validation for `calculatePrice` (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_calculate_price_zero_distance(graphql_client, known_tariff_id):
    """Verify calculatePrice with distanceKm = 0.0 returns validation error."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Минск",
            "distanceKm": 0.0,
            "weightKg": 1.0,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" in res and len(res["errors"]) > 0


@pytest.mark.asyncio
async def test_calculate_price_negative_distance(graphql_client, known_tariff_id):
    """Verify calculatePrice with negative distanceKm returns validation error."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Брест",
            "distanceKm": -150.0,
            "weightKg": 2.0,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" in res and len(res["errors"]) > 0


@pytest.mark.asyncio
async def test_calculate_price_zero_weight(graphql_client, known_tariff_id):
    """Verify calculatePrice with weightKg = 0.0 returns validation error."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Гродно",
            "distanceKm": 250.0,
            "weightKg": 0.0,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" in res and len(res["errors"]) > 0


@pytest.mark.asyncio
async def test_calculate_price_negative_weight(graphql_client, known_tariff_id):
    """Verify calculatePrice with negative weightKg returns validation error."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Гомель",
            "distanceKm": 300.0,
            "weightKg": -3.5,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" in res and len(res["errors"]) > 0


@pytest.mark.asyncio
async def test_calculate_price_non_existent_tariff(graphql_client, non_existent_uuid):
    """Verify calculatePrice with unknown tariffId returns GraphQL error."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": non_existent_uuid,
            "originCity": "Минск",
            "destCity": "Брест",
            "distanceKm": 350.0,
            "weightKg": 2.5,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" in res and len(res["errors"]) > 0


@pytest.mark.asyncio
async def test_calculate_price_minimal_positive_values(graphql_client, known_tariff_id):
    """Verify calculatePrice handles tiny non-zero values (0.01 kg, 0.1 km) without underflow."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
            weightPrice
            distancePrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Минск",
            "destCity": "Минск",
            "distanceKm": 0.1,
            "weightKg": 0.01,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    total = float(res["data"]["calculatePrice"]["totalPrice"])
    assert total > 0.0


# ==============================================================================
# Area 3: Empty Filters & Zero-Result Queries (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_courier_deliveries_unknown_courier_returns_empty_list(graphql_client, non_existent_uuid):
    """Verify courierDeliveries for unknown courier returns empty list."""
    query = """
    query GetDeliveries($id: ID!) {
        courierDeliveries(courierId: $id) {
            id
            status
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": non_existent_uuid})
    assert "errors" not in res or res["errors"] is None
    delivs = res.get("data", {}).get("courierDeliveries")
    assert delivs == []


@pytest.mark.asyncio
async def test_courier_deliveries_non_matching_status_filter(graphql_client, known_courier_id):
    """Verify filtering by status with no matches returns empty list without error."""
    query = """
    query GetDeliveries($id: ID!) {
        courierDeliveries(courierId: $id, status: FAILED) {
            id
            status
        }
    }
    """
    res = await graphql_client.execute(query, variables={"id": known_courier_id})
    assert "errors" not in res or res["errors"] is None
    delivs = res.get("data", {}).get("courierDeliveries")
    assert isinstance(delivs, list)


@pytest.mark.asyncio
async def test_analytics_summary_future_date_range_zeroes(graphql_client):
    """Verify far-future date range returns summary with 0 shipments and 0 revenue."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            totalShipments
            deliveredShipments
            totalRevenue
            slaComplianceRate
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2099-01-01T00:00:00Z",
            "endDate": "2099-01-02T00:00:00Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    s = res["data"]["analyticsSummary"]
    assert s["totalShipments"] == 0
    assert s["deliveredShipments"] == 0
    assert float(s["totalRevenue"]) == 0.0


@pytest.mark.asyncio
async def test_analytics_summary_reversed_date_range(graphql_client):
    """Verify startDate > endDate returns validation error or handles gracefully without crash."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            totalShipments
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-31T00:00:00Z",
            "endDate": "2026-10-01T00:00:00Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    # Server should either reject with validation error or handle gracefully
    assert "errors" in res or "data" in res


@pytest.mark.asyncio
async def test_analytics_summary_single_instant_range(graphql_client):
    """Verify single-moment range (startDate == endDate) executes safely."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            periodStart
            periodEnd
            totalShipments
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-15T12:00:00Z",
            "endDate": "2026-10-15T12:00:00Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    assert "analyticsSummary" in res.get("data", {})


# ==============================================================================
# Area 4: Nullable Field Handling & Missing Relationships (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_shipment_nullable_route_handling(graphql_client, known_tracking_number):
    """Verify querying route on shipment handles null cleanly if not assigned."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            route {
                id
                stages {
                    id
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    assert "shipment" in res.get("data", {})


@pytest.mark.asyncio
async def test_shipment_nullable_active_delivery_handling(graphql_client, known_tracking_number):
    """Verify querying activeDelivery on shipment handles null cleanly."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            activeDelivery {
                id
                courier {
                    id
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    assert "shipment" in res.get("data", {})


@pytest.mark.asyncio
async def test_delivery_nullable_courier_handling(graphql_client, known_tracking_number):
    """Verify delivery with unassigned courier returns null courier without crashing."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                courier {
                    id
                    transportType
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None


@pytest.mark.asyncio
async def test_delivery_checkpoints_empty_handling(graphql_client, known_tracking_number):
    """Verify empty checkpoints list does not produce GraphQL null constraint error."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            activeDelivery {
                checkpoints {
                    id
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    deliv = res["data"]["shipment"].get("activeDelivery")
    if deliv and deliv.get("checkpoints") is not None:
        assert isinstance(deliv["checkpoints"], list)


@pytest.mark.asyncio
async def test_route_stages_empty_handling(graphql_client, known_tracking_number):
    """Verify empty stages list does not violate GraphQL non-null list constraints."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            route {
                stages {
                    id
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    route = res["data"]["shipment"].get("route")
    if route and route.get("stages") is not None:
        assert isinstance(route["stages"], list)


# ==============================================================================
# Area 5: Unicode, Escaping, and Boundary String Handling (>=5 tests)
# ==============================================================================

@pytest.mark.asyncio
async def test_cyrillic_city_names_in_calculate_price(graphql_client, known_tariff_id):
    """Verify calculatePrice handles Cyrillic UTF-8 strings accurately."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Могилёв",
            "destCity": "Полоцк",
            "distanceKm": 210.5,
            "weightKg": 4.2,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    assert float(res["data"]["calculatePrice"]["totalPrice"]) > 0.0


@pytest.mark.asyncio
async def test_city_names_with_hyphens_and_spaces(graphql_client, known_tariff_id):
    """Verify calculatePrice handles city names with hyphens and spaces."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Марьина Горка",
            "destCity": "Барановичи-Центральные",
            "distanceKm": 180.0,
            "weightKg": 1.5,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None
    assert float(res["data"]["calculatePrice"]["totalPrice"]) > 0.0


@pytest.mark.asyncio
async def test_special_characters_escaping_in_cities(graphql_client, known_tariff_id):
    """Verify strings with quotes, apostrophes, and ampersands do not break JSON parsing."""
    query = """
    query Calc($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            totalPrice
        }
    }
    """
    variables = {
        "input": {
            "tariffId": known_tariff_id,
            "originCity": "Saint-Louis d'Antin",
            "destCity": "Port & Harbor",
            "distanceKm": 120.0,
            "weightKg": 2.0,
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None


@pytest.mark.asyncio
async def test_iso8601_timestamp_format_variations(graphql_client):
    """Verify DateTime scalar handles UTC 'Z' format in DateRangeInput."""
    query = """
    query Analytics($range: DateRangeInput!) {
        analyticsSummary(range: $range) {
            periodStart
            periodEnd
        }
    }
    """
    variables = {
        "range": {
            "startDate": "2026-10-01T00:00:00.000Z",
            "endDate": "2026-10-15T23:59:59.999Z",
        }
    }
    res = await graphql_client.execute(query, variables=variables)
    assert "errors" not in res or res["errors"] is None


@pytest.mark.asyncio
async def test_whitespace_padded_tracking_number(graphql_client, known_tracking_number):
    """Verify tracking query with padded whitespace is handled gracefully."""
    query = """
    query GetShipment($num: String!) {
        shipment(trackingNumber: $num) {
            id
            trackingNumber
        }
    }
    """
    padded_num = f"  {known_tracking_number}  "
    res = await graphql_client.execute(query, variables={"num": padded_num})
    # Either trimmed and found, or treated as not found (null) without 500
    assert "errors" not in res or res["errors"] is None
