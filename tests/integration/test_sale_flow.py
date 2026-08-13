"""
Integration test: Complete Sale Flow
Product → Cart → Sale → Inventory decrease → Stock movement → Ledger

This is the most critical test in the entire application.
All steps must be atomic.
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.database.models.sale import SaleStatus, PaymentMethod
from pakpos.database.models.stock_movement import StockMovement, MovementType
from pakpos.utils.validators import ValidationError


class TestSaleFlow:

    def test_complete_cash_sale(self, db_session, sample_product, cashier_user):
        """Full flow: product → cart → sale → stock decreases → movement recorded."""
        initial_stock = sample_product.current_stock  # 50

        service = SalesService(db_session)
        request = SaleRequest(
            items=[
                CartItem(
                    product_id=sample_product.id,
                    product_name=sample_product.name,
                    barcode=sample_product.barcode,
                    quantity=Decimal("2"),
                    unit_price=Decimal("150"),
                )
            ],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("300"),
            cashier_id=cashier_user.id,
        )

        result = service.create_sale(request)
        db_session.commit()

        # Verify sale result
        assert result.invoice_number.startswith("INV-")
        assert result.total == Decimal("300")
        assert result.paid_amount == Decimal("300")
        assert result.change == Decimal("0")
        assert result.due_amount == Decimal("0")

        # Verify stock decreased
        db_session.refresh(sample_product)
        assert sample_product.current_stock == initial_stock - Decimal("2")

        # Verify stock movement was created
        movements = (
            db_session.query(StockMovement)
            .filter(StockMovement.product_id == sample_product.id)
            .all()
        )
        assert len(movements) == 1
        movement = movements[0]
        assert movement.movement_type == MovementType.SALE
        assert movement.quantity == Decimal("-2")
        assert movement.previous_stock == initial_stock
        assert movement.new_stock == initial_stock - Decimal("2")

    def test_sale_with_change(self, db_session, sample_product, cashier_user):
        """Cash sale with overpayment — correct change calculated."""
        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=Decimal("150"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("200"),
            cashier_id=cashier_user.id,
        )
        result = service.create_sale(request)
        assert result.total == Decimal("150")
        assert result.paid_amount == Decimal("200")
        assert result.change == Decimal("50")

    def test_credit_sale_updates_customer_balance(
        self, db_session, sample_product, sample_customer, cashier_user
    ):
        """Credit sale increases customer balance (Khata)."""
        initial_balance = sample_customer.current_balance  # 0

        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=Decimal("150"),
            )],
            payment_method=PaymentMethod.CREDIT,
            customer_id=sample_customer.id,
            paid_amount=Decimal("0"),
            cashier_id=cashier_user.id,
        )
        result = service.create_sale(request)
        db_session.commit()

        db_session.refresh(sample_customer)
        assert sample_customer.current_balance == initial_balance + Decimal("150")
        assert result.due_amount == Decimal("150")

    def test_credit_sale_requires_customer(self, db_session, sample_product, cashier_user):
        """Credit sale without customer must fail."""
        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=None,
                quantity=Decimal("1"),
                unit_price=Decimal("150"),
            )],
            payment_method=PaymentMethod.CREDIT,
            customer_id=None,
            cashier_id=cashier_user.id,
        )
        with pytest.raises(ValidationError, match="customer"):
            service.create_sale(request)

    def test_sale_with_discount(self, db_session, sample_product, cashier_user):
        """Sale-level discount reduces total correctly."""
        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=None,
                quantity=Decimal("2"),
                unit_price=Decimal("150"),
            )],
            payment_method=PaymentMethod.CASH,
            discount=Decimal("50"),
            paid_amount=Decimal("250"),
            cashier_id=cashier_user.id,
        )
        result = service.create_sale(request)
        # subtotal=300, discount=50 → total=250
        assert result.total == Decimal("250")
        assert result.change == Decimal("0")

    def test_empty_cart_raises(self, db_session, cashier_user):
        """Cannot create a sale with no items."""
        service = SalesService(db_session)
        with pytest.raises(ValidationError, match="empty"):
            service.create_sale(SaleRequest(items=[], cashier_id=cashier_user.id))

    def test_insufficient_cash_raises(self, db_session, sample_product, cashier_user):
        """Cash payment less than total must be rejected."""
        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=None,
                quantity=Decimal("1"),
                unit_price=Decimal("500"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("100"),  # Less than 500
            cashier_id=cashier_user.id,
        )
        with pytest.raises(ValidationError, match="Insufficient"):
            service.create_sale(request)

    def test_invoice_numbers_are_unique(self, db_session, sample_product, cashier_user):
        """Each sale must have a unique invoice number."""
        service = SalesService(db_session)

        def make_request():
            return SaleRequest(
                items=[CartItem(
                    product_id=sample_product.id,
                    product_name=sample_product.name,
                    barcode=None,
                    quantity=Decimal("1"),
                    unit_price=Decimal("100"),
                )],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("100"),
                cashier_id=cashier_user.id,
            )

        result1 = service.create_sale(make_request())
        db_session.commit()
        result2 = service.create_sale(make_request())
        db_session.commit()
        assert result1.invoice_number != result2.invoice_number

    def test_multiple_items_in_sale(self, db_session, sample_category, cashier_user):
        """Sale with multiple different products."""
        from pakpos.database.models.product import Product

        prod1 = Product(
            name="Coke", barcode="111", unit="piece",
            purchase_price=Decimal("80"), sale_price=Decimal("100"),
            current_stock=Decimal("20"), minimum_stock=Decimal("5"),
            category_id=sample_category.id, is_active=True,
        )
        prod2 = Product(
            name="Bread", barcode="222", unit="piece",
            purchase_price=Decimal("120"), sale_price=Decimal("150"),
            current_stock=Decimal("15"), minimum_stock=Decimal("3"),
            category_id=sample_category.id, is_active=True,
        )
        db_session.add_all([prod1, prod2])
        db_session.flush()

        service = SalesService(db_session)
        request = SaleRequest(
            items=[
                CartItem(product_id=prod1.id, product_name="Coke", barcode="111",
                         quantity=Decimal("2"), unit_price=Decimal("100")),
                CartItem(product_id=prod2.id, product_name="Bread", barcode="222",
                         quantity=Decimal("1"), unit_price=Decimal("150")),
            ],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("500"),
            cashier_id=cashier_user.id,
        )
        result = service.create_sale(request)
        db_session.commit()
        # 2*100 + 1*150 = 350
        assert result.total == Decimal("350")
        assert result.change == Decimal("150")

        # Both products had stock movement
        movements = db_session.query(StockMovement).filter(
            StockMovement.movement_type == MovementType.SALE
        ).all()
        assert len(movements) == 2
