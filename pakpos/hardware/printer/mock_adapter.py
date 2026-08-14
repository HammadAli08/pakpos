"""
MockPrinterAdapter — used in tests and Fedora development.
Saves receipt to a text file instead of printing.
Requires Windows hardware for real printing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pakpos.config.settings import EXPORT_DIR
from pakpos.hardware.printer.base import PrinterBase, PrintResult, PrintStatus, ReceiptData
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class MockPrinterAdapter(PrinterBase):
    """
    Test/development printer that writes receipts to files.
    All tests must use this adapter — never a real printer.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or (EXPORT_DIR / "receipts")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._last_receipt: str | None = None

    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        try:
            text = self._render_receipt(receipt)
            self._last_receipt = text
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = self._output_dir / f"receipt_{receipt.invoice_number}_{timestamp}.txt"
            filename.write_text(text, encoding="utf-8")
            logger.info("MockPrinter: receipt saved to %s", filename)
            return PrintResult(status=PrintStatus.SUCCESS, message=f"Saved to {filename}")
        except Exception as e:
            logger.error("MockPrinter: failed to save receipt: %s", e, exc_info=True)
            return PrintResult(status=PrintStatus.FAILED, error=str(e))

    def print_test(self) -> PrintResult:
        receipt = ReceiptData(
            shop_name="TEST SHOP",
            shop_address="Test Address",
            shop_phone="0300-0000000",
            invoice_number="TEST-001",
            cashier_name="Test",
            items=[{"name": "Test Item", "qty": 1, "unit_price": 100.0, "total": 100.0}],
            subtotal=100.0,
            discount=0.0,
            tax=0.0,
            total=100.0,
            paid_amount=100.0,
            change=0.0,
            payment_method="CASH",
            customer_name=None,
            footer_message="--- TEST PRINT ---",
        )
        return self.print_receipt(receipt)

    def is_available(self) -> bool:
        return True

    def get_name(self) -> str:
        return "MockPrinter (Development)"

    def get_last_receipt(self) -> str | None:
        return self._last_receipt

    @staticmethod
    def _render_receipt(r: ReceiptData) -> str:
        from pakpos.hardware.printer.renderers.thermal_renderer import ThermalReceiptRenderer
        return ThermalReceiptRenderer().render_to_text(r)

