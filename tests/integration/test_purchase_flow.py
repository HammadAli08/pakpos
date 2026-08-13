"""
Integration test: Purchase Flow
Purchase → Inventory increase → Stock movement → Supplier ledger
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.purchase_service import PurchaseService, PurchaseRequest, PurchaseItemRequest
from pakpos.database.models.stock_movement import StockMovement, MovementType


class TestPurchaseFlow:

    def test_complete_purchase_increases_stock_and_creates_movement(
        self, db_session, sample_product, sample_supplier, owner_user
    ):
        initial_stock = sample_product.current_stock  # 50
        initial_balance = sample_supplier.current_balance  # 0

        service = PurchaseService(db_session)
        request = PurchaseRequest(
            supplier_id=sample_supplier.id,
            invoice_number="SUPP-INV-101",
            items=[
                PurchaseItemRequest(
                    product_id=sample_product.id,
                    product_name=sample_product.name,
                    quantity=Decimal("20"),
                    purchase_price=Decimal("110.00"),
                )
            ],
            paid_amount=Decimal("1000.00"),  # total = 20 * 110 = 2200, unpaid = 1200
            user_id=owner_user.id,
        )

        purchase = service.create_purchase(request)
        db_session.commit()

        # 1. Purchase record created
        assert purchase.id is not None
        assert purchase.total == Decimal("2200.00")
        assert purchase.due_amount == Decimal("1200.00")

        # 2. Stock increased
        db_session.refresh(sample_product)
        assert sample_product.current_stock == initial_stock + Decimal("20")
        assert sample_product.purchase_price == Decimal("110.00")

        # 3. Stock movement created
        movements = (
            db_session.query(StockMovement)
            .filter(StockMovement.product_id == sample_product.id)
            .all()
        )
        assert len(movements) == 1
        movement = movements[0]
        assert movement.movement_type == MovementType.PURCHASE
        assert movement.quantity == Decimal("20")
        assert movement.previous_stock == initial_stock
        assert movement.new_stock == initial_stock + Decimal("20")

        # 4. Supplier ledger balance updated (unpaid due_amount = 1200)
        db_session.refresh(sample_supplier)
        assert sample_supplier.current_balance == initial_balance + Decimal("1200.00")
