"""
PosScreen — Main Point of Sale Checkout Terminal Screen.

Features:
- Prominent BarcodeInput search field (auto-focus, scanner integration)
- ProductGridWidget with visual product cards & category filter tabs
- Compact POS CartWidget with live quantity spinboxes & stock limit guard
- Summary panel displaying Subtotal, Tax, and prominent GRAND TOTAL DUE
- F1 (search), Enter (add), F5 (checkout), Esc (clear), Delete (remove) shortcuts
- Post-sale completion confirmation and instant workflow reset for next customer
"""
from __future__ import annotations

from decimal import Decimal
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel,
    QPushButton, QMessageBox, QFrame
)

from pakpos.database.engine import get_session
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.database.repositories.customer_repo import CustomerRepository
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
from pakpos.hardware.printer.base import ReceiptData
from pakpos.ui.widgets.barcode_input import BarcodeInput
from pakpos.ui.widgets.product_grid import ProductGridWidget, ProductCard
from pakpos.ui.widgets.cart_widget import CartWidget
from pakpos.ui.dialogs.payment_dialog import PaymentDialog
from pakpos.events import app_events
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
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """Subscribe to central application domain events."""
        app_events.inventory_changed.connect(lambda _: self._load_products())
        app_events.sale_voided.connect(lambda _: self._load_products())

    def refresh(self) -> None:
        """Public API to force reload products directly from authoritative database."""
        self._load_products()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ─── LEFT PANEL: Search & Product Card Grid ───
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Search Bar
        search_frame = QFrame()
        search_frame.setObjectName("card")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 8, 8, 8)

        self.input_barcode = BarcodeInput()
        self.input_barcode.setPlaceholderText("Search product name, barcode, or SKU... (F1)")
        self.input_barcode.barcode_scanned.connect(self._on_barcode_scanned)
        self.input_barcode.textChanged.connect(self._on_search_text_changed)
        self.input_barcode.returnPressed.connect(self._on_search_enter_pressed)

        search_layout.addWidget(self.input_barcode)

        # Product Grid Widget (Category Tabs + Cards)
        self.product_grid = ProductGridWidget()
        self.product_grid.product_selected.connect(self._on_card_clicked)
        self.product_grid.out_of_stock_selected.connect(self._on_out_of_stock_clicked)

        left_layout.addWidget(search_frame)
        left_layout.addWidget(self.product_grid, 1)

        # ─── RIGHT PANEL: Cart & Totals Summary ───
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Cart Widget
        self.cart_widget = CartWidget()
        self.cart_widget.cart_updated.connect(self._update_totals)

        # Totals Summary Card
        box_totals = QFrame()
        box_totals.setObjectName("card")
        box_totals.setStyleSheet("""
            QFrame#card {
                background-color: #22252c;
                border: 1px solid #2d3139;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        tot_layout = QVBoxLayout(box_totals)
        tot_layout.setContentsMargins(12, 10, 12, 10)
        tot_layout.setSpacing(6)

        # Subtotal & Tax Row
        summary_row = QHBoxLayout()
        lbl_sub_title = QLabel("Subtotal:")
        lbl_sub_title.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.lbl_subtotal_amount = QLabel("Rs. 0.00")
        self.lbl_subtotal_amount.setStyleSheet("font-weight: 600; font-size: 13px; color: #e8eaed;")
        self.lbl_subtotal_amount.setAlignment(Qt.AlignmentFlag.AlignRight)

        lbl_tax_title = QLabel("Tax:")
        lbl_tax_title.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.lbl_tax_amount = QLabel("Rs. 0.00")
        self.lbl_tax_amount.setStyleSheet("font-weight: 600; font-size: 13px; color: #e8eaed;")
        self.lbl_tax_amount.setAlignment(Qt.AlignmentFlag.AlignRight)

        summary_row.addWidget(lbl_sub_title)
        summary_row.addWidget(self.lbl_subtotal_amount)
        summary_row.addSpacing(24)
        summary_row.addWidget(lbl_tax_title)
        summary_row.addWidget(self.lbl_tax_amount)

        # Grand Total Due
        lbl_tot_title = QLabel("TOTAL DUE")
        lbl_tot_title.setStyleSheet("font-weight: 700; font-size: 12px; color: #9ca3af; letter-spacing: 0.5px;")
        self.lbl_total_amount = QLabel("Rs. 0.00")
        self.lbl_total_amount.setStyleSheet("font-weight: 800; font-size: 26px; color: #20c997;")

        tot_layout.addLayout(summary_row)
        tot_layout.addWidget(lbl_tot_title)
        tot_layout.addWidget(self.lbl_total_amount)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_clear = QPushButton("Clear Cart (Esc)")
        btn_clear.setObjectName("btn_secondary")
        btn_clear.setFixedHeight(44)
        btn_clear.clicked.connect(self.cart_widget.clear_cart)

        btn_pay = QPushButton("CHECKOUT / PAY (F5)")
        btn_pay.setObjectName("btn_success")
        btn_pay.setFixedHeight(44)
        btn_pay.setStyleSheet("""
            QPushButton#btn_success {
                background-color: #198754;
                font-weight: 800;
                font-size: 14px;
                letter-spacing: 0.5px;
            }
            QPushButton#btn_success:hover {
                background-color: #1fa863;
            }
        """)
        btn_pay.clicked.connect(self._on_checkout)

        btn_layout.addWidget(btn_clear, 1)
        btn_layout.addWidget(btn_pay, 2)

        right_layout.addWidget(self.cart_widget, 1)
        right_layout.addWidget(box_totals)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 550])

        layout.addWidget(splitter)
        self._load_products()

    def _setup_shortcuts(self) -> None:
        shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        shortcut_f5.activated.connect(self._on_checkout)

        shortcut_f1 = QShortcut(QKeySequence("F1"), self)
        shortcut_f1.activated.connect(self.input_barcode.setFocus)

        shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        shortcut_esc.activated.connect(self._on_esc_pressed)

        shortcut_del = QShortcut(QKeySequence("Delete"), self)
        shortcut_del.activated.connect(self._on_delete_pressed)

    def _load_products(self, query: str = "") -> None:
        self.product_grid.refresh_products(query)

    def _on_search_text_changed(self, text: str) -> None:
        self._load_products(text)

    def _on_search_enter_pressed(self) -> None:
        query = self.input_barcode.text().strip()
        if not query:
            return

        # Check exact barcode match first
        with get_session() as session:
            repo = ProductRepository(session)
            product = repo.get_by_barcode(query)
            if product:
                if product.current_stock <= 0:
                    QMessageBox.warning(self, "Out of Stock", f"Product '{product.name}' is currently out of stock.")
                else:
                    self._add_product_to_cart(product)
                    self.input_barcode.clear()
                return

        # Otherwise add first available card in grid
        card = self.product_grid.get_first_available_card()
        if card:
            self._add_card_to_cart(card)
            self.input_barcode.clear()

    def _on_barcode_scanned(self, barcode: str) -> None:
        with get_session() as session:
            repo = ProductRepository(session)
            product = repo.get_by_barcode(barcode)
            if product:
                if product.current_stock <= 0:
                    QMessageBox.warning(self, "Out of Stock", f"Product '{product.name}' is currently out of stock.")
                else:
                    self._add_product_to_cart(product)
            else:
                QMessageBox.warning(self, "Product Not Found", f"No product found with barcode '{barcode}'.")

    def _on_card_clicked(self, card: ProductCard) -> None:
        self._add_card_to_cart(card)

    def _on_out_of_stock_clicked(self, card: ProductCard) -> None:
        QMessageBox.warning(self, "Out of Stock", f"Product '{card.product_name}' is currently out of stock.")

    def _add_card_to_cart(self, card: ProductCard) -> None:
        cart_item = CartItem(
            product_id=card.product_id,
            product_name=card.product_name,
            barcode=card.barcode,
            quantity=Decimal("1"),
            unit_price=card.sale_price,
            tax_rate=card.tax_rate,
        )
        self.cart_widget.add_item(cart_item)
        self.input_barcode.setFocus()

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

    def _on_esc_pressed(self) -> None:
        if self.input_barcode.hasFocus() and self.input_barcode.text():
            self.input_barcode.clear()
        else:
            self.cart_widget.clear_cart()

    def _on_delete_pressed(self) -> None:
        items = self.cart_widget.get_items()
        if items:
            self.cart_widget.remove_item(len(items) - 1)

    def _update_totals(self) -> None:
        subtotal = self.cart_widget.get_subtotal()
        tax = self.cart_widget.get_tax_total()
        total = self.cart_widget.get_total()
        self.lbl_subtotal_amount.setText(format_currency(subtotal))
        self.lbl_tax_amount.setText(format_currency(tax))
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
                    app_events.sale_completed.emit(result.sale_id)

                    # Print Receipt
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

                    # Sale Completed Confirmation Dialog
                    QMessageBox.information(
                        self,
                        "Sale Completed",
                        f"Invoice #{result.invoice_number} saved successfully!\n\n"
                        f"Total Amount: {format_currency(result.total)}\n"
                        f"Paid Amount:  {format_currency(result.paid_amount)}\n"
                        f"Change Due:   {format_currency(result.change)}"
                    )

                    # Reset workflow for next customer
                    self.cart_widget.clear_cart()
                    self.input_barcode.clear()
                    self._load_products()
                    self.input_barcode.setFocus()

                except Exception as e:
                    session.rollback()
                    logger.error("Checkout failed: %s", e, exc_info=True)
                    QMessageBox.critical(self, "Sale Error", f"Failed to complete sale: {e}")
