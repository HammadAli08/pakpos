"""
MockPrinterAdapter — used in tests and Fedora development.
Saves receipt to a text file instead of printing.
Requires Windows hardware for real printing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pakpos.hardware.printer.base import PrinterBase, PrintResult, PrintStatus, ReceiptData
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class MockPrinterAdapter(PrinterBase):
    """
    Test/development printer that writes receipts to files.
    All tests must use this adapter — never a real printer.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path("test_output")
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

    def _render_receipt(self, r: ReceiptData) -> str:
        width = 40 if r.paper_width_mm <= 58 else 48
        sep = "-" * width
        lines = [
            r.shop_name.center(width),
            r.shop_address.center(width),
            r.shop_phone.center(width),
            sep,
            f"Invoice: {r.invoice_number}",
            f"Date: {r.created_at or datetime.now().strftime('%d-%b-%Y %H:%M')}",
            f"Cashier: {r.cashier_name}",
        ]
        if r.customer_name:
            lines.append(f"Customer: {r.customer_name}")
        lines.append(sep)
        lines.append(f"{'Item':<22}{'Qty':>4}{'Total':>10}")
        lines.append(sep)
        for item in r.items:
            name = str(item.get("name", ""))[:22]
            qty = str(item.get("qty", ""))
            total = f"Rs.{item.get('total', 0):,.2f}"
            lines.append(f"{name:<22}{qty:>4}{total:>10}")
        lines += [
            sep,
            f"{'Subtotal':<30}{f'Rs.{r.subtotal:,.2f}':>10}",
        ]
        if r.discount:
            lines.append(f"{'Discount':<30}{f'-Rs.{r.discount:,.2f}':>10}")
        if r.tax:
            lines.append(f"{'Tax':<30}{f'Rs.{r.tax:,.2f}':>10}")
        lines += [
            f"{'TOTAL':<30}{f'Rs.{r.total:,.2f}':>10}",
            f"{'Payment':<30}{r.payment_method:>10}",
        ]
        if r.change > 0:
            lines.append(f"{'Change':<30}{f'Rs.{r.change:,.2f}':>10}")
        lines += [sep, r.footer_message.center(width), ""]
        return "\n".join(lines)
