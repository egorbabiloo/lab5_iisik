# -*- coding: utf-8 -*-
"""
FastAPI Gateway Application (BFF).
Mounts Ariadne GraphQL endpoint at /graphql with Auth Service JWT + Redis session context.
"""

from fastapi import FastAPI
from ariadne import format_error
from ariadne.asgi import GraphQL

from gateway.auth import resolve_auth_context
from gateway.clients.container import GatewayContainer
from gateway.schema import schema
from services.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)

app = FastAPI(
    title="Logistics Gateway BFF",
    description="Distributed parcel logistics management GraphQL Backend-For-Frontend with JWT + Redis Security",
    version="2.0.0",
)

# Shared GatewayContainer instance
container = GatewayContainer()


def get_context_value(request=None, data=None):
    auth_ctx = resolve_auth_context(request, container)
    return {
        "request": request,
        "clients": container,
        **auth_ctx,
    }


def graphql_error_formatter(error, debug: bool = False):
    formatted = format_error(error, debug)
    original = getattr(error, "original_error", None)
    extensions = formatted.setdefault("extensions", {})
    if isinstance(original, AuthenticationError):
        extensions["code"] = "UNAUTHENTICATED"
    elif isinstance(original, AuthorizationError):
        extensions["code"] = "FORBIDDEN"
    elif isinstance(original, ValidationError):
        extensions["code"] = "BAD_USER_INPUT"
    elif isinstance(original, EntityNotFoundError):
        extensions["code"] = "NOT_FOUND"
    elif isinstance(original, BusinessRuleViolationError):
        extensions["code"] = "BUSINESS_RULE_VIOLATION"
    return formatted


# Ariadne ASGI GraphQL application
graphql_app = GraphQL(
    schema=schema,
    context_value=get_context_value,
    error_formatter=graphql_error_formatter,
    debug=True,
)

# Route /graphql directly to prevent 307 redirects from Mount
app.add_route("/graphql", graphql_app)
app.add_route("/graphql/", graphql_app)
app.mount("/graphql", graphql_app)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "gateway_bff"}
