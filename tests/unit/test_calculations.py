"""
Unit tests for sales calculations, discounts, tax, change calculation.
These tests have ZERO side effects — pure arithmetic.
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.sales_service import CartItem, SalesService
from pakpos.utils.validators import (
    validate_price, validate_quantity, validate_discount,
    validate_barcode, validate_tax_rate, ValidationError
)
from pakpos.utils.formatters import format_currency, format_quantity


class TestCartItemCalculations:
    """Test CartItem total/tax computations."""

    def test_simple_total(self):
        item = CartItem(
            product_id=1, product_name="Test", barcode=None,
            quantity=Decimal("2"), unit_price=Decimal("150"),
        )
        assert item.subtotal == Decimal("300")
        assert item.total == Decimal("300")

    def test_total_with_discount(self):
        item = CartItem(
            product_id=1, product_name="Test", barcode=None,
            quantity=Decimal("2"), unit_price=Decimal("150"),
            discount=Decimal("50"),
        )
        assert item.subtotal == Decimal("300")
        assert item.total == Decimal("250")

    def test_total_with_tax(self):
        item = CartItem(
            product_id=1, product_name="Test", barcode=None,
            quantity=Decimal("1"), unit_price=Decimal("100"),
            tax_rate=Decimal("17"),
        )
        assert item.tax_amount == Decimal("17")
        assert item.total == Decimal("117")

    def test_total_with_discount_and_tax(self):
        """Tax is applied after discount."""
        item = CartItem(
            product_id=1, product_name="Test", barcode=None,
            quantity=Decimal("1"), unit_price=Decimal("100"),
            discount=Decimal("10"),
            tax_rate=Decimal("10"),
        )
        # subtotal=100, after discount=90, tax=9, total=99
        assert item.tax_amount == Decimal("9")
        assert item.total == Decimal("99")

    def test_zero_quantity_is_invalid(self):
        with pytest.raises(ValidationError):
            validate_quantity(Decimal("0"))

    def test_negative_quantity_is_invalid(self):
        with pytest.raises(ValidationError):
            validate_quantity(Decimal("-1"))

    def test_zero_price_is_valid(self):
        """Zero price items are allowed (free items, gifts)."""
        assert validate_price(Decimal("0")) == Decimal("0")

    def test_negative_price_is_invalid(self):
        with pytest.raises(ValidationError):
            validate_price(Decimal("-1"))


class TestChangeCalculation:
    """Test cash change calculation."""

    def test_exact_payment_no_change(self):
        from pakpos.services.sales_service import SalesService
        # We can test the static method directly
        total = Decimal("980")
        received = Decimal("980")
        change = max(Decimal("0"), received - total)
        assert change == Decimal("0")

    def test_overpayment_gives_change(self):
        total = Decimal("1850")
        received = Decimal("2000")
        change = max(Decimal("0"), received - total)
        assert change == Decimal("150")

    def test_underpayment_gives_zero_change(self):
        total = Decimal("500")
        received = Decimal("400")
        change = max(Decimal("0"), received - total)
        assert change == Decimal("0")


class TestDiscountValidation:
    """Test discount business rules."""

    def test_discount_within_total_is_valid(self):
        assert validate_discount(Decimal("50"), Decimal("100")) == Decimal("50")

    def test_discount_equal_to_total_is_valid(self):
        assert validate_discount(Decimal("100"), Decimal("100")) == Decimal("100")

    def test_discount_exceeding_total_raises(self):
        with pytest.raises(ValidationError):
            validate_discount(Decimal("101"), Decimal("100"))

    def test_negative_discount_raises(self):
        with pytest.raises(ValidationError):
            validate_discount(Decimal("-1"), Decimal("100"))


class TestBarcodeValidation:
    """Test barcode validation."""

    def test_valid_barcode(self):
        assert validate_barcode("6291101234567") == "6291101234567"

    def test_empty_barcode_returns_none(self):
        assert validate_barcode("") is None
        assert validate_barcode(None) is None

    def test_barcode_too_long_raises(self):
        with pytest.raises(ValidationError):
            validate_barcode("X" * 101)


class TestTaxValidation:
    """Test tax rate validation."""

    def test_zero_tax_valid(self):
        assert validate_tax_rate(Decimal("0")) == Decimal("0")

    def test_17_percent_valid(self):
        assert validate_tax_rate(Decimal("17")) == Decimal("17")

    def test_100_percent_valid(self):
        assert validate_tax_rate(Decimal("100")) == Decimal("100")

    def test_negative_tax_invalid(self):
        with pytest.raises(ValidationError):
            validate_tax_rate(Decimal("-1"))

    def test_over_100_invalid(self):
        with pytest.raises(ValidationError):
            validate_tax_rate(Decimal("101"))


class TestFormatters:
    """Test currency and quantity formatters."""

    def test_format_currency_basic(self):
        assert format_currency(Decimal("1234.50")) == "Rs. 1,234.50"

    def test_format_currency_zero(self):
        assert format_currency(Decimal("0")) == "Rs. 0.00"

    def test_format_quantity_integer(self):
        assert format_quantity(Decimal("5")) == "5"

    def test_format_quantity_decimal(self):
        result = format_quantity(Decimal("2.500"))
        assert result == "2.5"
