# -*- coding: utf-8 -*-
"""
AuthClient: REST API client communicating with the standalone Auth Service.
Never accesses user_db, Redis, JWT secrets, or password hashing directly.
"""

import os
from typing import Any, Optional

import httpx

from gateway.clients.base import AuthClientProtocol
from services.auth_service.config import AUTH_SERVICE_URL
from services.auth_service.schemas import (
    AuthTokenResponse,
    LoginRequest,
    RegisterRequest,
    SessionInfoDTO,
    VerifyTokenResponse,
)
from services.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    EntityNotFoundError,
    ValidationError,
)


class AuthClient(AuthClientProtocol):
    """REST client for Auth Service endpoints (/auth/*)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        http_client: Optional[Any] = None,
    ) -> None:
        self._base_url = (base_url or AUTH_SERVICE_URL).rstrip("/")
        self._http_client = http_client

    def _get_client(self) -> Any:
        if self._http_client is not None:
            return self._http_client

        # Prefer live HTTP REST transport if Auth Service is running on AUTH_SERVICE_URL
        force_live = os.getenv("AUTH_SERVICE_LIVE") == "1"
        if force_live:
            self._http_client = httpx.Client(base_url=self._base_url, timeout=10.0)
            return self._http_client

        try:
            probe = httpx.get(f"{self._base_url}/health", timeout=0.4)
            if probe.status_code == 200:
                self._http_client = httpx.Client(base_url=self._base_url, timeout=10.0)
                return self._http_client
        except Exception:
            pass

        # In-process ASGI REST transport fallback (still executes full FastAPI REST routes)
        from fastapi.testclient import TestClient
        from services.auth_service.app import app as auth_app

        self._http_client = TestClient(auth_app)
        return self._http_client

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            payload = response.json()
            detail = payload.get("detail") or response.text
        except Exception:
            detail = response.text or f"Auth Service error ({response.status_code})"

        if response.status_code == 401:
            raise AuthenticationError(str(detail))
        if response.status_code == 403:
            raise AuthorizationError(str(detail))
        if response.status_code == 404:
            raise EntityNotFoundError(str(detail))
        raise ValidationError(str(detail))

    def register(self, data: RegisterRequest) -> AuthTokenResponse:
        client = self._get_client()
        resp = client.post("/auth/register", json=data.model_dump(by_alias=True))
        self._raise_for_error(resp)
        return AuthTokenResponse.model_validate(resp.json())

    def login(self, data: LoginRequest) -> AuthTokenResponse:
        client = self._get_client()
        resp = client.post("/auth/login", json=data.model_dump())
        self._raise_for_error(resp)
        return AuthTokenResponse.model_validate(resp.json())

    def verify_token(self, token: str) -> VerifyTokenResponse:
        client = self._get_client()
        resp = client.post("/auth/verify", json={"token": token})
        self._raise_for_error(resp)
        return VerifyTokenResponse.model_validate(resp.json())

    def logout(self, token: str) -> bool:
        client = self._get_client()
        resp = client.post("/auth/logout", json={"token": token})
        self._raise_for_error(resp)
        return bool(resp.json().get("revoked", False))

    def refresh(self, refresh_token: str) -> AuthTokenResponse:
        client = self._get_client()
        resp = client.post("/auth/refresh", json={"refreshToken": refresh_token})
        self._raise_for_error(resp)
        return AuthTokenResponse.model_validate(resp.json())

    def get_session(self, session_id: str) -> Optional[SessionInfoDTO]:
        client = self._get_client()
        resp = client.get(f"/auth/sessions/{session_id}")
        if resp.status_code == 404:
            return None
        self._raise_for_error(resp)
        return SessionInfoDTO.model_validate(resp.json())
