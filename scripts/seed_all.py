#!/usr/bin/env python3
"""
scripts/seed_all.py
Multi-Database Idempotent Seeder and Verification Tool for Lab 3 Logistics BFF.
Populates all 7 PostgreSQL 16 microservice databases with linked mock data.
"""

import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Dict, List, Tuple

from sqlalchemy import text
from services.common.database import (
    get_engine_for_db,
    create_tables_for_db,
    session_scope,
)
from services.common.registry import SERVICE_REGISTRY

# Deterministic IDs
CLIENT_1_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
CLIENT_2_ID = uuid.UUID("a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d")
COURIER_USER_1_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
COURIER_USER_2_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")
ADMIN_USER_ID = uuid.UUID("990e8400-e29b-41d4-a716-446655449999")

TARIFF_STANDARD_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8001")
TARIFF_EXPRESS_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8002")
TARIFF_OVERNIGHT_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8003")

COURIER_1_ID = uuid.UUID("88776655-4433-2211-00aa-bbccddeeff11")
COURIER_2_ID = uuid.UUID("88776655-4433-2211-00aa-bbccddeeff22")

SHIPMENT_1_ID = uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d")
SHIPMENT_2_ID = uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6e")
SHIPMENT_3_ID = uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6f")

ROUTE_1_ID = uuid.UUID("4c219800-4b10-4100-bc11-9a8b7c6d5e4f")
ROUTE_2_ID = uuid.UUID("4c219800-4b10-4100-bc11-9a8b7c6d5e50")

STAGE_1_PICKUP_ID = uuid.UUID("a1100223-bb44-4555-8899-ccddeeff0011")
STAGE_1_MAIN_ID = uuid.UUID("a1100223-bb44-4555-8899-ccddeeff0012")
STAGE_1_LAST_ID = uuid.UUID("a1100223-bb44-4555-8899-ccddeeff0013")
STAGE_2_PICKUP_ID = uuid.UUID("a1100223-bb44-4555-8899-ccddeeff0021")
STAGE_2_LAST_ID = uuid.UUID("a1100223-bb44-4555-8899-ccddeeff0022")

DELIVERY_1_ID = uuid.UUID("33221100-4455-6677-8899-aabbccddeeff")
DELIVERY_2_ID = uuid.UUID("33221100-4455-6677-8899-aabbccddeef0")

CHECKPOINT_1_ID = uuid.UUID("77665544-3322-1100-ffee-ddccbbaa0001")
CHECKPOINT_2_ID = uuid.UUID("77665544-3322-1100-ffee-ddccbbaa0002")
CHECKPOINT_3_ID = uuid.UUID("77665544-3322-1100-ffee-ddccbbaa0003")
CHECKPOINT_4_ID = uuid.UUID("77665544-3322-1100-ffee-ddccbbaa0004")

# Tables to truncate per DB (child first)
TRUNCATE_TABLES = {
    "user_db": ["users", "roles"],
    "tariff_db": ["tariffs"],
    "courier_db": ["couriers"],
    "shipment_db": ["shipment_status_history", "shipments"],
    "route_db": ["route_stages", "routes"],
    "delivery_db": ["delivery_checkpoints", "deliveries"],
    "analytics_db": ["events_shipment_stream", "daily_delivery_stats"],
}

EXPECTED_COUNTS = {
    ("user_db", "roles"): 3,
    ("user_db", "users"): 5,
    ("tariff_db", "tariffs"): 3,
    ("courier_db", "couriers"): 2,
    ("shipment_db", "shipments"): 3,
    ("shipment_db", "shipment_status_history"): 7,
    ("route_db", "routes"): 2,
    ("route_db", "route_stages"): 5,
    ("delivery_db", "deliveries"): 2,
    ("delivery_db", "delivery_checkpoints"): 4,
    ("analytics_db", "events_shipment_stream"): 4,
    ("analytics_db", "daily_delivery_stats"): 3,
}


def ensure_tables():
    print("[1/4] Ensuring tables exist across all 7 databases via ORM metadata...")
    for db_name, models in SERVICE_REGISTRY.items():
        create_tables_for_db(db_name, models)
        print(f"  ✓ Tables created/verified for {db_name}")


