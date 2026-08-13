"""Sale repository."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, and_
from sqlalchemy.orm import Session, joinedload

from pakpos.database.models.sale import Sale, SaleItem, SaleStatus
from pakpos.database.repositories.base import BaseRepository


class SaleRepository(BaseRepository[Sale]):

    def __init__(self, session: Session) -> None:
        super().__init__(session, Sale)

    def get_by_invoice(self, invoice_number: str) -> Sale | None:
        return (
            self._session.query(Sale)
            .options(joinedload(Sale.items))
            .filter(Sale.invoice_number == invoice_number)
            .first()
        )

    def get_with_items(self, sale_id: int) -> Sale | None:
        return (
            self._session.query(Sale)
            .options(joinedload(Sale.items).joinedload(SaleItem.product))
            .filter(Sale.id == sale_id)
            .first()
        )

    def get_by_date_range(self, start: datetime, end: datetime) -> list[Sale]:
        return (
            self._session.query(Sale)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .order_by(Sale.created_at.desc())
            .all()
        )

    def get_today(self) -> list[Sale]:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
        return self.get_by_date_range(start, end)

    def get_total_for_date_range(self, start: datetime, end: datetime) -> Decimal:
        result = (
            self._session.query(func.sum(Sale.total))
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .scalar()
        )
        return Decimal(str(result or 0))

    def get_next_invoice_number(self) -> str:
        last = (
            self._session.query(Sale)
            .order_by(Sale.id.desc())
            .first()
        )
        next_id = (last.id + 1) if last else 1
        return f"INV-{next_id:06d}"

    def get_by_customer(self, customer_id: int) -> list[Sale]:
        return (
            self._session.query(Sale)
            .filter(Sale.customer_id == customer_id)
            .order_by(Sale.created_at.desc())
            .all()
        )
