"""
Inventory Service — manages stock movements and adjustments.
EVERY stock change must produce a StockMovement record.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from pakpos.database.models.stock_movement import StockMovement, MovementType
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.utils.logger import get_logger
from pakpos.utils.validators import ValidationError

logger = get_logger(__name__)


@dataclass
class StockAdjustmentRequest:
    product_id: int
    movement_type: str
    quantity: Decimal  # always positive — direction determined by type
    reason: str
    user_id: int | None = None


class InventoryService:
    """Business logic for inventory management."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._product_repo = ProductRepository(session)

    def set_opening_stock(self, product_id: int, quantity: Decimal, user_id: int | None) -> None:
        """Set opening stock for a product (first time or reset)."""
        product = self._product_repo.get_by_id(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")
        previous = Decimal(str(product.current_stock))
        product.current_stock = quantity
        movement = StockMovement(
            product_id=product_id,
            user_id=user_id,
            movement_type=MovementType.OPENING_STOCK,
            quantity=quantity - previous,
            previous_stock=previous,
            new_stock=quantity,
            reference_type="manual",
            notes="Opening stock set",
        )
        self._session.add(movement)
        self._session.flush()
        logger.info("Opening stock set for product_id=%d qty=%s", product_id, quantity)

    def adjust_stock(self, request: StockAdjustmentRequest) -> None:
        """Manual stock adjustment (damage, correction, etc.)."""
        if not request.reason.strip():
            raise ValidationError("reason", "Stock adjustment reason is required")
        if request.quantity <= 0:
            raise ValidationError("quantity", "Quantity must be positive")

        product = self._product_repo.get_by_id(request.product_id)
        if product is None:
            raise ValueError(f"Product {request.product_id} not found")

        previous = Decimal(str(product.current_stock))

        # Determine direction: damage and sale are reductions; purchase and adjustments can be +/-
        if request.movement_type in (MovementType.DAMAGE, MovementType.SALE):
            delta = -request.quantity
        elif request.movement_type in (MovementType.PURCHASE, MovementType.SALE_RETURN, MovementType.OPENING_STOCK):
            delta = request.quantity
        else:  # ADJUSTMENT — quantity can be signed
            delta = request.quantity

        new_stock = previous + delta
        product.current_stock = new_stock

        movement = StockMovement(
            product_id=request.product_id,
            user_id=request.user_id,
            movement_type=request.movement_type,
            quantity=delta,
            previous_stock=previous,
            new_stock=new_stock,
            reference_type="manual",
            notes=request.reason,
        )
        self._session.add(movement)
        self._session.flush()
        logger.info(
            "Stock adjusted product_id=%d type=%s delta=%s new=%s",
            request.product_id, request.movement_type, delta, new_stock
        )

    def get_stock_history(self, product_id: int) -> list[StockMovement]:
        return (
            self._session.query(StockMovement)
            .filter(StockMovement.product_id == product_id)
            .order_by(StockMovement.created_at.desc())
            .all()
        )

    def get_low_stock_products(self):
        return self._product_repo.get_low_stock()
