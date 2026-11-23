#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_lab5_demo.py
Demonstration runner for Laboratory Work 5:
Auth Service (REST), bcrypt password hashing, JWT issuance, Redis session TTL,
session revocation on logout, and RBAC / ownership protection in GraphQL API.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from decimal import Decimal

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ariadne import graphql
from starlette.datastructures import Headers
from gateway.app import graphql_error_formatter
from gateway.auth import resolve_auth_context
from gateway.clients.container import GatewayContainer
from gateway.schema import schema
from scripts.seed_all import clean_tables, seed_data


class _FakeRequest:
    def __init__(self, headers: dict | None = None):
        self.headers = Headers(headers or {})


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def run_graphql(
    query: str,
    variables: dict | None = None,
    container: GatewayContainer | None = None,
    token: str | None = None,
):
    cnt = container or GatewayContainer()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    auth_ctx = resolve_auth_context(_FakeRequest(headers), cnt)
    context = {"request": _FakeRequest(headers), "clients": cnt, **auth_ctx}
    _, result = await graphql(
        schema,
        {"query": query, "variables": variables or {}},
        context_value=context,
        error_formatter=graphql_error_formatter,
    )
    return result


async def main():
    print("================================================================================")
    print("  ЛАБОРАТОРНАЯ РАБОТА №5: БЕЗОПАСНОСТЬ GRAPHQL API, AUTH SERVICE, JWT И REDIS")
    print("================================================================================")

    print("\n[0/4] Инициализация и сидинг БД (пароли пользователей хешированы через bcrypt)...")
    clean_tables()
    seed_data()
    container = GatewayContainer()
    demo_results = {}

    # -------------------------------------------------------------------------
    # SCENARIO 1: LOGIN -> AUTH SERVICE -> JWT + REDIS SESSION
    # -------------------------------------------------------------------------
    print("\n[СЦЕНАРИЙ 1] Вход пользователя через Auth Service, выпуск JWT и создание сессии в Redis")
    q_login = """
    mutation LoginUser($input: LoginInput!) {
      login(input: $input) {
        accessToken
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
    var_client_login = {"input": {"email": "client@logistics.by", "password": "ClientPass123!"}}
    res_client_login = await run_graphql(q_login, var_client_login, container)
    client_payload = res_client_login["data"]["login"]
    client_token = client_payload["accessToken"]

    q_session = """
    query GetActiveSession {
      me {
        id
        email
        role
      }
      activeSession {
        sessionId
        email
        role
        ttlSeconds
        expiresAt
      }
    }
    """
    res_session = await run_graphql(q_session, {}, container, token=client_token)
    sess_info = res_session["data"]["activeSession"]
    print(f"  ✓ Пользователь {client_payload['user']['email']} ({client_payload['user']['role']}) аутентифицирован")
    print(f"  ✓ Сессия Redis: {sess_info['sessionId']} | TTL: {sess_info['ttlSeconds']} сек")

    # Mask raw JWT middle part in saved report JSON for readability
    masked_login_resp = json.loads(json.dumps(res_client_login))
    tok = masked_login_resp["data"]["login"]["accessToken"]
    masked_login_resp["data"]["login"]["accessToken"] = f"{tok[:24]}...{tok[-16:]}"

    demo_results["scenario1_login_session"] = {
        "login_query": q_login.strip(),
        "login_response": masked_login_resp,
        "session_query": q_session.strip(),
        "session_response": res_session,
    }

    # -------------------------------------------------------------------------
    # SCENARIO 2: UNAUTHENTICATED & INVALID TOKEN REJECTION
    # -------------------------------------------------------------------------
    print("\n[СЦЕНАРИЙ 2] Защита GraphQL API от неавторизованного доступа (без токена / невалидный JWT)")
    q_protected = """
    query ProtectedShipments {
      myShipments {
        totalCount
        items { trackingNumber }
      }
    }
    """
    res_unauth = await run_graphql(q_protected, {}, container, token=None)
    res_tampered = await run_graphql(q_protected, {}, container, token="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.bad_sig")
    print(f"  ✓ Запрос без токена: {res_unauth['errors'][0]['extensions']['code']} — {res_unauth['errors'][0]['message']}")
    print(f"  ✓ Запрос с поддельным JWT: {res_tampered['errors'][0]['extensions']['code']} — {res_tampered['errors'][0]['message']}")

    demo_results["scenario2_unauth_rejection"] = {
        "query": q_protected.strip(),
        "no_token_response": res_unauth,
        "tampered_token_response": res_tampered,
    }

    # -------------------------------------------------------------------------
    # SCENARIO 3: RBAC & RESOURCE OWNERSHIP ENFORCEMENT
    # -------------------------------------------------------------------------
    print("\n[СЦЕНАРИЙ 3] Разграничение прав доступа по ролям (RBAC) и владение ресурсами")
    # 3.1 Client allowed own shipment vs forbidden another client's shipment & admin analytics
    q_other_shipment = """
    query OtherClientShipment {
      shipment(trackingNumber: "PKG-BY-2026-849203") {
        trackingNumber
        calculatedPrice
      }
    }
    """
    res_client_other = await run_graphql(q_other_shipment, {}, container, token=client_token)
    print(f"  ✓ Клиент -> чужая посылка PKG-BY-2026-849203: {res_client_other['errors'][0]['extensions']['code']}")

    q_admin_analytics = """
    query AdminAnalytics {
      analyticsSummary(range: {startDate: "2026-10-01T00:00:00Z", endDate: "2026-10-31T23:59:59Z"}) {
        totalShipments
        deliveredShipments
        totalRevenue
        slaComplianceRate
      }
    }
    """
    res_client_analytics = await run_graphql(q_admin_analytics, {}, container, token=client_token)
    print(f"  ✓ Клиент -> analyticsSummary: {res_client_analytics['errors'][0]['extensions']['code']}")

    # 3.2 Login as Admin -> analyticsSummary succeeds
    res_admin_login = await run_graphql(
        q_login,
        {"input": {"email": "admin@logistics.by", "password": "AdminPass123!"}},
        container,
    )
    admin_token = res_admin_login["data"]["login"]["accessToken"]
    res_admin_analytics = await run_graphql(q_admin_analytics, {}, container, token=admin_token)
    print(f"  ✓ Администратор -> analyticsSummary: выручка {res_admin_analytics['data']['analyticsSummary']['totalRevenue']} BYN")

    # 3.3 Login as Courier -> own profile succeeds, assignCourier forbidden
    res_courier_login = await run_graphql(
        q_login,
        {"input": {"email": "courier1@logistics.by", "password": "CourierPass123!"}},
        container,
    )
    courier_token = res_courier_login["data"]["login"]["accessToken"]
    res_courier_prof = await run_graphql("query { courierProfile { id transportType currentStatus } }", {}, container, token=courier_token)
    res_courier_assign = await run_graphql(
        'mutation { assignCourier(input: {deliveryId: "33221100-4455-6677-8899-aabbccddeeff", courierId: "88776655-4433-2211-00aa-bbccddeeff11"}) { id } }',
        {},
        container,
        token=courier_token,
    )
    print(f"  ✓ Курьер -> свой профиль: {res_courier_prof['data']['courierProfile']['transportType']} ({res_courier_prof['data']['courierProfile']['currentStatus']})")
    print(f"  ✓ Курьер -> assignCourier: {res_courier_assign['errors'][0]['extensions']['code']}")

    demo_results["scenario3_rbac"] = {
        "client_other_shipment_query": q_other_shipment.strip(),
        "client_other_shipment_response": res_client_other,
        "client_analytics_response": res_client_analytics,
        "admin_analytics_query": q_admin_analytics.strip(),
        "admin_analytics_response": res_admin_analytics,
        "courier_profile_response": res_courier_prof,
        "courier_assign_response": res_courier_assign,
    }

    # -------------------------------------------------------------------------
    # SCENARIO 4: LOGOUT REVOKES REDIS SESSION (VALID JWT REJECTED)
    # -------------------------------------------------------------------------
    print("\n[СЦЕНАРИЙ 4] Отзыв сессии в Redis при logout: валидный JWT без активной сессии отклоняется")
    q_logout = "mutation { logout }"
    res_logout = await run_graphql(q_logout, {}, container, token=client_token)
    res_me_after_logout = await run_graphql("query { me { id email } }", {}, container, token=client_token)
    print(f"  ✓ Выход (logout): {res_logout['data']['logout']}")
    print(f"  ✓ Повторный запрос с тем же JWT после logout: {res_me_after_logout['errors'][0]['extensions']['code']} — {res_me_after_logout['errors'][0]['message']}")

    demo_results["scenario4_logout_revocation"] = {
        "logout_query": q_logout,
        "logout_response": res_logout,
        "after_logout_query": "query { me { id email } }",
        "after_logout_response": res_me_after_logout,
    }

    out_json_path = os.path.join(BASE_DIR, "scripts", "lab5_query_results.json")
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(demo_results, f, ensure_ascii=False, indent=2, default=decimal_default)
    print(f"\n[✓] Результаты демонстрации сохранены в: {out_json_path}")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(main())
