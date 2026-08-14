"""
Analytics Service — High-level analytics orchestration service with in-memory caching.
Calculates KPI cards, trends, top products, category breakdowns, payment breakdowns,
period-over-period comparison, inventory health, and deterministic insights.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from pakpos.analytics.analytics_repository import AnalyticsRepository
from pakpos.analytics.insights import InsightsEngine
from pakpos.analytics.metrics import (
    DateRangeOption, KPICardData, RevenueTrendPoint, TopProductItem,
    CategoryPerformanceItem, PaymentMethodItem, InventoryHealthData,
    StockAlertItem, PeriodComparison, BusinessInsight,
    DebtorItem, ExpenseCategoryItem,
)
from pakpos.utils.formatters import format_currency
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Business logic for retail POS dashboard analytics."""

    _cache: dict[str, Any] = {}

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = AnalyticsRepository(session)

    @classmethod
    def invalidate_cache(cls) -> None:
        """Clear cached analytics data."""
        cls._cache.clear()

    @staticmethod
    def get_date_range_bounds(
        option: DateRangeOption | str,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> tuple[datetime, datetime, datetime, datetime, str]:
        """
        Returns (curr_start, curr_end, prev_start, prev_end, comparison_label)
        All datetimes are timezone-aware (UTC).
        """
        now = datetime.now(timezone.utc)
        today = now.date()

        if isinstance(option, str):
            try:
                option = DateRangeOption(option)
            except ValueError:
                option = DateRangeOption.TODAY

        if option == DateRangeOption.TODAY:
            curr_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

            yesterday = today - timedelta(days=1)
            prev_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = "vs yesterday"

        elif option == DateRangeOption.YESTERDAY:
            yesterday = today - timedelta(days=1)
            curr_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)

            prev_day = yesterday - timedelta(days=1)
            prev_start = datetime.combine(prev_day, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(prev_day, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = "vs prev day"

        elif option == DateRangeOption.LAST_7_DAYS:
            start_date = today - timedelta(days=6)
            curr_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

            p_end_date = start_date - timedelta(days=1)
            p_start_date = p_end_date - timedelta(days=6)
            prev_start = datetime.combine(p_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(p_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = "vs prev 7 days"

        elif option == DateRangeOption.LAST_30_DAYS:
            start_date = today - timedelta(days=29)
            curr_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

            p_end_date = start_date - timedelta(days=1)
            p_start_date = p_end_date - timedelta(days=29)
            prev_start = datetime.combine(p_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(p_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = "vs prev 30 days"

        elif option == DateRangeOption.THIS_MONTH:
            start_date = today.replace(day=1)
            curr_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

            prev_month_end = start_date - timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1)
            prev_start = datetime.combine(prev_month_start, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(prev_month_end, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = "vs last month"

        elif option == DateRangeOption.CUSTOM and custom_start and custom_end:
            curr_start = datetime.combine(custom_start, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(custom_end, datetime.max.time()).replace(tzinfo=timezone.utc)

            delta_days = (custom_end - custom_start).days + 1
            prev_end_date = custom_start - timedelta(days=1)
            prev_start_date = prev_end_date - timedelta(days=delta_days - 1)
            prev_start = datetime.combine(prev_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(prev_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = f"vs prev {delta_days} days"

        else:  # Fallback to Today
            curr_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            curr_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
            yesterday = today - timedelta(days=1)
            prev_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
            prev_end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)
            label = "vs yesterday"

        return curr_start, curr_end, prev_start, prev_end, label

    def get_kpi_cards(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> list[KPICardData]:
        """
        Returns list of 6 KPI cards for top row:
        1. Revenue
        2. Gross Profit
        3. Transactions
        4. Average Order Value
        5. Outstanding Khata
        6. Low Stock Items
        """
        curr_start, curr_end, prev_start, prev_end, comp_label = self.get_date_range_bounds(
            option, custom_start, custom_end
        )

        c_rev, c_profit, c_tx, c_aov = self._repo.get_revenue_and_profit(curr_start, curr_end)
        p_rev, p_profit, p_tx, p_aov = self._repo.get_revenue_and_profit(prev_start, prev_end)

        # 1. Revenue Card
        r_pct, r_comp, r_pos = self._calculate_comparison(c_rev, p_rev, comp_label)
        card_rev = KPICardData(
            title="REVENUE",
            value_formatted=format_currency(c_rev),
            raw_value=c_rev,
            comparison_text=r_comp,
            change_pct=r_pct,
            is_positive=r_pos,
        )

        # 2. Gross Profit Card
        p_pct, p_comp, p_pos = self._calculate_comparison(c_profit, p_profit, comp_label)
        card_profit = KPICardData(
            title="GROSS PROFIT",
            value_formatted=format_currency(c_profit),
            raw_value=c_profit,
            comparison_text=p_comp,
            change_pct=p_pct,
            is_positive=p_pos,
        )

        # 3. Transactions Card
        t_pct, t_comp, t_pos = self._calculate_comparison(Decimal(c_tx), Decimal(p_tx), comp_label)
        card_tx = KPICardData(
            title="TRANSACTIONS",
            value_formatted=str(c_tx),
            raw_value=c_tx,
            comparison_text=t_comp,
            change_pct=t_pct,
            is_positive=t_pos,
        )

        # 4. Average Order Value Card
        a_pct, a_comp, a_pos = self._calculate_comparison(c_aov, p_aov, comp_label)
        card_aov = KPICardData(
            title="AVG ORDER VALUE",
            value_formatted=format_currency(c_aov),
            raw_value=c_aov,
            comparison_text=a_comp,
            change_pct=a_pct,
            is_positive=a_pos,
        )

        # 5. Outstanding Khata Card
        khata_total, debtor_count = self._repo.get_khata_summary()
        card_khata = KPICardData(
            title="OUTSTANDING KHATA",
            value_formatted=format_currency(khata_total),
            raw_value=khata_total,
            comparison_text=f"{debtor_count} customer(s)" if debtor_count > 0 else "0 debtors",
            change_pct=None,
            is_positive=False if khata_total > 0 else True,
        )

        # 6. Low Stock Card
        inv_health = self._repo.get_inventory_health()
        low_total = inv_health.low_stock_count + inv_health.out_of_stock_count
        card_low_stock = KPICardData(
            title="LOW / OUT OF STOCK",
            value_formatted=str(low_total),
            raw_value=low_total,
            comparison_text=f"{inv_health.out_of_stock_count} critical out-of-stock",
            change_pct=None,
            is_positive=True if low_total == 0 else False,
        )

        return [card_rev, card_profit, card_tx, card_aov, card_khata, card_low_stock]

    def get_revenue_trend(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> list[RevenueTrendPoint]:
        """
        Returns trend data points.
        For TODAY or YESTERDAY → hourly granularity.
        Otherwise → daily granularity.
        """
        curr_start, curr_end, _, _, _ = self.get_date_range_bounds(
            option, custom_start, custom_end
        )

        if option in (DateRangeOption.TODAY, DateRangeOption.YESTERDAY):
            target_date = curr_start.date()
            return self._repo.get_hourly_trend(target_date)

        return self._repo.get_daily_trend(curr_start, curr_end)

    def get_top_products(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
        limit: int = 5,
        sort_by: str = "units",
    ) -> list[TopProductItem]:
        curr_start, curr_end, _, _, _ = self.get_date_range_bounds(
            option, custom_start, custom_end
        )
        return self._repo.get_top_products(curr_start, curr_end, limit=limit, sort_by=sort_by)

    def get_category_performance(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> list[CategoryPerformanceItem]:
        curr_start, curr_end, _, _, _ = self.get_date_range_bounds(
            option, custom_start, custom_end
        )
        return self._repo.get_category_performance(curr_start, curr_end)

    def get_payment_breakdown(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> list[PaymentMethodItem]:
        curr_start, curr_end, _, _, _ = self.get_date_range_bounds(
            option, custom_start, custom_end
        )
        return self._repo.get_payment_breakdown(curr_start, curr_end)

    def get_inventory_health(self) -> InventoryHealthData:
        return self._repo.get_inventory_health()

    def get_stock_alerts(self, limit: int = 10) -> list[StockAlertItem]:
        return self._repo.get_stock_alerts(limit=limit)

    def get_top_debtors(self, limit: int = 6) -> list[DebtorItem]:
        """Returns customers with outstanding balances, ordered by amount (highest first)."""
        return self._repo.get_top_debtors(limit=limit)

    def get_expense_total(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start=None,
        custom_end=None,
    ) -> Decimal:
        """Returns total expenses for the given date range."""
        curr_start, curr_end, _, _, _ = self.get_date_range_bounds(option, custom_start, custom_end)
        return self._repo.get_expense_total(curr_start, curr_end)

    def get_expense_by_category(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start=None,
        custom_end=None,
    ) -> list[ExpenseCategoryItem]:
        """Returns expenses grouped by category for the given date range."""
        curr_start, curr_end, _, _, _ = self.get_date_range_bounds(option, custom_start, custom_end)
        return self._repo.get_expense_by_category(curr_start, curr_end)

    def get_period_comparison(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> PeriodComparison:
        curr_start, curr_end, prev_start, prev_end, comp_label = self.get_date_range_bounds(
            option, custom_start, custom_end
        )

        c_rev, c_profit, c_tx, c_aov = self._repo.get_revenue_and_profit(curr_start, curr_end)
        p_rev, p_profit, p_tx, p_aov = self._repo.get_revenue_and_profit(prev_start, prev_end)

        r_pct, _, _ = self._calculate_comparison(c_rev, p_rev, comp_label)
        p_pct, _, _ = self._calculate_comparison(c_profit, p_profit, comp_label)
        t_pct, _, _ = self._calculate_comparison(Decimal(c_tx), Decimal(p_tx), comp_label)
        a_pct, _, _ = self._calculate_comparison(c_aov, p_aov, comp_label)

        return PeriodComparison(
            label=comp_label,
            curr_revenue=c_rev,
            prev_revenue=p_rev,
            revenue_pct=r_pct,
            curr_profit=c_profit,
            prev_profit=p_profit,
            profit_pct=p_pct,
            curr_tx=c_tx,
            prev_tx=p_tx,
            tx_pct=t_pct,
            curr_aov=c_aov,
            prev_aov=p_aov,
            aov_pct=a_pct,
        )

    def get_insights(
        self,
        option: DateRangeOption | str = DateRangeOption.TODAY,
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> list[BusinessInsight]:
        curr_start, curr_end, prev_start, prev_end, _ = self.get_date_range_bounds(
            option, custom_start, custom_end
        )

        c_rev, c_profit, c_tx, _ = self._repo.get_revenue_and_profit(curr_start, curr_end)
        p_rev, _, _, _ = self._repo.get_revenue_and_profit(prev_start, prev_end)

        top_products = self._repo.get_top_products(curr_start, curr_end, limit=3)
        hourly_trend = self.get_revenue_trend(option, custom_start, custom_end)
        khata_total, khata_count = self._repo.get_khata_summary()
        inv_health = self._repo.get_inventory_health()
        stock_alerts = self._repo.get_stock_alerts(limit=10)

        return InsightsEngine.generate_insights(
            today_rev=c_rev,
            today_profit=c_profit,
            today_tx=c_tx,
            prev_rev=p_rev,
            top_products=top_products,
            hourly_trend=hourly_trend,
            khata_total=khata_total,
            khata_count=khata_count,
            inv_health=inv_health,
            stock_alerts=stock_alerts,
        )

    @staticmethod
    def _calculate_comparison(
        curr: Decimal, prev: Decimal, comp_label: str
    ) -> tuple[float | None, str, bool | None]:
        """
        Calculates mathematically correct percentage difference without infinity.
        """
        if prev == Decimal("0"):
            if curr == Decimal("0"):
                return None, "No sales", None
            return None, "No prev sales", True

        pct = float(((curr - prev) / prev * 100).quantize(Decimal("0.1")))
        if pct > 0:
            return pct, f"↑ {pct:.1f}% {comp_label}", True
        elif pct < 0:
            return pct, f"↓ {abs(pct):.1f}% {comp_label}", False
        else:
            return 0.0, f"→ 0.0% {comp_label}", None
