"""
Supplier Service — handles supplier ledger and payments to suppliers.
Every payment updates supplier balance and creates a Payment record atomically.
"""
from __future__ import annotations

from decimal import Decimal
from sqlalchemy.orm import Session

from pakpos.database.models.supplier import Supplier
from pakpos.database.models.payment import Payment, PaymentType
from pakpos.database.repositories.supplier_repo import SupplierRepository
from pakpos.utils.logger import get_logger
from pakpos.utils.validators import validate_name, validate_amount

logger = get_logger(__name__)


class SupplierService:
    """Business logic for Supplier dues tracking and payments."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SupplierRepository(session)

    def create_supplier(
        self,
        name: str,
        company: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        opening_balance: Decimal = Decimal("0"),
    ) -> Supplier:
        validated_name = validate_name(name, "name")
        supplier = Supplier(
            name=validated_name,
            company=company.strip() if company else None,
            phone=phone.strip() if phone else None,
            address=address.strip() if address else None,
            opening_balance=opening_balance,
            current_balance=opening_balance,
            is_active=True,
        )
        self._session.add(supplier)
        self._session.flush()
        logger.info("Created supplier id=%d name=%s", supplier.id, supplier.name)
        return supplier

    def record_supplier_payment(
        self,
        supplier_id: int,
        amount: Decimal,
        payment_type: str = PaymentType.CASH,
        user_id: int | None = None,
        notes: str = "",
    ) -> Payment:
        """
        Record a payment to a supplier.
        Decreases supplier.current_balance and creates a Payment record atomically.
        """
        validate_amount(amount, "amount")
        supplier = self._repo.get_by_id(supplier_id)
        if supplier is None:
            raise ValueError(f"Supplier {supplier_id} not found")

        # Reduce supplier balance (we owe less)
        self._repo.update_balance(supplier_id, -amount)

        # Create payment record
        payment = Payment(
            supplier_id=supplier_id,
            user_id=user_id,
            amount=amount,
            payment_type=payment_type,
            notes=notes or f"Payment made to supplier {supplier.name}",
        )
        self._session.add(payment)
        self._session.flush()
        logger.info("Supplier payment recorded id=%d supplier_id=%d amount=%s", payment.id, supplier_id, amount)
        return payment
