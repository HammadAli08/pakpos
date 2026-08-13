"""Product model."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pakpos.database.engine import Base

if TYPE_CHECKING:
    from pakpos.database.models.category import Category
    from pakpos.database.models.sale import SaleItem
    from pakpos.database.models.purchase import PurchaseItem
    from pakpos.database.models.stock_movement import StockMovement


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name_urdu: Mapped[str | None] = mapped_column(String(400), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="piece")
    # Pricing stored as integers (paisas) to avoid float precision issues
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    wholesale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    category: Mapped["Category | None"] = relationship("Category", back_populates="products")
    sale_items: Mapped[list["SaleItem"]] = relationship("SaleItem", back_populates="product")
    purchase_items: Mapped[list["PurchaseItem"]] = relationship("PurchaseItem", back_populates="product")
    stock_movements: Mapped[list["StockMovement"]] = relationship("StockMovement", back_populates="product")

    __table_args__ = (
        Index("ix_products_name_active", "name", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} stock={self.current_stock}>"

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.minimum_stock

    @property
    def stock_value(self) -> Decimal:
        return Decimal(str(self.current_stock)) * Decimal(str(self.purchase_price))
