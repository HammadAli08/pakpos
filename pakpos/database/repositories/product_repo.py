"""Product repository."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from pakpos.database.models.product import Product
from pakpos.database.models.category import Category
from pakpos.database.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):

    def __init__(self, session: Session) -> None:
        super().__init__(session, Product)

    def get_by_barcode(self, barcode: str) -> Product | None:
        return (
            self._session.query(Product)
            .filter(Product.barcode == barcode, Product.is_active == True)  # noqa: E712
            .first()
        )

    def get_by_sku(self, sku: str) -> Product | None:
        return (
            self._session.query(Product)
            .filter(Product.sku == sku, Product.is_active == True)  # noqa: E712
            .first()
        )

    def search(self, query: str, limit: int = 50) -> list[Product]:
        """Full-text search across name, barcode, SKU."""
        pattern = f"%{query}%"
        return (
            self._session.query(Product)
            .filter(
                Product.is_active == True,  # noqa: E712
                or_(
                    Product.name.ilike(pattern),
                    Product.barcode.ilike(pattern),
                    Product.sku.ilike(pattern),
                    Product.name_urdu.ilike(pattern),
                )
            )
            .limit(limit)
            .all()
        )

    def get_low_stock(self) -> list[Product]:
        return (
            self._session.query(Product)
            .filter(
                Product.is_active == True,  # noqa: E712
                Product.current_stock <= Product.minimum_stock
            )
            .all()
        )

    def update_stock(self, product_id: int, new_stock: Decimal) -> None:
        """Directly update stock level — ONLY called from inventory service with movement."""
        product = self.get_by_id(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")
        product.current_stock = new_stock
        self._session.flush()

    def get_by_category(self, category_id: int) -> list[Product]:
        return (
            self._session.query(Product)
            .filter(Product.category_id == category_id, Product.is_active == True)  # noqa: E712
            .all()
        )

    def get_all_with_category(self) -> list[Product]:
        return (
            self._session.query(Product)
            .outerjoin(Category, Product.category_id == Category.id)
            .filter(Product.is_active == True)  # noqa: E712
            .all()
        )
