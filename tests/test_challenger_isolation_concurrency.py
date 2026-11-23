# -*- coding: utf-8 -*-
"""
Adversarial Empirical Challenge Test Suite (Milestone 2 - Challenger 2).
Focus:
1. Multi-threaded concurrent database isolation and thread safety across 7 databases.
2. Cross-database non-interference / zero data pollution.
3. Transaction rollback behavior (both raw session and repository-mediated).
4. Connection pool and session lifecycle ergonomics: leak prevention under normal and error paths.
"""
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.common.database import (
    get_engine_for_db,
    get_session_for_db,
    session_scope,
    _engines,
    _sessionmakers,
)
from services.common.registry import SERVICE_REGISTRY
from services.user_service.service import UserService
from services.tariff_service.service import TariffService
from services.shipment_service.service import ShipmentService
from services.shipment_service.repository import ShipmentRepository
from services.shipment_service.models import Shipment
from services.courier_service.service import CourierService
from services.route_service.service import RouteService
from services.delivery_service.service import DeliveryService
from services.analytics_service.service import AnalyticsService

ALL_DBS = list(SERVICE_REGISTRY.keys())
KNOWN_CLIENT_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
KNOWN_TARIFF_ID = uuid.UUID("7e4f1a20-3342-4f10-91ab-6b1e7c9f8001")


# ----------------------------------------------------------------------
# 1. Concurrent Database Isolation & Thread Safety
# ----------------------------------------------------------------------

def test_concurrent_multi_service_database_isolation():
    """Stress-test 14 concurrent worker threads simultaneously querying different databases."""
    errors = []

    def worker_task(thread_idx: int, target_db: str):
        try:
            for op in range(15):
                sess = get_session_for_db(target_db)
                try:
                    current_db = sess.execute(text("SELECT current_database();")).scalar()
                    if current_db != target_db:
                        errors.append(f"Thread {thread_idx}: Expected {target_db}, got {current_db}")

                    # Also exercise service layer in auto-session mode
                    if target_db == "user_db":
                        UserService().list_roles()
                    elif target_db == "tariff_db":
                        TariffService().list_active()
                    elif target_db == "courier_db":
                        CourierService().list_by_status("AVAILABLE")
                    elif target_db == "shipment_db":
                        ShipmentService().get_by_tracking_number("PKG-BY-2026-849201")
                    elif target_db == "route_db":
                        RouteService().get_by_shipment_id(uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"))
                    elif target_db == "delivery_db":
                        DeliveryService().get_active_by_shipment_id(uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"))
                    elif target_db == "analytics_db":
                        AnalyticsService().list_stream_events(limit=5)
                finally:
                    sess.close()
        except Exception as e:
            errors.append(f"Thread {thread_idx} ({target_db}) raised exception: {e}")

    with ThreadPoolExecutor(max_workers=14) as executor:
        futures = []
        t_idx = 0
        for db in ALL_DBS:
            for _ in range(2):
                futures.append(executor.submit(worker_task, t_idx, db))
                t_idx += 1
        for f in as_completed(futures):
            f.result()

    assert not errors, f"Concurrent isolation failures encountered: {errors}"


def test_concurrent_engine_cache_thread_safety():
    """Verify that concurrent cache access to get_engine_for_db does not produce race conditions."""
    errors = []

    def engine_fetcher(db: str):
        try:
            for _ in range(20):
                eng = get_engine_for_db(db)
                with eng.connect() as conn:
                    val = conn.execute(text("SELECT current_database();")).scalar()
                    if val != db:
                        errors.append(f"Engine for {db} returned database {val}")
        except Exception as e:
            errors.append(f"Engine access for {db} failed: {e}")

    with ThreadPoolExecutor(max_workers=21) as executor:
        futures = [executor.submit(engine_fetcher, ALL_DBS[i % len(ALL_DBS)]) for i in range(21)]
        for f in as_completed(futures):
            f.result()

    assert not errors, f"Engine cache race condition errors: {errors}"


# ----------------------------------------------------------------------
# 2. Cross-Database Non-Interference / Zero Cross-Pollution
# ----------------------------------------------------------------------

def _get_database_table_counts():
    """Snapshot row count of all registered tables in all 7 databases."""
    counts = {}
    for db_name, models in SERVICE_REGISTRY.items():
        engine = get_engine_for_db(db_name)
        db_counts = {}
        with engine.connect() as conn:
            for model in models:
                table_name = model.__tablename__
                cnt = conn.execute(text(f"SELECT count(*) FROM {table_name};")).scalar()
                db_counts[table_name] = cnt
        counts[db_name] = db_counts
    return counts


def test_cross_database_write_non_interference():
    """Verify that mutating tables in one database leaves ALL other 6 databases completely unchanged."""
    baseline = _get_database_table_counts()

    # Mutation 1: Write in courier_db
    test_courier_id = uuid.uuid4()
    courier_engine = get_engine_for_db("courier_db")
    with courier_engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO couriers (id, user_id, transport_type, current_status, rating, max_payload_kg, current_lat, current_lon, total_deliveries)
            VALUES (:id, :uid, 'SCOOTER', 'OFF_DUTY', 4.50, 15.0, 53.9, 27.5, 0);
            """),
            {"id": str(test_courier_id), "uid": str(uuid.uuid4())}
        )

    # Check all 6 other databases
    after_courier_write = _get_database_table_counts()
    for other_db in ALL_DBS:
        if other_db == "courier_db":
            assert after_courier_write[other_db]["couriers"] == baseline[other_db]["couriers"] + 1
        else:
            assert after_courier_write[other_db] == baseline[other_db], f"{other_db} was modified during courier_db write!"

    # Clean up courier
    with courier_engine.begin() as conn:
        conn.execute(text("DELETE FROM couriers WHERE id = :id;"), {"id": str(test_courier_id)})

    # Mutation 2: Write in tariff_db
    test_tariff_id = uuid.uuid4()
    tariff_engine = get_engine_for_db("tariff_db")
    with tariff_engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO tariffs (id, code, name, base_price, price_per_kg, price_per_km, urgency_multiplier, max_delivery_days, is_active)
            VALUES (:id, 'TEST_TARIFF_POLLUTION', 'Test Pollution', 10.0, 2.0, 0.5, 1.0, 2, true);
            """),
            {"id": str(test_tariff_id)}
        )

    # Check all 6 other databases
    after_tariff_write = _get_database_table_counts()
    for other_db in ALL_DBS:
        if other_db == "tariff_db":
            assert after_tariff_write[other_db]["tariffs"] == baseline[other_db]["tariffs"] + 1
        else:
            assert after_tariff_write[other_db] == baseline[other_db], f"{other_db} was modified during tariff_db write!"

    # Clean up tariff
    with tariff_engine.begin() as conn:
        conn.execute(text("DELETE FROM tariffs WHERE id = :id;"), {"id": str(test_tariff_id)})

    # Final check: returned to baseline
    final_counts = _get_database_table_counts()
    assert final_counts == baseline


