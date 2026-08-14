"""
Unit and UI Integration tests for POS Screen redesign, ProductGridWidget, and CartWidget stock limit guard.
"""
from __future__ import annotations

from decimal import Decimal
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pakpos.database.engine import init_database
from pakpos.database.models.product import Product
from pakpos.services.sales_service import CartItem
from pakpos.ui.widgets.product_grid import ProductCard
from pakpos.ui.widgets.cart_widget import CartWidget


@pytest.fixture(scope="module", autouse=True)
def init_db():
    init_database()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_product_card_out_of_stock_display(qapp):
    p_in_stock = Product(id=1, name="In Stock Item", sale_price=Decimal("150.00"), current_stock=Decimal("10"), minimum_stock=Decimal("2"))
    card_in_stock = ProductCard(p_in_stock)
    assert not card_in_stock.is_out_of_stock

    p_out = Product(id=2, name="Out of Stock Item", sale_price=Decimal("200.00"), current_stock=Decimal("0"), minimum_stock=Decimal("2"))
    card_out = ProductCard(p_out)
    assert card_out.is_out_of_stock


def test_cart_widget_stock_limit_guard(qapp):
    cart = CartWidget()
    # Mock product stock cache
    cart._product_stocks[100] = Decimal("5")

    item = CartItem(
        product_id=100,
        product_name="Limited Item",
        barcode="123456",
        quantity=Decimal("3"),
        unit_price=Decimal("100"),
        tax_rate=Decimal("0"),
    )

    cart.add_item(item)
    assert len(cart.get_items()) == 1
    assert cart.get_items()[0].quantity == Decimal("3")

    # Attempting to add 5 more (total 8 > max 5) should clamp to max stock 5
    cart.add_item(CartItem(product_id=100, product_name="Limited Item", barcode="123456", quantity=Decimal("5"), unit_price=Decimal("100")))
    assert cart.get_items()[0].quantity == Decimal("5")


def test_cart_widget_empty_placeholder(qapp):
    cart = CartWidget()
    assert not cart.empty_placeholder.isHidden()
    assert cart.scroll_area.isHidden()

    cart.add_item(CartItem(product_id=9999, product_name="Test Product", barcode="0001", quantity=Decimal("1"), unit_price=Decimal("50")))
    assert cart.empty_placeholder.isHidden()
    assert not cart.scroll_area.isHidden()

    cart.clear_cart()
    assert not cart.empty_placeholder.isHidden()
    assert cart.scroll_area.isHidden()
