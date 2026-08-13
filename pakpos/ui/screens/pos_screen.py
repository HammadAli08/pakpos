"""
PosScreen — Main Point of Sale counter screen.

Features:
- BarcodeInput (auto-focus, instant scanner add)
- Product Search & Grid
- CartWidget with real-time totals
- Touch Numpad
- F1/F5 Keyboard Shortcuts
- Atomic sale saving
"""
from __future__ import annotations

from decimal import Decimal
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel,
    QPushButton, QMessageBox, QFrame, QListWidget, QListWidgetItem
)

from pakpos.database.engine import get_session
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.database.repositories.customer_repo import CustomerRepository
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
from pakpos.hardware.printer.base import ReceiptData
from pakpos.ui.widgets.barcode_input import BarcodeInput
from pakpos.ui.widgets.cart_widget import CartWidget
from pakpos.ui.widgets.numeric_pad import NumericPad
from pakpos.ui.dialogs.payment_dialog import PaymentDialog
from pakpos.utils.formatters import format_currency
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class PosScreen(QWidget):
    """
    Main Checkout Counter Screen.
    """

    def __init__(self, current_user, parent=None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.printer = MockPrinterAdapter()
        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ─── LEFT PANEL: Search & Product List ───
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.input_barcode = BarcodeInput()
        self.input_barcode.barcode_scanned.connect(self._on_barcode_scanned)
        self.input_barcode.textChanged.connect(self._on_search_text_changed)

        self.list_products = QListWidget()
        self.list_products.itemDoubleClicked.connect(self._on_product_double_clicked)

        left_layout.addWidget(self.input_barcode)
        left_layout.addWidget(self.list_products)

        # ─── RIGHT PANEL: Cart & Checkout ───
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.cart_widget = CartWidget()
        self.cart_widget.cart_updated.connect(self._update_totals)

        # Totals Panel
        box_totals = QFrame()
        box_totals.setObjectName("card")
        tot_layout = QVBoxLayout(box_totals)

        lbl_tot_title = QLabel("TOTAL DUE")
        lbl_tot_title.setObjectName("label_subtitle")
        self.lbl_total_amount = QLabel("Rs. 0.00")
        self.lbl_total_amount.setObjectName("label_amount")

        tot_layout.addWidget(lbl_tot_title)
        tot_layout.addWidget(self.lbl_total_amount)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_clear = QPushButton("Clear Cart (Esc)")
        btn_clear.setObjectName("btn_secondary")
        btn_clear.clicked.connect(self.cart_widget.clear_cart)

        btn_pay = QPushButton("Checkout Payment (F5)")
        btn_pay.setObjectName("btn_success")
        btn_pay.setFixedHeight(45)
        btn_pay.clicked.connect(self._on_checkout)

        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_pay)

        right_layout.addWidget(self.cart_widget)
        right_layout.addWidget(box_totals)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        self._load_products()

    def _setup_shortcuts(self) -> None:
        shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        shortcut_f5.activated.connect(self._on_checkout)

        shortcut_f1 = QShortcut(QKeySequence("F1"), self)
        shortcut_f1.activated.connect(self.input_barcode.setFocus)

    def _load_products(self, query: str = "") -> None:
        self.list_products.clear()
        with get_session() as session:
            repo = ProductRepository(session)
            products = repo.search(query, limit=30) if query else repo.get_all(active_only=True)[:30]
            for p in products:
                item = QListWidgetItem(f"{p.name} — Rs.{p.sale_price:,.2f} (Stock: {p.current_stock})")
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                self.list_products.addItem(item)

    def _on_search_text_changed(self, text: str) -> None:
        self._load_products(text)

    def _on_barcode_scanned(self, barcode: str) -> None:
        with get_session() as session:
            repo = ProductRepository(session)
            product = repo.get_by_barcode(barcode)
            if product:
                self._add_product_to_cart(product)
            else:
                QMessageBox.warning(self, "Product Not Found", f"No product found with barcode '{barcode}'.")

    def _on_product_double_clicked(self, item: QListWidgetItem) -> None:
        prod_id = item.data(Qt.ItemDataRole.UserRole)
        with get_session() as session:
            repo = ProductRepository(session)
            product = repo.get_by_id(prod_id)
            if product:
                self._add_product_to_cart(product)

    def _add_product_to_cart(self, product) -> None:
        cart_item = CartItem(
            product_id=product.id,
            product_name=product.name,
            barcode=product.barcode,
            quantity=Decimal("1"),
            unit_price=product.sale_price,
            tax_rate=product.tax_rate or Decimal("0"),
        )
        self.cart_widget.add_item(cart_item)
        self.input_barcode.setFocus()

    def _update_totals(self) -> None:
        total = self.cart_widget.get_total()
        self.lbl_total_amount.setText(format_currency(total))

    def _on_checkout(self) -> None:
        items = self.cart_widget.get_items()
        if not items:
            QMessageBox.warning(self, "Empty Cart", "Please add items to cart before checkout.")
            return

        total = self.cart_widget.get_total()

        with get_session() as session:
            cust_repo = CustomerRepository(session)
            customers = cust_repo.get_all(active_only=True)

            dlg = PaymentDialog(total, customers, self)
            if dlg.exec() == PaymentDialog.DialogCode.Accepted:
                # Create Sale
                sales_service = SalesService(session)
                req = SaleRequest(
                    items=items,
                    payment_method=dlg.payment_method,
                    paid_amount=dlg.paid_amount,
                    customer_id=dlg.selected_customer_id,
                    cashier_id=self.current_user.id if self.current_user else None,
                )

                try:
                    result = sales_service.create_sale(req)
                    session.commit()

                    # Print Receipt (Mock or Real)
                    receipt = ReceiptData(
                        shop_name="PakPOS Retail",
                        shop_address="Main Bazar, Lahore",
                        shop_phone="0300-1234567",
                        invoice_number=result.invoice_number,
                        cashier_name=self.current_user.username if self.current_user else "Cashier",
                        items=[{"name": i.product_name, "qty": float(i.quantity), "unit_price": float(i.unit_price), "total": float(i.total)} for i in items],
                        subtotal=float(self.cart_widget.get_subtotal()),
                        discount=0.0,
                        tax=0.0,
                        total=float(result.total),
                        paid_amount=float(result.paid_amount),
                        change=float(result.change),
                        payment_method=dlg.payment_method,
                        customer_name=None,
                        footer_message="Thank you for shopping with us!",
                    )
                    self.printer.print_receipt(receipt)

                    QMessageBox.information(
                        self, "Sale Completed",
                        f"Invoice {result.invoice_number} saved successfully!\n\n"
                        f"Total: {format_currency(result.total)}\n"
                        f"Change: {format_currency(result.change)}"
                    )

                    self.cart_widget.clear_cart()
                    self._load_products()

                except Exception as e:
                    session.rollback()
                    logger.error("Checkout failed: %s", e, exc_info=True)
                    QMessageBox.critical(self, "Sale Error", f"Failed to complete sale: {e}")
