"""
ThermalEscPosBackend — ESC/POS direct printer adapter.
Supports USB and Network/Ethernet thermal receipt printers (80mm & 58mm).
Translates ThermalReceiptRenderer output to hardware ESC/POS commands.
Must never raise — all errors return PrintResult with failure status.
"""
from __future__ import annotations

from pakpos.hardware.printer.base import (
    PrinterBase, PrintResult, PrintStatus, PrinterStatus,
    PrinterProfile, ReceiptData
)
from pakpos.hardware.printer.renderers.thermal_renderer import (
    ThermalReceiptRenderer, LineAlignment, FontSize
)
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class ThermalEscPosBackend(PrinterBase):
    """
    Direct ESC/POS driver for USB and Network POS receipt printers.
    Uses python-escpos for hardware communication.
    """

    def __init__(
        self,
        connection_type: str = "usb",
        vendor_id: int | str = 0x04b8,
        product_id: int | str = 0x0e15,
        host: str = "192.168.1.100",
        port: int = 9100,
        paper_width_mm: int = 80,
        auto_cut: bool = True,
        open_drawer: bool = True,
        profile: PrinterProfile | None = None,
    ) -> None:
        self.connection_type = connection_type.lower()
        if isinstance(vendor_id, str):
            self.vendor_id = int(vendor_id, 16) if vendor_id.startswith("0x") else int(vendor_id)
        else:
            self.vendor_id = vendor_id

        if isinstance(product_id, str):
            self.product_id = int(product_id, 16) if product_id.startswith("0x") else int(product_id)
        else:
            self.product_id = product_id

        self.host = host
        self.port = int(port)
        self.paper_width_mm = paper_width_mm
        self.auto_cut = auto_cut
        self.open_drawer = open_drawer
        self.profile = profile or PrinterProfile(columns=48 if paper_width_mm > 58 else 40)
        self._renderer = ThermalReceiptRenderer(self.profile)

    def _get_printer_device(self):
        """Instantiate python-escpos device object."""
        try:
            import escpos.printer as esc_printer
        except ImportError:
            raise RuntimeError("python-escpos library is not installed")

        if self.connection_type == "usb":
            return esc_printer.Usb(
                idVendor=self.vendor_id,
                idProduct=self.product_id,
                profile="TM-T88IV",
            )
        elif self.connection_type == "network":
            return esc_printer.Network(
                host=self.host,
                port=self.port,
                profile="TM-T88IV",
            )
        else:
            raise ValueError(f"Unsupported ESC/POS connection type: {self.connection_type}")

    def is_available(self) -> bool:
        """Check if printer device can be instantiated/reached."""
        try:
            device = self._get_printer_device()
            if hasattr(device, "close"):
                device.close()
            return True
        except Exception as e:
            logger.debug("ThermalEscPosBackend device unreachable: %s", e)
            return False

    def get_name(self) -> str:
        if self.connection_type == "usb":
            return f"ESC/POS Thermal USB (0x{self.vendor_id:04x}:0x{self.product_id:04x})"
        return f"ESC/POS Network Printer ({self.host}:{self.port})"

    def get_status(self) -> PrinterStatus:
        return PrinterStatus.READY if self.is_available() else PrinterStatus.OFFLINE

    def get_profile(self) -> PrinterProfile:
        return self.profile

    def trigger_cash_drawer(self) -> bool:
        """Pulse cash drawer pin via ESC/POS pin 2/5 command."""
        try:
            device = self._get_printer_device()
            if hasattr(device, "cashdraw"):
                device.cashdraw(2)
                device.cashdraw(5)
            if hasattr(device, "close"):
                device.close()
            return True
        except Exception as e:
            logger.warning("Failed to open cash drawer via ESC/POS: %s", e)
            return False

    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        try:
            device = self._get_printer_device()

            lines = self._renderer.render_lines(receipt)
            width = self._renderer.get_columns(receipt.paper_width_mm)

            for line in lines:
                if line.is_cut:
                    if self.auto_cut and hasattr(device, "cut"):
                        device.cut()
                    continue

                if line.is_separator:
                    device.text("-" * width + "\n")
                    continue

                if line.is_qr and line.qr_data:
                    if hasattr(device, "qr"):
                        device.qr(line.qr_data, size=6)
                    else:
                        device.text(f"[QR: {line.qr_data}]\n")
                    continue

                if line.is_barcode and line.barcode_data:
                    if hasattr(device, "barcode"):
                        device.barcode(line.barcode_data, "CODE39")
                    else:
                        device.text(f"[{line.barcode_data}]\n")
                    continue

                if line.is_logo and line.logo_path:
                    if hasattr(device, "image"):
                        try:
                            device.image(line.logo_path)
                        except Exception:
                            device.text("[LOGO]\n")
                    continue

                align_cmd = line.align.value if hasattr(line.align, "value") else str(line.align)
                bold_cmd = line.bold

                if hasattr(device, "set"):
                    device.set(align=align_cmd, bold=bold_cmd)

                device.text(line.text + "\n")

            if self.open_drawer and receipt.payment_method.lower() == "cash":
                self.trigger_cash_drawer()

            if hasattr(device, "close"):
                device.close()

            return PrintResult(status=PrintStatus.SUCCESS, message=f"Printed receipt {receipt.invoice_number}")

        except Exception as e:
            logger.error("ESC/POS thermal print failed: %s", e, exc_info=True)
            return PrintResult(status=PrintStatus.FAILED, error=f"Thermal print error: {e}")

    def print_test(self) -> PrintResult:
        receipt = ReceiptData(
            shop_name="TEST PAKPOS STORE",
            shop_address="123 Commercial Market, Lahore",
            shop_phone="0300-0000000",
            invoice_number="TEST-9999",
            cashier_name="Admin Test",
            items=[
                {"name": "Thermal Printer Test Item 1", "qty": 2, "unit_price": 150.0, "total": 300.0},
                {"name": "Long Product Name Wrapping Test", "qty": 1, "unit_price": 450.0, "total": 450.0},
            ],
            subtotal=750.0,
            discount=50.0,
            tax=0.0,
            total=700.0,
            paid_amount=1000.0,
            change=300.0,
            payment_method="CASH",
            customer_name="Test Customer",
            footer_message="--- ESC/POS TEST PRINT COMPLETE ---",
            paper_width_mm=self.paper_width_mm,
            qr_payload="PakPOS-TEST-RECEIPT",
        )
        return self.print_receipt(receipt)
