# -*- coding: utf-8 -*-
"""
Pytest configuration and session fixtures for isolated unit testing of all 7 microservices.
Provides clean SQLAlchemy session lifecycles against the seeded PostgreSQL databases.
"""
import os
import sys
import uuid
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.common.database import get_session_for_db

# Authoritative Test Identifiers (Matching seed_all.py)
KNOWN_CLIENT_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
KNOWN_CLIENT_2_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa7")
KNOWN_COURIER_ID = uuid.UUID("88776655-4433-2211-00aa-bbccddeeff11")
KNOWN_COURIER_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
KNOWN_TARIFF_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8001")
KNOWN_EXPRESS_TARIFF_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8002")
KNOWN_OVERNIGHT_TARIFF_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8003")
KNOWN_SHIPMENT_ID = uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d")
KNOWN_TRACKING_NUMBER = "PKG-BY-2026-849201"
KNOWN_ROUTE_ID = uuid.UUID("4c219800-4b10-4100-bc11-9a8b7c6d5e4f")
KNOWN_DELIVERY_ID = uuid.UUID("33221100-4455-6677-8899-aabbccddeeff")
NON_EXISTENT_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@pytest.fixture
def user_session():
    session = get_session_for_db("user_db")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tariff_session():
    session = get_session_for_db("tariff_db")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def courier_session():
    session = get_session_for_db("courier_db")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def shipment_session():
    session = get_session_for_db("shipment_db")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def route_session():
    session = get_session_for_db("route_db")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def delivery_session():
    session = get_session_for_db("delivery_db")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def analytics_session():
    session = get_session_for_db("analytics_db")
    try:
        yield session
    finally:
        session.close()
