"""Customer repository."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from pakpos.database.models.customer import Customer
from pakpos.database.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):

    def __init__(self, session: Session) -> None:
        super().__init__(session, Customer)

    def search(self, query: str, limit: int = 50) -> list[Customer]:
        pattern = f"%{query}%"
        return (
            self._session.query(Customer)
            .filter(
                Customer.is_active == True,  # noqa: E712
                or_(
                    Customer.name.ilike(pattern),
                    Customer.phone.ilike(pattern),
                )
            )
            .limit(limit)
            .all()
        )

    def get_by_phone(self, phone: str) -> Customer | None:
        return (
            self._session.query(Customer)
            .filter(Customer.phone == phone)
            .first()
        )

    def get_with_balance(self) -> list[Customer]:
        """Return all customers with outstanding balance."""
        return (
            self._session.query(Customer)
            .filter(Customer.is_active == True, Customer.current_balance > 0)  # noqa: E712
            .order_by(Customer.current_balance.desc())
            .all()
        )

    def update_balance(self, customer_id: int, delta: float) -> None:
        """Add delta to customer balance (positive=debt, negative=payment)."""
        customer = self.get_by_id(customer_id)
        if customer is None:
            raise ValueError(f"Customer {customer_id} not found")
        from decimal import Decimal
        customer.current_balance = Decimal(str(customer.current_balance)) + Decimal(str(delta))
        self._session.flush()
