# -*- coding: utf-8 -*-
"""
Field relationship resolvers for cross-service stitching in Ariadne.
"""

from typing import Any
from ariadne import ObjectType

from gateway.clients.container import GatewayContainer

shipment = ObjectType("Shipment")


@shipment.field("client")
def resolve_shipment_client(parent: Any, info: Any):
    clients: GatewayContainer = info.context["clients"]
    client_id = getattr(parent, "client_id", None)
    if client_id is None and isinstance(parent, dict):
        client_id = parent.get("client_id") or parent.get("clientId")
    if not client_id:
        return None
    return clients.user_client.get_user_by_id(client_id)


@shipment.field("tariff")
def resolve_shipment_tariff(parent: Any, info: Any):
    clients: GatewayContainer = info.context["clients"]
    tariff_id = getattr(parent, "tariff_id", None)
    if tariff_id is None and isinstance(parent, dict):
        tariff_id = parent.get("tariff_id") or parent.get("tariffId")
    if not tariff_id:
        return None
    return clients.tariff_client.get_tariff_by_id(tariff_id)


@shipment.field("route")
def resolve_shipment_route(parent: Any, info: Any):
    clients: GatewayContainer = info.context["clients"]
    shipment_id = getattr(parent, "id", None)
    if shipment_id is None and isinstance(parent, dict):
        shipment_id = parent.get("id")
    if not shipment_id:
        return None
    return clients.route_client.get_route_by_shipment_id(shipment_id)


@shipment.field("activeDelivery")
def resolve_shipment_active_delivery(parent: Any, info: Any):
    clients: GatewayContainer = info.context["clients"]
    shipment_id = getattr(parent, "id", None)
    if shipment_id is None and isinstance(parent, dict):
        shipment_id = parent.get("id")
    if not shipment_id:
        return None
    return clients.delivery_client.get_active_delivery_by_shipment_id(shipment_id)


route = ObjectType("Route")


@route.field("stages")
def resolve_route_stages(parent: Any, info: Any):
    stages = getattr(parent, "stages", None)
    if stages is None and isinstance(parent, dict):
        stages = parent.get("stages")
    if stages is not None and len(stages) > 0:
        return stages

    clients: GatewayContainer = info.context["clients"]
    route_id = getattr(parent, "id", None)
    if route_id is None and isinstance(parent, dict):
        route_id = parent.get("id")
    if not route_id:
        return []
    return clients.route_client.get_stages_by_route_id(route_id)


delivery = ObjectType("Delivery")


@delivery.field("courier")
def resolve_delivery_courier(parent: Any, info: Any):
    courier_id = getattr(parent, "courier_id", None)
    if courier_id is None and isinstance(parent, dict):
        courier_id = parent.get("courier_id") or parent.get("courierId")
    if not courier_id:
        return None
    clients: GatewayContainer = info.context["clients"]
    return clients.courier_client.get_courier_by_id(courier_id)


@delivery.field("checkpoints")
def resolve_delivery_checkpoints(parent: Any, info: Any):
    checkpoints = getattr(parent, "checkpoints", None)
    if checkpoints is None and isinstance(parent, dict):
        checkpoints = parent.get("checkpoints")
    if checkpoints is not None and len(checkpoints) > 0:
        return checkpoints

    clients: GatewayContainer = info.context["clients"]
    delivery_id = getattr(parent, "id", None)
    if delivery_id is None and isinstance(parent, dict):
        delivery_id = parent.get("id")
    if not delivery_id:
        return []
    return clients.delivery_client.get_checkpoints_by_delivery_id(delivery_id)
