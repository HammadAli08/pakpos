"""
Integration test: Sale Return Flow
Return → Inventory increase → Financial adjustment / Audit trail
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.services.inventory_service import InventoryService, StockAdjustmentRequest
from pakpos.database.models.stock_movement import MovementType, StockMovement
from pakpos.database.models.sale import PaymentMethod


class TestReturnFlow:

    def test_sale_return_restores_inventory(self, db_session, sample_product, cashier_user):
        sales_service = SalesService(db_session)
        inv_service = InventoryService(db_session)

        # 1. Make a sale of 5 items
        initial_stock = sample_product.current_stock  # 50
        sale_res = sales_service.create_sale(SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("5"),
                unit_price=Decimal("150"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("750"),
            cashier_id=cashier_user.id,
        ))
        db_session.commit()

        db_session.refresh(sample_product)
        assert sample_product.current_stock == Decimal("45")

        # 2. Return 2 items
        inv_service.adjust_stock(StockAdjustmentRequest(
            product_id=sample_product.id,
            movement_type=MovementType.SALE_RETURN,
            quantity=Decimal("2"),
            reason=f"Customer return from invoice {sale_res.invoice_number}",
            user_id=cashier_user.id,
        ))
        db_session.commit()

        # 3. Stock increases back to 47
        db_session.refresh(sample_product)
        assert sample_product.current_stock == Decimal("47")

        # 4. Stock movement audit trail exists
        movements = inv_service.get_stock_history(sample_product.id)
        assert len(movements) == 2  # 1 sale + 1 sale_return
        return_mvt = movements[0]  # newest first
        assert return_mvt.movement_type == MovementType.SALE_RETURN
        assert return_mvt.quantity == Decimal("2")
        assert return_mvt.previous_stock == Decimal("45")
        assert return_mvt.new_stock == Decimal("47")
