"""Supplier repository."""
from __future__ import annotations

from decimal import Decimal
from sqlalchemy import or_
from sqlalchemy.orm import Session

from pakpos.database.models.supplier import Supplier
from pakpos.database.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):

    def __init__(self, session: Session) -> None:
        super().__init__(session, Supplier)

    def search(self, query: str, limit: int = 50) -> list[Supplier]:
        pattern = f"%{query}%"
        return (
            self._session.query(Supplier)
            .filter(
                Supplier.is_active == True,  # noqa: E712
                or_(
                    Supplier.name.ilike(pattern),
                    Supplier.phone.ilike(pattern),
                    Supplier.company.ilike(pattern),
                )
            )
            .limit(limit)
            .all()
        )

    def update_balance(self, supplier_id: int, delta: Decimal) -> None:
        supplier = self.get_by_id(supplier_id)
        if supplier is None:
            raise ValueError(f"Supplier {supplier_id} not found")
        supplier.current_balance = Decimal(str(supplier.current_balance)) + delta
        self._session.flush()