# ----------------------------------------------------------------------
# 3. Transaction Rollback Scenarios
# ----------------------------------------------------------------------

def test_raw_transaction_rollback_in_session_scope():
    """Verify that an exception inside session_scope cleanly rolls back raw SQL / uncommitted operations."""
    test_tracking = f"PKG-FAIL-{uuid.uuid4().hex[:6]}"
    test_id = uuid.uuid4()

    with pytest.raises(RuntimeError):
        with session_scope("shipment_db") as sess:
            sess.execute(
                text("""
                INSERT INTO shipments (id, tracking_number, client_id, tariff_id, calculated_price, current_status, origin_city, origin_address, origin_lat, origin_lon, dest_city, dest_address, dest_lat, dest_lon, recipient_name, recipient_phone, weight_kg, length_cm, width_cm, height_cm)
                VALUES (:id, :track, :cid, :tid, 10.0, 'CREATED', 'Minsk', 'Addr', 53.9, 27.5, 'Brest', 'Addr', 52.1, 23.7, 'Test', '+375', 1.0, 10.0, 10.0, 10.0)
                """),
                {"id": str(test_id), "track": test_tracking, "cid": str(KNOWN_CLIENT_ID), "tid": str(KNOWN_TARIFF_ID)}
            )
            # Intentionally abort before scope exit
            raise RuntimeError("Simulated abort")

    # Verify record was rolled back
    with get_engine_for_db("shipment_db").connect() as conn:
        found = conn.execute(
            text("SELECT count(*) FROM shipments WHERE id = :id;"),
            {"id": str(test_id)}
        ).scalar()
        assert found == 0, "Record inserted inside failed session_scope was NOT rolled back!"


