# -*- coding: utf-8 -*-
"""
Comprehensive Security, Authentication, Redis Session & RBAC Tests for Lab 5.
Covers:
1. Auth Service REST API & bcrypt password hashing (never plaintext).
2. JWT issuance, verification, expiration, and tampering rejection.
3. Redis session creation, TTL expiration, logout revocation, and rejection of valid JWT when Redis session is missing.
4. RBAC role restrictions and resource ownership checks across ROLE_CLIENT, ROLE_COURIER, and ROLE_ADMIN.
5. Service-layer actor authorization integration without re-verifying JWT.
"""

import asyncio
import time
import uuid
import pytest
from sqlalchemy import text

from services.auth_service.schemas import LoginRequest
from services.auth_service.security_utils import create_access_token
from services.auth_service.service import AuthService
from services.auth_service.session_store import RedisSessionStore
from services.common.database import get_engine_for_db
from services.common.exceptions import AuthenticationError, AuthorizationError
from services.common.security import AuthenticatedUser, ROLE_CLIENT, ROLE_COURIER, ROLE_ADMIN
from services.shipment_service.service import ShipmentService
from services.courier_service.service import CourierService
from services.analytics_service.service import AnalyticsService
from services.analytics_service.schemas import DateRangeInputDTO
from tests.test_graphql_e2e.conftest import (
    GraphQLExecutor,
    KNOWN_CLIENT_ID,
    KNOWN_COURIER_ID,
    KNOWN_DELIVERY_ID,
    KNOWN_TARIFF_ID,
    KNOWN_TRACKING_NUMBER,
)

CLIENT2_TRACKING = "PKG-BY-2026-849203"
COURIER2_ID = "88776655-4433-2211-00aa-bbccddeeff22"


# ==============================================================================
# 1. Password Security & Auth Service / Redis Session Unit & Integration Tests
# ==============================================================================

def test_passwords_are_hashed_with_bcrypt_in_user_db():
    """Verify user_db stores real bcrypt hashes, never plaintext or fake hashes."""
    engine = get_engine_for_db("user_db")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, password_hash FROM users;")).mappings().all()
    assert len(rows) >= 5
    for row in rows:
        pw_hash = row["password_hash"]
        assert pw_hash.startswith("$2b$") or pw_hash.startswith("$2a$"), (
            f"User {row['email']} does not have a bcrypt hash"
        )
        assert "Pass123!" not in pw_hash
        assert "fakehash" not in pw_hash


def test_redis_session_ttl_expiration_rejects_valid_jwt():
    """
    Critical Lab 5 invariant:
    Even when JWT is cryptographically valid and unexpired, missing/expired Redis session
    MUST cause verification failure.
    """
    store = RedisSessionStore()
    assert store.ping(), "Redis must be running for Lab 5 session tests"

    auth_svc = AuthService(session_store=store)
    tokens = auth_svc.login(
        LoginRequest(email="client@logistics.by", password="ClientPass123!"),
        session_ttl_seconds=2,
        access_ttl_seconds=300,  # JWT itself valid for 5 min, Redis session expires in 2s
    )

    # Immediately valid
    verified = auth_svc.verify_token(tokens.access_token)
    assert verified.valid is True
    assert verified.session.ttl_seconds >= 1

    # Wait for Redis TTL expiration
    time.sleep(2.3)

    with pytest.raises(AuthenticationError, match="session|expired|Redis"):
        auth_svc.verify_token(tokens.access_token)


# ==============================================================================
# 2. GraphQL Gateway Authentication & Session Lifecycle E2E Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected_on_protected_operations(graphql_client: GraphQLExecutor):
    """Unauthenticated calls (no Bearer token) to protected Query & Mutation must fail with UNAUTHENTICATED."""
    protected_ops = [
        ("query { me { id email } }", None),
        ("query { activeSession { sessionId } }", None),
        ("query { myShipments { totalCount } }", None),
        ("query { shipments { totalCount } }", None),
        ("query { couriers { id } }", None),
        ("query { shipmentStats { totalCount } }", None),
        ("query { courierPerformanceStats { totalCouriers } }", None),
        ('query { shipment(trackingNumber: "PKG-BY-2026-849201") { id } }', None),
        ('query { tracking(trackingNumber: "PKG-BY-2026-849201") { status } }', None),
        ('query { analyticsSummary(range: {startDate: "2026-10-01T00:00:00Z", endDate: "2026-10-31T00:00:00Z"}) { totalShipments } }', None),
        ('mutation { cancelShipment(trackingNumber: "PKG-BY-2026-849201") }', None),
        ('mutation { assignCourier(input: {deliveryId: "33221100-4455-6677-8899-aabbccddeeff", courierId: "88776655-4433-2211-00aa-bbccddeeff11"}) { id } }', None),
        ("mutation { logout }", None),
    ]
    for query_str, vars_dict in protected_ops:
        res = await graphql_client.execute(query_str, variables=vars_dict, headers={})
        assert "errors" in res, f"Expected auth error for unauthenticated call: {query_str}"
        code = res["errors"][0].get("extensions", {}).get("code")
        assert code == "UNAUTHENTICATED", f"Expected UNAUTHENTICATED for {query_str}, got {res['errors']}"


