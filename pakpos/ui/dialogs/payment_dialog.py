"""
PaymentDialog — Checkout payment modal.
Handles Cash, Credit (Khata), Card, Bank payments.
Calculates change automatically in real time.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QGroupBox
)

from pakpos.database.models.sale import PaymentMethod
from pakpos.utils.formatters import format_currency
from pakpos.utils.validators import parse_amount


class PaymentDialog(QDialog):
    """
    Modal dialog for processing cashier payment.
    """

    def __init__(self, total_amount: Decimal, customers: list, parent=None) -> None:
        super().__init__(parent)
        self.total_amount = total_amount
        self.customers = customers
        self.payment_method = PaymentMethod.CASH
        self.paid_amount = Decimal("0")
        self.selected_customer_id: int | None = None

        self.setWindowTitle("Process Payment")
        self.setFixedSize(450, 420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Total Banner
        lbl_total_title = QLabel("TOTAL DUE")
        lbl_total_title.setObjectName("label_subtitle")
        self.lbl_total = QLabel(format_currency(self.total_amount))
        self.lbl_total.setObjectName("label_amount")
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_total_title)
        layout.addWidget(self.lbl_total)

        # Payment Method
        layout.addWidget(QLabel("Payment Method:"))
        self.combo_method = QComboBox()
        self.combo_method.addItems([
            "Cash", "Credit / Khata", "Card", "Bank Transfer"
        ])
        self.combo_method.currentIndexChanged.connect(self._on_method_changed)
        layout.addWidget(self.combo_method)

        # Customer Selection (Hidden for Cash by default)
        self.box_customer = QGroupBox("Customer (Required for Credit)")
        cust_layout = QVBoxLayout(self.box_customer)
        self.combo_customer = QComboBox()
        self.combo_customer.addItem("-- Select Customer --", None)
        for c in self.customers:
            self.combo_customer.addItem(f"{c.name} ({c.phone or 'No phone'})", c.id)
        cust_layout.addWidget(self.combo_customer)
        layout.addWidget(self.box_customer)
        self.box_customer.setVisible(False)

        # Amount Received (Cash)
        layout.addWidget(QLabel("Amount Received:"))
        self.input_received = QLineEdit()
        self.input_received.setText(str(self.total_amount))
        self.input_received.textChanged.connect(self._on_received_changed)
        layout.addWidget(self.input_received)

        # Change Display
        lbl_change_title = QLabel("Change to Return:")
        self.lbl_change = QLabel(format_currency(Decimal("0")))
        self.lbl_change.setObjectName("label_title")
        layout.addWidget(lbl_change_title)
        layout.addWidget(self.lbl_change)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("Complete Sale (F5)")
        self.btn_confirm.setObjectName("btn_success")
        self.btn_confirm.clicked.connect(self._on_confirm)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

        self._on_received_changed()

    def _on_method_changed(self, idx: int) -> None:
        methods = [PaymentMethod.CASH, PaymentMethod.CREDIT, PaymentMethod.CARD, PaymentMethod.BANK]
        self.payment_method = methods[idx]
        self.box_customer.setVisible(self.payment_method == PaymentMethod.CREDIT)

        if self.payment_method == PaymentMethod.CREDIT:
            self.input_received.setText("0")
            self.input_received.setEnabled(False)
        else:
            self.input_received.setEnabled(True)
            self.input_received.setText(str(self.total_amount))

    def _on_received_changed(self) -> None:
        try:
            val = parse_amount(self.input_received.text() or "0")
            change = max(Decimal("0"), val - self.total_amount)
            self.lbl_change.setText(format_currency(change))
        except Exception:
            self.lbl_change.setText(format_currency(Decimal("0")))

    def _on_confirm(self) -> None:
        try:
            self.paid_amount = parse_amount(self.input_received.text() or "0")
        except Exception:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid received amount.")
            return

        if self.payment_method == PaymentMethod.CREDIT:
            cust_id = self.combo_customer.currentData()
            if cust_id is None:
                QMessageBox.warning(self, "Customer Required", "Please select a customer for credit (Khata) sale.")
                return
            self.selected_customer_id = cust_id
        elif self.payment_method == PaymentMethod.CASH:
            if self.paid_amount < self.total_amount:
                QMessageBox.warning(self, "Insufficient Amount", "Cash received is less than total amount.")
                return

        self.accept()
