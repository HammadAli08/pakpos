"""
Analytics Repository — High-performance aggregated database queries for business analytics.
Uses SQLAlchemy aggregations for fast offline performance.
Excludes voided, cancelled, or held transactions.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, case, and_, or_, cast, Integer, Date
from sqlalchemy.orm import Session

from pakpos.database.models.sale import Sale, SaleItem, SaleStatus, PaymentMethod
from pakpos.database.models.product import Product
from pakpos.database.models.category import Category
from pakpos.database.models.customer import Customer
from pakpos.database.models.expense import Expense
from pakpos.analytics.metrics import (
    RevenueTrendPoint, TopProductItem, CategoryPerformanceItem,
    PaymentMethodItem, InventoryHealthData, StockAlertItem,
    DebtorItem, ExpenseCategoryItem,
)
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsRepository:
    """Data access layer for analytical summaries and aggregations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_revenue_and_profit(
        self, start: datetime, end: datetime
    ) -> tuple[Decimal, Decimal, int, Decimal]:
        """
        Returns (total_revenue, gross_profit, transaction_count, avg_order_value)
        for completed sales in the given timezone-aware datetime range.
        """
        # Query total revenue & count
        sales_stats = (
            self._session.query(
                func.coalesce(func.sum(Sale.total), 0).label("revenue"),
                func.count(Sale.id).label("tx_count"),
            )
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .first()
        )

        total_revenue = Decimal(str(sales_stats.revenue or 0)) if sales_stats else Decimal("0")
        tx_count = int(sales_stats.tx_count or 0) if sales_stats else 0
        avg_order = (total_revenue / Decimal(tx_count)) if tx_count > 0 else Decimal("0")

        # Query Cost of Goods Sold (COGS)
        cogs_result = (
            self._session.query(
                func.coalesce(
                    func.sum(SaleItem.quantity * Product.purchase_price), 0
                ).label("cogs")
            )
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .scalar()
        )

        cogs = Decimal(str(cogs_result or 0))
        gross_profit = total_revenue - cogs

        return total_revenue, gross_profit, tx_count, avg_order

    def get_hourly_trend(self, target_date: date) -> list[RevenueTrendPoint]:
        """
        Calculates hourly revenue, gross profit, and transactions for a single day (00:00 - 23:59).
        """
        start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Build hour map (0 to 23)
        hourly_data: dict[int, dict] = {
            h: {"revenue": Decimal("0"), "cogs": Decimal("0"), "count": 0} for h in range(24)
        }

        # Query sales per hour
        # SQLite strftime('%H', created_at) returns '00'..'23'
        hour_expr = func.strftime("%H", Sale.created_at)

        sale_rows = (
            self._session.query(
                hour_expr.label("hour_str"),
                func.sum(Sale.total).label("revenue"),
                func.count(Sale.id).label("tx_count"),
            )
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(hour_expr)
            .all()
        )

        for row in sale_rows:
            if row.hour_str is not None:
                h = int(row.hour_str)
                hourly_data[h]["revenue"] = Decimal(str(row.revenue or 0))
                hourly_data[h]["count"] = int(row.tx_count or 0)

        # Query COGS per hour
        cogs_rows = (
            self._session.query(
                hour_expr.label("hour_str"),
                func.sum(SaleItem.quantity * Product.purchase_price).label("cogs"),
            )
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(hour_expr)
            .all()
        )

        for row in cogs_rows:
            if row.hour_str is not None:
                h = int(row.hour_str)
                hourly_data[h]["cogs"] = Decimal(str(row.cogs or 0))

        points: list[RevenueTrendPoint] = []
        for h in range(24):
            rev = hourly_data[h]["revenue"]
            profit = rev - hourly_data[h]["cogs"]
            tx = hourly_data[h]["count"]

            # Format hour label (e.g. 9 AM, 1 PM)
            hour_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=h, tzinfo=timezone.utc)
            label = hour_dt.strftime("%I %p").lstrip("0")

            points.append(
                RevenueTrendPoint(
                    label=label,
                    timestamp=hour_dt,
                    revenue=rev,
                    profit=profit,
                    transactions=tx,
                )
            )

        return points

    def get_daily_trend(self, start: datetime, end: datetime) -> list[RevenueTrendPoint]:
        """
        Calculates daily revenue, profit, and transaction count for a multi-day range.
        """
        date_expr = func.strftime("%Y-%m-%d", Sale.created_at)

        # Daily sales
        sale_rows = (
            self._session.query(
                date_expr.label("date_str"),
                func.sum(Sale.total).label("revenue"),
                func.count(Sale.id).label("tx_count"),
            )
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(date_expr)
            .all()
        )

        daily_sales = {
            r.date_str: (Decimal(str(r.revenue or 0)), int(r.tx_count or 0)) for r in sale_rows if r.date_str
        }

        # Daily COGS
        cogs_rows = (
            self._session.query(
                date_expr.label("date_str"),
                func.sum(SaleItem.quantity * Product.purchase_price).label("cogs"),
            )
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(date_expr)
            .all()
        )

        daily_cogs = {r.date_str: Decimal(str(r.cogs or 0)) for r in cogs_rows if r.date_str}

        # Build dense daily sequence for all dates between start and end
        current = start.date()
        end_date = end.date()
        points: list[RevenueTrendPoint] = []

        while current <= end_date:
            d_str = current.strftime("%Y-%m-%d")
            rev, tx = daily_sales.get(d_str, (Decimal("0"), 0))
            cogs = daily_cogs.get(d_str, Decimal("0"))
            profit = rev - cogs
            dt_val = datetime.combine(current, datetime.min.time()).replace(tzinfo=timezone.utc)
            label = current.strftime("%d %b")

            points.append(
                RevenueTrendPoint(
                    label=label,
                    timestamp=dt_val,
                    revenue=rev,
                    profit=profit,
                    transactions=tx,
                )
            )
            current += timedelta(days=1)

        return points

    def get_top_products(
        self,
        start: datetime,
        end: datetime,
        limit: int = 5,
        sort_by: Literal["units", "revenue", "profit"] = "units",
    ) -> list[TopProductItem]:
        """
        Top performing products sorted by units, revenue, or gross profit.
        """
        cogs_expr = SaleItem.quantity * Product.purchase_price
        profit_expr = SaleItem.total - cogs_expr

        rows = (
            self._session.query(
                Product.id.label("product_id"),
                Product.name.label("name"),
                func.sum(SaleItem.quantity).label("units_sold"),
                func.sum(SaleItem.total).label("revenue"),
                func.sum(profit_expr).label("profit"),
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Product.id, Product.name)
        )

        if sort_by == "revenue":
            rows = rows.order_by(func.sum(SaleItem.total).desc())
        elif sort_by == "profit":
            rows = rows.order_by(func.sum(profit_expr).desc())
        else:
            rows = rows.order_by(func.sum(SaleItem.quantity).desc())

        result_rows = rows.limit(limit).all()

        return [
            TopProductItem(
                product_id=r.product_id,
                name=r.name,
                units_sold=Decimal(str(r.units_sold or 0)),
                revenue=Decimal(str(r.revenue or 0)),
                profit=Decimal(str(r.profit or 0)),
            )
            for r in result_rows
        ]

    def get_category_performance(
        self, start: datetime, end: datetime
    ) -> list[CategoryPerformanceItem]:
        """
        Returns revenue and units sold per product category.
        """
        rows = (
            self._session.query(
                Category.id.label("cat_id"),
                func.coalesce(Category.name, "Uncategorized").label("cat_name"),
                func.sum(SaleItem.total).label("revenue"),
                func.sum(SaleItem.quantity).label("units_sold"),
            )
            .join(Product, SaleItem.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Category.id, Category.name)
            .order_by(func.sum(SaleItem.total).desc())
            .all()
        )

        total_rev = sum(Decimal(str(r.revenue or 0)) for r in rows)

        items: list[CategoryPerformanceItem] = []
        for r in rows:
            rev = Decimal(str(r.revenue or 0))
            pct = float((rev / total_rev * 100).quantize(Decimal("0.1"))) if total_rev > 0 else 0.0
            items.append(
                CategoryPerformanceItem(
                    category_id=r.cat_id,
                    category_name=r.cat_name,
                    revenue=rev,
                    units_sold=Decimal(str(r.units_sold or 0)),
                    percentage=pct,
                )
            )

        return items

    def get_payment_breakdown(
        self, start: datetime, end: datetime
    ) -> list[PaymentMethodItem]:
        """
        Returns payment breakdown by payment method for completed sales.
        """
        rows = (
            self._session.query(
                Sale.payment_method,
                func.sum(Sale.total).label("amount"),
                func.count(Sale.id).label("tx_count"),
            )
            .filter(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Sale.payment_method)
            .all()
        )

        total_amt = sum(Decimal(str(r.amount or 0)) for r in rows)

        labels_map = {
            PaymentMethod.CASH.value: "Cash",
            PaymentMethod.CREDIT.value: "Credit / Khata",
            PaymentMethod.CARD.value: "Card",
            PaymentMethod.BANK.value: "Bank Transfer",
            PaymentMethod.OTHER.value: "Other",
            PaymentMethod.MIXED.value: "Mixed",
        }

        items: list[PaymentMethodItem] = []
        for r in rows:
            amt = Decimal(str(r.amount or 0))
            pct = float((amt / total_amt * 100).quantize(Decimal("0.1"))) if total_amt > 0 else 0.0
            method_code = r.payment_method or "cash"
            label = labels_map.get(method_code, method_code.capitalize())

            items.append(
                PaymentMethodItem(
                    method_code=method_code,
                    label=label,
                    amount=amt,
                    count=int(r.tx_count or 0),
                    percentage=pct,
                )
            )

        return items

    def get_inventory_health(self) -> InventoryHealthData:
        """
        Calculates inventory counts and valuation (cost & retail).
        """
        products = (
            self._session.query(Product)
            .filter(Product.is_active == True)  # noqa: E712
            .all()
        )

        total = len(products)
        healthy = 0
        low = 0
        out = 0

        cost_val = Decimal("0")
        retail_val = Decimal("0")

        for p in products:
            qty = Decimal(str(p.current_stock or 0))
            min_stock = Decimal(str(p.minimum_stock or 0))
            p_price = Decimal(str(p.purchase_price or 0))
            s_price = Decimal(str(p.sale_price or 0))

            if qty <= 0:
                out += 1
            elif qty <= min_stock:
                low += 1
            else:
                healthy += 1

            if qty > 0:
                cost_val += qty * p_price
                retail_val += qty * s_price

        potential_margin = retail_val - cost_val

        return InventoryHealthData(
            total_products=total,
            healthy_count=healthy,
            low_stock_count=low,
            out_of_stock_count=out,
            stock_cost_value=cost_val,
            stock_retail_value=retail_val,
            potential_margin=potential_margin,
        )

    def get_stock_alerts(self, limit: int = 10) -> list[StockAlertItem]:
        """
        Returns list of low stock or out-of-stock active products.
        """
        products = (
            self._session.query(Product)
            .filter(
                Product.is_active == True,  # noqa: E712
                Product.current_stock <= Product.minimum_stock,
            )
            .order_by(Product.current_stock.asc())
            .limit(limit)
            .all()
        )

        return [
            StockAlertItem(
                product_id=p.id,
                name=p.name,
                current_stock=Decimal(str(p.current_stock or 0)),
                minimum_stock=Decimal(str(p.minimum_stock or 0)),
                unit=p.unit or "piece",
                is_out_of_stock=Decimal(str(p.current_stock or 0)) <= 0,
            )
            for p in products
        ]

    def get_khata_summary(self) -> tuple[Decimal, int]:
        """
        Returns (total_outstanding_khata, debtor_customer_count)
        """
        row = (
            self._session.query(
                func.coalesce(func.sum(Customer.current_balance), 0).label("total"),
                func.count(Customer.id).label("count"),
            )
            .filter(
                Customer.is_active == True,  # noqa: E712
                Customer.current_balance > 0,
            )
            .first()
        )

        total = Decimal(str(row.total or 0)) if row else Decimal("0")
        count = int(row.count or 0) if row else 0

        return total, count

    def get_top_debtors(self, limit: int = 6) -> list[DebtorItem]:
        """
        Returns the top customers with outstanding credit balances, ordered
        by balance descending. Used for the Udhaar list on the dashboard.
        """
        customers = (
            self._session.query(Customer)
            .filter(
                Customer.is_active == True,  # noqa: E712
                Customer.current_balance > 0,
            )
            .order_by(Customer.current_balance.desc())
            .limit(limit)
            .all()
        )
        return [
            DebtorItem(
                customer_id=c.id,
                name=c.name,
                balance=Decimal(str(c.current_balance or 0)),
            )
            for c in customers
        ]

    def get_expense_total(
        self, start: datetime, end: datetime
    ) -> Decimal:
        """
        Returns the total amount of expenses recorded between start and end.
        """
        result = (
            self._session.query(
                func.coalesce(func.sum(Expense.amount), 0)
            )
            .filter(
                Expense.created_at >= start,
                Expense.created_at <= end,
            )
            .scalar()
        )
        return Decimal(str(result or 0))

    def get_expense_by_category(
        self, start: datetime, end: datetime
    ) -> list[ExpenseCategoryItem]:
        """
        Returns expense totals grouped by category for the given date range.
        """
        rows = (
            self._session.query(
                Expense.category,
                func.sum(Expense.amount).label("cat_total"),
            )
            .filter(
                Expense.created_at >= start,
                Expense.created_at <= end,
            )
            .group_by(Expense.category)
            .all()
        )
        return [
            ExpenseCategoryItem(
                category=r.category or "عام خرچہ",
                total=Decimal(str(r.cat_total or 0)),
            )
            for r in rows
        ]
