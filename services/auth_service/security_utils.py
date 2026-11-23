# -*- coding: utf-8 -*-
"""
Cryptographic utilities for Auth Service: bcrypt password hashing and PyJWT token handling.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from services.auth_service.config import (
    ACCESS_TOKEN_TTL_SECONDS,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_TTL_SECONDS,
)
from services.common.exceptions import AuthenticationError


def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password using bcrypt with a random salt."""
    if not plain_password or len(plain_password) < 6:
        raise ValueError("Password must be at least 6 characters long")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifies plaintext password against stored bcrypt hash in constant time."""
    if not plain_password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    session_id: str,
    ttl_seconds: Optional[int] = None,
) -> str:
    """Generates a signed HS256 JWT access token bound to a Redis session_id."""
    now = datetime.now(timezone.utc)
    ttl = ttl_seconds if ttl_seconds is not None else ACCESS_TOKEN_TTL_SECONDS
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "sid": session_id,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    email: str,
    role: str,
    session_id: str,
    ttl_seconds: Optional[int] = None,
) -> str:
    """Generates a signed HS256 JWT refresh token bound to a Redis session_id."""
    now = datetime.now(timezone.utc)
    ttl = ttl_seconds if ttl_seconds is not None else REFRESH_TOKEN_TTL_SECONDS
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "sid": session_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str, expected_type: Optional[str] = "access") -> Dict[str, Any]:
    """Validates JWT signature, expiration, and token type."""
    if not token or not token.strip():
        raise AuthenticationError("Missing JWT token")
    try:
        payload = jwt.decode(
            token.strip(),
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "sid", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("JWT token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid JWT token: {exc}") from exc

    if expected_type and payload.get("type") != expected_type:
        raise AuthenticationError(
            f"Invalid token type '{payload.get('type')}', expected '{expected_type}'"
        )
    return payload
