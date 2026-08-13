"""
PrinterBase — Abstract base class for all printer adapters.
Sale must be saved BEFORE calling any print method.
A print failure must NEVER roll back a saved sale.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class PrintStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass
class ReceiptData:
    """DTO containing all data needed to render a receipt."""
    shop_name: str
    shop_address: str
    shop_phone: str
    invoice_number: str
    cashier_name: str
    items: list[dict]          # [{name, qty, unit_price, total}]
    subtotal: float
    discount: float
    tax: float
    total: float
    paid_amount: float
    change: float
    payment_method: str
    customer_name: str | None
    footer_message: str
    paper_width_mm: int = 80
    created_at: str = ""


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
