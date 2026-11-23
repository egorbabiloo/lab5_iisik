# -*- coding: utf-8 -*-
"""
Tier 4: Realistic Real-World Application Scenarios (Opaque-Box E2E).
Simulates real end-user and business operations workflows:
1. Scenario 1: Standard Parcel Lifecycle Inquiry (Client checks parcel details & status)
2. Scenario 2: End-to-End Tracking Timeline Audit (Recipient tracks live parcel on map)
3. Scenario 3: Dynamic Price Calculation Comparison (Sender compares shipping tiers & weights)
4. Scenario 4: Courier Shift & Deliveries Overview (Courier checks morning schedule)
5. Scenario 5: Operational Business Analytics & SLA Audit (Manager reviews monthly performance)
6. Scenario 6: Customer Portal Dashboard View (Client opens overview with shipments & profile)
7. Scenario 7: Dispatcher Inter-City Route Audit (Dispatcher inspects multi-stage transit)
"""

import pytest
from conftest import (
    KNOWN_TRACKING_NUMBER,
    KNOWN_COURIER_ID,
    KNOWN_TARIFF_ID,
)


@pytest.mark.asyncio
async def test_scenario_1_standard_parcel_lifecycle_inquiry(graphql_client, known_tracking_number):
    """
    Scenario 1: Standard Parcel Lifecycle Inquiry
    A client looks up their parcel by tracking number on the portal.
    Exercises: `shipment`, `client`, `tariff`, `dimensions`, `route`, `activeDelivery`.
    Validates complete federated object graph across User, Tariff, Shipment, Route, and Delivery services.
    """
    query = """
    query InspectParcel($trackingNumber: String!) {
        shipment(trackingNumber: $trackingNumber) {
            id
            trackingNumber
            currentStatus
            weightKg
            calculatedPrice
            originCity
            originAddress
            destCity
            destAddress
            recipientName
            recipientPhone
            dimensions {
                lengthCm
                widthCm
                heightCm
            }
            client {
                id
                firstName
                lastName
                email
                phone
            }
            tariff {
                code
                name
                basePrice
                maxDeliveryDays
            }
            route {
                totalDistanceKm
                estimatedDurationMin
                status
                stages {
                    stageOrder
                    stageType
                    originPoint
                    destPoint
                    status
                }
            }
            activeDelivery {
                id
                deliveryType
                status
                windowStart
                windowEnd
                courier {
                    transportType
                    vehiclePlate
                    rating
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"trackingNumber": known_tracking_number})
    assert "errors" not in res or res["errors"] is None
    parcel = res.get("data", {}).get("shipment")
    assert parcel is not None

    # Verify parcel basics
    assert parcel["trackingNumber"] == known_tracking_number
    assert float(parcel["weightKg"]) > 0.0
    assert float(parcel["calculatedPrice"]) > 0.0

    # Verify client details stitched from UserService
    client = parcel["client"]
    assert len(client["firstName"]) > 0
    assert len(client["lastName"]) > 0
    assert "@" in client["email"]

    # Verify tariff stitched from TariffService
    tariff = parcel["tariff"]
    assert len(tariff["name"]) > 0
    assert int(tariff["maxDeliveryDays"]) > 0

    # Verify route and stages stitched from RouteService
    route = parcel["route"]
    assert route is not None
    assert float(route["totalDistanceKm"]) > 0.0
    assert len(route["stages"]) >= 1

    # Verify active delivery stitched from DeliveryService
    delivery = parcel["activeDelivery"]
    assert delivery is not None
    assert len(delivery["status"]) > 0


@pytest.mark.asyncio
async def test_scenario_2_end_to_end_tracking_timeline_audit(graphql_client, known_tracking_number):
    """
    Scenario 2: End-to-End Tracking Timeline Audit
    A recipient enters their tracking code on the public tracking page to view the parcel timeline
    and active courier position on a live map.
    Exercises: `tracking`, `events`, courier GPS coordinates (`courierLat`, `courierLon`).
    """
    query = """
    query TrackParcel($trackingNumber: String!) {
        tracking(trackingNumber: $trackingNumber) {
            trackingNumber
            status
            originCity
            destCity
            courierLat
            courierLon
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
    assert "errors" not in res or res["errors"] is None
    timeline = res["data"]["tracking"]
    assert timeline is not None

    # Verify public header
    assert timeline["trackingNumber"] == known_tracking_number
    assert len(timeline["originCity"]) > 0
    assert len(timeline["destCity"]) > 0

    # Verify timeline events
    events = timeline["events"]
    assert isinstance(events, list) and len(events) >= 1

    # Check chronological ordering
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)

    # Verify GPS coordinates for map rendering (if active)
    if timeline["courierLat"] is not None:
        lat = float(timeline["courierLat"])
        lon = float(timeline["courierLon"])
        # Belarusian geographic bounds roughly: lat 51..57, lon 23..33
        assert 50.0 <= lat <= 60.0
        assert 20.0 <= lon <= 35.0


@pytest.mark.asyncio
async def test_scenario_3_dynamic_price_calculation_comparison(graphql_client):
    """
    Scenario 3: Dynamic Price Calculation Comparison
    A prospective sender checks shipping calculator on the website, comparing
    different tariff options (Standard, Express, Cargo) for different package weights.
    Exercises: `tariffs` catalog + multiple parameterized `calculatePrice` queries.
    """
    # 1. Fetch available tariffs
    tariffs_query = """
    query {
        tariffs {
            id
            code
            name
            basePrice
            urgencyMultiplier
            maxDeliveryDays
        }
    }
    """
    t_res = await graphql_client.execute(tariffs_query)
    tariffs = t_res["data"]["tariffs"]
    assert len(tariffs) >= 1

    calc_query = """
    query ComparePrice($input: CalculatePriceInput!) {
        calculatePrice(input: $input) {
            tariffName
            totalPrice
            estimatedDeliveryDays
        }
    }
    """

    # 2. Compare small parcel (1 kg, 100 km) vs medium parcel (10 kg, 100 km) for each tariff
    for tariff in tariffs:
        v_small = {
            "input": {
                "tariffId": tariff["id"],
                "originCity": "Минск",
                "destCity": "Борисов",
                "distanceKm": 100.0,
                "weightKg": 1.0,
            }
        }
        v_medium = {
            "input": {
                "tariffId": tariff["id"],
                "originCity": "Минск",
                "destCity": "Борисов",
                "distanceKm": 100.0,
                "weightKg": 10.0,
            }
        }

        r_small = await graphql_client.execute(calc_query, variables=v_small)
        r_medium = await graphql_client.execute(calc_query, variables=v_medium)

        price_small = float(r_small["data"]["calculatePrice"]["totalPrice"])
        price_medium = float(r_medium["data"]["calculatePrice"]["totalPrice"])

        assert price_medium > price_small
        assert r_small["data"]["calculatePrice"]["estimatedDeliveryDays"] == tariff["maxDeliveryDays"]


@pytest.mark.asyncio
async def test_scenario_4_courier_shift_and_deliveries_overview(graphql_client, known_courier_id):
    """
    Scenario 4: Courier Shift & Deliveries Overview
    A courier logs in to their mobile terminal at the beginning of their shift,
    checks their operational profile, rating, vehicle, and assigned delivery schedule.
    Exercises: `courierProfile`, `courierDeliveries`.
    """
    query = """
    query CourierShiftOverview($courierId: ID!) {
        courierProfile(courierId: $courierId) {
            id
            transportType
            vehiclePlate
            currentStatus
            rating
            totalDeliveries
            maxPayloadKg
        }
        assignedDeliveries: courierDeliveries(courierId: $courierId, status: ASSIGNED) {
            id
            shipmentId
            deliveryType
            status
            windowStart
            windowEnd
            checkpoints {
                status
                locationName
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"courierId": known_courier_id})
    assert "errors" not in res or res["errors"] is None

    profile = res["data"]["courierProfile"]
    assert profile is not None
    assert profile["id"] == known_courier_id
    assert float(profile["rating"]) >= 0.0

    deliveries = res["data"]["assignedDeliveries"]
    assert isinstance(deliveries, list)
    for deliv in deliveries:
        assert deliv["status"] == "ASSIGNED"
        assert deliv["windowStart"] <= deliv["windowEnd"]


@pytest.mark.asyncio
async def test_scenario_5_operational_business_analytics_and_sla_audit(graphql_client):
    """
    Scenario 5: Operational Business Analytics & SLA Audit
    An operations director opens the management dashboard to audit delivery SLA
    and financial metrics for the current operational month.
    Exercises: `analyticsSummary` with comprehensive date range.
    """
    query = """
    query AuditDashboard($range: DateRangeInput!) {
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

    audit = res["data"]["analyticsSummary"]
    assert audit is not None
    assert audit["totalShipments"] >= 0
    assert audit["deliveredShipments"] >= 0
    assert float(audit["totalRevenue"]) >= 0.0
    assert 0.0 <= float(audit["slaComplianceRate"]) <= 1.0
    assert float(audit["averageDeliveryDurationMin"]) >= 0.0


@pytest.mark.asyncio
async def test_scenario_6_customer_portal_dashboard_view(graphql_client):
    """
    Scenario 6: Customer Portal Dashboard View
    A logged-in client opens the customer portal dashboard.
    The single GraphQL query loads:
    - User account status and name (`me`)
    - List of recent shipments with statuses and costs (`myShipments`)
    - Active tariffs available for new bookings (`tariffs`)
    """
    dashboard_query = """
    query CustomerDashboard {
        me {
            id
            firstName
            lastName
            email
            accountStatus
        }
        myShipments {
            totalCount
            items {
                id
                trackingNumber
                calculatedPrice
                currentStatus
                originCity
                destCity
                createdAt
                tariff {
                    code
                    name
                }
            }
        }
        tariffs {
            id
            name
            basePrice
        }
    }
    """
    res = await graphql_client.execute(dashboard_query)
    assert "errors" not in res or res["errors"] is None

    data = res["data"]
    # 1. User profile section
    me = data["me"]
    assert len(me["firstName"]) > 0
    assert me["accountStatus"] == "ACTIVE"

    # 2. My shipments section
    shipments = data["myShipments"]
    assert shipments["totalCount"] >= 0
    for s in shipments["items"]:
        assert len(s["trackingNumber"]) > 0
        assert float(s["calculatedPrice"]) > 0.0

    # 3. Available tariffs section
    tariffs = data["tariffs"]
    assert len(tariffs) >= 1


@pytest.mark.asyncio
async def test_scenario_7_dispatcher_intercity_route_audit(graphql_client, known_tracking_number):
    """
    Scenario 7: Dispatcher Inter-City Route Audit
    A logistics dispatcher audits a parcel's route schedule, ensuring that
    all intermediate route stages are accounted for from origin hub to destination.
    Exercises: `shipment.route.stages` complete stage sequence check.
    """
    query = """
    query RouteAudit($num: String!) {
        shipment(trackingNumber: $num) {
            originCity
            destCity
            route {
                id
                totalDistanceKm
                currentStageOrder
                status
                stages {
                    stageOrder
                    stageType
                    originPoint
                    destPoint
                    plannedStart
                    plannedEnd
                    status
                }
            }
        }
    }
    """
    res = await graphql_client.execute(query, variables={"num": known_tracking_number})
    assert "errors" not in res or res["errors"] is None

    sh = res["data"]["shipment"]
    route = sh["route"]
    assert route is not None
    assert float(route["totalDistanceKm"]) > 0.0

    stages = route["stages"]
    assert len(stages) >= 1
    # Verify stages form an unbroken chronological chain
    for i in range(len(stages) - 1):
        assert stages[i]["plannedStart"] <= stages[i]["plannedEnd"]
        assert stages[i]["plannedEnd"] <= stages[i + 1]["plannedStart"]
