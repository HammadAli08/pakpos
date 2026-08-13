"""
CartWidget — Table display for cashier cart items.
Supports quantity adjustment, row removal, and summary calculation.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QHBoxLayout, QPushButton, QLabel, QVBoxLayout
)

from pakpos.services.sales_service import CartItem
from pakpos.utils.formatters import format_currency, format_quantity


class CartWidget(QTableWidget):
    """
    Cart table displaying items, quantities, unit prices, and totals.
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
        # Check if already in cart
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

    def get_total(self) -> Decimal:
        return sum(item.total for item in self._cart_items)

    def refresh(self) -> None:
        self.setRowCount(0)
        for i, item in enumerate(self._cart_items):
            self.insertRow(i)
            
            # Product Name
            self.setItem(i, 0, QTableWidgetItem(item.product_name))
            
            # Price
            p_item = QTableWidgetItem(format_currency(item.unit_price))
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
            self.setItem(i, 1, p_item)

            # Qty
            q_item = QTableWidgetItem(format_quantity(item.quantity))
            q_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.VCenter)
            self.setItem(i, 2, q_item)

            # Discount
            d_item = QTableWidgetItem(format_currency(item.discount))
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
            self.setItem(i, 3, d_item)

            # Total
            t_item = QTableWidgetItem(format_currency(item.total))
            t_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.VCenter)
            self.setItem(i, 4, t_item)

            # Remove Button
            btn_del = QPushButton("X")
            btn_del.setObjectName("btn_danger")
            btn_del.setFixedWidth(28)
            btn_del.clicked.connect(lambda _, idx=i: self.remove_item(idx))
            self.setCellWidget(i, 5, btn_del)

        self.cart_updated.emit()
