"""
Integration tests for product creation and stock validation.
"""
from __future__ import annotations

from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication

from pakpos.database.engine import init_database, get_session
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.ui.dialogs.product_dialog import ProductDialog
from pakpos.utils.validators import validate_quantity


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestProductCreation:

    def test_validate_quantity_allows_zero_stock_when_requested(self):
        assert validate_quantity("0", allow_zero=True) == Decimal("0")
        assert validate_quantity("10.5", allow_zero=True) == Decimal("10.5")
        with pytest.raises(Exception):
            validate_quantity("-1", allow_zero=True)

    def test_product_dialog_save_zero_stock(self, qapp):
        dialog = ProductDialog(categories=[])
        dialog.input_name.setText("Zero Stock Product")
        dialog.input_purchase.setText("50")
        dialog.input_sale.setText("100")
        dialog.input_stock.setText("0")
        dialog.input_min_stock.setText("5")

        dialog._on_save()

        assert dialog.product_data["name"] == "Zero Stock Product"
        assert dialog.product_data["current_stock"] == Decimal("0")

    def test_add_product_to_database(self, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'product_test.db'}"
        init_database(db_url)

        with get_session() as session:
            repo = ProductRepository(session)
            prod = repo.create(
                name="Test Milk 1L",
                barcode="1234567890",
                sku="MILK-1",
                category_id=None,
                purchase_price=Decimal("150"),
                sale_price=Decimal("200"),
                current_stock=Decimal("0"),
                minimum_stock=Decimal("10"),
                unit="pack",
            )
            session.commit()
            prod_id = prod.id

        with get_session() as session:
            repo = ProductRepository(session)
            saved = repo.get_by_id(prod_id)
            assert saved is not None
            assert saved.name == "Test Milk 1L"
            assert saved.current_stock == Decimal("0")
