"""Payment model — records all customer/supplier payments."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pakpos.database.engine import Base

if TYPE_CHECKING:
    from pakpos.database.models.customer import Customer
    from pakpos.database.models.supplier import Supplier
    from pakpos.database.models.sale import Sale
    from pakpos.database.models.purchase import Purchase
    from pakpos.database.models.user import User


class PaymentType(str, Enum):
    CASH = "cash"
    CARD = "card"
    BANK = "bank"
    OTHER = "other"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    supplier_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sale_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True
    )
    purchase_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False, default=PaymentType.CASH)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    customer: Mapped["Customer | None"] = relationship(
        "Customer", primaryjoin="Payment.customer_id == Customer.id",
        back_populates="payments"
    )
    supplier: Mapped["Supplier | None"] = relationship(
        "Supplier", primaryjoin="Payment.supplier_id == Supplier.id",
        back_populates="payments"
    )
    sale: Mapped["Sale | None"] = relationship("Sale", back_populates="payments")
    user: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} amount={self.amount} type={self.payment_type}>"
