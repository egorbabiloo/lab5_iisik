# -*- coding: utf-8 -*-
"""
Pydantic v2 schemas for Auth Service REST API and internal DTOs.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AuthUserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    email: str
    phone: str
    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    role: str
    account_status: str = Field(..., alias="accountStatus")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str
    phone: str
    password: str
    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    role: str = "ROLE_CLIENT"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken")


class VerifyTokenRequest(BaseModel):
    token: str


class LogoutRequest(BaseModel):
    token: str


class SessionInfoDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    user_id: UUID = Field(..., alias="userId")
    email: str
    role: str
    account_status: str = Field(..., alias="accountStatus")
    created_at: datetime = Field(..., alias="createdAt")
    expires_at: datetime = Field(..., alias="expiresAt")
    ttl_seconds: int = Field(..., alias="ttlSeconds")


class AuthTokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    token_type: str = Field("Bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn")
    session_id: str = Field(..., alias="sessionId")
    user: AuthUserDTO


class VerifyTokenResponse(BaseModel):
    valid: bool
    user: AuthUserDTO
    session: SessionInfoDTO
