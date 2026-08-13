"""
WindowsPrinterAdapter — Windows-only thermal/receipt printer.
Uses Python's win32print for Windows printing.
This file is imported only on Windows builds.
Requires Windows hardware validation before commercial use.
"""
from __future__ import annotations

import platform
from pakpos.hardware.printer.base import PrinterBase, PrintResult, PrintStatus, ReceiptData
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)

# NOTE: win32print is only available on Windows.
# On Linux, this adapter raises ImportError — that's correct behaviour.


class WindowsPrinterAdapter(PrinterBase):
    """
    Windows printer adapter using win32print.
    REQUIRES WINDOWS HARDWARE VALIDATION before commercial deployment.
    """

    def __init__(self, printer_name: str | None = None) -> None:
        self._printer_name = printer_name
        self._win32print = None
        self._available = False
        self._init_win32()

    def _init_win32(self) -> None:
        if platform.system() != "Windows":
            logger.warning("WindowsPrinterAdapter loaded on non-Windows — will be unavailable")
            return
        try:
            import win32print  # type: ignore[import]
            self._win32print = win32print
            if self._printer_name is None:
                self._printer_name = win32print.GetDefaultPrinter()
            self._available = True
        except ImportError:
            logger.warning("win32print not available — printer unavailable")
        except Exception as e:
            logger.warning("Printer init failed: %s", e)

    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        if not self._available or self._win32print is None:
            return PrintResult(status=PrintStatus.UNAVAILABLE, error="Windows printer not available")
        try:
            from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
            text = MockPrinterAdapter()._render_receipt(receipt)
            text_bytes = text.encode("cp1252", errors="replace")

            handle = self._win32print.OpenPrinter(self._printer_name)
            try:
                self._win32print.StartDocPrinter(handle, 1, ("PakPOS Receipt", None, "RAW"))
                self._win32print.StartPagePrinter(handle)
                self._win32print.WritePrinter(handle, text_bytes)
                self._win32print.EndPagePrinter(handle)
                self._win32print.EndDocPrinter(handle)
            finally:
                self._win32print.ClosePrinter(handle)
            return PrintResult(status=PrintStatus.SUCCESS)
        except Exception as e:
            logger.error("Windows print failed: %s", e, exc_info=True)
            return PrintResult(status=PrintStatus.FAILED, error=str(e))

    def print_test(self) -> PrintResult:
        from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
        mock = MockPrinterAdapter()
        test_receipt = mock.print_test()
        # Re-print via Windows if available
        return self.print_receipt(ReceiptData(
            shop_name="PakPOS TEST", shop_address="", shop_phone="",
            invoice_number="TEST-001", cashier_name="System",
            items=[], subtotal=0, discount=0, tax=0, total=0,
            paid_amount=0, change=0, payment_method="CASH",
            customer_name=None, footer_message="--- PRINTER TEST ---",
        ))

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        if self._printer_name:
            return f"Windows Printer: {self._printer_name}"
        return "Windows Printer (not configured)"

    def get_available_printers(self) -> list[str]:
        if self._win32print is None:
            return []
        try:
            printers = self._win32print.EnumPrinters(
                self._win32print.PRINTER_ENUM_LOCAL | self._win32print.PRINTER_ENUM_CONNECTIONS
            )
            return [p[2] for p in printers]
        except Exception:
            return []
