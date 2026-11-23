"""
scripts/init_databases.py
Idempotent script to verify and create all 7 microservice databases if missing.
"""
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DATABASES = [
    "user_db",
    "tariff_db",
    "shipment_db",
    "courier_db",
    "route_db",
    "delivery_db",
    "analytics_db",
]

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def init_databases():
    conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    cursor.execute("SELECT datname FROM pg_database;")
    existing_dbs = {row[0] for row in cursor.fetchall()}

    for db_name in DATABASES:
        if db_name not in existing_dbs:
            cursor.execute(f"CREATE DATABASE {db_name};")
            print(f"Created database: {db_name}")
        else:
            print(f"Database already exists: {db_name}")

    cursor.close()
    conn.close()
    print("All 7 databases verified successfully.")


if __name__ == "__main__":
    init_databases()
