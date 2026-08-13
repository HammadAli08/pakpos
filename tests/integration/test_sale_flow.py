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
from pakpos.database.models.sale import SaleStatus, PaymentMethod, SaleItem
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
                    unit_price=sample_product.sale_price,
                )],
                payment_method=PaymentMethod.CASH,
                paid_amount=sample_product.sale_price,
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

    def test_stock_validation_insufficient_single_item(self, db_session, sample_product, cashier_user):
        """Selling more than available stock must raise ValidationError and leave stock unchanged."""
        sample_product.current_stock = Decimal("5")
        db_session.flush()

        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("10"),
                unit_price=sample_product.sale_price,
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("1500"),
            cashier_id=cashier_user.id,
        )

        with pytest.raises(ValidationError) as exc:
            service.create_sale(request)

        assert "Insufficient stock" in str(exc.value)
        db_session.refresh(sample_product)
        assert sample_product.current_stock == Decimal("5")

    def test_stock_validation_insufficient_multi_item_atomic(self, db_session, sample_category, cashier_user):
        """If one item out of multiple has insufficient stock, entire sale fails and zero stock changes happen."""
        from pakpos.database.models.product import Product

        prod1 = Product(
            name="Available Item", barcode="A1", unit="pc",
            purchase_price=Decimal("50"), sale_price=Decimal("100"),
            current_stock=Decimal("10"), minimum_stock=Decimal("1"),
            category_id=sample_category.id, is_active=True,
        )
        prod2 = Product(
            name="Short Stock Item", barcode="A2", unit="pc",
            purchase_price=Decimal("50"), sale_price=Decimal("100"),
            current_stock=Decimal("2"), minimum_stock=Decimal("1"),
            category_id=sample_category.id, is_active=True,
        )
        db_session.add_all([prod1, prod2])
        db_session.flush()

        service = SalesService(db_session)
        request = SaleRequest(
            items=[
                CartItem(product_id=prod1.id, product_name="Available Item", barcode="A1",
                         quantity=Decimal("5"), unit_price=Decimal("100")),
                CartItem(product_id=prod2.id, product_name="Short Stock Item", barcode="A2",
                         quantity=Decimal("5"), unit_price=Decimal("100")),
            ],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("1000"),
            cashier_id=cashier_user.id,
        )

        with pytest.raises(ValidationError) as exc:
            service.create_sale(request)

        assert "Insufficient stock" in str(exc.value)
        db_session.refresh(prod1)
        db_session.refresh(prod2)
        assert prod1.current_stock == Decimal("10")
        assert prod2.current_stock == Decimal("2")

    def test_sale_item_price_snapshot_isolation(self, db_session, sample_product, cashier_user):
        """Updating product sale price after sale does NOT affect existing sale item unit price snapshot."""
        sample_product.sale_price = Decimal("150")
        db_session.flush()

        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=sample_product.sale_price,
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("150"),
            cashier_id=cashier_user.id,
        )
        result = service.create_sale(request)
        db_session.commit()

        # Product price updated to 250 in catalog
        sample_product.sale_price = Decimal("250")
        db_session.commit()

        sale_item = service._session.query(SaleItem).filter(SaleItem.sale_id == result.sale_id).first()
        assert sale_item.unit_price == Decimal("150")
        assert sale_item.total == Decimal("150")

    def test_price_integrity_authoritative_db_price_used(self, db_session, sample_product, cashier_user):
        """Cart item with stale price automatically uses authoritative DB price at checkout time."""
        sample_product.sale_price = Decimal("200")
        db_session.flush()

        service = SalesService(db_session)
        # Cart passed with stale unit_price=100
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("200"),
            cashier_id=cashier_user.id,
        )
        result = service.create_sale(request)
        db_session.commit()

        assert result.total == Decimal("200")
        sale_item = service._session.query(SaleItem).filter(SaleItem.sale_id == result.sale_id).first()
        assert sale_item.unit_price == Decimal("200")

    def test_revenue_report_and_transaction_count(self, db_session, sample_product, cashier_user):
        """Completed sales increase report revenue and transaction count."""
        from pakpos.services.report_service import ReportService

        service = SalesService(db_session)
        report_service = ReportService(db_session)

        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("2"),
                unit_price=sample_product.sale_price,
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("300"),
            cashier_id=cashier_user.id,
        )
        service.create_sale(request)
        db_session.commit()

        summary = report_service.get_today_summary()
        assert summary.total_revenue == Decimal("300")
        assert summary.total_transactions == 1

    def test_voided_sales_excluded_from_reports(self, db_session, sample_product, owner_user):
        """Voided sales are not counted toward total sales revenue."""
        from pakpos.services.report_service import ReportService

        service = SalesService(db_session)
        report_service = ReportService(db_session)

        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=sample_product.sale_price,
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("150"),
            cashier_id=owner_user.id,
        )
        result = service.create_sale(request)
        db_session.commit()

        service.void_sale(result.sale_id, reason="Customer cancelled", user_id=owner_user.id)
        db_session.commit()

        summary = report_service.get_today_summary()
        assert summary.total_revenue == Decimal("0")
        assert summary.total_transactions == 0

    def test_inactive_product_sale_fails(self, db_session, sample_product, cashier_user):
        """Inactive products cannot be sold."""
        sample_product.is_active = False
        db_session.flush()

        service = SalesService(db_session)
        request = SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=sample_product.sale_price,
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("150"),
            cashier_id=cashier_user.id,
        )

        with pytest.raises(ValidationError) as exc:
            service.create_sale(request)

        assert "not found" in str(exc.value).lower()
