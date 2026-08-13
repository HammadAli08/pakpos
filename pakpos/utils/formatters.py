"""Formatting utilities for currency, dates, and numbers."""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime


def format_currency(amount: Decimal | float | int, symbol: str = "Rs.") -> str:
    """Format amount as Pakistani Rupees."""
    try:
        value = float(amount)
        return f"{symbol} {value:,.2f}"
    except (TypeError, ValueError):
        return f"{symbol} 0.00"


def format_quantity(qty: Decimal | float) -> str:
    """Format quantity — show decimals only if needed."""
    value = float(qty)
    if value == int(value):
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_date(dt: datetime | None, fmt: str = "%d-%b-%Y") -> str:
    if dt is None:
        return ""
    return dt.strftime(fmt)


def format_datetime(dt: datetime | None, fmt: str = "%d-%b-%Y %H:%M") -> str:
    if dt is None:
        return ""
    return dt.strftime(fmt)


def parse_amount(text: str) -> Decimal:
    """Parse a string like '1,234.50' or '1234' to Decimal."""
    cleaned = text.replace(",", "").strip()
    return Decimal(cleaned)
