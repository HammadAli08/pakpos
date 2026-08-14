"""
CartWidget — Professional Retail POS Cart Panel.
Displays compact cart items, quantity spinbox controls with stock limit guard,
line totals, and a sleek empty-cart placeholder.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QDoubleSpinBox, QMessageBox, QSizePolicy
)

from pakpos.database.engine import get_session
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.services.sales_service import CartItem
from pakpos.utils.formatters import format_currency
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class CartItemRow(QFrame):
    """
    Individual compact POS Cart Item Row with [-] quantity [+] controls.
    """
    quantity_changed = Signal(Decimal)
    remove_requested = Signal()

    def __init__(self, item: CartItem, max_stock: Decimal, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.max_stock = max_stock
        self.setObjectName("cart_item_row")
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#cart_item_row {
                background-color: #22252c;
                border: 1px solid #2d3139;
                border-radius: 6px;
                padding: 6px;
            }
            QFrame#cart_item_row:hover {
                border-color: #3d4350;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Top row: Product Name & Remove Button
        top_layout = QHBoxLayout()
        lbl_name = QLabel(self.item.product_name)
        lbl_name.setStyleSheet("font-weight: 600; font-size: 13px; color: #e8eaed;")
        lbl_name.setWordWrap(True)

        btn_remove = QPushButton("×")
        btn_remove.setFixedSize(22, 22)
        btn_remove.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9ca3af;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 11px;
            }
            QPushButton:hover {
                background-color: #dc3545;
                color: white;
            }
        """)
        btn_remove.clicked.connect(self.remove_requested.emit)

        top_layout.addWidget(lbl_name, 1)
        top_layout.addWidget(btn_remove)

        # Bottom row: Price x Qty SpinBox -> Line Total
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        lbl_price_unit = QLabel(f"{format_currency(self.item.unit_price)}")
        lbl_price_unit.setStyleSheet("color: #9ca3af; font-size: 12px;")

        # Quantity SpinBox
        self.spin_qty = QDoubleSpinBox()
        self.spin_qty.setRange(0.001, 99999.0)
        self.spin_qty.setDecimals(3 if float(self.item.quantity) != int(float(self.item.quantity)) else 0)
        self.spin_qty.setSingleStep(1.0)
        self.spin_qty.setValue(float(self.item.quantity))
        self.spin_qty.setFixedWidth(80)
        self.spin_qty.setFixedHeight(28)
        self.spin_qty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_qty.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #1a1d23;
                color: #20c997;
                border: 1px solid #3a3d45;
                border-radius: 4px;
                font-weight: 700;
                font-size: 13px;
            }
            QDoubleSpinBox:focus {
                border-color: #2d6cdf;
            }
        """)
        self.spin_qty.valueChanged.connect(self._on_qty_spin_changed)

        self.lbl_line_total = QLabel(format_currency(self.item.total))
        self.lbl_line_total.setStyleSheet("font-weight: 700; font-size: 14px; color: #20c997;")
        self.lbl_line_total.setAlignment(Qt.AlignmentFlag.AlignRight)

        bottom_layout.addWidget(lbl_price_unit)
        bottom_layout.addWidget(QLabel("×"))
        bottom_layout.addWidget(self.spin_qty)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.lbl_line_total)

        layout.addLayout(top_layout)
        layout.addLayout(bottom_layout)

    def _on_qty_spin_changed(self, val: float) -> None:
        new_qty = Decimal(str(val))
        # Stock Limit Guard
        if self.max_stock is not None and new_qty > self.max_stock:
            QMessageBox.warning(
                self,
                "Stock Limit Exceeded",
                f"Only {float(self.max_stock):g} units available for '{self.item.product_name}'."
            )
            # Revert to max stock
            self.spin_qty.blockSignals(True)
            self.spin_qty.setValue(float(self.max_stock))
            self.spin_qty.blockSignals(False)
            new_qty = self.max_stock

        self.item.quantity = new_qty
        self.lbl_line_total.setText(format_currency(self.item.total))
        self.quantity_changed.emit(new_qty)


class CartWidget(QFrame):
    """
    Main Cart Container with Item List & Empty State.
    """
    cart_updated = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cart_items: List[CartItem] = []
        self._product_stocks: dict[int, Decimal] = {}
        self.setObjectName("cart_container")
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#cart_container {
                background-color: #1a1d23;
                border: 1px solid #2d3139;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Cart Header
        header_layout = QHBoxLayout()
        self.lbl_cart_header = QLabel("CART (0 ITEMS)")
        self.lbl_cart_header.setStyleSheet("font-weight: 700; font-size: 13px; color: #9ca3af; letter-spacing: 0.5px;")

        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("btn_secondary")
        btn_clear.setFixedSize(60, 24)
        btn_clear.setStyleSheet("font-size: 11px; padding: 2px 8px; border-radius: 4px;")
        btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_clear.clicked.connect(self.clear_cart)

        header_layout.addWidget(self.lbl_cart_header)
        header_layout.addStretch()
        header_layout.addWidget(btn_clear)
        layout.addLayout(header_layout)

        # ─── SCROLL AREA FOR CART ROWS ───
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.rows_container)
        layout.addWidget(self.scroll_area, 1)

        # ─── EMPTY CART PLACEHOLDER Widget ───
        self.empty_placeholder = QFrame()
        empty_layout = QVBoxLayout(self.empty_placeholder)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(8)

        lbl_icon = QLabel("🛒")
        lbl_icon.setStyleSheet("font-size: 42px; color: #4b5563;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_empty_title = QLabel("YOUR CART IS EMPTY")
        lbl_empty_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #6b7280;")
        lbl_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_empty_sub = QLabel("Search or scan a product\nto start a sale")
        lbl_empty_sub.setStyleSheet("font-size: 12px; color: #4b5563;")
        lbl_empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_layout.addWidget(lbl_icon)
        empty_layout.addWidget(lbl_empty_title)
        empty_layout.addWidget(lbl_empty_sub)

        layout.addWidget(self.empty_placeholder, 1)
        self._update_visibility()

    def _fetch_product_stock(self, product_id: int) -> Decimal:
        """Fetch fresh current_stock from DB."""
        if product_id in self._product_stocks:
            return self._product_stocks[product_id]
        with get_session() as session:
            repo = ProductRepository(session)
            p = repo.get_by_id(product_id)
            if p:
                self._product_stocks[product_id] = p.current_stock
                return p.current_stock
        return Decimal("99999")

    def add_item(self, item: CartItem) -> None:
        """Add item to cart or increment quantity if item exists."""
        max_stock = self._fetch_product_stock(item.product_id)

        for existing in self._cart_items:
            if existing.product_id == item.product_id:
                requested = existing.quantity + item.quantity
                if max_stock is not None and requested > max_stock:
                    QMessageBox.warning(
                        self,
                        "Stock Limit Exceeded",
                        f"Cannot add more units. Only {float(max_stock):g} units available for '{item.product_name}'."
                    )
                    existing.quantity = max_stock
                else:
                    existing.quantity = requested
                self.refresh()
                return

        if max_stock is not None and item.quantity > max_stock:
            QMessageBox.warning(
                self,
                "Stock Limit Exceeded",
                f"Only {float(max_stock):g} units available for '{item.product_name}'."
            )
            item.quantity = max_stock

        self._cart_items.append(item)
        self.refresh()

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self._cart_items):
            self._cart_items.pop(index)
            self.refresh()

    def clear_cart(self) -> None:
        self._cart_items.clear()
        self._product_stocks.clear()
        self.refresh()

    def get_items(self) -> List[CartItem]:
        return list(self._cart_items)

    def get_subtotal(self) -> Decimal:
        return sum(item.subtotal for item in self._cart_items)

    def get_tax_total(self) -> Decimal:
        return sum(item.tax_amount for item in self._cart_items)

    def get_total(self) -> Decimal:
        return sum(item.total for item in self._cart_items)

    def _update_visibility(self) -> None:
        count = len(self._cart_items)
        self.lbl_cart_header.setText(f"CART ({count} ITEM{'S' if count != 1 else ''})")
        if count == 0:
            self.scroll_area.hide()
            self.empty_placeholder.show()
        else:
            self.empty_placeholder.hide()
            self.scroll_area.show()

    def refresh(self) -> None:
        """Re-render cart item rows."""
        # Clear existing row widgets
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, cart_item in enumerate(self._cart_items):
            max_stock = self._fetch_product_stock(cart_item.product_id)
            row = CartItemRow(cart_item, max_stock=max_stock)
            row.quantity_changed.connect(lambda _, idx=i: self.cart_updated.emit())
            row.remove_requested.connect(lambda idx=i: self.remove_item(idx))
            self.rows_layout.addWidget(row)

        self._update_visibility()
        self.cart_updated.emit()
