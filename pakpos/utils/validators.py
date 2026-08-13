"""Input validation utilities — enforced at service layer."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re


class ValidationError(Exception):
    """Raised when input data fails validation."""
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_price(value: Decimal | float | str, field: str = "price") -> Decimal:
    """Price or monetary amount must be >= 0."""
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(field, "Must be a valid number")
    if d < 0:
        raise ValidationError(field, "Cannot be negative")
    return d


validate_amount = validate_price  # Alias for general monetary amounts


def validate_quantity(value: Decimal | float | str, field: str = "quantity") -> Decimal:
    """Quantity must be > 0."""
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(field, "Must be a valid number")
    if d <= 0:
        raise ValidationError(field, "Must be greater than zero")
    return d


def validate_discount(discount: Decimal, total: Decimal) -> Decimal:
    """Discount cannot exceed the total."""
    if discount < 0:
        raise ValidationError("discount", "Cannot be negative")
    if discount > total:
        raise ValidationError("discount", "Cannot exceed the total amount")
    return discount


def validate_barcode(barcode: str | None) -> str | None:
    if barcode is None or barcode.strip() == "":
        return None
    cleaned = barcode.strip()
    if len(cleaned) > 100:
        raise ValidationError("barcode", "Too long (max 100 characters)")
    return cleaned


def validate_phone(phone: str | None) -> str | None:
    if phone is None or phone.strip() == "":
        return None
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if len(cleaned) > 20:
        raise ValidationError("phone", "Too long")
    return cleaned


def validate_name(name: str, field: str = "name", max_len: int = 200) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValidationError(field, "Cannot be empty")
    if len(stripped) > max_len:
        raise ValidationError(field, f"Too long (max {max_len} characters)")
    return stripped


def validate_tax_rate(rate: Decimal) -> Decimal:
    if rate < 0 or rate > 100:
        raise ValidationError("tax_rate", "Must be between 0 and 100")
    return rate
