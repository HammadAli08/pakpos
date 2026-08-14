"""Application Settings stored in database."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pakpos.database.engine import Base


class SettingKey:
    """Well-known keys for application settings."""
    SHOP_NAME = "shop_name"
    SHOP_ADDRESS = "shop_address"
    SHOP_PHONE = "shop_phone"
    RECEIPT_PRINTER = "receipt_printer"
    RECEIPT_FOOTER = "receipt_footer"
    TAX_NUMBER = "tax_number"
    SHOP_LOGO_PATH = "shop_logo_path"

    # Printer configuration
    PRINTER_BACKEND = "printer_backend"         # "thermal_escpos" | "windows_a4" | "pdf" | "mock"
    PRINTER_NAME = "printer_name"               # Windows printer name or ESC/POS name
    PRINTER_TYPE = "printer_type"               # "thermal" | "a4"
    PRINTER_PAPER_WIDTH = "printer_paper_width" # "80" | "58"
    PRINTER_CONNECTION = "printer_connection"   # "usb" | "network" | "windows"
    PRINTER_USB_VENDOR = "printer_usb_vendor"   # Hex string e.g. "0x04b8"
    PRINTER_USB_PRODUCT = "printer_usb_product" # Hex string e.g. "0x0e15"
    PRINTER_NETWORK_HOST = "printer_network_host" # IP e.g. "192.168.1.100"
    PRINTER_NETWORK_PORT = "printer_network_port" # Port e.g. "9100"
    PRINTER_AUTO_CUT = "printer_auto_cut"       # "true" | "false"
    PRINTER_OPEN_DRAWER = "printer_open_drawer" # "true" | "false"
    PRINTER_PRINT_LOGO = "printer_print_logo"   # "true" | "false"
    PRINTER_PRINT_QR = "printer_print_qr"       # "true" | "false"
    PRINTER_COPIES = "printer_copies"           # int e.g. "1"



class Setting(Base):
    """Key-value store for application settings."""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Setting key={self.key!r} value={self.value!r}>"
