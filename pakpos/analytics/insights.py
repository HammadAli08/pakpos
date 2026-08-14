"""
Insights Engine — Rule-based, deterministic business intelligence generator.
Evaluates authoritative database metrics to produce actionable human-readable insights.
No AI models, no external web APIs, 100% offline and explainable.
"""
from __future__ import annotations

from decimal import Decimal
from pakpos.analytics.metrics import (
    BusinessInsight, KPICardData, TopProductItem, RevenueTrendPoint,
    InventoryHealthData, StockAlertItem
)
from pakpos.utils.formatters import format_currency


class InsightsEngine:
    """Generates deterministic business recommendations and warnings."""

    @staticmethod
    def generate_insights(
        today_rev: Decimal,
        today_profit: Decimal,
        today_tx: int,
        prev_rev: Decimal,
        top_products: list[TopProductItem],
        hourly_trend: list[RevenueTrendPoint],
        khata_total: Decimal,
        khata_count: int,
        inv_health: InventoryHealthData,
        stock_alerts: list[StockAlertItem],
    ) -> list[BusinessInsight]:
        insights: list[BusinessInsight] = []

        # 1. Zero data fallback
        if today_tx == 0 and prev_rev == 0:
            insights.append(
                BusinessInsight(
                    category="sales",
                    message="No sales recorded for the selected period yet.",
                    severity="info",
                )
            )

        # 2. Revenue trend comparison
        if prev_rev > 0:
            pct = float(((today_rev - prev_rev) / prev_rev * 100).quantize(Decimal("0.1")))
            if pct > 20.0:
                insights.append(
                    BusinessInsight(
                        category="sales",
                        message=f"Revenue is significantly higher (+{pct:.1f}%) compared to the previous period.",
                        severity="info",
                    )
                )
            elif pct > 0:
                insights.append(
                    BusinessInsight(
                        category="sales",
                        message=f"Revenue is up {pct:.1f}% compared to the previous period.",
                        severity="info",
                    )
                )
            elif pct < -20.0:
                insights.append(
                    BusinessInsight(
                        category="sales",
                        message=f"Revenue has dropped sharply ({pct:.1f}%) compared to the previous period.",
                        severity="warning",
                    )
                )
            elif pct < 0:
                insights.append(
                    BusinessInsight(
                        category="sales",
                        message=f"Revenue is down {abs(pct):.1f}% compared to the previous period.",
                        severity="warning",
                    )
                )

        # 3. Gross Profit Margin
        if today_rev > 0:
            margin_pct = float((today_profit / today_rev * 100).quantize(Decimal("0.1")))
            if margin_pct >= 25.0:
                insights.append(
                    BusinessInsight(
                        category="margin",
                        message=f"Healthy gross profit margin of {margin_pct:.1f}%.",
                        severity="info",
                    )
                )
            elif margin_pct < 10.0:
                insights.append(
                    BusinessInsight(
                        category="margin",
                        message=f"Low gross profit margin ({margin_pct:.1f}%). Check purchase pricing vs sale prices.",
                        severity="warning",
                    )
                )

        # 4. Top Selling Product
        if top_products:
            top = top_products[0]
            if top.units_sold > 0:
                qty_str = f"{top.units_sold:g}" if top.units_sold == int(top.units_sold) else f"{top.units_sold:.2f}"
                insights.append(
                    BusinessInsight(
                        category="top_product",
                        message=f"Top selling product is '{top.name}' with {qty_str} units sold ({format_currency(top.revenue)}).",
                        severity="info",
                    )
                )

        # 5. Peak Sales Hours
        if hourly_trend:
            active_hours = [p for p in hourly_trend if p.revenue > 0]
            if active_hours:
                sorted_hours = sorted(active_hours, key=lambda p: p.revenue, reverse=True)
                peak = sorted_hours[0]
                insights.append(
                    BusinessInsight(
                        category="trend",
                        message=f"Peak sales activity observed around {peak.label} ({format_currency(peak.revenue)}).",
                        severity="info",
                    )
                )

        # 6. Inventory & Stockout Alerts
        out_of_stock = [s for s in stock_alerts if s.is_out_of_stock]
        low_stock = [s for s in stock_alerts if not s.is_out_of_stock]

        if out_of_stock:
            count = len(out_of_stock)
            names = ", ".join([f"'{item.name}'" for item in out_of_stock[:3]])
            extra = f" (+{count - 3} more)" if count > 3 else ""
            insights.append(
                BusinessInsight(
                    category="inventory",
                    message=f"Critical stockout: {count} product(s) out of stock ({names}{extra}). Restock immediately.",
                    severity="critical",
                )
            )

        if low_stock:
            count = len(low_stock)
            insights.append(
                BusinessInsight(
                    category="inventory",
                    message=f"{count} product(s) are below their minimum stock threshold.",
                    severity="warning" if count < 5 else "critical",
                )
            )

        # 7. Customer Credit / Khata
        if khata_total > 0:
            severity = "warning" if khata_total > Decimal("50000") else "info"
            cust_label = f"across {khata_count} customer(s)" if khata_count > 0 else ""
            insights.append(
                BusinessInsight(
                    category="khata",
                    message=f"Total outstanding customer Khata is {format_currency(khata_total)} {cust_label}.",
                    severity=severity,
                )
            )

        return insights
