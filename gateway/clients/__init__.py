# -*- coding: utf-8 -*-
"""
Gateway Clients package.
"""

from gateway.clients.base import (
    AuthClientProtocol,
    UserClientProtocol,
    TariffClientProtocol,
    CourierClientProtocol,
    ShipmentClientProtocol,
    RouteClientProtocol,
    DeliveryClientProtocol,
    AnalyticsClientProtocol,
)
from gateway.clients.container import GatewayContainer
from gateway.clients.auth_client import AuthClient
from gateway.clients.user_client import UserClient
from gateway.clients.tariff_client import TariffClient
from gateway.clients.courier_client import CourierClient
from gateway.clients.shipment_client import ShipmentClient
from gateway.clients.route_client import RouteClient
from gateway.clients.delivery_client import DeliveryClient
from gateway.clients.analytics_client import AnalyticsClient

__all__ = [
    "GatewayContainer",
    "UserClientProtocol",
    "TariffClientProtocol",
    "CourierClientProtocol",
    "ShipmentClientProtocol",
    "RouteClientProtocol",
    "DeliveryClientProtocol",
    "AnalyticsClientProtocol",
    "UserClient",
    "TariffClient",
    "CourierClient",
    "ShipmentClient",
    "RouteClient",
    "DeliveryClient",
    "AnalyticsClient",
]