@pytest.mark.asyncio
async def test_public_tariffs_allowed_without_token(graphql_client: GraphQLExecutor):
    """Public catalog query `tariffs` remains accessible without authentication."""
    res = await graphql_client.execute("query { tariffs { id code name } }", headers={})
    assert "errors" not in res
    assert len(res["data"]["tariffs"]) >= 3


@pytest.mark.asyncio
async def test_login_invalid_credentials_rejected(graphql_client: GraphQLExecutor):
    """Wrong password fails authentication at Auth Service."""
    res = await graphql_client.execute(
        """
        mutation BadLogin($input: LoginInput!) {
          login(input: $input) { accessToken }
        }
        """,
        variables={"input": {"email": "client@logistics.by", "password": "WrongPassword!"}},
        headers={},
    )
    assert "errors" in res
    assert res["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_tampered_and_expired_jwt_rejected(graphql_client: GraphQLExecutor):
    """Tampered or expired JWTs are rejected before any resolver logic executes."""
    # 1. Tampered JWT
    res_tampered = await graphql_client.execute(
        "query { me { id } }",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.invalid_sig"},
    )
    assert "errors" in res_tampered
    assert res_tampered["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"

    # 2. Expired JWT
    expired_jwt = create_access_token(
        user_id=KNOWN_CLIENT_ID,
        email="client@logistics.by",
        role=ROLE_CLIENT,
        session_id=str(uuid.uuid4()),
        ttl_seconds=-10,
    )
    res_expired = await graphql_client.execute(
        "query { me { id } }",
        headers={"Authorization": f"Bearer {expired_jwt}"},
    )
    assert "errors" in res_expired
    assert res_expired["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_logout_revokes_redis_session_and_blocks_subsequent_requests(graphql_client: GraphQLExecutor):
    """
    Validates full Auth Service -> Redis session lifecycle:
    login -> activeSession works -> logout -> same valid JWT is rejected!
    """
    auth_payload = await graphql_client.login_as("client@logistics.by", "ClientPass123!")
    token = auth_payload["accessToken"]
    session_id = auth_payload["sessionId"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Active session query succeeds
    sess_res = await graphql_client.execute(
        "query { activeSession { sessionId email role ttlSeconds } }",
        headers=auth_headers,
    )
    assert "errors" not in sess_res
    assert sess_res["data"]["activeSession"]["sessionId"] == session_id
    assert sess_res["data"]["activeSession"]["ttlSeconds"] > 0

    # 2. Logout revokes Redis session
    logout_res = await graphql_client.execute("mutation { logout }", headers=auth_headers)
    assert "errors" not in logout_res
    assert logout_res["data"]["logout"] is True

    # 3. Same cryptographically valid JWT is now rejected because Redis session is gone
    after_logout = await graphql_client.execute("query { me { id email } }", headers=auth_headers)
    assert "errors" in after_logout
    assert after_logout["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_register_new_client_and_block_admin_self_registration(graphql_client: GraphQLExecutor):
    """Tests public registration via Auth Service and rejection of ROLE_ADMIN self-elevation."""
    unique_suffix = uuid.uuid4().hex[:8]
    reg_mutation = """
    mutation RegisterUser($input: RegisterUserInput!) {
      register(input: $input) {
        accessToken
        sessionId
        user {
          id
          email
          role
        }
      }
    }
    """
    # 1. Self-registration as ROLE_ADMIN must be rejected
    admin_attempt = await graphql_client.execute(
        reg_mutation,
        variables={
            "input": {
                "email": f"hacker_{unique_suffix}@logistics.by",
                "phone": f"+37529{unique_suffix[:7]}",
                "password": "StrongPassword123!",
                "firstName": "Hack",
                "lastName": "Attempt",
                "role": "ROLE_ADMIN",
            }
        },
        headers={},
    )
    assert "errors" in admin_attempt
    assert admin_attempt["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # 2. Standard ROLE_CLIENT registration succeeds and can call `me` immediately
    ok_reg = await graphql_client.execute(
        reg_mutation,
        variables={
            "input": {
                "email": f"newuser_{unique_suffix}@logistics.by",
                "phone": f"+37544{int(unique_suffix, 16) % 10000000:07d}",
                "password": "ClientPass123!",
                "firstName": "Мария",
                "lastName": "Новикова",
                "role": "ROLE_CLIENT",
            }
        },
        headers={},
    )
    assert "errors" not in ok_reg, f"Registration failed: {ok_reg.get('errors')}"
    token = ok_reg["data"]["register"]["accessToken"]
    me_res = await graphql_client.execute(
        "query { me { email role } }",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "errors" not in me_res
    assert me_res["data"]["me"]["email"] == f"newuser_{unique_suffix}@logistics.by"
    assert me_res["data"]["me"]["role"] == "ROLE_CLIENT"


# ==============================================================================
# 3. Role-Based Access Control (RBAC) & Ownership Enforcement Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_rbac_client_permissions_and_ownership(graphql_client: GraphQLExecutor):
    """
    ROLE_CLIENT:
    - Allowed: me, myShipments, own shipment/tracking, createShipment, cancel own shipment
    - Forbidden: admin analytics/lists, courier ops, other client's shipments
    """
    client_auth = await graphql_client.login_as("client@logistics.by", "ClientPass123!")
    headers = {"Authorization": f"Bearer {client_auth['accessToken']}"}

    # Allowed: own shipment
    own_res = await graphql_client.execute(
        'query { shipment(trackingNumber: "PKG-BY-2026-849201") { trackingNumber client { id } } }',
        headers=headers,
    )
    assert "errors" not in own_res
    assert own_res["data"]["shipment"]["trackingNumber"] == KNOWN_TRACKING_NUMBER

    # Forbidden: another client's shipment (client2)
    other_res = await graphql_client.execute(
        f'query {{ shipment(trackingNumber: "{CLIENT2_TRACKING}") {{ trackingNumber }} }}',
        headers=headers,
    )
    assert "errors" in other_res
    assert other_res["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # Forbidden: cancel another client's shipment
    cancel_other = await graphql_client.execute(
        f'mutation {{ cancelShipment(trackingNumber: "{CLIENT2_TRACKING}", reason: "Unauthorized") }}',
        headers=headers,
    )
    assert "errors" in cancel_other
    assert cancel_other["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # Forbidden: admin & courier operations
    forbidden_queries = [
        'query { analyticsSummary(range: {startDate: "2026-10-01T00:00:00Z", endDate: "2026-10-31T00:00:00Z"}) { totalShipments } }',
        "query { shipments { totalCount } }",
        "query { shipmentStats { totalCount } }",
        "query { couriers { id } }",
        "query { courierPerformanceStats { totalCouriers } }",
        "query { courierProfile { id } }",
        f'mutation {{ assignCourier(input: {{deliveryId: "{KNOWN_DELIVERY_ID}", courierId: "{KNOWN_COURIER_ID}"}}) {{ id }} }}',
        'mutation { updateCourierStatus(input: {status: OFFLINE}) { id } }',
    ]
    for q in forbidden_queries:
        res = await graphql_client.execute(q, headers=headers)
        assert "errors" in res, f"Expected FORBIDDEN for client executing {q}"
        assert res["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_rbac_courier_permissions_and_ownership(graphql_client: GraphQLExecutor):
    """
    ROLE_COURIER:
    - Allowed: own courierProfile, own courierDeliveries, own updateCourierStatus/Location, own delivery checkpoint
    - Forbidden: admin ops, client create/cancel shipment, other courier's profile/deliveries
    """
    courier1_auth = await graphql_client.login_as("courier1@logistics.by", "CourierPass123!")
    c1_headers = {"Authorization": f"Bearer {courier1_auth['accessToken']}"}

    courier2_auth = await graphql_client.login_as("courier2@logistics.by", "CourierPass123!")
    c2_headers = {"Authorization": f"Bearer {courier2_auth['accessToken']}"}

    # Allowed: own profile & deliveries
    prof_res = await graphql_client.execute("query { courierProfile { id transportType } }", headers=c1_headers)
    assert "errors" not in prof_res
    assert prof_res["data"]["courierProfile"]["id"] == KNOWN_COURIER_ID

    deliv_res = await graphql_client.execute(
        f'query {{ courierDeliveries(courierId: "{KNOWN_COURIER_ID}") {{ id status }} }}',
        headers=c1_headers,
    )
    assert "errors" not in deliv_res
    assert len(deliv_res["data"]["courierDeliveries"]) >= 1

    # Allowed: update own location
    loc_res = await graphql_client.execute(
        "mutation { updateCourierLocation(input: {latitude: 53.90, longitude: 27.56}) }",
        headers=c1_headers,
    )
    assert "errors" not in loc_res
    assert loc_res["data"]["updateCourierLocation"] is True

    # Forbidden: courier2 trying to view courier1's profile/deliveries or update courier1's delivery
    other_prof = await graphql_client.execute(
        f'query {{ courierProfile(courierId: "{KNOWN_COURIER_ID}") {{ id }} }}',
        headers=c2_headers,
    )
    assert other_prof["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    other_deliv = await graphql_client.execute(
        f'query {{ courierDeliveries(courierId: "{KNOWN_COURIER_ID}") {{ id }} }}',
        headers=c2_headers,
    )
    assert other_deliv["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    other_cp = await graphql_client.execute(
        f'mutation {{ updateDeliveryCheckpoint(input: {{deliveryId: "{KNOWN_DELIVERY_ID}", status: "IN_TRANSIT", locationName: "Hack"}}) {{ id }} }}',
        headers=c2_headers,
    )
    assert other_cp["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # Forbidden: courier calling admin or client-only mutations
    for q in [
        "query { shipments { totalCount } }",
        'query { analyticsSummary(range: {startDate: "2026-10-01T00:00:00Z", endDate: "2026-10-31T00:00:00Z"}) { totalShipments } }',
        f'mutation {{ assignCourier(input: {{deliveryId: "{KNOWN_DELIVERY_ID}", courierId: "{KNOWN_COURIER_ID}"}}) {{ id }} }}',
        f'mutation {{ createShipment(input: {{tariffId: "{KNOWN_TARIFF_ID}", weightKg: 1.0, dimensions: {{lengthCm: 10, widthCm: 10, heightCm: 10}}, originCity: "Минск", originAddress: "А", destCity: "Брест", destAddress: "Б", recipientName: "Иван", recipientPhone: "+375291112233"}}) {{ id }} }}',
    ]:
        res = await graphql_client.execute(q, headers=c1_headers)
        assert res["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_rbac_admin_full_operational_access(graphql_client: GraphQLExecutor):
    """ROLE_ADMIN has authorized access to analytics, rosters, shipments, and dispatch operations."""
    admin_auth = await graphql_client.login_as("admin@logistics.by", "AdminPass123!")
    headers = {"Authorization": f"Bearer {admin_auth['accessToken']}"}

    res = await graphql_client.execute(
        """
        query AdminOverview {
          me { email role }
          shipments { totalCount }
          couriers { id }
          shipmentStats { totalCount totalRevenue }
          courierPerformanceStats { totalCouriers }
          analyticsSummary(range: {startDate: "2026-10-01T00:00:00Z", endDate: "2026-10-31T23:59:59Z"}) {
            totalShipments
            totalRevenue
          }
        }
        """,
        headers=headers,
    )
    assert "errors" not in res, f"Admin overview failed: {res.get('errors')}"
    assert res["data"]["me"]["role"] == "ROLE_ADMIN"
    assert res["data"]["shipments"]["totalCount"] >= 3
    assert len(res["data"]["couriers"]) >= 2


# ==============================================================================
# 4. Service-Layer Actor Authorization Unit Tests (No JWT Re-verification)
# ==============================================================================

def test_service_layer_enforces_actor_rbac_without_jwt():
    """Verify internal services accept verified AuthenticatedUser and reject unauthorized actors."""
    client_actor = AuthenticatedUser(
        user_id=uuid.UUID(KNOWN_CLIENT_ID),
        email="client@logistics.by",
        role=ROLE_CLIENT,
        session_id="test-session",
    )
    courier_actor = AuthenticatedUser(
        user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),  # courier2
        email="courier2@logistics.by",
        role=ROLE_COURIER,
        session_id="test-session-2",
    )

    # ShipmentService: client1 cannot cancel client2's shipment; client cannot query global stats
    s_svc = ShipmentService()
    with pytest.raises(AuthorizationError):
        s_svc.cancel_shipment(CLIENT2_TRACKING, actor=client_actor)
    with pytest.raises(AuthorizationError):
        s_svc.get_shipment_stats(actor=client_actor)

    # CourierService: courier2 cannot update courier1's status
    c_svc = CourierService()
    with pytest.raises(AuthorizationError):
        c_svc.update_status(KNOWN_COURIER_ID, "OFFLINE", actor=courier_actor)

    # AnalyticsService: client cannot view analyticsSummary
    a_svc = AnalyticsService()
    with pytest.raises(AuthorizationError):
        a_svc.get_analytics_summary(
            DateRangeInputDTO(
                startDate="2026-10-01T00:00:00Z",
                endDate="2026-10-31T23:59:59Z",
            ),
            actor=client_actor,
        )