def clean_tables():
    print("[2/4] Truncating tables for clean idempotency...")
    for db_name, tables in TRUNCATE_TABLES.items():
        engine = get_engine_for_db(db_name)
        with engine.begin() as conn:
            for table in tables:
                conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
        print(f"  ✓ Purged {db_name} ({', '.join(tables)})")


def seed_data():
    print("[3/4] Seeding linked mock data with cross-service UUIDs...")

    # 1. user_db (passwords hashed with bcrypt; never stored in plaintext)
    from services.auth_service.security_utils import hash_password

    client_pw_hash = hash_password("ClientPass123!")
    courier_pw_hash = hash_password("CourierPass123!")
    admin_pw_hash = hash_password("AdminPass123!")

    user_eng = get_engine_for_db("user_db")
    with user_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO roles (id, code, name, description) VALUES
            (1, 'ROLE_CLIENT', 'Клиент', 'Заказчик услуг доставки'),
            (2, 'ROLE_COURIER', 'Курьер', 'Исполнитель доставки'),
            (3, 'ROLE_ADMIN', 'Администратор', 'Управление системой и аналитика');
        """
            )
        )
        conn.execute(
            text(
                """
            INSERT INTO users (id, email, phone, password_hash, first_name, last_name, role_id, account_status) VALUES
            (:c1, 'client@logistics.by', '+375291234567', :pw_client, 'Иван', 'Иванов', 1, 'ACTIVE'),
            (:c2, 'client2@logistics.by', '+375297654321', :pw_client, 'Анна', 'Петрова', 1, 'ACTIVE'),
            (:co1, 'courier1@logistics.by', '+375292223344', :pw_courier, 'Дмитрий', 'Ковалев', 2, 'ACTIVE'),
            (:co2, 'courier2@logistics.by', '+375293334455', :pw_courier, 'Сергей', 'Сидоров', 2, 'ACTIVE'),
            (:adm, 'admin@logistics.by', '+375299998877', :pw_admin, 'Алексей', 'Администраторов', 3, 'ACTIVE');
        """
            ),
            {
                "c1": str(CLIENT_1_ID),
                "c2": str(CLIENT_2_ID),
                "co1": str(COURIER_USER_1_ID),
                "co2": str(COURIER_USER_2_ID),
                "adm": str(ADMIN_USER_ID),
                "pw_client": client_pw_hash,
                "pw_courier": courier_pw_hash,
                "pw_admin": admin_pw_hash,
            },
        )
    print("  ✓ Seeded user_db")

    # 2. tariff_db
    tariff_eng = get_engine_for_db("tariff_db")
    with tariff_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO tariffs (id, code, name, description, base_price, price_per_kg, price_per_km, urgency_multiplier, max_delivery_days, is_active) VALUES
            (:t_std, 'STANDARD', 'Стандарт', 'Доставка по РБ за 3 дня', 5.00, 1.50, 0.05, 1.00, 3, TRUE),
            (:t_exp, 'EXPRESS', 'Экспресс', 'Доставка на следующий день', 10.00, 2.50, 0.10, 1.50, 1, TRUE),
            (:t_ovn, 'OVERNIGHT', 'Ночной экспресс', 'Доставка к утру', 20.00, 4.00, 0.15, 2.00, 1, TRUE);
        """
            ),
            {
                "t_std": str(TARIFF_STANDARD_ID),
                "t_exp": str(TARIFF_EXPRESS_ID),
                "t_ovn": str(TARIFF_OVERNIGHT_ID),
            },
        )
    print("  ✓ Seeded tariff_db")

    # 3. courier_db
    courier_eng = get_engine_for_db("courier_db")
    with courier_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO couriers (id, user_id, transport_type, vehicle_plate, max_payload_kg, current_status, current_lat, current_lon, rating, total_deliveries) VALUES
            (:c1, :u1, 'CAR', '1234-AB-7', 250.00, 'AVAILABLE', 52.098110, 23.689020, 4.95, 142),
            (:c2, :u2, 'BICYCLE', NULL, 15.00, 'AVAILABLE', 53.902280, 27.561830, 4.80, 89);
        """
            ),
            {
                "c1": str(COURIER_1_ID),
                "u1": str(COURIER_USER_1_ID),
                "c2": str(COURIER_2_ID),
                "u2": str(COURIER_USER_2_ID),
            },
        )
    print("  ✓ Seeded courier_db")

    # 4. shipment_db
    shipment_eng = get_engine_for_db("shipment_db")
    with shipment_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO shipments (
                id, tracking_number, client_id, tariff_id, weight_kg, length_cm, width_cm, height_cm,
                calculated_price, current_status, origin_city, origin_address, origin_lat, origin_lon,
                dest_city, dest_address, dest_lat, dest_lon, recipient_name, recipient_phone, created_at, updated_at
            ) VALUES
            (
                :s1, 'PKG-BY-2026-849201', :c1, :t1, 2.50, 30.00, 20.00, 15.00, 24.50, 'IN_TRANSIT',
                'Минск', 'пр-т Независимости, 4', 53.899820, 27.566580,
                'Брест', 'ул. Ленина, 22', 52.097550, 23.687750,
                'Иванов Иван Иванович', '+375291234567', '2026-10-12 10:00:00+00', '2026-10-12 14:30:00+00'
            ),
            (
                :s2, 'PKG-BY-2026-849202', :c1, :t2, 1.20, 20.00, 15.00, 10.00, 18.00, 'DELIVERED',
                'Минск', 'ул. Якуба Коласа, 28', 53.921500, 27.592300,
                'Гродно', 'ул. Советская, 10', 53.681200, 23.831500,
                'Смирнова Ольга Викторовна', '+375294445566', '2026-10-10 09:00:00+00', '2026-10-11 16:00:00+00'
            ),
            (
                :s3, 'PKG-BY-2026-849203', :c2, :t3, 5.00, 40.00, 30.00, 25.00, 65.00, 'CREATED',
                'Минск', 'пр-т Дзержинского, 100', 53.864300, 27.485100,
                'Витебск', 'ул. Ленина, 5', 55.192700, 30.206400,
                'Кузнецов Петр Васильевич', '+375298887766', '2026-10-25 11:00:00+00', '2026-10-25 11:00:00+00'
            );
        """
            ),
            {
                "s1": str(SHIPMENT_1_ID),
                "c1": str(CLIENT_1_ID),
                "t1": str(TARIFF_STANDARD_ID),
                "s2": str(SHIPMENT_2_ID),
                "t2": str(TARIFF_EXPRESS_ID),
                "s3": str(SHIPMENT_3_ID),
                "c2": str(CLIENT_2_ID),
                "t3": str(TARIFF_OVERNIGHT_ID),
            },
        )
        conn.execute(
            text(
                """
            INSERT INTO shipment_status_history (id, shipment_id, status, comment, changed_at) VALUES
            (gen_random_uuid(), :s1, 'CREATED', 'Заказ оформлен клиентом', '2026-10-12 10:00:00+00'),
            (gen_random_uuid(), :s1, 'ASSIGNED', 'Назначен курьер', '2026-10-12 10:05:00+00'),
            (gen_random_uuid(), :s1, 'PICKED_UP', 'Посылка получена у отправителя', '2026-10-12 11:30:00+00'),
            (gen_random_uuid(), :s1, 'IN_TRANSIT', 'Магистральный транзит Минск-Брест', '2026-10-12 14:30:00+00'),
            (gen_random_uuid(), :s2, 'CREATED', 'Заказ оформлен клиентом', '2026-10-10 09:00:00+00'),
            (gen_random_uuid(), :s2, 'DELIVERED', 'Вручено получателю лично', '2026-10-11 16:00:00+00'),
            (gen_random_uuid(), :s3, 'CREATED', 'Заказ оформлен клиентом', '2026-10-25 11:00:00+00');
        """
            ),
            {"s1": str(SHIPMENT_1_ID), "s2": str(SHIPMENT_2_ID), "s3": str(SHIPMENT_3_ID)},
        )
    print("  ✓ Seeded shipment_db")

    # 5. route_db
    route_eng = get_engine_for_db("route_db")
    with route_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO routes (id, shipment_id, total_distance_km, estimated_duration_min, current_stage_order, status, created_at) VALUES
            (:r1, :s1, 352.40, 360, 2, 'ACTIVE', '2026-10-12 10:00:02+00'),
            (:r2, :s2, 295.00, 300, 3, 'COMPLETED', '2026-10-10 09:05:00+00');
        """
            ),
            {
                "r1": str(ROUTE_1_ID),
                "s1": str(SHIPMENT_1_ID),
                "r2": str(ROUTE_2_ID),
                "s2": str(SHIPMENT_2_ID),
            },
        )
        conn.execute(
            text(
                """
            INSERT INTO route_stages (id, route_id, stage_order, stage_type, origin_point, dest_point, planned_start, planned_end, status) VALUES
            (:st1_1, :r1, 1, 'PICKUP', 'г. Минск, пр-т Независимости, 4', 'Сортировочный хаб Минск-Север', '2026-10-12 10:30:00+00', '2026-10-12 12:00:00+00', 'COMPLETED'),
            (:st1_2, :r1, 2, 'MAIN_TRANSIT', 'Хаб Минск-Север', 'Хаб Брест-Центр', '2026-10-12 13:00:00+00', '2026-10-12 17:00:00+00', 'IN_PROGRESS'),
            (:st1_3, :r1, 3, 'LAST_MILE', 'Хаб Брест-Центр', 'г. Брест, ул. Ленина, 22', '2026-10-13 09:00:00+00', '2026-10-13 12:00:00+00', 'PENDING'),
            (:st2_1, :r2, 1, 'PICKUP', 'Минск', 'Хаб Минск', '2026-10-10 09:30:00+00', '2026-10-10 11:00:00+00', 'COMPLETED'),
            (:st2_2, :r2, 2, 'LAST_MILE', 'Хаб Гродно', 'Гродно', '2026-10-11 14:00:00+00', '2026-10-11 16:00:00+00', 'COMPLETED');
        """
            ),
            {
                "r1": str(ROUTE_1_ID),
                "r2": str(ROUTE_2_ID),
                "st1_1": str(STAGE_1_PICKUP_ID),
                "st1_2": str(STAGE_1_MAIN_ID),
                "st1_3": str(STAGE_1_LAST_ID),
                "st2_1": str(STAGE_2_PICKUP_ID),
                "st2_2": str(STAGE_2_LAST_ID),
            },
        )
    print("  ✓ Seeded route_db")

    # 6. delivery_db
    delivery_eng = get_engine_for_db("delivery_db")
    with delivery_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO deliveries (
                id, shipment_id, route_stage_id, courier_id, delivery_type, status,
                window_start, window_end, actual_delivered_at, otp_code_hash, created_at
            ) VALUES
            (
                :d1, :s1, :st1, :c1,
                'FIRST_MILE_PICKUP', 'PICKED_UP',
                '2026-10-12 10:30:00+00', '2026-10-12 12:00:00+00', NULL,
                '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', '2026-10-12 10:05:00+00'
            ),
            (
                :d2, :s2, :st2, :c1,
                'LAST_MILE_DROPOFF', 'DELIVERED',
                '2026-10-11 14:00:00+00', '2026-10-11 16:00:00+00', '2026-10-11 15:45:00+00',
                '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', '2026-10-11 13:30:00+00'
            );
        """
            ),
            {
                "d1": str(DELIVERY_1_ID),
                "s1": str(SHIPMENT_1_ID),
                "st1": str(STAGE_1_PICKUP_ID),
                "c1": str(COURIER_1_ID),
                "d2": str(DELIVERY_2_ID),
                "s2": str(SHIPMENT_2_ID),
                "st2": str(STAGE_2_LAST_ID),
            },
        )
        conn.execute(
            text(
                """
            INSERT INTO delivery_checkpoints (id, delivery_id, status, recorded_at, location_name, notes) VALUES
            (:cp1, :d1, 'ACCEPTED', '2026-10-12 10:10:00+00', 'Курьер принял заказ в работу', 'Курьер выехал на адрес забора'),
            (:cp2, :d1, 'PICKED_UP', '2026-10-12 11:30:00+00', 'Адрес клиента (г. Минск, Независимости 4)', 'Груз получен, вес и габариты проверены'),
            (:cp3, :d1, 'AT_HUB', '2026-10-12 12:15:00+00', 'Сортировочный хаб Минск-Север', 'Груз принят на складе консолидации'),
            (:cp4, :d2, 'DELIVERED', '2026-10-11 15:45:00+00', 'г. Гродно, ул. Советская, 10', 'Вручено получателю лично в руки с проверкой OTP');
        """
            ),
            {
                "cp1": str(CHECKPOINT_1_ID),
                "cp2": str(CHECKPOINT_2_ID),
                "cp3": str(CHECKPOINT_3_ID),
                "cp4": str(CHECKPOINT_4_ID),
                "d1": str(DELIVERY_1_ID),
                "d2": str(DELIVERY_2_ID),
            },
        )
    print("  ✓ Seeded delivery_db")

    # 7. analytics_db
    analytics_eng = get_engine_for_db("analytics_db")
    with analytics_eng.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO events_shipment_stream (
                event_id, event_time, event_type, shipment_id, client_id, tariff_id,
                weight_kg, price, origin_city, dest_city, total_distance_km, courier_id, is_delayed
            ) VALUES
            ('c8a412b1-6a20-410d-88b1-3cf8a2e1d091', '2026-10-12 10:00:00+00', 'CREATED', :s1, :c1, :t1, 2.50, 24.50, 'Минск', 'Брест', 352.40, NULL, FALSE),
            ('c8a412b1-6a20-410d-88b1-3cf8a2e1d092', '2026-10-12 10:05:00+00', 'ASSIGNED', :s1, :c1, :t1, 2.50, 24.50, 'Минск', 'Брест', 352.40, :co1, FALSE),
            ('c8a412b1-6a20-410d-88b1-3cf8a2e1d093', '2026-10-12 11:30:00+00', 'PICKED_UP', :s1, :c1, :t1, 2.50, 24.50, 'Минск', 'Брест', 352.40, :co1, FALSE),
            ('c8a412b1-6a20-410d-88b1-3cf8a2e1d094', '2026-10-11 15:45:00+00', 'DELIVERED', :s2, :c1, :t2, 1.20, 18.00, 'Минск', 'Гродно', 295.00, :co1, FALSE);
        """
            ),
            {
                "s1": str(SHIPMENT_1_ID),
                "s2": str(SHIPMENT_2_ID),
                "c1": str(CLIENT_1_ID),
                "t1": str(TARIFF_STANDARD_ID),
                "t2": str(TARIFF_EXPRESS_ID),
                "co1": str(COURIER_1_ID),
            },
        )
        conn.execute(
            text(
                """
            INSERT INTO daily_delivery_stats (report_date, tariff_code, shipments_count, delivered_count, total_revenue, avg_delivery_time_min, sla_compliance_rate) VALUES
            ('2026-10-11', 'EXPRESS', 5, 5, 90.00, 180.0, 1.00),
            ('2026-10-12', 'STANDARD', 8, 7, 196.00, 320.0, 0.95),
            ('2026-10-12', 'OVERNIGHT', 2, 2, 130.00, 120.0, 1.00);
        """
            )
        )
    print("  ✓ Seeded analytics_db")


def verify_counts() -> bool:
    print("[4/4] Verifying table counts across all databases...")
    print("=" * 72)
    print(f" {'DATABASE':<15} {'TABLE':<26} {'EXPECTED':<10} {'ACTUAL':<10} {'STATUS'}")
    print("=" * 72)

    all_passed = True
    total_records = 0

    for (db_name, table_name), expected_count in EXPECTED_COUNTS.items():
        engine = get_engine_for_db(db_name)
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};")).scalar()
            actual_count = int(result)
            total_records += actual_count
            passed = actual_count == expected_count
            if not passed:
                all_passed = False
            status = "OK" if passed else "FAIL"
            print(
                f" {db_name:<15} {table_name:<26} {expected_count:<10} {actual_count:<10} {status}"
            )

    print("=" * 72)
    if all_passed:
        print(f" SUCCESS: 12 tables verified, {total_records} records active!")
    else:
        print(" ERROR: Record count mismatch detected!")
    print("=" * 72)
    return all_passed


def main():
    try:
        ensure_tables()
        clean_tables()
        seed_data()
        success = verify_counts()
        if not success:
            sys.exit(1)
        sys.exit(0)
    except Exception as e:
        print(f"FATAL: Seeding failed with exception: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
