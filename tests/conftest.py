# -*- coding: utf-8 -*-
"""
Global root test fixtures for all test packages.
"""

from tests.test_graphql_e2e.conftest import (
    graphql_client,
    GraphQLExecutor,
    KNOWN_TRACKING_NUMBER,
    KNOWN_CLIENT_ID,
    KNOWN_TARIFF_ID,
    KNOWN_COURIER_ID,
    KNOWN_DELIVERY_ID,
    KNOWN_ROUTE_ID,
    KNOWN_SHIPMENT_ID,
    NON_EXISTENT_TRACKING,
    NON_EXISTENT_UUID,
)

__all__ = [
    "graphql_client",
    "GraphQLExecutor",
    "KNOWN_TRACKING_NUMBER",
    "KNOWN_CLIENT_ID",
    "KNOWN_TARIFF_ID",
    "KNOWN_COURIER_ID",
    "KNOWN_DELIVERY_ID",
    "KNOWN_ROUTE_ID",
    "KNOWN_SHIPMENT_ID",
    "NON_EXISTENT_TRACKING",
    "NON_EXISTENT_UUID",
]
