"""
PdfBackend — Receipt backend that exports receipts directly to PDF files.
Useful for digital receipt dispatch, archiving, testing, and backup print fallback.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from pakpos.config.settings import EXPORT_DIR
from pakpos.hardware.printer.base import (
    PrinterBase, PrintResult, PrintStatus, PrinterStatus,
    PrinterProfile, ReceiptData
)
from pakpos.hardware.printer.renderers.a4_renderer import A4ReceiptRenderer
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class PdfBackend(PrinterBase):
    """PDF exporter backend. Always available without printer hardware."""

    def __init__(self, export_dir: Path | None = None) -> None:
        self.export_dir = export_dir or (EXPORT_DIR / "receipts")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self._renderer = A4ReceiptRenderer()
        self._last_pdf_path: Path | None = None

    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.export_dir / f"receipt_{receipt.invoice_number}_{timestamp}.pdf"
            self._renderer.render_pdf(receipt, target=filename)
            self._last_pdf_path = filename
            logger.info("PdfBackend: PDF receipt created at %s", filename)
            return PrintResult(
                status=PrintStatus.SUCCESS,
                message=f"PDF saved to {filename}",
            )
        except Exception as e:
            logger.error("PdfBackend failed to render PDF: %s", e, exc_info=True)
            return PrintResult(status=PrintStatus.FAILED, error=str(e))

    def print_test(self) -> PrintResult:
        receipt = ReceiptData(
            shop_name="PakPOS TEST STORE",
            shop_address="Main Bazar, Lahore",
            shop_phone="0300-1234567",
            invoice_number="TEST-PDF-01",
            cashier_name="Admin",
            items=[
                {"name": "Sample Product A", "qty": 1, "unit_price": 250.0, "total": 250.0},
                {"name": "Sample Product B", "qty": 2, "unit_price": 100.0, "total": 200.0},
            ],
            subtotal=450.0,
            discount=0.0,
            tax=0.0,
            total=450.0,
            paid_amount=500.0,
            change=50.0,
            payment_method="CASH",
            customer_name="Test Customer",
            footer_message="--- TEST PDF EXPORT ---",
            qr_payload="PAKPOS-TEST-PDF",
        )
        return self.print_receipt(receipt)

    def is_available(self) -> bool:
        return True

    def get_name(self) -> str:
        return "PDF File Exporter"

    def get_status(self) -> PrinterStatus:
        return PrinterStatus.READY

    def get_last_pdf_path(self) -> Path | None:
        return self._last_pdf_path
