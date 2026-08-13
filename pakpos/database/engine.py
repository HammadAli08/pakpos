"""
SQLAlchemy engine, session factory, and connection configuration.
Applies all required SQLite PRAGMAs on every connection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from pakpos.config.settings import DB_URL, paths
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _apply_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """Apply SQLite PRAGMAs on every new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA cache_size = -64000")   # 64 MB
    cursor.execute("PRAGMA temp_store = MEMORY")
    cursor.close()


def create_db_engine(db_url: str | None = None) -> Engine:
    """Create and configure the SQLAlchemy engine."""
    url = db_url or DB_URL
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=False,
    )
    event.listen(engine, "connect", _apply_pragmas)
    logger.info("Database engine created: %s", url)
    return engine


def create_all_tables(engine: Engine) -> None:
    """Create all tables defined in models."""
    # Import all models to register them with Base.metadata
    from pakpos.database.models import (  # noqa: F401
        category, product, customer, supplier,
        sale, purchase, payment, expense,
        stock_movement, user, audit, setting,
    )
    Base.metadata.create_all(engine)
    logger.info("All database tables created/verified.")


# ---------------------------------------------------------------------------
# Global engine and session factory (initialized at startup)
# ---------------------------------------------------------------------------
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_database(db_url: str | None = None) -> Engine:
    """
    Initialize the database — creates directories, engine, tables.
    Call once at application startup.
    """
    global _engine, _SessionLocal
    paths.ensure_all()
    _engine = create_db_engine(db_url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    create_all_tables(_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine


def get_session() -> Session:
    """Return a new database session. Caller is responsible for closing."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _SessionLocal()


def session_scope() -> Generator[Session, None, None]:
    """Context manager that provides a transactional scope."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
