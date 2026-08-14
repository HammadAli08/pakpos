"""
ReceiptPreviewDialog — Interactive receipt preview modal.
Allows viewing how receipts look in 80mm thermal, 58mm thermal, and A4 formats.
Supports direct printing and PDF export.
"""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox
)

from pakpos.hardware.printer.base import ReceiptData, PrinterStatus
from pakpos.hardware.printer.printer_manager import PrinterManager
from pakpos.hardware.printer.pdf_backend import PdfBackend
from pakpos.hardware.printer.renderers.thermal_renderer import ThermalReceiptRenderer
from pakpos.hardware.printer.renderers.a4_renderer import A4ReceiptRenderer
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class ReceiptPreviewDialog(QDialog):
    """Modal dialog for receipt rendering preview and actions."""

    def __init__(self, receipt: ReceiptData, parent=None) -> None:
        super().__init__(parent)
        self.receipt = receipt
        self.manager = PrinterManager()

        self.setWindowTitle(f"Receipt Preview — Invoice {receipt.invoice_number}")
        self.setMinimumSize(580, 680)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Top Bar: Format Selector & Status Badge ──
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Preview Format:"))

        self.combo_format = QComboBox()
        self.combo_format.addItems(["80mm Thermal POS", "58mm Thermal POS", "A4 Tax Invoice"])
        # Set default format matching receipt paper width
        if self.receipt.paper_width_mm <= 58:
            self.combo_format.setCurrentIndex(1)
        else:
            self.combo_format.setCurrentIndex(0)

        self.combo_format.currentIndexChanged.connect(self._update_preview)
        top_layout.addWidget(self.combo_format)

        top_layout.addStretch()

        # Status badge
        status = self.manager.get_status()
        status_color = "#10b981" if status == PrinterStatus.READY else "#f59e0b"
        self.lbl_status = QLabel(f"● {status.value} ({self.manager.backend.get_name()})")
        self.lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold; font-size: 11px;")
        top_layout.addWidget(self.lbl_status)

        layout.addLayout(top_layout)

        # ── Preview Box Container ──
        self.frame_preview = QFrame()
        self.frame_preview.setStyleSheet("QFrame { background-color: #1e293b; border-radius: 6px; padding: 12px; }")
        frame_layout = QVBoxLayout(self.frame_preview)

        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setStyleSheet(
            "QTextEdit { font-family: 'Courier New', monospace; font-size: 12px; line-height: 1.2; "
            "background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 4px; padding: 8px; }"
        )
        frame_layout.addWidget(self.txt_preview)
        layout.addWidget(self.frame_preview)

        # ── Bottom Action Buttons ──
        btn_layout = QHBoxLayout()

        btn_pdf = QPushButton("Save PDF...")
        btn_pdf.setObjectName("btn_secondary")
        btn_pdf.clicked.connect(self._on_save_pdf)
        btn_layout.addWidget(btn_pdf)

        btn_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)

        self.btn_print = QPushButton("Print Receipt")
        self.btn_print.setObjectName("btn_primary")
        self.btn_print.clicked.connect(self._on_print)
        btn_layout.addWidget(self.btn_print)

        layout.addLayout(btn_layout)

        self._update_preview()

    def _update_preview(self) -> None:
        idx = self.combo_format.currentIndex()

        if idx == 0:  # 80mm Thermal
            r_copy = ReceiptData(**{**self.receipt.__dict__, 'paper_width_mm': 80})
            text = ThermalReceiptRenderer().render_to_text(r_copy)
            self.txt_preview.setPlainText(text)
        elif idx == 1:  # 58mm Thermal
            r_copy = ReceiptData(**{**self.receipt.__dict__, 'paper_width_mm': 58})
            text = ThermalReceiptRenderer().render_to_text(r_copy)
            self.txt_preview.setPlainText(text)
        else:  # A4 Invoice summary
            text = ThermalReceiptRenderer().render_to_text(self.receipt)
            summary = f"=== A4 TAX INVOICE PREVIEW ===\n\n{text}\n\n[Full A4 document rendered via ReportLab on print/export]"
            self.txt_preview.setPlainText(summary)

    def _on_save_pdf(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Receipt PDF", f"receipt_{self.receipt.invoice_number}.pdf", "PDF Files (*.pdf)"
        )
        if not path_str:
            return

        try:
            PdfBackend().print_receipt(ReceiptData(**{**self.receipt.__dict__}))
            A4ReceiptRenderer().render_pdf(self.receipt, target=path_str)
            QMessageBox.information(self, "PDF Saved", f"Receipt saved successfully to:\n{path_str}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save PDF: {e}")

    def _on_print(self) -> None:
        result = self.manager.print_receipt(self.receipt)
        if result.success:
            QMessageBox.information(self, "Printed", result.message or "Receipt printed successfully.")
            self.accept()
        else:
            QMessageBox.warning(
                self, "Print Failed",
                f"Receipt print failed:\n{result.error or result.message}\n\nYou can retry or save as PDF."
            )
