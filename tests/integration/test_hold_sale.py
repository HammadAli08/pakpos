"""
Integration test: Hold Sale & Receipt Reprint
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.database.models.sale import SaleStatus, PaymentMethod


class TestHoldAndReprint:

    def test_hold_sale_does_not_affect_stock(self, db_session, sample_product, cashier_user):
        initial_stock = sample_product.current_stock  # 50
        sales_service = SalesService(db_session)

        sale = sales_service.hold_sale(SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("3"),
                unit_price=Decimal("150"),
            )],
            cashier_id=cashier_user.id,
        ))
        db_session.commit()

        # Sale status is HELD
        assert sale.status == SaleStatus.HELD

        # Stock is NOT affected
        db_session.refresh(sample_product)
        assert sample_product.current_stock == initial_stock

        # Held sales list contains it
        held_list = sales_service.get_held_sales()
        assert len(held_list) == 1
        assert held_list[0].id == sale.id

    def test_receipt_reprint_data(self, db_session, sample_product, cashier_user):
        sales_service = SalesService(db_session)
        result = sales_service.create_sale(SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=Decimal("150"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("150"),
            cashier_id=cashier_user.id,
        ))
        db_session.commit()

        receipt_data = sales_service.get_receipt_data(result.sale_id, is_reprint=True)
        assert receipt_data.invoice_number == result.invoice_number
        assert receipt_data.total == 150.0
        assert len(receipt_data.items) == 1
        assert "(REPRINT)" in receipt_data.footer_message
