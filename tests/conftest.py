"""
Shared test fixtures for all PakPOS tests.
Uses in-memory SQLite — no file created, no cleanup needed.
Never uses real hardware — MockPrinter and MockBarcodeScanner only.
"""
from __future__ import annotations

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from decimal import Decimal
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from pakpos.database.engine import Base, _apply_pragmas
from pakpos.database.models import (
    Category, Product, Customer, Supplier, User, Setting
)
from pakpos.database.models.user import UserRole
from pakpos.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def prevent_modal_dialog_hang(monkeypatch):
    """Safety net: auto-mock QMessageBox modal dialogs so they never block execution in headless CI."""
    from unittest.mock import MagicMock
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", MagicMock(return_value=QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "critical", MagicMock(return_value=QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "information", MagicMock(return_value=QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question", MagicMock(return_value=QMessageBox.StandardButton.Yes))


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _apply_pragmas)
    # Import all models to register with Base.metadata
    from pakpos.database.models import (
        category, product, customer, supplier,
        sale, purchase, payment, expense,
        stock_movement, user, audit, setting,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Session:
    """Provide a database session with automatic rollback."""
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_category(db_session) -> Category:
    cat = Category(name="Beverages", name_urdu="مشروبات")
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def sample_product(db_session, sample_category) -> Product:
    product = Product(
        name="Coca Cola 500ml",
        barcode="6291101234567",
        sku="COKE-500",
        category_id=sample_category.id,
        unit="piece",
        purchase_price=Decimal("100.00"),
        sale_price=Decimal("150.00"),
        wholesale_price=Decimal("130.00"),
        minimum_stock=Decimal("5"),
        current_stock=Decimal("50"),
        tax_rate=Decimal("0"),
        is_active=True,
    )
    db_session.add(product)
    db_session.flush()
    return product


@pytest.fixture
def sample_customer(db_session) -> Customer:
    customer = Customer(
        name="Ahmed Khan",
        phone="0300-1234567",
        address="Main Bazar, Lahore",
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        credit_limit=Decimal("10000"),
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()
    return customer


@pytest.fixture
def sample_supplier(db_session) -> Supplier:
    supplier = Supplier(
        name="Allied Foods",
        phone="0321-9876543",
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()
    return supplier


@pytest.fixture
def owner_user(db_session) -> User:
    auth = AuthService(db_session)
    return auth.create_user("owner", "Shop Owner", "password123", UserRole.OWNER)


@pytest.fixture
def cashier_user(db_session) -> User:
    auth = AuthService(db_session)
    return auth.create_user("cashier1", "Ali Cashier", "cashier123", UserRole.CASHIER)


@pytest.fixture
def mock_printer():
    from pathlib import Path
    import tempfile
    from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
    with tempfile.TemporaryDirectory() as tmpdir:
        yield MockPrinterAdapter(output_dir=Path(tmpdir))


@pytest.fixture
def mock_scanner():
    from pakpos.hardware.barcode.mock_scanner import MockBarcodeScanner
    return MockBarcodeScanner()
