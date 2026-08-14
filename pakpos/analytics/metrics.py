"""
Metrics DTOs for PakPOS Analytics Dashboard.
Data Transfer Objects used between Analytics Repository, Service, and UI layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class DateRangeOption(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    THIS_MONTH = "this_month"
    CUSTOM = "custom"


@dataclass
class KPICardData:
    title: str
    value_formatted: str
    raw_value: Decimal | int
    comparison_text: str = ""  # e.g., "vs yesterday" or "vs prev 7 days"
    change_pct: float | None = None  # float percentage (e.g. 18.4) or None if no comparison
    is_positive: bool | None = None  # True if positive, False if negative, None if neutral
    subtitle: str = ""  # e.g. "3 customers" or "2 critical"


@dataclass
class RevenueTrendPoint:
    label: str  # e.g. "09:00 AM" or "14 Aug"
    timestamp: datetime | None
    revenue: Decimal
    profit: Decimal
    transactions: int


@dataclass
class TopProductItem:
    product_id: int
    name: str
    units_sold: Decimal
    revenue: Decimal
    profit: Decimal


@dataclass
class CategoryPerformanceItem:
    category_id: int | None
    category_name: str
    revenue: Decimal
    units_sold: Decimal
    percentage: float = 0.0


@dataclass
class PaymentMethodItem:
    method_code: str  # e.g. "cash", "credit"
    label: str  # e.g. "Cash", "Credit / Khata"
    amount: Decimal
    count: int
    percentage: float = 0.0


@dataclass
class InventoryHealthData:
    total_products: int = 0
    healthy_count: int = 0
    low_stock_count: int = 0
    out_of_stock_count: int = 0
    stock_cost_value: Decimal = Decimal("0")
    stock_retail_value: Decimal = Decimal("0")
    potential_margin: Decimal = Decimal("0")


@dataclass
class StockAlertItem:
    product_id: int
    name: str
    current_stock: Decimal
    minimum_stock: Decimal
    unit: str
    is_out_of_stock: bool = False


@dataclass
class PeriodComparison:
    label: str  # e.g. "Today vs Yesterday"
    curr_revenue: Decimal
    prev_revenue: Decimal
    revenue_pct: float | None
    curr_profit: Decimal
    prev_profit: Decimal
    profit_pct: float | None
    curr_tx: int
    prev_tx: int
    tx_pct: float | None
    curr_aov: Decimal
    prev_aov: Decimal
    aov_pct: float | None


@dataclass
class DebtorItem:
    """A customer who has an outstanding credit balance (ادھار)."""
    customer_id: int
    name: str
    balance: Decimal


@dataclass
class ExpenseCategoryItem:
    """Total expenses grouped by category for the expense breakdown list."""
    category: str
    total: Decimal


@dataclass
class BusinessInsight:
    category: str  # "sales", "inventory", "khata", "margin", "trend"
    message: str
    severity: str = "info"  # "info", "warning", "critical"
