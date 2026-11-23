# -*- coding: utf-8 -*-
"""
Configuration settings for Auth Service (JWT & Redis session store).
"""

import os

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "bsuir-iisik-lab5-super-secret-signing-key-2026-min-32-bytes")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "1800"))
REFRESH_TOKEN_TTL_SECONDS = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "604800"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001")
