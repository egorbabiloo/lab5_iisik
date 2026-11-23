# -*- coding: utf-8 -*-
"""
GatewayContainer: dependency injection container holding client instances for BFF.
"""

from typing import Optional

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
from gateway.clients.auth_client import AuthClient
from gateway.clients.user_client import UserClient
from gateway.clients.tariff_client import TariffClient
from gateway.clients.courier_client import CourierClient
from gateway.clients.shipment_client import ShipmentClient
from gateway.clients.route_client import RouteClient
from gateway.clients.delivery_client import DeliveryClient
from gateway.clients.analytics_client import AnalyticsClient


class GatewayContainer:
    """Central registry of microservice client abstractions."""

    def __init__(
        self,
        auth_client: Optional[AuthClientProtocol] = None,
        user_client: Optional[UserClientProtocol] = None,
        tariff_client: Optional[TariffClientProtocol] = None,
        courier_client: Optional[CourierClientProtocol] = None,
        shipment_client: Optional[ShipmentClientProtocol] = None,
        route_client: Optional[RouteClientProtocol] = None,
        delivery_client: Optional[DeliveryClientProtocol] = None,
        analytics_client: Optional[AnalyticsClientProtocol] = None,
    ) -> None:
        self.auth_client = auth_client or AuthClient()
        self.user_client = user_client or UserClient()
        self.tariff_client = tariff_client or TariffClient()
        self.courier_client = courier_client or CourierClient()
        self.route_client = route_client or RouteClient()
        self.analytics_client = analytics_client or AnalyticsClient()

        # Wire cross-service mock dependencies
        courier_svc = getattr(self.courier_client, "_service", None)
        tariff_svc = getattr(self.tariff_client, "_service", None)
        route_svc = getattr(self.route_client, "_service", None)
        user_svc = getattr(self.user_client, "_service", None)

        self.delivery_client = delivery_client or DeliveryClient(
            courier_service=courier_svc,
        )
        delivery_svc = getattr(self.delivery_client, "_delivery_service", None) or getattr(self.delivery_client, "_service", None)

        self.shipment_client = shipment_client or ShipmentClient(
            delivery_service=delivery_svc,
            courier_service=courier_svc,
            tariff_service=tariff_svc,
            route_service=route_svc,
            user_service=user_svc,
        )

        # Ensure DeliveryClient also knows shipment_service for syncing status
        if hasattr(self.delivery_client, "_shipment_service") and getattr(self.delivery_client, "_shipment_service") is None:
            self.delivery_client._shipment_service = getattr(self.shipment_client, "_shipment_service", None)
