"""
PrinterTestDialog — Modal dialog for testing printer hardware and renderers with synthetic data.
Does NOT impact sales data or database records.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QGroupBox
)

from pakpos.hardware.printer.base import ReceiptData, PrinterStatus
from pakpos.hardware.printer.printer_manager import PrinterManager
from pakpos.hardware.printer.pdf_backend import PdfBackend
from pakpos.ui.dialogs.receipt_preview_dialog import ReceiptPreviewDialog
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class PrinterTestDialog(QDialog):
    """Printer hardware testing and preview dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.manager = PrinterManager()
        self.setWindowTitle("Test Printer Hardware & Layouts")
        self.setFixedSize(500, 360)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header Info
        backend_name = self.manager.backend.get_name()
        status = self.manager.get_status()
        status_color = "#10b981" if status == PrinterStatus.READY else "#f59e0b"

        lbl_header = QLabel(f"Active Backend: <b>{backend_name}</b>")
        lbl_status = QLabel(f"Status: <font color='{status_color}'><b>● {status.value}</b></font>")

        layout.addWidget(lbl_header)
        layout.addWidget(lbl_status)

        # Group 1: Preview Layouts
        box_preview = QGroupBox("Layout Previews (Synthetic Sample Data)")
        prev_layout = QHBoxLayout(box_preview)

        btn_prev_80 = QPushButton("80mm Thermal")
        btn_prev_80.clicked.connect(lambda: self._show_preview(80))
        prev_layout.addWidget(btn_prev_80)

        btn_prev_58 = QPushButton("58mm Thermal")
        btn_prev_58.clicked.connect(lambda: self._show_preview(58))
        prev_layout.addWidget(btn_prev_58)

        btn_prev_a4 = QPushButton("A4 Tax Invoice")
        btn_prev_a4.clicked.connect(lambda: self._show_preview(0))
        prev_layout.addWidget(btn_prev_a4)

        layout.addWidget(box_preview)

        # Group 2: Physical Hardware & Output Testing
        box_hardware = QGroupBox("Hardware Print Test")
        hw_layout = QHBoxLayout(box_hardware)

        btn_test_print = QPushButton("Send Test Receipt")
        btn_test_print.setObjectName("btn_primary")
        btn_test_print.clicked.connect(self._on_test_print)
        hw_layout.addWidget(btn_test_print)

        btn_test_pdf = QPushButton("Export Test PDF")
        btn_test_pdf.setObjectName("btn_secondary")
        btn_test_pdf.clicked.connect(self._on_test_pdf)
        hw_layout.addWidget(btn_test_pdf)

        layout.addWidget(box_hardware)

        layout.addStretch()

        # Bottom Close Button
        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _create_sample_receipt(self, paper_width: int = 80) -> ReceiptData:
        return ReceiptData(
            shop_name="PakPOS DEMO STORE",
            shop_address="Shop #12, Liberty Market, Gulberg, Lahore",
            shop_phone="042-35712345 / 0300-9876543",
            invoice_number="INV-TEST-2026",
            cashier_name="Ali Raza (Cashier)",
            items=[
                {"name": "Super Basmati Rice 5kg", "qty": 1, "unit_price": 1850.0, "discount": 50.0, "tax": 0.0, "total": 1800.0},
                {"name": "Olpers Milk 1L Pack of 12 Carton Box", "qty": 2, "unit_price": 3400.0, "discount": 0.0, "tax": 0.0, "total": 6800.0},
                {"name": "Lipton Yellow Label Tea 950g", "qty": 1, "unit_price": 1650.0, "discount": 0.0, "tax": 0.0, "total": 1650.0},
            ],
            subtotal=10300.0,
            discount=50.0,
            tax=0.0,
            total=10250.0,
            paid_amount=10500.0,
            change=250.0,
            payment_method="CASH",
            customer_name="Muhammad Usman",
            customer_phone="0321-1234567",
            footer_message="Thank you for shopping at PakPOS Demo!\nSoftware by PakPOS Desktop Application",
            paper_width_mm=paper_width,
            qr_payload="INV:TEST-2026|TOTAL:10250.00|DATE:14-Aug-2026",
            tax_number="NTN-1234567-8",
        )

    def _show_preview(self, width: int) -> None:
        receipt = self._create_sample_receipt(paper_width=width if width > 0 else 80)
        dlg = ReceiptPreviewDialog(receipt, parent=self)
        if width == 58:
            dlg.combo_format.setCurrentIndex(1)
        elif width == 0:
            dlg.combo_format.setCurrentIndex(2)
        else:
            dlg.combo_format.setCurrentIndex(0)
        dlg.exec()

    def _on_test_print(self) -> None:
        result = self.manager.print_test()
        if result.success:
            QMessageBox.information(self, "Test Print Success", result.message or "Test print completed successfully.")
        else:
            QMessageBox.warning(self, "Test Print Failed", f"Test print error:\n{result.error or result.message}")

    def _on_test_pdf(self) -> None:
        result = PdfBackend().print_test()
        if result.success:
            QMessageBox.information(self, "PDF Created", result.message)
        else:
            QMessageBox.warning(self, "PDF Creation Failed", result.error or "Could not create PDF.")
