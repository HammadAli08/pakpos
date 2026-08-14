"""
CustomerDialog & QuickCustomerDialog — Dialogs for customer management.
Enables creating new Khata customers directly from POS checkout modal or customers screen.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame
)

from pakpos.database.models.customer import Customer
from pakpos.database.repositories.customer_repo import CustomerRepository
from pakpos.utils.validators import parse_amount
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class QuickCustomerDialog(QDialog):
    """
    Compact modal dialog for adding a new Khata customer on the fly during checkout.
    """

    def __init__(self, parent=None, session=None) -> None:
        super().__init__(parent)
        self.session = session
        self.created_customer: Optional[Customer] = None

        self.setWindowTitle("Add New Khata Customer")
        self.setMinimumWidth(400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Title
        lbl_header = QLabel("NEW KHATA CUSTOMER")
        lbl_header.setStyleSheet("""
            font-weight: 700;
            font-size: 14px;
            color: #20c997;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(lbl_header)

        # Customer Name (Required)
        layout.addWidget(QLabel("Customer Name *"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("e.g. Tariq Mahmood")
        self.input_name.setFixedHeight(36)
        layout.addWidget(self.input_name)

        # Mobile / Cell Number
        layout.addWidget(QLabel("Mobile / Cell Number"))
        self.input_phone = QLineEdit()
        self.input_phone.setPlaceholderText("e.g. 0300-1122334")
        self.input_phone.setFixedHeight(36)
        layout.addWidget(self.input_phone)

        # Address (Optional)
        layout.addWidget(QLabel("Address (Optional)"))
        self.input_address = QLineEdit()
        self.input_address.setPlaceholderText("e.g. Shop #4, Main Bazaar, Lahore")
        self.input_address.setFixedHeight(36)
        layout.addWidget(self.input_address)

        # Opening Balance (Optional)
        layout.addWidget(QLabel("Opening Balance (Rs.)"))
        self.input_balance = QLineEdit()
        self.input_balance.setText("0.00")
        self.input_balance.setFixedHeight(36)
        layout.addWidget(self.input_balance)

        # Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.setFixedHeight(38)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Customer")
        btn_save.setObjectName("btn_success")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet("""
            QPushButton#btn_success {
                background-color: #198754;
                color: white;
                font-weight: 700;
                font-size: 13px;
                border-radius: 6px;
            }
            QPushButton#btn_success:hover {
                background-color: #1fa863;
            }
        """)
        btn_save.clicked.connect(self._on_save)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        # Auto-focus name field
        self.input_name.setFocus()

    def _on_save(self) -> None:
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Customer name is required.")
            self.input_name.setFocus()
            return

        phone = self.input_phone.text().strip() or None
        address = self.input_address.text().strip() or None

        try:
            opening_bal = parse_amount(self.input_balance.text() or "0")
        except Exception:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid numeric opening balance.")
            self.input_balance.setFocus()
            return

        if self.session is not None:
            try:
                repo = CustomerRepository(self.session)
                customer = repo.create(
                    name=name,
                    phone=phone,
                    address=address,
                    opening_balance=opening_bal,
                    current_balance=opening_bal,
                    is_active=True
                )
                self.session.flush()
                self.created_customer = customer
                logger.info("Created new customer on the fly: %s (ID: %s)", customer.name, customer.id)
            except Exception as e:
                logger.error("Failed to create customer on the fly: %s", e, exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to save customer: {e}")
                return
        else:
            # Fallback if no session provided
            self.created_customer = Customer(
                name=name,
                phone=phone,
                address=address,
                opening_balance=opening_bal,
                current_balance=opening_bal,
                is_active=True
            )

        self.accept()
