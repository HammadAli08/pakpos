"""
Purchase Service — handles supplier purchases and stock increases.
All purchase operations are atomic: purchase + items + stock + supplier ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from pakpos.database.models.purchase import Purchase, PurchaseItem, PurchaseStatus
from pakpos.database.models.stock_movement import StockMovement, MovementType
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.database.repositories.supplier_repo import SupplierRepository
from pakpos.utils.logger import get_logger
from pakpos.utils.validators import validate_quantity, validate_price, ValidationError

logger = get_logger(__name__)


@dataclass
class PurchaseItemRequest:
    product_id: int
    product_name: str
    quantity: Decimal
    purchase_price: Decimal
    discount: Decimal = Decimal("0")


@dataclass
class PurchaseRequest:
    items: list[PurchaseItemRequest]
    supplier_id: int | None = None
    invoice_number: str | None = None
    paid_amount: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    notes: str = ""
    user_id: int | None = None


class PurchaseService:
    """Business logic for supplier purchases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._product_repo = ProductRepository(session)
        self._supplier_repo = SupplierRepository(session)

    def create_purchase(self, request: PurchaseRequest) -> Purchase:
        """
        Atomic purchase:
        1. Validate items
        2. Create Purchase
        3. Create PurchaseItems
        4. Increase stock
        5. Create StockMovements
        6. Update supplier balance
        """
        if not request.items:
            raise ValidationError("items", "Purchase must have at least one item")

        # Validate all products exist
        products = {}
        for item in request.items:
            product = self._product_repo.get_by_id(item.product_id)
            if product is None:
                raise ValidationError("product", f"Product '{item.product_name}' not found")
            validate_quantity(item.quantity, "quantity")
            validate_price(item.purchase_price, "purchase_price")
            products[item.product_id] = product

        # Calculate totals
        subtotal = sum(
            item.quantity * item.purchase_price - item.discount
            for item in request.items
        )
        total = subtotal - request.discount + request.tax
        due = max(Decimal("0"), total - request.paid_amount)

        # Create purchase record
        purchase = Purchase(
            supplier_id=request.supplier_id,
            invoice_number=request.invoice_number,
            user_id=request.user_id,
            subtotal=subtotal,
            discount=request.discount,
            tax=request.tax,
            total=total,
            paid_amount=request.paid_amount,
            due_amount=due,
            status=PurchaseStatus.RECEIVED,
            notes=request.notes,
        )
        self._session.add(purchase)
        self._session.flush()

        # Create items + stock movements
        for item in request.items:
            product = products[item.product_id]
            item_total = item.quantity * item.purchase_price - item.discount

            purchase_item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=item.product_id,
                quantity=item.quantity,
                purchase_price=item.purchase_price,
                discount=item.discount,
                total=item_total,
                product_name_snapshot=product.name,
            )
            self._session.add(purchase_item)

            # Update stock
            previous = Decimal(str(product.current_stock))
            new_stock = previous + item.quantity
            product.current_stock = new_stock
            # Update purchase price
            product.purchase_price = item.purchase_price

            movement = StockMovement(
                product_id=product.id,
                user_id=request.user_id,
                movement_type=MovementType.PURCHASE,
                quantity=item.quantity,
                previous_stock=previous,
                new_stock=new_stock,
                reference_type="purchase",
                reference_id=purchase.id,
                notes=f"Purchase #{purchase.id}",
            )
            self._session.add(movement)

        # Update supplier balance
        if request.supplier_id and due > 0:
            self._supplier_repo.update_balance(request.supplier_id, due)

        self._session.flush()
        logger.info("Purchase created id=%d total=%s supplier_id=%s", purchase.id, total, request.supplier_id)
        return purchase
