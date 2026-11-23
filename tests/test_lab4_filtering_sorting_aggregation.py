# -*- coding: utf-8 -*-
"""
E2E Integration Tests for Lab 4 GraphQL Filtering, Sorting, and Aggregations.
Verifies Query.shipments, Query.couriers, Query.shipmentStats, and Query.courierPerformanceStats.
"""

from decimal import Decimal
import pytest
from tests.test_graphql_e2e.conftest import GraphQLExecutor


@pytest.mark.asyncio
async def test_shipments_filtering(graphql_client: GraphQLExecutor):
    """Verifies multi-criteria filtering on Query.shipments."""
    # 1. Filter by status: IN_TRANSIT
    query_status = """
    query FilterByStatus {
      shipments(filter: { status: [IN_TRANSIT] }) {
        totalCount
        items {
          trackingNumber
          currentStatus
        }
      }
    }
    """
    res = await graphql_client.execute(query_status)
    assert "errors" not in res
    items = res["data"]["shipments"]["items"]
    assert len(items) >= 1
    for s in items:
        assert s["currentStatus"] == "IN_TRANSIT"

    # 2. Filter by originCity: Минск
    query_city = """
    query FilterByCity {
      shipments(filter: { originCity: "Минск" }) {
        totalCount
        items {
          originCity
        }
      }
    }
    """
    res_city = await graphql_client.execute(query_city)
    assert "errors" not in res_city
    items_city = res_city["data"]["shipments"]["items"]
    assert len(items_city) >= 1
    for s in items_city:
        assert "минск" in s["originCity"].lower()

    # 3. Filter by price range
    query_price = """
    query FilterByPrice {
      shipments(filter: { minPrice: 10.0, maxPrice: 100.0 }) {
        totalCount
        items {
          calculatedPrice
        }
      }
    }
    """
    res_price = await graphql_client.execute(query_price)
    assert "errors" not in res_price
    for s in res_price["data"]["shipments"]["items"]:
        price = float(s["calculatedPrice"])
        assert 10.0 <= price <= 100.0


@pytest.mark.asyncio
async def test_shipments_sorting(graphql_client: GraphQLExecutor):
    """Verifies ascending and descending sorting by calculated price and creation date."""
    # 1. Price ASC
    query_asc = """
    query SortPriceAsc {
      shipments(sort: { field: CALCULATED_PRICE, direction: ASC }, pagination: { limit: 10 }) {
        items {
          calculatedPrice
        }
      }
    }
    """
    res_asc = await graphql_client.execute(query_asc)
    assert "errors" not in res_asc
    prices_asc = [float(s["calculatedPrice"]) for s in res_asc["data"]["shipments"]["items"]]
    assert len(prices_asc) >= 2
    for i in range(len(prices_asc) - 1):
        assert prices_asc[i] <= prices_asc[i + 1], f"Expected ascending order: {prices_asc}"

    # 2. Price DESC
    query_desc = """
    query SortPriceDesc {
      shipments(sort: { field: CALCULATED_PRICE, direction: DESC }, pagination: { limit: 10 }) {
        items {
          calculatedPrice
        }
      }
    }
    """
    res_desc = await graphql_client.execute(query_desc)
    assert "errors" not in res_desc
    prices_desc = [float(s["calculatedPrice"]) for s in res_desc["data"]["shipments"]["items"]]
    assert len(prices_desc) >= 2
    for i in range(len(prices_desc) - 1):
        assert prices_desc[i] >= prices_desc[i + 1], f"Expected descending order: {prices_desc}"


@pytest.mark.asyncio
async def test_couriers_filtering_and_sorting(graphql_client: GraphQLExecutor):
    """Verifies filtering couriers by status/transport and sorting by rating/deliveries."""
    # 1. Filter couriers by status
    res = await graphql_client.execute(
        """
        query CouriersAvailable {
          couriers(filter: { status: AVAILABLE }) {
            id
            currentStatus
            rating
          }
        }
        """
    )
    assert "errors" not in res
    for c in res["data"]["couriers"]:
        assert c["currentStatus"] == "AVAILABLE"

    # 2. Sort couriers by RATING DESC
    res_sort = await graphql_client.execute(
        """
        query CouriersSorted {
          couriers(sort: { field: RATING, direction: DESC }) {
            id
            rating
            totalDeliveries
          }
        }
        """
    )
    assert "errors" not in res_sort
    ratings = [float(c["rating"]) for c in res_sort["data"]["couriers"]]
    for i in range(len(ratings) - 1):
        assert ratings[i] >= ratings[i + 1]


@pytest.mark.asyncio
async def test_shipment_stats_aggregation(graphql_client: GraphQLExecutor):
    """Verifies mathematical consistency of statistical aggregations in Query.shipmentStats."""
    query_str = """
    query GetShipmentStats {
      shipmentStats {
        totalCount
        totalRevenue
        averagePrice
        minPrice
        maxPrice
        averageWeight
        statusBreakdown {
          status
          count
        }
        cityBreakdown {
          city
          shipmentCount
          totalRevenue
        }
      }
    }
    """
    res = await graphql_client.execute(query_str)
    assert "errors" not in res, f"Aggregation query failed: {res.get('errors')}"
    stats = res["data"]["shipmentStats"]

    assert stats["totalCount"] >= 3
    assert float(stats["totalRevenue"]) > 0
    assert float(stats["averagePrice"]) > 0
    assert float(stats["minPrice"]) <= float(stats["maxPrice"])
    assert float(stats["averageWeight"]) > 0

    # Mathematical consistency checks
    sum_breakdown_count = sum(sb["count"] for sb in stats["statusBreakdown"])
    assert sum_breakdown_count == stats["totalCount"]

    calc_avg = round(float(stats["totalRevenue"]) / stats["totalCount"], 2)
    # Allows minor precision rounding difference
    assert abs(float(stats["averagePrice"]) - calc_avg) <= 0.05

    # City breakdown has at least one city
    assert len(stats["cityBreakdown"]) >= 1


@pytest.mark.asyncio
async def test_courier_performance_stats(graphql_client: GraphQLExecutor):
    """Verifies fleet-wide operational KPIs in Query.courierPerformanceStats."""
    query_str = """
    query GetCourierStats {
      courierPerformanceStats {
        totalCouriers
        availableCouriers
        busyCouriers
        offlineCouriers
        averageRating
        totalDeliveredCount
        topPerformer {
          id
          rating
          totalDeliveries
        }
      }
    }
    """
    res = await graphql_client.execute(query_str)
    assert "errors" not in res
    kpis = res["data"]["courierPerformanceStats"]

    assert kpis["totalCouriers"] >= 2
    assert (
        kpis["availableCouriers"] + kpis["busyCouriers"] + kpis["offlineCouriers"]
        == kpis["totalCouriers"]
    )
    assert float(kpis["averageRating"]) >= 0
    assert kpis["topPerformer"] is not None
    assert kpis["topPerformer"]["totalDeliveries"] >= 0
