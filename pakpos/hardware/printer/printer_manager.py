"""
PrinterManager — Central management singleton for printer backends.
Reads active configuration from settings repository and constructs appropriate PrinterBackend.
"""
from __future__ import annotations

import platform
from typing import Any
from sqlalchemy.orm import Session

from pakpos.hardware.printer.base import (
    PrinterBase, PrinterBackend, PrintResult, PrintStatus,
    PrinterStatus, PrinterProfile, ReceiptData
)
from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
from pakpos.hardware.printer.pdf_backend import PdfBackend
from pakpos.hardware.printer.thermal_escpos_backend import ThermalEscPosBackend
from pakpos.hardware.printer.windows_a4_backend import WindowsA4Backend
from pakpos.hardware.printer.windows_adapter import WindowsPrinterAdapter
from pakpos.database.repositories.setting_repo import SettingRepository
from pakpos.database.models.setting import SettingKey
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class PrinterManager:
    """Manages active printer backend instance based on application settings."""

    _instance: PrinterManager | None = None

    def __new__(cls) -> PrinterManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._backend = MockPrinterAdapter()
            cls._instance._active_config = {}
        return cls._instance

    @property
    def backend(self) -> PrinterBackend:
        return self._backend

    def load_from_settings(self, session: Session) -> None:
        """Load printer configuration from DB settings and initialize active backend."""
        try:
            repo = SettingRepository(session)
            config = repo.get_printer_settings()
            self._active_config = config

            backend_type = config.get(SettingKey.PRINTER_BACKEND, "mock").lower()
            paper_width = int(config.get(SettingKey.PRINTER_PAPER_WIDTH, "80"))
            auto_cut = config.get(SettingKey.PRINTER_AUTO_CUT, "true").lower() == "true"
            open_drawer = config.get(SettingKey.PRINTER_OPEN_DRAWER, "true").lower() == "true"
            printer_name = config.get(SettingKey.PRINTER_NAME, "")

            if backend_type == "thermal_escpos":
                conn_type = config.get(SettingKey.PRINTER_CONNECTION, "usb")
                vendor_id = config.get(SettingKey.PRINTER_USB_VENDOR, "0x04b8")
                product_id = config.get(SettingKey.PRINTER_USB_PRODUCT, "0x0e15")
                host = config.get(SettingKey.PRINTER_NETWORK_HOST, "192.168.1.100")
                port = int(config.get(SettingKey.PRINTER_NETWORK_PORT, "9100"))

                self._backend = ThermalEscPosBackend(
                    connection_type=conn_type,
                    vendor_id=vendor_id,
                    product_id=product_id,
                    host=host,
                    port=port,
                    paper_width_mm=paper_width,
                    auto_cut=auto_cut,
                    open_drawer=open_drawer,
                )
            elif backend_type == "windows_a4":
                self._backend = WindowsA4Backend(printer_name=printer_name)
            elif backend_type == "pdf":
                self._backend = PdfBackend()
            else:
                self._backend = MockPrinterAdapter()

            logger.info("PrinterManager loaded backend: %s (%s)", self._backend.get_name(), backend_type)

        except Exception as e:
            logger.error("Failed to load printer settings in PrinterManager: %s", e, exc_info=True)
            self._backend = MockPrinterAdapter()

    def set_backend(self, backend: PrinterBackend) -> None:
        """Override active backend directly (used in tests or manual selection)."""
        self._backend = backend

    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        """Delegate receipt printing to active backend."""
        return self._backend.print_receipt(receipt)

    def print_test(self) -> PrintResult:
        """Delegate test print to active backend."""
        return self._backend.print_test()

    def get_status(self) -> PrinterStatus:
        """Get active printer status."""
        return self._backend.get_status()

    def discover_windows_printers(self) -> list[str]:
        """Discover installed Windows printers."""
        return WindowsA4Backend().get_available_printers()
