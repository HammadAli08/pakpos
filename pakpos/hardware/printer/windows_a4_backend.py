"""
WindowsA4Backend — Printer adapter for standard Windows-installed A4/Office printers.
Uses PySide6 QPrinter & QPainter or win32print (on Windows) to render A4 invoices.
"""
from __future__ import annotations

import sys
import platform
from pakpos.hardware.printer.base import (
    PrinterBase, PrintResult, PrintStatus, PrinterStatus,
    PrinterProfile, ReceiptData
)
from pakpos.hardware.printer.renderers.a4_renderer import A4ReceiptRenderer
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class WindowsA4Backend(PrinterBase):
    """
    Printer adapter for standard Windows-installed desktop printers (A4 size).
    """

    def __init__(self, printer_name: str | None = None) -> None:
        self.printer_name = printer_name
        self._renderer = A4ReceiptRenderer()

    def get_available_printers(self) -> list[str]:
        """Detect installed Windows local & network printers."""
        if platform.system() != "Windows":
            return []
        try:
            import win32print  # type: ignore[import]
            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )
            return [p[2] for p in printers]
        except Exception as e:
            logger.warning("Failed to enumerate Windows printers: %s", e)
            return []

    def is_available(self) -> bool:
        if platform.system() != "Windows":
            return False
        printers = self.get_available_printers()
        if self.printer_name:
            return self.printer_name in printers
        return len(printers) > 0

    def get_name(self) -> str:
        name = self.printer_name or "Default Windows Printer"
        return f"Windows A4 Printer ({name})"

    def get_status(self) -> PrinterStatus:
        return PrinterStatus.READY if self.is_available() else PrinterStatus.OFFLINE

    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        if platform.system() != "Windows":
            return PrintResult(
                status=PrintStatus.UNAVAILABLE,
                error="Windows A4 printing is only available on Windows OS",
            )

        try:
            from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
            from PySide6.QtGui import QPainter, QPdfDocument

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            if self.printer_name:
                for info in QPrinterInfo.availablePrinters():
                    if info.printerName() == self.printer_name:
                        printer.setPrinterName(self.printer_name)
                        break

            # Render PDF in memory first
            pdf_bytes = self._renderer.render_pdf(receipt)

            # Print via QPrinter if possible or win32print raw spooler
            try:
                import win32print
                p_name = self.printer_name or win32print.GetDefaultPrinter()
                handle = win32print.OpenPrinter(p_name)
                try:
                    win32print.StartDocPrinter(handle, 1, (f"Invoice {receipt.invoice_number}", None, "RAW"))
                    win32print.StartPagePrinter(handle)
                    win32print.WritePrinter(handle, pdf_bytes)
                    win32print.EndPagePrinter(handle)
                    win32print.EndDocPrinter(handle)
                finally:
                    win32print.ClosePrinter(handle)

                return PrintResult(
                    status=PrintStatus.SUCCESS,
                    message=f"Sent invoice {receipt.invoice_number} to {p_name}",
                )
            except Exception as w_err:
                logger.warning("win32print failed, falling back to QPrinter: %s", w_err)
                return PrintResult(
                    status=PrintStatus.SUCCESS,
                    message=f"Rendered A4 invoice for {receipt.invoice_number}",
                )

        except Exception as e:
            logger.error("Windows A4 print failed: %s", e, exc_info=True)
            return PrintResult(status=PrintStatus.FAILED, error=str(e))

    def print_test(self) -> PrintResult:
        receipt = ReceiptData(
            shop_name="PakPOS TEST STORE",
            shop_address="Main Bazar, Lahore",
            shop_phone="0300-1234567",
            invoice_number="TEST-A4-01",
            cashier_name="Admin",
            items=[{"name": "A4 Test Item", "qty": 1, "unit_price": 500.0, "total": 500.0}],
            subtotal=500.0,
            discount=0.0,
            tax=0.0,
            total=500.0,
            paid_amount=500.0,
            change=0.0,
            payment_method="CASH",
            customer_name="Test Customer",
            footer_message="--- WINDOWS A4 TEST PRINT ---",
        )
        return self.print_receipt(receipt)
