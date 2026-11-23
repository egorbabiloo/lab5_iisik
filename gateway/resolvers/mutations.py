# -*- coding: utf-8 -*-
"""
Root Mutation resolvers for GraphQL Gateway BFF.
Delegates authentication/session operations to Auth Service REST API.
Enforces RBAC checks and forwards verified actor context to domain clients/services.
"""

from typing import Optional, Any
from ariadne import MutationType

from gateway.auth import require_gateway_auth
from gateway.clients.container import GatewayContainer
from services.auth_service.schemas import LoginRequest, RegisterRequest
from services.common.exceptions import ValidationError, EntityNotFoundError
from services.common.security import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_CLIENT,
    ROLE_COURIER,
)

mutation = MutationType()


@mutation.field("register")
def resolve_register(parent: Any, info: Any, input: dict, **kwargs):
    clients: GatewayContainer = info.context["clients"]
    req = RegisterRequest(
        email=input.get("email", ""),
        phone=input.get("phone", ""),
        password=input.get("password", ""),
        first_name=input.get("first_name") or input.get("firstName", ""),
        last_name=input.get("last_name") or input.get("lastName", ""),
        role=input.get("role", ROLE_CLIENT),
    )
    return clients.auth_client.register(req)


@mutation.field("login")
def resolve_login(parent: Any, info: Any, input: dict, **kwargs):
    clients: GatewayContainer = info.context["clients"]
    req = LoginRequest(
        email=input.get("email", ""),
        password=input.get("password", ""),
    )
    return clients.auth_client.login(req)


@mutation.field("refreshToken")
def resolve_refresh_token(
    parent: Any,
    info: Any,
    refresh_token: Optional[str] = None,
    refreshToken: Optional[str] = None,
    **kwargs,
):
    clients: GatewayContainer = info.context["clients"]
    token = refresh_token if refresh_token is not None else refreshToken
    if not token:
        raise ValidationError("refreshToken is required")
    return clients.auth_client.refresh(token)


@mutation.field("logout")
def resolve_logout(parent: Any, info: Any, **kwargs):
    require_gateway_auth(info, ALL_ROLES, "logout")
    clients: GatewayContainer = info.context["clients"]
    token = info.context.get("auth_token")
    return clients.auth_client.logout(token)


@mutation.field("createShipment")
def resolve_create_shipment(parent: Any, info: Any, input: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_CLIENT, ROLE_ADMIN], "createShipment")
    clients: GatewayContainer = info.context["clients"]
    return clients.shipment_client.create_shipment(input, actor=actor)


@mutation.field("cancelShipment")
def resolve_cancel_shipment(
    parent: Any,
    info: Any,
    tracking_number: Optional[str] = None,
    trackingNumber: Optional[str] = None,
    reason: Optional[str] = None,
    **kwargs,
):
    actor = require_gateway_auth(info, [ROLE_CLIENT, ROLE_ADMIN], "cancelShipment")
    clients: GatewayContainer = info.context["clients"]
    num = tracking_number if tracking_number is not None else trackingNumber
    if not num:
        raise ValidationError("trackingNumber is required")
    return clients.shipment_client.cancel_shipment(num.strip(), reason=reason, actor=actor)


@mutation.field("assignCourier")
def resolve_assign_courier(parent: Any, info: Any, input: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_ADMIN], "assignCourier")
    clients: GatewayContainer = info.context["clients"]
    delivery_id = input.get("delivery_id") or input.get("deliveryId")
    courier_id = input.get("courier_id") or input.get("courierId")
    if not delivery_id or not courier_id:
        raise ValidationError("deliveryId and courierId are required")
    return clients.delivery_client.assign_courier(delivery_id, courier_id, actor=actor)


@mutation.field("updateCourierStatus")
def resolve_update_courier_status(parent: Any, info: Any, input: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_COURIER, ROLE_ADMIN], "updateCourierStatus")
    clients: GatewayContainer = info.context["clients"]
    status = input.get("status")
    if not status:
        raise ValidationError("status is required")

    courier_id = input.get("courier_id") or input.get("courierId")
    if not courier_id:
        if actor.role == ROLE_COURIER:
            own_courier = clients.courier_client.get_courier_by_user_id(actor.user_id)
            if not own_courier:
                raise EntityNotFoundError("Courier profile not found for current user")
            courier_id = own_courier.id
        else:
            couriers = clients.courier_client.list_couriers()
            if not couriers:
                raise EntityNotFoundError("No couriers found in the system")
            courier_id = couriers[0].id

    return clients.courier_client.update_status(courier_id, status, actor=actor)


@mutation.field("updateCourierLocation")
def resolve_update_courier_location(parent: Any, info: Any, input: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_COURIER, ROLE_ADMIN], "updateCourierLocation")
    clients: GatewayContainer = info.context["clients"]
    lat = float(input.get("latitude", 0.0))
    lon = float(input.get("longitude", 0.0))

    courier_id = input.get("courier_id") or input.get("courierId")
    if not courier_id:
        if actor.role == ROLE_COURIER:
            own_courier = clients.courier_client.get_courier_by_user_id(actor.user_id)
            if not own_courier:
                raise EntityNotFoundError("Courier profile not found for current user")
            courier_id = own_courier.id
        else:
            couriers = clients.courier_client.list_couriers()
            if not couriers:
                raise EntityNotFoundError("No couriers found in the system")
            courier_id = couriers[0].id

    return clients.courier_client.update_location(courier_id, lat, lon, actor=actor)


@mutation.field("updateDeliveryCheckpoint")
def resolve_update_delivery_checkpoint(parent: Any, info: Any, input: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_COURIER, ROLE_ADMIN], "updateDeliveryCheckpoint")
    clients: GatewayContainer = info.context["clients"]
    delivery_id = input.get("delivery_id") or input.get("deliveryId")
    status = input.get("status")
    location_name = input.get("location_name") or input.get("locationName", "Пункт логистики")
    notes = input.get("notes")

    if not delivery_id or not status:
        raise ValidationError("deliveryId and status are required")

    return clients.delivery_client.update_checkpoint(
        delivery_id=delivery_id,
        status=status,
        location_name=location_name,
        notes=notes,
        actor=actor,
    )


@mutation.field("verifyAndCompleteDelivery")
def resolve_verify_and_complete_delivery(parent: Any, info: Any, input: dict, **kwargs):
    actor = require_gateway_auth(info, [ROLE_COURIER, ROLE_ADMIN], "verifyAndCompleteDelivery")
    clients: GatewayContainer = info.context["clients"]
    delivery_id = input.get("delivery_id") or input.get("deliveryId")
    plain_otp_code = input.get("plain_otp_code") or input.get("plainOtpCode")

    if not delivery_id or not plain_otp_code:
        raise ValidationError("deliveryId and plainOtpCode are required")

    return clients.delivery_client.verify_and_complete_delivery(
        delivery_id=delivery_id, plain_otp_code=plain_otp_code, actor=actor
    )
