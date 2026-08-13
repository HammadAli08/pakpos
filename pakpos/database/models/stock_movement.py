"""StockMovement model — immutable audit trail for all inventory changes."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pakpos.database.engine import Base

if TYPE_CHECKING:
    from pakpos.database.models.product import Product
    from pakpos.database.models.user import User


class MovementType(str, Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    SALE_RETURN = "SALE_RETURN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    DAMAGE = "DAMAGE"
    ADJUSTMENT = "ADJUSTMENT"
    OPENING_STOCK = "OPENING_STOCK"


class ReferenceType(str, Enum):
    SALE = "sale"
    PURCHASE = "purchase"
    MANUAL = "manual"
    RETURN = "return"
    ADJUSTMENT = "adjustment"


class StockMovement(Base):
    """
    Immutable record of every inventory change.
    Never delete these records — they are the audit trail.
    """
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)  # positive=in, negative=out
    previous_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    new_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")
    user: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<StockMovement id={self.id} product_id={self.product_id} "
            f"type={self.movement_type} qty={self.quantity}>"
        )
