# -*- coding: utf-8 -*-
"""
AuthService: Core authentication, credential verification, JWT issuance,
and Redis session lifecycle management.
"""

from typing import Optional

from services.auth_service.config import ACCESS_TOKEN_TTL_SECONDS, SESSION_TTL_SECONDS
from services.auth_service.repository import AuthRepository
from services.auth_service.schemas import (
    AuthTokenResponse,
    AuthUserDTO,
    LoginRequest,
    RegisterRequest,
    SessionInfoDTO,
    VerifyTokenResponse,
)
from services.auth_service.security_utils import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    verify_password,
)
from services.auth_service.session_store import RedisSessionStore
from services.common.database import session_scope
from services.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from services.common.security import ROLE_ADMIN, ROLE_CLIENT, ROLE_COURIER


class AuthService:
    """Dedicated security service owning registration, credentials, JWT, and Redis sessions."""

    PUBLIC_REGISTRATION_ROLES = {ROLE_CLIENT, ROLE_COURIER}

    def __init__(
        self,
        session_store: Optional[RedisSessionStore] = None,
        repository: Optional[AuthRepository] = None,
    ) -> None:
        self._session_store = session_store or RedisSessionStore()
        self._repo = repository

    def _issue_tokens_and_session(
        self,
        user_dto: AuthUserDTO,
        session_ttl_seconds: Optional[int] = None,
        access_ttl_seconds: Optional[int] = None,
    ) -> AuthTokenResponse:
        ttl = session_ttl_seconds or SESSION_TTL_SECONDS
        access_ttl = access_ttl_seconds or ACCESS_TOKEN_TTL_SECONDS

        session_info = self._session_store.create_session(
            user_id=str(user_dto.id),
            email=user_dto.email,
            role=str(user_dto.role),
            account_status=user_dto.account_status,
            ttl_seconds=ttl,
        )
        access_token = create_access_token(
            user_id=str(user_dto.id),
            email=user_dto.email,
            role=str(user_dto.role),
            session_id=session_info.session_id,
            ttl_seconds=access_ttl,
        )
        refresh_token = create_refresh_token(
            user_id=str(user_dto.id),
            email=user_dto.email,
            role=str(user_dto.role),
            session_id=session_info.session_id,
        )
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=access_ttl,
            session_id=session_info.session_id,
            user=user_dto,
        )

    def register(
        self,
        data: RegisterRequest,
        allow_admin_creation: bool = False,
        session_ttl_seconds: Optional[int] = None,
    ) -> AuthTokenResponse:
        email = (data.email or "").strip().lower()
        phone = (data.phone or "").strip()
        if not email or "@" not in email:
            raise ValidationError("Valid email is required")
        if not phone:
            raise ValidationError("Phone number is required")
        if not data.password or len(data.password) < 6:
            raise ValidationError("Password must be at least 6 characters long")

        requested_role = (data.role or ROLE_CLIENT).strip()
        if requested_role == ROLE_ADMIN and not allow_admin_creation:
            raise AuthorizationError(
                "Self-registration with ROLE_ADMIN is forbidden"
            )
        if requested_role not in (ROLE_CLIENT, ROLE_COURIER, ROLE_ADMIN):
            raise ValidationError(f"Unsupported role '{requested_role}'")

        password_hash = hash_password(data.password)

        def _create(repo: AuthRepository) -> AuthUserDTO:
            _, existing = repo.get_user_with_hash_by_email(email)
            if existing:
                raise ValidationError(f"User with email '{email}' already exists")
            if repo.exists_by_phone(phone):
                raise ValidationError(f"User with phone '{phone}' already exists")

            role_id = repo.get_role_id_by_code(requested_role)
            if role_id is None:
                raise ValidationError(f"Role '{requested_role}' is not configured")

            return repo.create_user(
                email=email,
                phone=phone,
                password_hash=password_hash,
                first_name=(data.first_name or "").strip() or "User",
                last_name=(data.last_name or "").strip() or "Account",
                role_id=role_id,
            )

        if self._repo is not None:
            user_dto = _create(self._repo)
        else:
            with session_scope("user_db") as db_sess:
                user_dto = _create(AuthRepository(db_sess))

        return self._issue_tokens_and_session(
            user_dto, session_ttl_seconds=session_ttl_seconds
        )

    def login(
        self,
        data: LoginRequest,
        session_ttl_seconds: Optional[int] = None,
        access_ttl_seconds: Optional[int] = None,
    ) -> AuthTokenResponse:
        email = (data.email or "").strip().lower()
        password = data.password or ""
        if not email or not password:
            raise AuthenticationError("Email and password are required")

        if self._repo is not None:
            stored_hash, user_dto = self._repo.get_user_with_hash_by_email(email)
        else:
            with session_scope("user_db") as db_sess:
                stored_hash, user_dto = AuthRepository(db_sess).get_user_with_hash_by_email(email)

        if not stored_hash or not user_dto:
            raise AuthenticationError("Invalid email or password")

        if not verify_password(password, stored_hash):
            raise AuthenticationError("Invalid email or password")

        if user_dto.account_status != "ACTIVE":
            raise AuthenticationError(
                f"Account '{email}' is {user_dto.account_status} and cannot sign in"
            )

        return self._issue_tokens_and_session(
            user_dto,
            session_ttl_seconds=session_ttl_seconds,
            access_ttl_seconds=access_ttl_seconds,
        )

    def verify_token(self, token: str) -> VerifyTokenResponse:
        """
        Verifies both JWT cryptographic validity/expiration AND active session presence in Redis.
        Even a cryptographically valid JWT is rejected if its Redis session is missing or expired.
        """
        payload = decode_jwt(token, expected_type="access")
        session_id = payload.get("sid")
        user_id = payload.get("sub")
        if not session_id or not user_id:
            raise AuthenticationError("JWT token is missing required session claims")

        session_info = self._session_store.get_session(session_id)
        if not session_info:
            raise AuthenticationError(
                "Active session not found or expired in Redis; please re-authenticate"
            )

        if str(session_info.user_id) != str(user_id):
            raise AuthenticationError("JWT subject does not match active Redis session")

        if self._repo is not None:
            user_dto = self._repo.get_user_by_id(user_id)
        else:
            with session_scope("user_db") as db_sess:
                user_dto = AuthRepository(db_sess).get_user_by_id(user_id)

        if not user_dto:
            raise AuthenticationError("User associated with token no longer exists")

        if user_dto.account_status != "ACTIVE":
            raise AuthenticationError(
                f"User account is '{user_dto.account_status}'"
            )

        return VerifyTokenResponse(valid=True, user=user_dto, session=session_info)

    def logout(self, token: str) -> bool:
        """Invalidates the active Redis session referenced by the JWT."""
        payload = decode_jwt(token, expected_type="access")
        session_id = payload.get("sid")
        if not session_id:
            raise AuthenticationError("JWT token missing session_id")
        return self._session_store.delete_session(session_id)

    def refresh(self, refresh_token: str) -> AuthTokenResponse:
        """Issues a fresh access token if the refresh JWT and Redis session are still active."""
        payload = decode_jwt(refresh_token, expected_type="refresh")
        session_id = payload.get("sid")
        user_id = payload.get("sub")

        session_info = self._session_store.refresh_session_ttl(session_id)
        if not session_info:
            raise AuthenticationError(
                "Refresh rejected: Redis session expired or revoked"
            )

        if str(session_info.user_id) != str(user_id):
            raise AuthenticationError("Refresh token does not match Redis session")

        if self._repo is not None:
            user_dto = self._repo.get_user_by_id(user_id)
        else:
            with session_scope("user_db") as db_sess:
                user_dto = AuthRepository(db_sess).get_user_by_id(user_id)

        if not user_dto or user_dto.account_status != "ACTIVE":
            raise AuthenticationError("User not found or inactive")

        access_token = create_access_token(
            user_id=str(user_dto.id),
            email=user_dto.email,
            role=str(user_dto.role),
            session_id=session_info.session_id,
        )
        new_refresh_token = create_refresh_token(
            user_id=str(user_dto.id),
            email=user_dto.email,
            role=str(user_dto.role),
            session_id=session_info.session_id,
        )
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            session_id=session_info.session_id,
            user=user_dto,
        )

    def get_session_info(self, session_id: str) -> Optional[SessionInfoDTO]:
        return self._session_store.get_session(session_id)
