# -*- coding: utf-8 -*-
"""
Shared security primitives for verified user identity and RBAC checks.
Does NOT handle JWT signing, password hashing, or Redis directly (delegated to Auth Service).
"""

from typing import Iterable, Optional
from uuid import UUID
from pydantic import BaseModel

from services.common.exceptions import AuthenticationError, AuthorizationError

ROLE_CLIENT = "ROLE_CLIENT"
ROLE_COURIER = "ROLE_COURIER"
ROLE_ADMIN = "ROLE_ADMIN"
ALL_ROLES = (ROLE_CLIENT, ROLE_COURIER, ROLE_ADMIN)


class AuthenticatedUser(BaseModel):
    """Verified user context propagated from GraphQL Gateway to internal services."""

    user_id: UUID
    email: str
    role: str
    session_id: str
    account_status: str = "ACTIVE"


def require_authenticated(actor: Optional[AuthenticatedUser]) -> AuthenticatedUser:
    """Ensures a verified user identity is present."""
    if actor is None:
        raise AuthenticationError("Authentication required: missing or invalid Bearer token")
    if actor.account_status != "ACTIVE":
        raise AuthenticationError(f"User account is '{actor.account_status}' and cannot perform operations")
    return actor


def require_roles(
    actor: Optional[AuthenticatedUser],
    allowed_roles: Iterable[str],
    operation_name: Optional[str] = None,
) -> AuthenticatedUser:
    """Ensures actor is authenticated and holds one of the allowed roles."""
    user = require_authenticated(actor)
    allowed_set = set(allowed_roles)
    if user.role not in allowed_set:
        op = f" '{operation_name}'" if operation_name else ""
        raise AuthorizationError(
            f"Access denied for role '{user.role}' to operation{op}. "
            f"Required roles: {', '.join(sorted(allowed_set))}"
        )
    return user
