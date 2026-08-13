"""
ProductDialog — Add or Edit product modal.
Input validation at UI before calling service layer.
"""
from __future__ import annotations

from decimal import Decimal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QDoubleSpinBox, QFormLayout
)

from pakpos.utils.validators import parse_amount, parse_quantity, validate_barcode


class ProductDialog(QDialog):
    """Dialog for creating or editing a product."""

    def __init__(self, categories: list, product=None, parent=None) -> None:
        super().__init__(parent)
        self.categories = categories
        self.product = product
        self.setWindowTitle("Edit Product" if product else "Add New Product")
        self.setFixedSize(450, 480)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.input_name = QLineEdit()
        self.input_barcode = QLineEdit()
        self.input_sku = QLineEdit()
        self.combo_cat = QComboBox()
        self.combo_cat.addItem("-- None --", None)
        for cat in self.categories:
            self.combo_cat.addItem(cat.name, cat.id)

        self.input_purchase = QLineEdit("0")
        self.input_sale = QLineEdit("0")
        self.input_stock = QLineEdit("0")
        self.input_min_stock = QLineEdit("5")
        self.input_unit = QLineEdit("piece")

        form.addRow("Product Name *:", self.input_name)
        form.addRow("Barcode:", self.input_barcode)
        form.addRow("SKU:", self.input_sku)
        form.addRow("Category:", self.combo_cat)
        form.addRow("Purchase Price (Rs) *:", self.input_purchase)
        form.addRow("Sale Price (Rs) *:", self.input_sale)
        form.addRow("Current Stock *:", self.input_stock)
        form.addRow("Min Stock Warning:", self.input_min_stock)
        form.addRow("Unit (piece/kg/pack):", self.input_unit)

        layout.addLayout(form)

        # Pre-fill if editing
        if self.product:
            self.input_name.setText(self.product.name)
            self.input_barcode.setText(self.product.barcode or "")
            self.input_sku.setText(self.product.sku or "")
            self.input_purchase.setText(str(self.product.purchase_price))
            self.input_sale.setText(str(self.product.sale_price))
            self.input_stock.setText(str(self.product.current_stock))
            self.input_min_stock.setText(str(self.product.minimum_stock))
            self.input_unit.setText(self.product.unit or "piece")
            if self.product.category_id:
                idx = self.combo_cat.findData(self.product.category_id)
                if idx >= 0:
                    self.combo_cat.setCurrentIndex(idx)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Product")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._on_save)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Product Name is required.")
            return

        try:
            purchase_price = parse_amount(self.input_purchase.text())
            sale_price = parse_amount(self.input_sale.text())
            stock = parse_quantity(self.input_stock.text())
            min_stock = parse_quantity(self.input_min_stock.text())
        except Exception as e:
            QMessageBox.warning(self, "Validation Error", f"Invalid numeric input: {e}")
            return

        self.product_data = {
            "name": name,
            "barcode": validate_barcode(self.input_barcode.text()),
            "sku": self.input_sku.text().strip() or None,
            "category_id": self.combo_cat.currentData(),
            "purchase_price": purchase_price,
            "sale_price": sale_price,
            "current_stock": stock,
            "minimum_stock": min_stock,
            "unit": self.input_unit.text().strip() or "piece",
        }
        self.accept()
