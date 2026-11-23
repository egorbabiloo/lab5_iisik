# -*- coding: utf-8 -*-
"""
E2E Test Configuration & Fixtures for GraphQL Gateway (BFF).
Provides an opaque-box GraphQL execution client supporting both live uvicorn server
and in-process ASGI FastAPI application testing via httpx.
Handles real JWT + Redis session authentication via Mutation.login.
"""

import os
import sys
import pytest
import pytest_asyncio
import httpx

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Authoritative Test Identifiers from Seed / Specification
KNOWN_TRACKING_NUMBER = "PKG-BY-2026-849201"
KNOWN_CLIENT_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
KNOWN_TARIFF_ID = "7e4f1a20-3342-4f10-91ab-6b1e7c9f8001"
KNOWN_COURIER_ID = "88776655-4433-2211-00aa-bbccddeeff11"
KNOWN_DELIVERY_ID = "33221100-4455-6677-8899-aabbccddeeff"
KNOWN_ROUTE_ID = "4c219800-4b10-4100-bc11-9a8b7c6d5e4f"
KNOWN_SHIPMENT_ID = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"

NON_EXISTENT_TRACKING = "PKG-UNKNOWN-999999999"
NON_EXISTENT_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_OPS_MARKERS = (
    "analyticsSummary",
    "shipments(",
    "shipments {",
    "shipments{",
    "couriers(",
    "couriers {",
    "couriers{",
    "shipmentStats",
    "courierPerformanceStats",
    "courierProfile",
    "courierDeliveries",
    "assignCourier",
    "updateCourierStatus",
    "updateCourierLocation",
    "updateDeliveryCheckpoint",
    "verifyAndCompleteDelivery",
)

PUBLIC_AUTH_MARKERS = (
    "mutation Register",
    "mutation Login",
    "register(",
    "login(",
    "refreshToken(",
)


class GraphQLExecutor:
    """Opaque-box GraphQL test executor sending HTTP POST requests to /graphql."""

    def __init__(self, client: httpx.AsyncClient, endpoint: str = "/graphql"):
        self._client = client
        self.endpoint = endpoint
        self._token_cache: dict[str, str] = {}

    async def login_as(self, email: str, password: str) -> dict:
        """Logs in through GraphQL Mutation.login -> Auth Service -> Redis session."""
        mutation = """
        mutation LoginUser($input: LoginInput!) {
          login(input: $input) {
            accessToken
            refreshToken
            tokenType
            expiresIn
            sessionId
            user {
              id
              email
              role
              accountStatus
            }
          }
        }
        """
        res = await self.execute(
            mutation,
            variables={"input": {"email": email, "password": password}},
            headers={},
        )
        assert "errors" not in res, f"Login failed for {email}: {res.get('errors')}"
        payload = res["data"]["login"]
        self._token_cache[email] = payload["accessToken"]
        return payload

    async def _resolve_default_headers(self, query: str) -> dict[str, str]:
        if any(marker in query for marker in PUBLIC_AUTH_MARKERS):
            return {}

        if any(marker in query for marker in ADMIN_OPS_MARKERS):
            email, pw = "admin@logistics.by", "AdminPass123!"
        else:
            email, pw = "client@logistics.by", "ClientPass123!"

        token = self._token_cache.get(email)
        if not token:
            payload = await self.login_as(email, pw)
            token = payload["accessToken"]
        return {"Authorization": f"Bearer {token}"}

    async def execute(
        self,
        query: str,
        variables: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """
        Executes a GraphQL query/mutation and returns the JSON payload.
        When `headers` is explicitly provided (even `{}`), uses it verbatim.
        When `headers` is None, attaches a valid JWT for legacy regression tests.
        """
        payload = {"query": query}
        if variables is not None:
            payload["variables"] = variables

        req_headers = {"Content-Type": "application/json"}
        if headers is not None:
            req_headers.update(headers)
        else:
            req_headers.update(await self._resolve_default_headers(query))

        response = await self._client.post(
            self.endpoint,
            json=payload,
            headers=req_headers,
            timeout=15.0,
        )
        return response.json()

    async def execute_raw(
        self,
        query: str,
        variables: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Executes a GraphQL query and returns raw httpx.Response for status code assertions."""
        payload = {"query": query}
        if variables is not None:
            payload["variables"] = variables

        req_headers = {"Content-Type": "application/json"}
        if headers is not None:
            req_headers.update(headers)
        else:
            req_headers.update(await self._resolve_default_headers(query))

        return await self._client.post(
            self.endpoint,
            json=payload,
            headers=req_headers,
            timeout=15.0,
        )


@pytest_asyncio.fixture(scope="session")
async def graphql_client():
    """
    Session-scoped GraphQL client fixture.
    Checks if a live server is running at GRAPHQL_URL / http://127.0.0.1:8000.
    If yes, targets the live server.
    If not, imports gateway.app:app and runs with httpx ASGI transport in-process.
    """
    live_url = os.environ.get("GRAPHQL_URL", "http://127.0.0.1:8000/graphql")
    base_live = live_url.rsplit("/graphql", 1)[0] or "http://127.0.0.1:8000"

    use_live = False
    if os.environ.get("USE_LIVE_SERVER") == "1":
        use_live = True
    else:
        try:
            async with httpx.AsyncClient(timeout=1.0) as probe:
                r = await probe.get(live_url)
                if r.status_code in (200, 400, 405):
                    use_live = True
        except Exception:
            use_live = False

    if use_live:
        async with httpx.AsyncClient(base_url=base_live) as client:
            yield GraphQLExecutor(client, endpoint="/graphql")
    else:
        from gateway.app import app

        try:
            from httpx import ASGITransport
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield GraphQLExecutor(client, endpoint="/graphql")
        except ImportError:
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                yield GraphQLExecutor(client, endpoint="/graphql")


@pytest.fixture
def known_tracking_number() -> str:
    return KNOWN_TRACKING_NUMBER


@pytest.fixture
def known_client_id() -> str:
    return KNOWN_CLIENT_ID


@pytest.fixture
def known_tariff_id() -> str:
    return KNOWN_TARIFF_ID


@pytest.fixture
def known_courier_id() -> str:
    return KNOWN_COURIER_ID


@pytest.fixture
def known_delivery_id() -> str:
    return KNOWN_DELIVERY_ID


@pytest.fixture
def non_existent_tracking() -> str:
    return NON_EXISTENT_TRACKING


@pytest.fixture
def non_existent_uuid() -> str:
    return NON_EXISTENT_UUID
