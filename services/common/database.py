"""
Database configuration, Base DeclarativeBase, Engine, and Session factories for all 7 microservices.
"""
import os
from contextlib import contextmanager
from typing import Generator, Dict, Any, List, Type
from sqlalchemy import create_engine, Engine, MetaData
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

class Base(DeclarativeBase):
    metadata = MetaData()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

_engines: Dict[str, Engine] = {}
_sessionmakers: Dict[str, sessionmaker[Session]] = {}

def get_database_url(db_name: str) -> str:
    """Returns database URL for given database name. Supports env override e.g. DATABASE_URL_USER_DB."""
    env_var = f"DATABASE_URL_{db_name.upper()}"
    if os.getenv(env_var):
        return os.environ[env_var]
    
    driver = os.getenv("DB_DRIVER", "postgresql+psycopg2")
    return f"{driver}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}"

def get_engine_for_db(db_name: str) -> Engine:
    """Retrieve or create a cached SQLAlchemy Engine for the specified database."""
    if db_name not in _engines:
        db_url = get_database_url(db_name)
        try:
            engine = create_engine(db_url, pool_pre_ping=True, echo=False)
            with engine.connect():
                pass
        except Exception:
            fallback_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}"
            engine = create_engine(fallback_url, pool_pre_ping=True, echo=False)
        _engines[db_name] = engine
    return _engines[db_name]

def get_session_for_db(db_name: str) -> Session:
    """Creates a new Session instance for the specified database."""
    if db_name not in _sessionmakers:
        engine = get_engine_for_db(db_name)
        _sessionmakers[db_name] = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _sessionmakers[db_name]()

@contextmanager
def session_scope(db_name: str) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session_for_db(db_name)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def create_tables_for_db(db_name: str, models: List[Type[Any]]) -> None:
    """Creates only the tables associated with the specified models in the target database."""
    engine = get_engine_for_db(db_name)
    tables = [m.__table__ for m in models]
    Base.metadata.create_all(bind=engine, tables=tables)

def drop_tables_for_db(db_name: str, models: List[Type[Any]]) -> None:
    """Drops only the tables associated with the specified models in the target database."""
    engine = get_engine_for_db(db_name)
    tables = [m.__table__ for m in models]
    Base.metadata.drop_all(bind=engine, tables=tables)
