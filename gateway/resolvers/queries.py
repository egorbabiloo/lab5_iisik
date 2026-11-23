# -*- coding: utf-8 -*-
"""
Root Query resolvers for GraphQL Gateway.
Adheres strictly to Database-per-Service and RBAC security:
verifies JWT + Redis session at the gateway boundary and forwards verified actor context.
"""

from typing import Optional, Any
from ariadne import QueryType

from services.tariff_service.schemas import CalculatePriceInputDTO
from services.analytics_service.schemas import DateRangeInputDTO
from services.shipment_service.schemas import ShipmentFilterDTO, ShipmentSortDTO
from services.courier_service.schemas import CourierFilterDTO, CourierSortDTO
from services.common.exceptions import AuthorizationError
from services.common.security import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_CLIENT,
    ROLE_COURIER,
)
from gateway.auth import require_gateway_auth
from gateway.clients.container import GatewayContainer

query = QueryType()


@query.field("me")
def resolve_me(parent: Any, info: Any):
    actor = require_gateway_auth(info, ALL_ROLES, "me")
    clients: GatewayContainer = info.context["clients"]
    return clients.user_client.get_user_by_id(actor.user_id)


@query.field("activeSession")
def resolve_active_session(parent: Any, info: Any):
    require_gateway_auth(info, ALL_ROLES, "activeSession")
    return info.context.get("current_session")


@query.field("tariffs")
def resolve_tariffs(parent: Any, info: Any):
    clients: GatewayContainer = info.context["clients"]
    return clients.tariff_client.list_active_tariffs()


@query.field("calculatePrice")
def resolve_calculate_price(parent: Any, info: Any, input: dict, **kwargs):
    clients: GatewayContainer = info.context["clients"]
    input_dto = CalculatePriceInputDTO.model_validate(input)
    return clients.tariff_client.calculate_price(input_dto)


@query.field("shipment")
def resolve_shipment(
    parent: Any,
    info: Any,
    tracking_number: Optional[str] = None,
    trackingNumber: Optional[str] = None,
    **kwargs,
):
    actor = require_gateway_auth(info, ALL_ROLES, "shipment")
    clients: GatewayContainer = info.context["clients"]
    num = tracking_number if tracking_number is not None else trackingNumber
    clean_num = (num or "").strip()
    if not clean_num:
        return None
    return clients.shipment_client.get_by_tracking_number(clean_num, actor=actor)


@query.field("myShipments")
def resolve_my_shipments(parent: Any, info: Any):
    actor = require_gateway_auth(info, [ROLE_CLIENT, ROLE_ADMIN], "myShipments")
    clients: GatewayContainer = info.context["clients"]
    return clients.shipment_client.get_client_shipments(actor.user_id)


@query.field("shipments")
def resolve_shipments(
    parent: Any,
    info: Any,
    filter: Optional[dict] = None,
    sort: Optional[dict] = None,
    pagination: Optional[dict] = None,
    **kwargs,
):
    """Rich filtering, sorting, and pagination for parcel shipments (Admin only)."""
    actor = require_gateway_auth(info, [ROLE_ADMIN], "shipments")
    clients: GatewayContainer = info.context["clients"]
    filter_dto = ShipmentFilterDTO.model_validate(filter) if filter else None
    sort_dto = ShipmentSortDTO.model_validate(sort) if sort else None
    limit = pagination.get("limit", 50) if pagination else kwargs.get("limit", 50)
    offset = pagination.get("offset", 0) if pagination else kwargs.get("offset", 0)
    return clients.shipment_client.filter_and_sort_shipments(
        filter_dto=filter_dto, sort_dto=sort_dto, limit=limit, offset=offset, actor=actor
    )


@query.field("couriers")
def resolve_couriers(
    parent: Any,
    info: Any,
    filter: Optional[dict] = None,
    sort: Optional[dict] = None,
    **kwargs,
):
    """Filtered and sorted courier roster (Admin only)."""
    actor = require_gateway_auth(info, [ROLE_ADMIN], "couriers")
    clients: GatewayContainer = info.context["clients"]
    filter_dto = CourierFilterDTO.model_validate(filter) if filter else None
    sort_dto = CourierSortDTO.model_validate(sort) if sort else None
    return clients.courier_client.filter_and_sort_couriers(
        filter_dto=filter_dto, sort_dto=sort_dto, actor=actor
    )


@query.field("shipmentStats")
def resolve_shipment_stats(
    parent: Any,
    info: Any,
    filter: Optional[dict] = None,
    **kwargs,
):
    """Calculates operational and financial shipment aggregation statistics (Admin only)."""
    actor = require_gateway_auth(info, [ROLE_ADMIN], "shipmentStats")
    clients: GatewayContainer = info.context["clients"]
    filter_dto = ShipmentFilterDTO.model_validate(filter) if filter else None
    return clients.shipment_client.get_shipment_stats(filter_dto=filter_dto, actor=actor)


@query.field("courierPerformanceStats")
def resolve_courier_performance_stats(parent: Any, info: Any, **kwargs):
    """Aggregates courier team KPIs and identifies top performer (Admin only)."""
    actor = require_gateway_auth(info, [ROLE_ADMIN], "courierPerformanceStats")
    clients: GatewayContainer = info.context["clients"]
    return clients.courier_client.get_performance_stats(actor=actor)


@query.field("tracking")
def resolve_tracking(
    parent: Any,
    info: Any,
    tracking_number: Optional[str] = None,
    trackingNumber: Optional[str] = None,
    **kwargs,
):
    actor = require_gateway_auth(info, ALL_ROLES, "tracking")
    clients: GatewayContainer = info.context["clients"]
    num = tracking_number if tracking_number is not None else trackingNumber
    clean_num = (num or "").strip()
    if not clean_num:
        return None
    return clients.shipment_client.get_tracking_timeline(clean_num, actor=actor)


@query.field("courierProfile")
def resolve_courier_profile(
    parent: Any,
    info: Any,
    courier_id: Optional[str] = None,
    courierId: Optional[str] = None,
    **kwargs,
):
    actor = require_gateway_auth(info, [ROLE_COURIER, ROLE_ADMIN], "courierProfile")
    clients: GatewayContainer = info.context["clients"]
    cid = courier_id if courier_id is not None else courierId

    if actor.role == ROLE_COURIER:
        own_courier = clients.courier_client.get_courier_by_user_id(actor.user_id)
        if cid and (not own_courier or str(own_courier.id) != str(cid)):
            raise AuthorizationError("Access denied: courier can only view their own profile")
        return own_courier

    if cid:
        return clients.courier_client.get_courier_by_id(cid)
    couriers = clients.courier_client.list_couriers()
    return couriers[0] if couriers else None


@query.field("courierDeliveries")
def resolve_courier_deliveries(
    parent: Any,
    info: Any,
    courier_id: Optional[str] = None,
    courierId: Optional[str] = None,
    status: Optional[str] = None,
    **kwargs,
):
    actor = require_gateway_auth(info, [ROLE_COURIER, ROLE_ADMIN], "courierDeliveries")
    clients: GatewayContainer = info.context["clients"]
    cid = courier_id if courier_id is not None else courierId
    if not cid:
        return []
    return clients.delivery_client.get_deliveries_by_courier(cid, status=status, actor=actor)


@query.field("analyticsSummary")
def resolve_analytics_summary(parent: Any, info: Any, range: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_ADMIN], "analyticsSummary")
    clients: GatewayContainer = info.context["clients"]
    range_dto = DateRangeInputDTO.model_validate(range)
    return clients.analytics_client.get_analytics_summary(range_dto, actor=actor)
