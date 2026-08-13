"""Sale and SaleItem models."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pakpos.database.engine import Base

if TYPE_CHECKING:
    from pakpos.database.models.customer import Customer
    from pakpos.database.models.user import User
    from pakpos.database.models.product import Product
    from pakpos.database.models.payment import Payment


class SaleStatus(str, Enum):
    COMPLETED = "completed"
    HELD = "held"
    VOIDED = "voided"
    RETURNED = "returned"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CREDIT = "credit"      # Udhaar / Khata
    CARD = "card"
    BANK = "bank"
    OTHER = "other"
    MIXED = "mixed"


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    cashier_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    due_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    payment_method: Mapped[str] = mapped_column(String(20), nullable=False, default=PaymentMethod.CASH)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SaleStatus.COMPLETED)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Return tracking
    original_sale_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="sales")
    cashier: Mapped["User | None"] = relationship("User")
    items: Mapped[list["SaleItem"]] = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="sale")

    def __repr__(self) -> str:
        return f"<Sale id={self.id} invoice={self.invoice_number!r} total={self.total}>"


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)

    # Relationships
    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="sale_items")

    def __repr__(self) -> str:
        return f"<SaleItem sale_id={self.sale_id} product={self.product_name_snapshot!r} qty={self.quantity}>"