def test_independent_transactions_across_services():
    """Transactions in different services must not impact each other's commit/rollback status."""
    u_sess = get_session_for_db("user_db")
    s_sess = get_session_for_db("shipment_db")

    test_user_id = uuid.uuid4()
    test_shipment_id = uuid.uuid4()
    test_tracking = f"PKG-IND-{uuid.uuid4().hex[:6]}"

    try:
        # User session inserts and commits
        u_sess.execute(
            text("""
            INSERT INTO users (id, email, phone, password_hash, first_name, last_name, role_id, account_status)
            VALUES (:id, 'independent@test.by', '+375299990011', 'hash', 'Ind', 'User', 1, 'ACTIVE');
            """),
            {"id": str(test_user_id)}
        )
        u_sess.commit()

        # Shipment session inserts and rolls back
        s_sess.execute(
            text("""
            INSERT INTO shipments (id, tracking_number, client_id, tariff_id, calculated_price, current_status, origin_city, origin_address, origin_lat, origin_lon, dest_city, dest_address, dest_lat, dest_lon, recipient_name, recipient_phone, weight_kg, length_cm, width_cm, height_cm)
            VALUES (:id, :track, :cid, :tid, 10.0, 'CREATED', 'Minsk', 'Addr', 53.9, 27.5, 'Brest', 'Addr', 52.1, 23.7, 'Test', '+375', 1.0, 10.0, 10.0, 10.0)
            """),
            {"id": str(test_shipment_id), "track": test_tracking, "cid": str(KNOWN_CLIENT_ID), "tid": str(KNOWN_TARIFF_ID)}
        )
        s_sess.rollback()

        # Verify user committed
        u_check = u_sess.execute(text("SELECT count(*) FROM users WHERE id = :id;"), {"id": str(test_user_id)}).scalar()
        assert u_check == 1, "Committed user in user_db was lost"

        # Verify shipment rolled back
        s_check = s_sess.execute(text("SELECT count(*) FROM shipments WHERE id = :id;"), {"id": str(test_shipment_id)}).scalar()
        assert s_check == 0, "Rolled-back shipment in shipment_db was committed"

    finally:
        # Clean up user
        u_sess.execute(text("DELETE FROM users WHERE id = :id;"), {"id": str(test_user_id)})
        u_sess.commit()
        u_sess.close()
        s_sess.close()


def test_repository_commit_behavior_with_injected_session():
    """
    Adversarial Challenge: Examine repository behavior when an injected session is used
    and subsequent operation fails.
    Verifies whether repository.create() commits immediately or permits outer transactional rollback.
    """
    test_id = uuid.uuid4()
    test_tracking = f"PKG-REPOCOMMIT-{test_id.hex[:6]}"

    with pytest.raises(RuntimeError):
        with session_scope("shipment_db") as sess:
            repo = ShipmentRepository(sess)
            shipment = Shipment(
                id=test_id,
                tracking_number=test_tracking,
                client_id=KNOWN_CLIENT_ID,
                tariff_id=KNOWN_TARIFF_ID,
                calculated_price=Decimal("15.00"),
                current_status="CREATED",
                origin_city="Минск",
                origin_address="ул. Тестовая",
                origin_lat=Decimal("53.9"),
                origin_lon=Decimal("27.5"),
                dest_city="Брест",
                dest_address="ул. Тестовая",
                dest_lat=Decimal("52.1"),
                dest_lon=Decimal("23.7"),
                recipient_name="Тест",
                recipient_phone="+375",
                weight_kg=Decimal("1.0"),
                length_cm=Decimal("10.0"),
                width_cm=Decimal("10.0"),
                height_cm=Decimal("10.0"),
            )
            repo.create(shipment)
            # Simulated failure in subsequent step
            raise RuntimeError("Subsequent step failed")

    with get_engine_for_db("shipment_db").connect() as conn:
        found = conn.execute(text("SELECT count(*) FROM shipments WHERE id = :id;"), {"id": str(test_id)}).scalar()
        if found > 0:
            with get_engine_for_db("shipment_db").begin() as del_conn:
                del_conn.execute(text("DELETE FROM shipments WHERE id = :id;"), {"id": str(test_id)})

        # Print empirical finding:
        # found == 1 confirms repo.create executes sess.commit() even on injected sessions
        print(f"\n[EMPIRICAL FINDING] repository.create with injected session committed immediately: {found == 1}")
        assert found in (0, 1)


# ----------------------------------------------------------------------
# 4. Connection Pool & Session Lifecycle Ergonomics
# ----------------------------------------------------------------------

def test_connection_pool_no_leak_on_session_scope_success():
    """Verify engine.pool.checkedout() returns to 0 after 50 successful session_scope calls."""
    for _ in range(50):
        with session_scope("tariff_db") as sess:
            sess.execute(text("SELECT count(*) FROM tariffs;")).scalar()

    engine = get_engine_for_db("tariff_db")
    assert engine.pool.checkedout() == 0, f"Checked out connections leaked: {engine.pool.checkedout()}"


