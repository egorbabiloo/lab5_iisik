# -*- coding: utf-8 -*-
"""
Gateway security context resolution and RBAC enforcement helpers.
Delegates JWT + Redis session validation exclusively to Auth Service via AuthClient REST API.
"""

from typing import Any, Dict, Iterable, Optional

from services.common.exceptions import AuthenticationError
from services.common.security import (
    AuthenticatedUser,
    require_authenticated,
    require_roles,
)
from gateway.clients.container import GatewayContainer


def extract_bearer_token(request: Any) -> Optional[str]:
    """Extracts Bearer JWT token from HTTP Authorization header if present."""
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    auth_header = headers.get("authorization") or headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthenticationError("Invalid Authorization header format; expected 'Bearer <token>'")
    return parts[1].strip()


def resolve_auth_context(request: Any, clients: GatewayContainer) -> Dict[str, Any]:
    """
    Validates incoming Bearer token against Auth Service (JWT + Redis session check).
    Populates `current_user`, `current_session`, `auth_token`, and `auth_error` in GraphQL context.
    """
    try:
        token = extract_bearer_token(request)
    except AuthenticationError as exc:
        return {
            "current_user": None,
            "current_session": None,
            "auth_token": None,
            "auth_error": exc,
        }

    if not token:
        return {
            "current_user": None,
            "current_session": None,
            "auth_token": None,
            "auth_error": None,
        }

    try:
        verified = clients.auth_client.verify_token(token)
        actor = AuthenticatedUser(
            user_id=verified.user.id,
            email=verified.user.email,
            role=str(verified.user.role),
            session_id=verified.session.session_id,
            account_status=verified.user.account_status,
        )
        return {
            "current_user": actor,
            "current_session": verified.session,
            "auth_token": token,
            "auth_error": None,
        }
    except AuthenticationError as exc:
        return {
            "current_user": None,
            "current_session": None,
            "auth_token": token,
            "auth_error": exc,
        }
    except Exception as exc:
        return {
            "current_user": None,
            "current_session": None,
            "auth_token": token,
            "auth_error": AuthenticationError(f"Authentication verification failed: {exc}"),
        }


def require_gateway_auth(
    info: Any,
    allowed_roles: Optional[Iterable[str]] = None,
    operation_name: Optional[str] = None,
) -> AuthenticatedUser:
    """
    Enforces authentication and optional RBAC role checks at the GraphQL Gateway boundary.
    Always surfaces token/session errors before executing any service call.
    """
    auth_error = info.context.get("auth_error")
    if auth_error is not None:
        raise auth_error

    actor: Optional[AuthenticatedUser] = info.context.get("current_user")
    if allowed_roles is not None:
        return require_roles(actor, allowed_roles, operation_name=operation_name)
    return require_authenticated(actor)
