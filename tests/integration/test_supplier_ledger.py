"""
Integration test: Supplier Ledger
Purchase → Supplier Dues Increase → Payment Made → Dues Decrease → Payment Record Created
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.supplier_service import SupplierService
from pakpos.services.purchase_service import PurchaseService, PurchaseRequest, PurchaseItemRequest
from pakpos.database.models.payment import PaymentType


class TestSupplierLedger:

    def test_supplier_ledger_cycle(self, db_session, sample_product, sample_supplier, owner_user):
        supp_service = SupplierService(db_session)
        purchase_service = PurchaseService(db_session)

        # 1. Purchase of 10 items @ 100 = 1000 total, 0 paid -> 1000 due
        purchase_service.create_purchase(PurchaseRequest(
            supplier_id=sample_supplier.id,
            items=[PurchaseItemRequest(
                product_id=sample_product.id,
                product_name=sample_product.name,
                quantity=Decimal("10"),
                purchase_price=Decimal("100"),
            )],
            paid_amount=Decimal("0"),
            user_id=owner_user.id,
        ))
        db_session.commit()

        db_session.refresh(sample_supplier)
        assert sample_supplier.current_balance == Decimal("1000")

        # 2. Pay supplier Rs 600
        payment = supp_service.record_supplier_payment(
            supplier_id=sample_supplier.id,
            amount=Decimal("600"),
            payment_type=PaymentType.CASH,
            user_id=owner_user.id,
        )
        db_session.commit()

        # 3. Balance reduces to Rs 400
        db_session.refresh(sample_supplier)
        assert sample_supplier.current_balance == Decimal("400")

        # 4. Payment record exists
        assert payment.id is not None
        assert payment.supplier_id == sample_supplier.id
        assert payment.amount == Decimal("600")
