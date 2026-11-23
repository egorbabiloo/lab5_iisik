"""
tests/test_isolation_integrity.py
Adversarial Verification Test Suite for Milestone 1:
- Proves physical database isolation (PostgreSQL strictly rejects cross-db joins)
- Asserts absence of cross-database bypass mechanisms (fdw, dblink)
- Verifies exhaustive logical UUID cross-reference integrity across all 7 databases
- Verifies intra-database foreign key constraint rejection behavior
"""
import uuid
import pytest
from sqlalchemy import text
from services.common.database import get_engine_for_db
from services.common.registry import SERVICE_REGISTRY


@pytest.mark.parametrize(
    "source_db,query,desc",
    [
        ("shipment_db", "SELECT * FROM user_db.public.users;", "select_users_from_shipment_db"),
        ("shipment_db", "SELECT s.id, u.email FROM shipments s JOIN user_db.public.users u ON s.client_id = u.id;", "join_users_from_shipment_db"),
        ("shipment_db", "SELECT s.id, t.name FROM shipments s JOIN tariff_db.public.tariffs t ON s.tariff_id = t.id;", "join_tariffs_from_shipment_db"),
        ("delivery_db", "SELECT d.id, c.user_id FROM deliveries d JOIN courier_db.public.couriers c ON d.courier_id = c.id;", "join_couriers_from_delivery_db"),
        ("route_db", "SELECT r.id, s.tracking_number FROM routes r JOIN shipment_db.public.shipments s ON r.shipment_id = s.id;", "join_shipments_from_route_db"),
        ("analytics_db", "SELECT e.event_id, s.tracking_number FROM events_shipment_stream e JOIN shipment_db.public.shipments s ON e.shipment_id = s.id;", "join_shipments_from_analytics_db"),
    ],
)
def test_cross_database_queries_strictly_rejected(source_db, query, desc):
    """PostgreSQL must raise FeatureNotSupported (cross-database references not implemented)."""
    engine = get_engine_for_db(source_db)
    with pytest.raises(Exception) as exc_info:
        with engine.connect() as conn:
            conn.execute(text(query))
    assert "cross-database references are not implemented" in str(exc_info.value)


def test_no_bypass_extensions():
    """Verify no FDW or dblink extensions exist to circumvent DB isolation."""
    suspicious_exts = {"postgres_fdw", "dblink", "file_fdw"}
    for db_name in SERVICE_REGISTRY.keys():
        engine = get_engine_for_db(db_name)
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT extname FROM pg_extension;")).fetchall()
            ext_names = {r[0] for r in rows}
            assert not ext_names.intersection(suspicious_exts), f"Database {db_name} has suspicious extensions: {ext_names}"


