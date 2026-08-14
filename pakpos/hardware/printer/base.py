"""
PrinterBase — Abstract base class for all printer adapters.
Sale must be saved BEFORE calling any print method.
A print failure must NEVER roll back a saved sale.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class PrintStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class PrinterStatus(str, Enum):
    READY = "READY"
    OFFLINE = "OFFLINE"
    NOT_FOUND = "NOT_FOUND"
    PAPER_OUT = "PAPER_OUT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class PrinterProfile:
    """Capabilities and parameters for a printer type."""
    columns: int = 48
    char_width_mm: float = 1.5
    has_barcode: bool = True
    has_qr: bool = True
    has_cutter: bool = True
    has_cash_drawer: bool = True


@dataclass
class ReceiptData:
    """DTO containing all data needed to render a receipt."""
    shop_name: str
    shop_address: str
    shop_phone: str
    invoice_number: str
    cashier_name: str
    items: list[dict]          # [{name, qty, unit_price, discount, tax, total}]
    subtotal: float
    discount: float
    tax: float
    total: float
    paid_amount: float
    change: float
    payment_method: str
    customer_name: str | None = None
    footer_message: str = "Thank you for shopping with us!"
    paper_width_mm: int = 80
    created_at: str = ""
    sale_id: int | None = None
    customer_phone: str | None = None
    due_amount: float = 0.0
    qr_payload: str | None = None
    logo_path: str | None = None
    is_reprint: bool = False
    sale_date: str = ""
    sale_time: str = ""
    tax_number: str | None = None

    @property
    def footer(self) -> str:
        return self.footer_message


@dataclass
class PrintResult:
    status: PrintStatus
    message: str = ""
    error: str = ""

    @property
    def success(self) -> bool:
        return self.status == PrintStatus.SUCCESS


class PrinterBase(ABC):
    """Abstract printer — all adapters must implement this interface."""

    @abstractmethod
    def print_receipt(self, receipt: ReceiptData) -> PrintResult:
        """Print a receipt. Must not raise — return PrintResult with status."""
        ...

    @abstractmethod
    def print_test(self) -> PrintResult:
        """Print a test page."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the printer is reachable."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Return human-readable printer name."""
        ...

    def get_status(self) -> PrinterStatus:
        """Return current status of printer."""
        return PrinterStatus.READY if self.is_available() else PrinterStatus.OFFLINE

    def get_profile(self) -> PrinterProfile:
        """Return printer profile capabilities."""
        return PrinterProfile()

    def trigger_cash_drawer(self) -> bool:
        """Trigger cash drawer open if supported. Default no-op."""
        return False


# Alias PrinterBackend to PrinterBase for architecture consistency
PrinterBackend = PrinterBase

