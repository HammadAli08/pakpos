"""
CartWidget — Table display for cashier cart items.
Supports inline quantity adjustment, row removal, and real-time summary calculation.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QHBoxLayout, QPushButton, QLabel, QVBoxLayout, QDoubleSpinBox
)

from pakpos.services.sales_service import CartItem
from pakpos.utils.formatters import format_currency, format_quantity


class CartWidget(QTableWidget):
    """
    Cart table displaying items, interactive quantities, unit prices, and totals.
    """
    cart_updated = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cart_items: list[CartItem] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["Product", "Price", "Qty", "Disc", "Total", "Action"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)

    def add_item(self, item: CartItem) -> None:
        """Add item to cart or increment quantity if item with same product_id exists."""
        for existing in self._cart_items:
            if existing.product_id == item.product_id:
                existing.quantity += item.quantity
                self.refresh()
                return

        self._cart_items.append(item)
        self.refresh()

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self._cart_items):
            self._cart_items.pop(index)
            self.refresh()

    def clear_cart(self) -> None:
        self._cart_items.clear()
        self.refresh()

    def get_items(self) -> list[CartItem]:
        return list(self._cart_items)

    def get_subtotal(self) -> Decimal:
        return sum(item.subtotal for item in self._cart_items)

    def get_tax_total(self) -> Decimal:
        return sum(item.tax_amount for item in self._cart_items)

    def get_total(self) -> Decimal:
        return sum(item.total for item in self._cart_items)

    def refresh(self) -> None:
        self.setRowCount(0)
        for i, item in enumerate(self._cart_items):
            self.insertRow(i)
            
            # Product Name (Read-only)
            name_item = QTableWidgetItem(item.product_name)
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.setItem(i, 0, name_item)
            
            # Price (Read-only — loaded from DB product)
            p_item = QTableWidgetItem(format_currency(item.unit_price))
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
            p_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.setItem(i, 1, p_item)

            # Qty SpinBox (Editable quantity)
            spin_qty = QDoubleSpinBox()
            spin_qty.setRange(0.001, 99999.0)
            spin_qty.setDecimals(3 if float(item.quantity) != int(float(item.quantity)) else 0)
            spin_qty.setSingleStep(1.0)
            spin_qty.setValue(float(item.quantity))
            spin_qty.setFixedWidth(85)
            spin_qty.setAlignment(Qt.AlignmentFlag.AlignCenter)

            def _on_qty_changed(val: float, cart_item: CartItem=item, row_idx: int=i) -> None:
                try:
                    cart_item.quantity = Decimal(str(val))
                    t_item = QTableWidgetItem(format_currency(cart_item.total))
                    t_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
                    t_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                    self.setItem(row_idx, 4, t_item)
                    self.cart_updated.emit()
                except Exception:
                    pass

            spin_qty.valueChanged.connect(_on_qty_changed)
            self.setCellWidget(i, 2, spin_qty)

            # Discount (Read-only)
            d_item = QTableWidgetItem(format_currency(item.discount))
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
            d_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.setItem(i, 3, d_item)

            # Total (Read-only)
            t_item = QTableWidgetItem(format_currency(item.total))
            t_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
            t_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.setItem(i, 4, t_item)

            # Remove Button
            btn_del = QPushButton("X")
            btn_del.setObjectName("btn_danger")
            btn_del.setFixedWidth(28)
            btn_del.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn_del.clicked.connect(lambda _, idx=i: self.remove_item(idx))
            self.setCellWidget(i, 5, btn_del)

        self.cart_updated.emit()