def test_exhaustive_uuid_cross_references():
    """Verify all logical UUID cross-references across databases resolve without orphans."""
    # 1. user_db
    with get_engine_for_db("user_db").connect() as conn:
        users = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM users;")).mappings().all()}
        roles = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM roles;")).mappings().all()}

    # 2. tariff_db
    with get_engine_for_db("tariff_db").connect() as conn:
        tariffs = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM tariffs;")).mappings().all()}
        tariffs_by_code = {row["code"]: dict(row) for row in tariffs.values()}

    # 3. courier_db
    with get_engine_for_db("courier_db").connect() as conn:
        couriers = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM couriers;")).mappings().all()}

    # 4. shipment_db
    with get_engine_for_db("shipment_db").connect() as conn:
        shipments = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM shipments;")).mappings().all()}

    # 5. route_db
    with get_engine_for_db("route_db").connect() as conn:
        routes = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM routes;")).mappings().all()}
        stages = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM route_stages;")).mappings().all()}

    # 6. delivery_db
    with get_engine_for_db("delivery_db").connect() as conn:
        deliveries = {row["id"]: dict(row) for row in conn.execute(text("SELECT * FROM deliveries;")).mappings().all()}

    # 7. analytics_db
    with get_engine_for_db("analytics_db").connect() as conn:
        events = conn.execute(text("SELECT * FROM events_shipment_stream;")).mappings().all()
        daily_stats = conn.execute(text("SELECT * FROM daily_delivery_stats;")).mappings().all()

    # Shipments -> Users & Tariffs
    for s in shipments.values():
        assert s["client_id"] in users, f"Shipment {s['id']} client_id missing in user_db"
        assert s["tariff_id"] in tariffs, f"Shipment {s['id']} tariff_id missing in tariff_db"

    # Couriers -> Users
    courier_role_id = next(r_id for r_id, r in roles.items() if r["code"] == "ROLE_COURIER")
    for c in couriers.values():
        assert c["user_id"] in users, f"Courier {c['id']} user_id missing in user_db"
        assert users[c["user_id"]]["role_id"] == courier_role_id, f"Courier user does not have ROLE_COURIER"

    # Routes -> Shipments
    for r in routes.values():
        assert r["shipment_id"] in shipments, f"Route {r['id']} shipment_id missing in shipment_db"

    # Deliveries -> Shipments, Couriers, RouteStages
    for d in deliveries.values():
        assert d["shipment_id"] in shipments, f"Delivery {d['id']} shipment_id missing in shipment_db"
        if d["courier_id"] is not None:
            assert d["courier_id"] in couriers, f"Delivery {d['id']} courier_id missing in courier_db"
        assert d["route_stage_id"] in stages, f"Delivery {d['id']} route_stage_id missing in route_db"
        # Consistency
        parent_route = routes[stages[d["route_stage_id"]]["route_id"]]
        assert parent_route["shipment_id"] == d["shipment_id"], f"Delivery route stage doesn't match shipment"

    # Analytics Events -> Shipments, Users, Tariffs, Couriers
    for ev in events:
        assert ev["shipment_id"] in shipments
        assert ev["client_id"] in users
        assert ev["tariff_id"] in tariffs
        if ev["courier_id"] is not None:
            assert ev["courier_id"] in couriers
        # Value consistency
        s = shipments[ev["shipment_id"]]
        assert ev["client_id"] == s["client_id"]
        assert ev["tariff_id"] == s["tariff_id"]

    # Daily Stats -> Tariffs
    for stat in daily_stats:
        assert stat["tariff_code"] in tariffs_by_code


def test_intra_db_foreign_key_violations():
    """Verify that intra-database FK violations are strictly caught by PostgreSQL engine."""
    fake_uuid = str(uuid.uuid4())

    # shipment_status_history -> shipments
    with pytest.raises(Exception) as exc_info:
        with get_engine_for_db("shipment_db").begin() as conn:
            conn.execute(
                text("INSERT INTO shipment_status_history (id, shipment_id, status) VALUES (:id, :s_id, 'TEST');"),
                {"id": str(uuid.uuid4()), "s_id": fake_uuid}
            )
    assert "violates foreign key constraint" in str(exc_info.value)

    # route_stages -> routes
    with pytest.raises(Exception) as exc_info:
        with get_engine_for_db("route_db").begin() as conn:
            conn.execute(
                text("""
                INSERT INTO route_stages (id, route_id, stage_order, stage_type, origin_point, dest_point, planned_start, planned_end, status)
                VALUES (:id, :r_id, 99, 'TEST', 'A', 'B', NOW(), NOW(), 'PENDING');
                """),
                {"id": str(uuid.uuid4()), "r_id": fake_uuid}
            )
    assert "violates foreign key constraint" in str(exc_info.value)

    # delivery_checkpoints -> deliveries
    with pytest.raises(Exception) as exc_info:
        with get_engine_for_db("delivery_db").begin() as conn:
            conn.execute(
                text("""
                INSERT INTO delivery_checkpoints (id, delivery_id, status, location_name)
                VALUES (:id, :d_id, 'TEST', 'Nowhere');
                """),
                {"id": str(uuid.uuid4()), "d_id": fake_uuid}
            )
    assert "violates foreign key constraint" in str(exc_info.value)

    # users -> roles
    with pytest.raises(Exception) as exc_info:
        with get_engine_for_db("user_db").begin() as conn:
            conn.execute(
                text("""
                INSERT INTO users (id, email, phone, password_hash, first_name, last_name, role_id, account_status)
                VALUES (:id, 'fake@test.by', '+375000000000', 'hash', 'Fake', 'User', 9999, 'ACTIVE');
                """),
                {"id": str(uuid.uuid4())}
            )
    assert "violates foreign key constraint" in str(exc_info.value)
