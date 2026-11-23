# -*- coding: utf-8 -*-
"""
Standalone FastAPI REST Microservice for Authentication, JWT, and Redis Sessions.
Runs independently from the GraphQL Gateway (default port 8001).
"""

from fastapi import FastAPI, HTTPException, Header, status
from typing import Optional

from services.auth_service.schemas import (
    AuthTokenResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    SessionInfoDTO,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from services.auth_service.service import AuthService
from services.auth_service.session_store import RedisSessionStore
from services.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)

app = FastAPI(
    title="Parcel Delivery Auth Service",
    description="Dedicated REST microservice for registration, credential verification, JWT issuance, and Redis sessions",
    version="1.0.0",
)

_session_store = RedisSessionStore()
_auth_service = AuthService(session_store=_session_store)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "auth_service",
        "redis_connected": _session_store.ping(),
    }


@app.post(
    "/auth/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest):
    try:
        return _auth_service.register(payload)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/auth/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest):
    try:
        return _auth_service.login(payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@app.post("/auth/verify", response_model=VerifyTokenResponse)
def verify_token(
    payload: Optional[VerifyTokenRequest] = None,
    authorization: Optional[str] = Header(default=None),
):
    token = None
    if payload and payload.token:
        token = payload.token
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    try:
        return _auth_service.verify_token(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@app.post("/auth/logout")
def logout(
    payload: Optional[LogoutRequest] = None,
    authorization: Optional[str] = Header(default=None),
):
    token = None
    if payload and payload.token:
        token = payload.token
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    try:
        revoked = _auth_service.logout(token)
        return {"revoked": revoked}
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@app.post("/auth/refresh", response_model=AuthTokenResponse)
def refresh_token(payload: RefreshRequest):
    try:
        return _auth_service.refresh(payload.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@app.get("/auth/sessions/{session_id}", response_model=SessionInfoDTO)
def get_session(session_id: str):
    info = _auth_service.get_session_info(session_id)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )
    return info
