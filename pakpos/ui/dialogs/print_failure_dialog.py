"""
PrintFailureDialog — Non-blocking error recovery dialog for failed receipt prints.
Mandated by PakPOS resilience rules: Sale is ALREADY committed to database.
Print failure must NEVER attempt sale rollback.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QFileDialog
)

from pakpos.hardware.printer.base import ReceiptData, PrintResult
from pakpos.hardware.printer.printer_manager import PrinterManager
from pakpos.hardware.printer.pdf_backend import PdfBackend
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class PrintFailureDialog(QDialog):
    """Resilient post-sale print failure recovery modal."""

    def __init__(self, receipt: ReceiptData, error_message: str = "", parent=None) -> None:
        super().__init__(parent)
        self.receipt = receipt
        self.error_message = error_message
        self.manager = PrinterManager()

        self.setWindowTitle("Receipt Printing Issue")
        self.setFixedSize(480, 260)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Status Notice Header
        lbl_header = QLabel("✔ Sale Saved Successfully")
        lbl_header.setStyleSheet("color: #10b981; font-weight: bold; font-size: 16px;")
        layout.addWidget(lbl_header)

        # Failure detail label
        msg = (
            f"The sale (Invoice #{self.receipt.invoice_number}) was recorded in the database.\n"
            f"However, the receipt printer failed or is unreachable.\n\n"
            f"Reason: {self.error_message or 'Printer offline or disconnected.'}"
        )
        lbl_detail = QLabel(msg)
        lbl_detail.setWordWrap(True)
        lbl_detail.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        layout.addWidget(lbl_detail)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()

        btn_pdf = QPushButton("Save PDF...")
        btn_pdf.setObjectName("btn_secondary")
        btn_pdf.clicked.connect(self._on_save_pdf)
        btn_layout.addWidget(btn_pdf)

        btn_retry = QPushButton("Retry Print")
        btn_retry.setObjectName("btn_primary")
        btn_retry.clicked.connect(self._on_retry)
        btn_layout.addWidget(btn_retry)

        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _on_retry(self) -> None:
        result = self.manager.print_receipt(self.receipt)
        if result.success:
            QMessageBox.information(self, "Printed", "Receipt printed successfully on retry.")
            self.accept()
        else:
            QMessageBox.warning(self, "Retry Failed", f"Print retry failed:\n{result.error or result.message}")

    def _on_save_pdf(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Receipt", f"receipt_{self.receipt.invoice_number}.pdf", "PDF Files (*.pdf)"
        )
        if not path_str:
            return

        res = PdfBackend().print_receipt(self.receipt)
        if res.success:
            QMessageBox.information(self, "PDF Saved", f"Receipt saved to:\n{path_str}")
            self.accept()
        else:
            QMessageBox.warning(self, "PDF Export Failed", res.error or "Failed to export PDF.")
