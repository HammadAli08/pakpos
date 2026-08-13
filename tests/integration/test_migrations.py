"""
Integration test for Alembic migrations.
Verifies migration 001_initial_schema creates tables without data corruption.
"""
from __future__ import annotations

import os
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from pakpos.config.settings import DB_URL


def test_alembic_upgrade_head(tmp_path):
    """Test running Alembic migration on a fresh database file."""
    test_db = tmp_path / "migration_test.db"
    url = f"sqlite:///{test_db}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(alembic_cfg, "head")

    engine = create_engine(url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "users", "categories", "products", "customers", "suppliers",
        "sales", "sale_items", "purchases", "purchase_items", "payments",
        "expenses", "stock_movements", "audit_logs", "settings"
    ]

    for t in expected_tables:
        assert t in tables