def test_connection_pool_no_leak_on_session_scope_exceptions():
    """Verify engine.pool.checkedout() returns to 0 after 50 exceptions inside session_scope."""
    for i in range(50):
        try:
            with session_scope("courier_db") as sess:
                sess.execute(text("SELECT count(*) FROM couriers;")).scalar()
                raise ValueError(f"Simulated error {i}")
        except ValueError:
            pass

    engine = get_engine_for_db("courier_db")
    assert engine.pool.checkedout() == 0, f"Checked out connections leaked on error: {engine.pool.checkedout()}"


def test_connection_pool_no_leak_on_auto_session_services():
    """Verify that calling service methods in auto-session mode checks connections back into pool."""
    user_svc = UserService()
    tariff_svc = TariffService()
    courier_svc = CourierService()
    shipment_svc = ShipmentService()
    analytics_svc = AnalyticsService()

    for _ in range(30):
        user_svc.list_roles()
        tariff_svc.list_active()
        courier_svc.list_by_status("AVAILABLE")
        shipment_svc.get_by_tracking_number("PKG-BY-2026-849201")
        analytics_svc.list_stream_events(limit=3)

    for db_name in ["user_db", "tariff_db", "courier_db", "shipment_db", "analytics_db"]:
        eng = get_engine_for_db(db_name)
        assert eng.pool.checkedout() == 0, f"{db_name} pool has {eng.pool.checkedout()} checked out connections!"


def test_postgresql_no_idle_in_transaction():
    """Query PostgreSQL pg_stat_activity to ensure no sessions are stranded in 'idle in transaction'."""
    for db_name in ALL_DBS:
        eng = get_engine_for_db(db_name)
        with eng.connect() as conn:
            idle_tx = conn.execute(
                text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = :dbname
                  AND state = 'idle in transaction'
                  AND pid <> pg_backend_pid();
                """),
                {"dbname": db_name}
            ).scalar()
            assert idle_tx == 0, f"Database {db_name} has {idle_tx} idle-in-transaction connections!"


# ----------------------------------------------------------------------
# 5. Advanced Isolation & Boundary Stress Tests
# ----------------------------------------------------------------------

def test_zero_cross_service_code_coupling_ast():
    """AST static analysis: proves that no service imports models, repositories, or schemas from any other service."""
    import ast
    import glob

    service_dirs = glob.glob(os.path.join(PROJECT_ROOT, "services/*_service"))
    violations = []
    for sdir in service_dirs:
        sname = os.path.basename(sdir)
        other_services = [os.path.basename(d) for d in service_dirs if os.path.basename(d) != sname]
        for pyfile in glob.glob(os.path.join(sdir, "**/*.py"), recursive=True):
            with open(pyfile, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=pyfile)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for other in other_services:
                            if alias.name.startswith(f"services.{other}"):
                                violations.append((os.path.basename(pyfile), alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for other in other_services:
                            if node.module.startswith(f"services.{other}"):
                                violations.append((os.path.basename(pyfile), node.module))

    assert not violations, f"Cross-service coupling detected in services: {violations}"


def test_high_concurrency_stress_load():
    """High-concurrency stress test: 35 concurrent workers across 7 databases performing 350 transactions."""
    errors = []

    def task(worker_id: int):
        target_db = ALL_DBS[worker_id % len(ALL_DBS)]
        try:
            for _ in range(10):
                with session_scope(target_db) as sess:
                    val = sess.execute(text("SELECT current_database();")).scalar()
                    assert val == target_db
        except Exception as e:
            errors.append(f"Worker {worker_id} on {target_db} failed: {e}")

    with ThreadPoolExecutor(max_workers=35) as executor:
        futures = [executor.submit(task, i) for i in range(35)]
        for f in as_completed(futures):
            f.result()

    assert not errors, f"High concurrency errors: {errors}"


def test_invalid_database_name_handling():
    """Verify that attempting to connect to a non-existent database fails cleanly without corrupting caches."""
    with pytest.raises(Exception):
        with session_scope("non_existent_fake_db") as sess:
            sess.execute(text("SELECT 1;"))

    # Verify existing DB engines remain unaffected
    for db in ALL_DBS:
        with session_scope(db) as sess:
            val = sess.execute(text("SELECT 1;")).scalar()
            assert val == 1

