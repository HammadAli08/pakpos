"""
Report Service — generates sales, profit, inventory, and customer reports.
All calculations are deterministic database queries — no AI, no guessing.
Clearly distinguishes Revenue from Gross Profit from Net Profit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from pakpos.database.models.sale import Sale, SaleItem, SaleStatus
from pakpos.database.models.purchase import Purchase
from pakpos.database.models.expense import Expense
from pakpos.database.models.product import Product
from pakpos.database.models.customer import Customer
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DailySummary:
    date: datetime
    total_revenue: Decimal
    total_transactions: int
    cash_sales: Decimal
    credit_sales: Decimal
    total_expenses: Decimal
    gross_profit: Decimal


@dataclass
class BusinessInsight:
    category: str  # "low_stock", "sales_trend", "top_product", "outstanding"
    message: str
    severity: str  # "info", "warning", "critical"


class ReportService:
    """Deterministic business reports and insights."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_today_summary(self) -> DailySummary:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
        return self._get_summary_for_range(start, end)

    def _get_summary_for_range(self, start: datetime, end: datetime) -> DailySummary:
        sales = (
            self._session.query(Sale)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .all()
        )
        total_revenue = sum(s.total for s in sales) if sales else Decimal("0")
        cash_sales = sum(s.total for s in sales if s.payment_method == "cash") if sales else Decimal("0")
        credit_sales = sum(s.total for s in sales if s.payment_method == "credit") if sales else Decimal("0")

        expenses = (
            self._session.query(func.coalesce(func.sum(Expense.amount), 0))
            .filter(Expense.created_at >= start, Expense.created_at <= end)
            .scalar()
        )
        total_expenses = Decimal(str(expenses))

        # Gross profit = revenue - COGS (purchase prices)
        cogs = self._calculate_cogs(sales)
        gross_profit = total_revenue - cogs

        return DailySummary(
            date=start,
            total_revenue=Decimal(str(total_revenue)),
            total_transactions=len(sales),
            cash_sales=Decimal(str(cash_sales)),
            credit_sales=Decimal(str(credit_sales)),
            total_expenses=total_expenses,
            gross_profit=gross_profit,
        )

    def _calculate_cogs(self, sales: list[Sale]) -> Decimal:
        """Cost of Goods Sold from sale items."""
        total_cost = Decimal("0")
        for sale in sales:
            for item in sale.items:
                product = item.product
                if product:
                    total_cost += item.quantity * product.purchase_price
        return total_cost

    def get_low_stock_count(self) -> int:
        return (
            self._session.query(Product)
            .filter(
                Product.is_active == True,  # noqa: E712
                Product.current_stock <= Product.minimum_stock,
            )
            .count()
        )

    def get_total_outstanding_khata(self) -> Decimal:
        result = (
            self._session.query(func.coalesce(func.sum(Customer.current_balance), 0))
            .filter(Customer.is_active == True)  # noqa: E712
            .scalar()
        )
        return Decimal(str(result))

    def get_business_insights(self) -> list[BusinessInsight]:
        """Generate deterministic business insights from database."""
        insights: list[BusinessInsight] = []

        # Low stock
        low_stock_count = self.get_low_stock_count()
        if low_stock_count > 0:
            insights.append(BusinessInsight(
                category="low_stock",
                message=f"{low_stock_count} product(s) are below minimum stock level.",
                severity="warning" if low_stock_count < 5 else "critical",
            ))

        # Outstanding Khata
        outstanding = self.get_total_outstanding_khata()
        if outstanding > 0:
            insights.append(BusinessInsight(
                category="outstanding",
                message=f"Total outstanding customer balance: Rs. {outstanding:,.2f}",
                severity="info",
            ))

        # Compare today vs yesterday sales
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
        yest_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
        yest_end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)

        today_rev = self._session.query(
            func.coalesce(func.sum(Sale.total), 0)
        ).filter(Sale.created_at >= today_start, Sale.created_at <= today_end, Sale.status == SaleStatus.COMPLETED).scalar()
        yest_rev = self._session.query(
            func.coalesce(func.sum(Sale.total), 0)
        ).filter(Sale.created_at >= yest_start, Sale.created_at <= yest_end, Sale.status == SaleStatus.COMPLETED).scalar()

        today_rev = Decimal(str(today_rev))
        yest_rev = Decimal(str(yest_rev))
        if yest_rev > 0:
            pct = ((today_rev - yest_rev) / yest_rev * 100).quantize(Decimal("1"))
            direction = "increased" if pct >= 0 else "decreased"
            insights.append(BusinessInsight(
                category="sales_trend",
                message=f"Today's sales {direction} {abs(pct)}% compared to yesterday.",
                severity="info",
            ))

        return insights
