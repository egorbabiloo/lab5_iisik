# -*- coding: utf-8 -*-
"""
Redis-backed active user session store with strict TTL enforcement.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis

from services.auth_service.config import (
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    SESSION_TTL_SECONDS,
)
from services.auth_service.schemas import SessionInfoDTO


class RedisSessionStore:
    """Manages active user sessions in Redis with automatic TTL expiration."""

    SESSION_KEY_PREFIX = "auth:session:"
    USER_SESSIONS_PREFIX = "auth:user_sessions:"

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        self._client = redis_client or redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )

    @classmethod
    def _session_key(cls, session_id: str) -> str:
        return f"{cls.SESSION_KEY_PREFIX}{session_id}"

    @classmethod
    def _user_sessions_key(cls, user_id: str) -> str:
        return f"{cls.USER_SESSIONS_PREFIX}{user_id}"

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def create_session(
        self,
        user_id: str,
        email: str,
        role: str,
        account_status: str = "ACTIVE",
        ttl_seconds: Optional[int] = None,
    ) -> SessionInfoDTO:
        ttl = int(ttl_seconds if ttl_seconds is not None else SESSION_TTL_SECONDS)
        if ttl <= 0:
            raise ValueError("Session TTL must be strictly positive")

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)

        payload = {
            "session_id": session_id,
            "user_id": str(user_id),
            "email": email,
            "role": role,
            "account_status": account_status,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        key = self._session_key(session_id)
        user_key = self._user_sessions_key(str(user_id))

        pipe = self._client.pipeline()
        pipe.set(key, json.dumps(payload), ex=ttl)
        pipe.sadd(user_key, session_id)
        pipe.expire(user_key, ttl)
        pipe.execute()

        return SessionInfoDTO(
            session_id=session_id,
            user_id=user_id,
            email=email,
            role=role,
            account_status=account_status,
            created_at=now,
            expires_at=expires_at,
            ttl_seconds=ttl,
        )

    def get_session(self, session_id: str) -> Optional[SessionInfoDTO]:
        if not session_id:
            return None
        key = self._session_key(session_id)
        raw = self._client.get(key)
        if not raw:
            return None

        ttl = self._client.ttl(key)
        if ttl is None or ttl <= 0:
            return None

        data = json.loads(raw)
        return SessionInfoDTO(
            session_id=data["session_id"],
            user_id=data["user_id"],
            email=data["email"],
            role=data["role"],
            account_status=data.get("account_status", "ACTIVE"),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            ttl_seconds=int(ttl),
        )

    def refresh_session_ttl(
        self, session_id: str, ttl_seconds: Optional[int] = None
    ) -> Optional[SessionInfoDTO]:
        session = self.get_session(session_id)
        if not session:
            return None
        ttl = int(ttl_seconds if ttl_seconds is not None else SESSION_TTL_SECONDS)
        now = datetime.now(timezone.utc)
        new_expires_at = now + timedelta(seconds=ttl)
        key = self._session_key(session_id)
        payload = {
            "session_id": session.session_id,
            "user_id": str(session.user_id),
            "email": session.email,
            "role": session.role,
            "account_status": session.account_status,
            "created_at": session.created_at.isoformat(),
            "expires_at": new_expires_at.isoformat(),
        }
        self._client.set(key, json.dumps(payload), ex=ttl)
        session.expires_at = new_expires_at
        session.ttl_seconds = ttl
        return session

    def delete_session(self, session_id: str) -> bool:
        if not session_id:
            return False
        key = self._session_key(session_id)
        raw = self._client.get(key)
        if raw:
            try:
                data = json.loads(raw)
                user_id = data.get("user_id")
                if user_id:
                    self._client.srem(self._user_sessions_key(str(user_id)), session_id)
            except Exception:
                pass
        deleted = self._client.delete(key)
        return bool(deleted)

    def revoke_user_sessions(self, user_id: str) -> int:
        user_key = self._user_sessions_key(str(user_id))
        session_ids = list(self._client.smembers(user_key) or [])
        count = 0
        if session_ids:
            keys = [self._session_key(sid) for sid in session_ids]
            count = int(self._client.delete(*keys))
        self._client.delete(user_key)
        return count
