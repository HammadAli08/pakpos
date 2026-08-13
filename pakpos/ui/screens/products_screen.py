"""
ProductsScreen — Management interface for catalog products and stock levels.
"""
from __future__ import annotations

from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QHeaderView
)

from pakpos.database.engine import get_session
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.database.repositories.base import BaseRepository
from pakpos.database.models.category import Category
from pakpos.ui.dialogs.product_dialog import ProductDialog
from pakpos.utils.formatters import format_currency, format_quantity


class ProductsScreen(QWidget):
    """
    Product & Inventory Catalog Screen.
    """

    def __init__(self, current_user, parent=None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top Bar
        top_layout = QHBoxLayout()
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Search products by name, barcode, or SKU...")
        self.input_search.textChanged.connect(self._load_products)

        btn_add = QPushButton("+ Add Product")
        btn_add.setObjectName("btn_success")
        btn_add.clicked.connect(self._on_add_product)

        top_layout.addWidget(self.input_search)
        top_layout.addWidget(btn_add)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Barcode", "Category", "Purchase Price", "Sale Price", "Stock", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)

        layout.addLayout(top_layout)
        layout.addWidget(self.table)

        self._load_products()

    def _load_products(self) -> None:
        query = self.input_search.text().strip()
        self.table.setRowCount(0)

        with get_session() as session:
            repo = ProductRepository(session)
            products = repo.search(query) if query else repo.get_all(active_only=False)

            for i, p in enumerate(products):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(p.id)))
                self.table.setItem(i, 1, QTableWidgetItem(p.name))
                self.table.setItem(i, 2, QTableWidgetItem(p.barcode or ""))
                self.table.setItem(i, 3, QTableWidgetItem(p.category.name if p.category else "-"))
                self.table.setItem(i, 4, QTableWidgetItem(format_currency(p.purchase_price)))
                self.table.setItem(i, 5, QTableWidgetItem(format_currency(p.sale_price)))

                stock_item = QTableWidgetItem(format_quantity(p.current_stock))
                if p.current_stock <= p.minimum_stock:
                    stock_item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(i, 6, stock_item)

                # Edit button
                btn_edit = QPushButton("Edit")
                btn_edit.setObjectName("btn_secondary")
                btn_edit.clicked.connect(lambda _, prod=p: self._on_edit_product(prod))
                self.table.setCellWidget(i, 7, btn_edit)

    def _on_add_product(self) -> None:
        with get_session() as session:
            cat_repo = BaseRepository(Category, session)
            categories = cat_repo.get_all()

            dlg = ProductDialog(categories, parent=self)
            if dlg.exec() == ProductDialog.DialogCode.Accepted:
                repo = ProductRepository(session)
                repo.create(**dlg.product_data)
                session.commit()
                QMessageBox.information(self, "Success", "Product added successfully!")
                self._load_products()

    def _on_edit_product(self, product) -> None:
        with get_session() as session:
            cat_repo = BaseRepository(Category, session)
            categories = cat_repo.get_all()

            dlg = ProductDialog(categories, product=product, parent=self)
            if dlg.exec() == ProductDialog.DialogCode.Accepted:
                repo = ProductRepository(session)
                repo.update(product.id, **dlg.product_data)
                session.commit()
                QMessageBox.information(self, "Success", "Product updated successfully!")
                self._load_products()
