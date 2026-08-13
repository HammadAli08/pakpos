"""
Customer Service — handles customer management, Khata (credit ledger), and payments.
Every payment updates customer balance and creates a Payment record atomically.
"""
from __future__ import annotations

from decimal import Decimal
from sqlalchemy.orm import Session

from pakpos.database.models.customer import Customer
from pakpos.database.models.payment import Payment, PaymentType
from pakpos.database.repositories.customer_repo import CustomerRepository
from pakpos.utils.logger import get_logger
from pakpos.utils.validators import validate_name, validate_amount, ValidationError

logger = get_logger(__name__)


class CustomerService:
    """Business logic for Customer Khata balance tracking and payments."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = CustomerRepository(session)

    def create_customer(
        self,
        name: str,
        phone: str | None = None,
        address: str | None = None,
        credit_limit: Decimal = Decimal("0"),
        opening_balance: Decimal = Decimal("0"),
    ) -> Customer:
        validated_name = validate_name(name, "name")
        customer = Customer(
            name=validated_name,
            phone=phone.strip() if phone else None,
            address=address.strip() if address else None,
            credit_limit=credit_limit,
            opening_balance=opening_balance,
            current_balance=opening_balance,
            is_active=True,
        )
        self._session.add(customer)
        self._session.flush()
        logger.info("Created customer id=%d name=%s", customer.id, customer.name)
        return customer

    def record_customer_payment(
        self,
        customer_id: int,
        amount: Decimal,
        payment_type: str = PaymentType.CASH,
        user_id: int | None = None,
        notes: str = "",
    ) -> Payment:
        """
        Record a customer Khata payment.
        Decreases customer.current_balance and creates a Payment record atomically.
        """
        validate_amount(amount, "amount")
        customer = self._repo.get_by_id(customer_id)
        if customer is None:
            raise ValueError(f"Customer {customer_id} not found")

        # Reduce customer outstanding balance
        self._repo.update_balance(customer_id, -amount)

        # Create payment record
        payment = Payment(
            customer_id=customer_id,
            user_id=user_id,
            amount=amount,
            payment_type=payment_type,
            notes=notes or f"Khata payment received from {customer.name}",
        )
        self._session.add(payment)
        self._session.flush()
        logger.info("Customer payment recorded id=%d customer_id=%d amount=%s", payment.id, customer_id, amount)
        return payment

    def get_customer_ledger(self, customer_id: int):
        customer = self._repo.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        sales = customer.sales
        payments = customer.payments
        return {
            "customer": customer,
            "sales": sales,
            "payments": payments,
            "current_balance": customer.current_balance,
        }
