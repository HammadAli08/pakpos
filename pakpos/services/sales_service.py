"""
Sales Service — Core POS business logic.

CRITICAL: The entire sale operation (sale header + items + stock movements + ledger)
must be one atomic database transaction. If any step fails, everything rolls back.
Print failure must NEVER roll back a saved sale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from pakpos.database.models.sale import Sale, SaleItem, SaleStatus, PaymentMethod
from pakpos.database.models.stock_movement import StockMovement, MovementType
from pakpos.database.models.payment import Payment, PaymentType
from pakpos.database.models.user import User
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.database.repositories.sale_repo import SaleRepository
from pakpos.database.repositories.customer_repo import CustomerRepository
from pakpos.hardware.printer.base import ReceiptData
from pakpos.utils.logger import get_logger
from pakpos.utils.validators import validate_quantity, validate_price, validate_discount, ValidationError
from pakpos.utils.formatters import format_quantity

logger = get_logger(__name__)


class PermissionError(Exception):
    pass


@dataclass
class CartItem:
    """DTO representing one item in the cashier cart."""
    product_id: int
    product_name: str
    barcode: str | None
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")

    @property
    def subtotal(self) -> Decimal:
        return self.quantity * self.unit_price

    @property
    def tax_amount(self) -> Decimal:
        return (self.subtotal - self.discount) * self.tax_rate / Decimal("100")

    @property
    def total(self) -> Decimal:
        return self.subtotal - self.discount + self.tax_amount


@dataclass
class SaleRequest:
    """DTO for creating a sale."""
    items: list[CartItem]
    payment_method: str = PaymentMethod.CASH
    discount: Decimal = Decimal("0")
    customer_id: int | None = None
    cashier_id: int | None = None
    paid_amount: Decimal = Decimal("0")
    notes: str = ""


@dataclass
class SaleResult:
    """DTO returned after a successful sale."""
    sale_id: int
    invoice_number: str
    total: Decimal
    paid_amount: Decimal
    change: Decimal
    due_amount: Decimal


class SalesService:
    """Business logic for creating sales, holding sales, reprinting receipts, and voiding sales."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._product_repo = ProductRepository(session)
        self._sale_repo = SaleRepository(session)
        self._customer_repo = CustomerRepository(session)

    def create_sale(self, request: SaleRequest) -> SaleResult:
        """
        Create a sale atomically.
        Enforces stock validation before writes and uses authoritative DB prices.
        """
        if not request.items:
            raise ValidationError("items", "Cart cannot be empty")

        # Step 1: Validate all items, check stock, and collect products
        products = {}
        requested_stock: dict[int, Decimal] = {}

        for item in request.items:
            validate_quantity(item.quantity, "quantity")
            if item.product_id not in products:
                product = self._product_repo.get_by_id(item.product_id)
                if product is None or not product.is_active:
                    raise ValidationError("product", f"Product '{item.product_name}' not found")
                products[item.product_id] = product
                requested_stock[item.product_id] = Decimal("0")

            requested_stock[item.product_id] += item.quantity

        # Stock validation: Ensure requested quantity <= current stock for every product
        for prod_id, total_requested in requested_stock.items():
            product = products[prod_id]
            available = Decimal(str(product.current_stock))
            if total_requested > available:
                raise ValidationError(
                    "stock",
                    f"Insufficient stock for '{product.name}'. Requested: {format_quantity(total_requested)}, Available: {format_quantity(available)}."
                )

        # Step 2: Calculate totals using authoritative DB prices
        subtotal = Decimal("0")
        item_tax = Decimal("0")

        for item in request.items:
            product = products[item.product_id]
            unit_price = Decimal(str(product.sale_price))
            item_sub = item.quantity * unit_price
            item_tax_amt = (item_sub - item.discount) * Decimal(str(product.tax_rate or 0)) / Decimal("100")
            subtotal += item_sub
            item_tax += item_tax_amt

        sale_discount = validate_discount(request.discount, subtotal)
        total = subtotal - sale_discount + item_tax

        paid = request.paid_amount
        if request.payment_method == PaymentMethod.CASH:
            if paid < total:
                raise ValidationError("paid_amount", "Insufficient cash payment for cash sale")
        elif request.payment_method == PaymentMethod.CREDIT:
            if request.customer_id is None:
                raise ValidationError("customer_id", "A customer is required for credit sales")
            paid = Decimal("0")

        change = max(Decimal("0"), paid - total)
        due = max(Decimal("0"), total - paid)

        invoice_number = self._sale_repo.get_next_invoice_number()

        sale = Sale(
            invoice_number=invoice_number,
            customer_id=request.customer_id,
            cashier_id=request.cashier_id,
            subtotal=subtotal,
            discount=sale_discount,
            tax=item_tax,
            total=total,
            paid_amount=paid,
            due_amount=due,
            payment_method=request.payment_method,
            status=SaleStatus.COMPLETED,
            notes=request.notes,
        )
        self._session.add(sale)
        self._session.flush()

        for item in request.items:
            product = products[item.product_id]
            unit_price = Decimal(str(product.sale_price))
            item_sub = item.quantity * unit_price
            item_tax_amt = (item_sub - item.discount) * Decimal(str(product.tax_rate or 0)) / Decimal("100")
            item_total = item_sub - item.discount + item_tax_amt

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=unit_price,
                discount=item.discount,
                tax=item_tax_amt,
                total=item_total,
                product_name_snapshot=product.name,
            )
            self._session.add(sale_item)

            previous_stock = Decimal(str(product.current_stock))
            new_stock = previous_stock - item.quantity
            movement = StockMovement(
                product_id=product.id,
                user_id=request.cashier_id,
                movement_type=MovementType.SALE,
                quantity=-item.quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                reference_type="sale",
                reference_id=sale.id,
                notes=f"Sale {invoice_number}",
            )
            self._session.add(movement)
            product.current_stock = new_stock

        if request.payment_method == PaymentMethod.CREDIT and request.customer_id:
            self._customer_repo.update_balance(request.customer_id, float(total))

        if paid > 0:
            payment = Payment(
                customer_id=request.customer_id,
                sale_id=sale.id,
                user_id=request.cashier_id,
                amount=paid,
                payment_type=PaymentType.CASH if request.payment_method == PaymentMethod.CASH else PaymentType.CARD,
            )
            self._session.add(payment)

        self._session.flush()
        logger.info("Sale created: %s total=%s", invoice_number, total)

        return SaleResult(
            sale_id=sale.id,
            invoice_number=invoice_number,
            total=total,
            paid_amount=paid,
            change=change,
            due_amount=due,
        )

    def hold_sale(self, request: SaleRequest) -> Sale:
        """Park/Hold a sale without affecting stock or creating ledger entries."""
        if not request.items:
            raise ValidationError("items", "Cart cannot be empty to hold sale")

        invoice_number = self._sale_repo.get_next_invoice_number()
        subtotal = sum(item.subtotal for item in request.items)
        total = subtotal - request.discount

        sale = Sale(
            invoice_number=invoice_number,
            customer_id=request.customer_id,
            cashier_id=request.cashier_id,
            subtotal=subtotal,
            discount=request.discount,
            tax=Decimal("0"),
            total=total,
            paid_amount=Decimal("0"),
            due_amount=total,
            payment_method=request.payment_method,
            status=SaleStatus.HELD,
            notes="HELD SALE",
        )
        self._session.add(sale)
        self._session.flush()

        for item in request.items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount,
                tax=Decimal("0"),
                total=item.total,
                product_name_snapshot=item.product_name,
            )
            self._session.add(sale_item)

        self._session.flush()
        logger.info("Held sale parked: invoice=%s id=%d", invoice_number, sale.id)
        return sale

    def get_held_sales(self) -> list[Sale]:
        return (
            self._session.query(Sale)
            .filter(Sale.status == SaleStatus.HELD)
            .order_by(Sale.created_at.desc())
            .all()
        )

    def get_receipt_data(self, sale_id: int) -> ReceiptData:
        """Generate ReceiptData DTO for printing or reprinting any completed sale."""
        sale = self._sale_repo.get_by_id(sale_id)
        if sale is None:
            raise ValueError(f"Sale #{sale_id} not found")

        items_dto = [
            {
                "name": item.product_name_snapshot,
                "qty": float(item.quantity),
                "unit_price": float(item.unit_price),
                "total": float(item.total),
            }
            for item in sale.items
        ]

        return ReceiptData(
            shop_name="PakPOS Retail Store",
            shop_address="Main Market, Lahore",
            shop_phone="0300-1234567",
            invoice_number=sale.invoice_number,
            cashier_name=sale.cashier.username if sale.cashier else "System",
            items=items_dto,
            subtotal=float(sale.subtotal),
            discount=float(sale.discount),
            tax=float(sale.tax),
            total=float(sale.total),
            paid_amount=float(sale.paid_amount),
            change=float(max(Decimal("0"), sale.paid_amount - sale.total)),
            payment_method=sale.payment_method,
            customer_name=sale.customer.name if sale.customer else None,
            footer_message="Thank you for shopping with us! (REPRINT)" if sale.status == SaleStatus.COMPLETED else f"--- {sale.status.upper()} ---",
            created_at=sale.created_at.strftime("%d-%b-%Y %H:%M") if sale.created_at else "",
        )

    def void_sale(self, sale_id: int, reason: str, user_id: int | None = None) -> None:
        """Void a sale — requires OWNER or MANAGER authorization."""
        if user_id:
            user = self._session.get(User, user_id)
            if user and not (user.is_owner or user.is_manager):
                raise PermissionError("Only Managers or Shop Owners are authorized to void sales")

        sale = self._sale_repo.get_by_id(sale_id)
        if sale is None:
            raise ValueError(f"Sale {sale_id} not found")
        if sale.status == SaleStatus.VOIDED:
            raise ValueError("Sale is already voided")

        sale.status = SaleStatus.VOIDED
        sale.notes = (sale.notes or "") + f" | VOIDED: {reason}"
        self._session.flush()
        logger.info("Sale voided: %s reason=%s", sale.invoice_number, reason)

    def calculate_change(self, total: Decimal, received: Decimal) -> Decimal:
        """Calculate change for cash payment."""
        return max(Decimal("0"), received - total)
