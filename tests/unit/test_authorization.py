"""
Unit test: Service-level authorization enforcement.
Verifies Cashier role cannot void sales or perform unauthorized actions.
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.services.sales_service import SalesService, SaleRequest, CartItem, PermissionError
from pakpos.database.models.sale import PaymentMethod


class TestServiceAuthorization:

    def test_cashier_cannot_void_sale(self, db_session, sample_product, cashier_user):
        sales_service = SalesService(db_session)

        result = sales_service.create_sale(SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("100"),
            cashier_id=cashier_user.id,
        ))
        db_session.commit()

        # Cashier user attempts to void sale -> raises PermissionError
        with pytest.raises(PermissionError, match="Only Managers or Shop Owners"):
            sales_service.void_sale(result.sale_id, reason="Customer canceled", user_id=cashier_user.id)

    def test_owner_can_void_sale(self, db_session, sample_product, owner_user):
        sales_service = SalesService(db_session)

        result = sales_service.create_sale(SaleRequest(
            items=[CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
            )],
            payment_method=PaymentMethod.CASH,
            paid_amount=Decimal("100"),
            cashier_id=owner_user.id,
        ))
        db_session.commit()

        # Owner voids sale -> succeeds
        sales_service.void_sale(result.sale_id, reason="Manager authorized return", user_id=owner_user.id)
        db_session.commit()

        sale = sales_service._sale_repo.get_by_id(result.sale_id)
        assert sale.status == "voided"
