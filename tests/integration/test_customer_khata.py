"""
Integration test: Customer Khata Ledger
Credit Sale → Balance Increases → Payment Made → Balance Decreases → Audit Payment Recorded
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.customer_service import CustomerService
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.database.models.sale import PaymentMethod
from pakpos.database.models.payment import Payment, PaymentType


class TestCustomerKhata:

    def test_customer_khata_cycle(self, db_session, sample_product, sample_customer, cashier_user):
        cust_service = CustomerService(db_session)
        sales_service = SalesService(db_session)

        # 1. Initial balance
        assert sample_customer.current_balance == Decimal("0")
        sample_product.sale_price = Decimal("250")

        # 2. Credit Sale of Rs 500
        sales_service.create_sale(SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("2"),
                unit_price=Decimal("250"),
            )],
            payment_method=PaymentMethod.CREDIT,
            customer_id=sample_customer.id,
            cashier_id=cashier_user.id,
        ))
        db_session.commit()

        db_session.refresh(sample_customer)
        assert sample_customer.current_balance == Decimal("500")

        # 3. Customer makes partial payment of Rs 300
        payment = cust_service.record_customer_payment(
            customer_id=sample_customer.id,
            amount=Decimal("300"),
            payment_type=PaymentType.CASH,
            user_id=cashier_user.id,
        )
        db_session.commit()

        # 4. Balance reduces to Rs 200
        db_session.refresh(sample_customer)
        assert sample_customer.current_balance == Decimal("200")

        # 5. Payment record exists and is linked
        assert payment.id is not None
        assert payment.amount == Decimal("300")
        assert payment.customer_id == sample_customer.id
