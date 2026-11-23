"""
tests/test_seed.py
Automated pytest suite for Milestone 1:
- Validates SQLAlchemy 2.0 ORM models compilation
- Enforces strict zero cross-database foreign key constraints
- Validates database-per-service isolation (no metadata leakage)
- Asserts exact record counts across all 12 operational tables
- Validates cross-service logical UUID reference integrity
"""
import pytest
from sqlalchemy import text, inspect
from services.common.database import Base, get_engine_for_db
from services.common.registry import SERVICE_REGISTRY, ALL_SERVICE_MODELS


def test_models_compilation():
    """All 14 models compile into Base.metadata without duplicate tables or missing attributes."""
    assert len(ALL_SERVICE_MODELS) == 14
    assert len(Base.metadata.tables) == 14


def test_foreign_key_constraints():
    """Strictly assert that no cross-database foreign keys exist."""
    allowed_fks = {
        ("user_db", "users"): {"roles.id"},
        ("shipment_db", "shipment_status_history"): {"shipments.id"},
        ("route_db", "route_stages"): {"routes.id"},
        ("delivery_db", "delivery_checkpoints"): {"deliveries.id"},
    }

    total_fks = 0
    for db_name, models in SERVICE_REGISTRY.items():
        for model in models:
            table_name = model.__tablename__
            col_fks = [fk.target_fullname for col in model.__table__.columns for fk in col.foreign_keys]
            total_fks += len(col_fks)

            expected_fks = allowed_fks.get((db_name, table_name), set())
            assert set(col_fks) == expected_fks, f"Unexpected FK in {db_name}.{table_name}: {col_fks}"

    assert total_fks == 4, f"Found {total_fks} FKs, expected exactly 4 intra-DB FKs."


def test_database_table_isolation():
    """Verify each database contains only its designated tables, with zero table leakage."""
    for db_name, models in SERVICE_REGISTRY.items():
        engine = get_engine_for_db(db_name)
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names())
        expected_tables = {m.__tablename__ for m in models}

        missing = expected_tables - actual_tables
        assert not missing, f"Database {db_name} missing tables: {missing}"

        other_tables = {
            m.__tablename__
            for other_db, other_models in SERVICE_REGISTRY.items()
            if other_db != db_name
            for m in other_models
        }
        leaked = actual_tables.intersection(other_tables)
        assert not leaked, f"Database {db_name} leaked tables: {leaked}"


def test_seed_record_counts():
    """Verify all 12 operational tables have exact seed record counts (43 records total)."""
    from scripts.seed_all import clean_tables, seed_data
    clean_tables()
    seed_data()

    expected_counts = {
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

    total = 0
    for (db_name, table_name), expected in expected_counts.items():
        engine = get_engine_for_db(db_name)
        with engine.connect() as conn:
            actual = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};")).scalar()
            assert actual == expected, f"Mismatch in {db_name}.{table_name}: expected {expected}, got {actual}"
            total += actual

    assert total == 43


def test_cross_service_logical_integrity():
    """Verify stitched references resolve across the 7 databases."""
    shipment_eng = get_engine_for_db("shipment_db")
    with shipment_eng.connect() as conn:
        s1 = conn.execute(text("SELECT client_id, tariff_id FROM shipments WHERE tracking_number = 'PKG-BY-2026-849201';")).mappings().one()
        client_id = s1["client_id"]
        tariff_id = s1["tariff_id"]

    user_eng = get_engine_for_db("user_db")
    with user_eng.connect() as conn:
        client = conn.execute(text("SELECT email FROM users WHERE id = :id;"), {"id": client_id}).mappings().one_or_none()
        assert client is not None
        assert client["email"] == "client@logistics.by"

    tariff_eng = get_engine_for_db("tariff_db")
    with tariff_eng.connect() as conn:
        tariff = conn.execute(text("SELECT code FROM tariffs WHERE id = :id;"), {"id": tariff_id}).mappings().one_or_none()
        assert tariff is not None
        assert tariff["code"] == "STANDARD"

    courier_eng = get_engine_for_db("courier_db")
    with courier_eng.connect() as conn:
        courier = conn.execute(text("SELECT id, user_id FROM couriers WHERE transport_type = 'CAR';")).mappings().one()
        courier_id = courier["id"]
        courier_user_id = courier["user_id"]

    with user_eng.connect() as conn:
        c_user = conn.execute(text("SELECT email FROM users WHERE id = :id;"), {"id": courier_user_id}).mappings().one_or_none()
        assert c_user is not None
        assert c_user["email"] == "courier1@logistics.by"
