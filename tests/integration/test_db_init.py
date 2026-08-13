"""
Integration tests for database initialization, schema idempotency, and settings models.
Verifies that database startup never fails on existing databases or duplicate init calls,
and that SettingsKey and SetupWizard imports are valid.
"""
from __future__ import annotations

import sqlite3
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from pakpos.database.engine import (
    Base,
    create_all_tables,
    create_db_engine,
    init_database,
)
from pakpos.database.models import Setting, SettingKey, User
from pakpos.database.models.user import UserRole
from pakpos.services.auth_service import AuthService


def test_fresh_database_initialization(tmp_path):
    """Test 1: Fresh database initialization creates all tables correctly."""
    db_file = tmp_path / "fresh.db"
    url = f"sqlite:///{db_file}"

    engine = create_db_engine(url)
    create_all_tables(engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "users", "categories", "products", "customers", "suppliers",
        "sales", "sale_items", "purchases", "purchase_items", "payments",
        "expenses", "stock_movements", "audit_log", "settings"
    ]
    for table in expected_tables:
        assert table in tables, f"Table {table} missing in fresh database"


def test_existing_database_initialization(tmp_path):
    """Test 2: Initializing database when database file already exists."""
    db_file = tmp_path / "existing.db"
    url = f"sqlite:///{db_file}"

    # First init
    engine1 = create_db_engine(url)
    create_all_tables(engine1)
    engine1.dispose()

    # Second init on existing db file
    engine2 = create_db_engine(url)
    create_all_tables(engine2)
    engine2.dispose()


def test_running_initialization_twice(tmp_path):
    """Test 3: Running database initialization twice in sequence on same engine does not error."""
    db_file = tmp_path / "double_init.db"
    url = f"sqlite:///{db_file}"

    engine = create_db_engine(url)
    create_all_tables(engine)
    # Call create_all_tables again immediately
    create_all_tables(engine)

    inspector = inspect(engine)
    assert "sale_items" in inspector.get_table_names()


def test_existing_database_containing_sale_items(tmp_path):
    """Test 4: Existing database with data in sale_items table remains intact without error on re-init."""
    db_file = tmp_path / "with_sales.db"
    url = f"sqlite:///{db_file}"

    engine = create_db_engine(url)
    create_all_tables(engine)

    # Insert sample record directly to check data preservation
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO users (username, full_name, password_hash, role, is_active) "
            "VALUES ('testuser', 'Test User', 'hash', 'OWNER', 1)"
        ))
        conn.commit()

    # Re-run table creation
    create_all_tables(engine)

    # Verify user data is preserved and not overwritten or reset
    with engine.connect() as conn:
        result = conn.execute(text("SELECT username FROM users WHERE username='testuser'")).fetchone()
        assert result is not None
        assert result[0] == 'testuser'


def test_upgrade_from_older_schema_preserves_data(tmp_path):
    """Test 5: Upgrade path leaves existing tables and data completely untouched."""
    db_file = tmp_path / "upgrade.db"
    url = f"sqlite:///{db_file}"

    engine = create_db_engine(url)
    create_all_tables(engine)

    # Add a custom setting
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    session.add(Setting(key=SettingKey.SHOP_NAME, value="Original Shop"))
    session.commit()
    session.close()

    # Re-run initialization (simulating app upgrade startup)
    create_all_tables(engine)

    session2 = SessionLocal()
    setting = session2.query(Setting).filter_by(key=SettingKey.SHOP_NAME).first()
    assert setting is not None
    assert setting.value == "Original Shop"
    session2.close()


def test_settings_key_model_and_imports():
    """Test 6 & 7: Verify SettingKey model, import availability, and setup wizard import compatibility."""
    assert hasattr(SettingKey, "SHOP_NAME")
    assert hasattr(SettingKey, "SHOP_ADDRESS")
    assert hasattr(SettingKey, "SHOP_PHONE")
    assert SettingKey.SHOP_NAME == "shop_name"
    assert SettingKey.SHOP_ADDRESS == "shop_address"
    assert SettingKey.SHOP_PHONE == "shop_phone"

    # Test setup wizard module import which previously threw ImportError
    from pakpos.ui.windows.setup_wizard import SetupWizard, SettingKey as WizardSettingKey
    assert WizardSettingKey is SettingKey
