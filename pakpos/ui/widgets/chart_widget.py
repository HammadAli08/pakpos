"""
Chart Container & QtCharts Builders — Native PySide6 QtCharts rendering components.
Supports 5 chart types: Area/Line trend, Grouped bar, Horizontal bar, Donut chart x2.
Includes built-in empty state overlays and dark professional styling.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from PySide6.QtCore import Qt, QPointF, QMargins
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QStackedLayout, QWidget
)
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QAreaSeries, QBarSeries, QBarSet,
    QHorizontalBarSeries, QPieSeries, QPieSlice, QBarCategoryAxis, QValueAxis
)

from pakpos.analytics.metrics import (
    RevenueTrendPoint, TopProductItem, CategoryPerformanceItem, PaymentMethodItem
)
from pakpos.utils.formatters import format_currency


class ChartContainer(QFrame):
    """Container frame wrapping a QtChartView with title and empty-state overlay."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet("""
            QFrame#card {
                background-color: #22252c;
                border: 1px solid #2d3139;
                border-radius: 10px;
            }
        """)
        self._setup_ui(title)

    def _setup_ui(self, title: str) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # Header Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #e8eaed;")
        main_layout.addWidget(self.lbl_title)

        # Stacked layout for chart vs empty state
        self.stack_widget = QWidget()
        self.stack_layout = QStackedLayout(self.stack_widget)

        # Chart View
        self.chart = QChart()
        self._style_chart(self.chart)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setStyleSheet("background: transparent;")

        # Empty state widget
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_empty = QLabel("No sales data available for this range.")
        self.lbl_empty.setStyleSheet("color: #6b7280; font-size: 13px; font-weight: 500;")
        self.lbl_empty_sub = QLabel("Complete transactions to view performance charts.")
        self.lbl_empty_sub.setStyleSheet("color: #4b5563; font-size: 11px;")

        empty_layout.addWidget(self.lbl_empty, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_sub, 0, Qt.AlignmentFlag.AlignCenter)

        self.stack_layout.addWidget(self.chart_view)   # index 0
        self.stack_layout.addWidget(self.empty_widget)  # index 1

        main_layout.addWidget(self.stack_widget, 1)

    def _style_chart(self, chart: QChart) -> None:
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))
        chart.legend().setVisible(False)

    def show_empty_state(self, is_empty: bool = True) -> None:
        if is_empty:
            self.stack_layout.setCurrentIndex(1)
        else:
            self.stack_layout.setCurrentIndex(0)


# ─────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────

def build_revenue_trend_chart(
    chart: QChart, points: list[RevenueTrendPoint]
) -> bool:
    """Builds an Area/Line Revenue Trend Chart."""
    chart.removeAllSeries()
    for axis in chart.axes():
        chart.removeAxis(axis)

    has_data = any(p.revenue > 0 for p in points)
    if not points or not has_data:
        return False

    upper_series = QLineSeries()
    lower_series = QLineSeries()

    max_rev = Decimal("0")
    categories: list[str] = []

    for idx, pt in enumerate(points):
        upper_series.append(idx, float(pt.revenue))
        lower_series.append(idx, 0)
        categories.append(pt.label)
        if pt.revenue > max_rev:
            max_rev = pt.revenue

    area_series = QAreaSeries(upper_series, lower_series)
    area_series._upper = upper_series
    area_series._lower = lower_series
    area_series.setPen(QPen(QColor("#2d6cdf"), 2))
    
    grad = QBrush(QColor(45, 108, 223, 70))
    area_series.setBrush(grad)

    chart.addSeries(area_series)

    # X Axis (Categories or step numbers)
    axis_x = QBarCategoryAxis()
    axis_x.append(categories)
    axis_x.setLabelsColor(QColor("#9ca3af"))
    axis_x.setGridLineColor(QColor("#2d3139"))
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    area_series.attachAxis(axis_x)

    # Y Axis (Revenue PKR)
    axis_y = QValueAxis()
    max_val = float(max_rev) * 1.15 if max_rev > 0 else 100
    axis_y.setRange(0, max_val)
    axis_y.setLabelsColor(QColor("#9ca3af"))
    axis_y.setGridLineColor(QColor("#2d3139"))
    axis_y.setLabelFormat("Rs. %.0f")
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    area_series.attachAxis(axis_y)

    return True


def build_revenue_vs_profit_chart(
    chart: QChart, points: list[RevenueTrendPoint]
) -> bool:
    """Builds Grouped Bar Chart comparing Revenue vs Gross Profit."""
    chart.removeAllSeries()
    for axis in chart.axes():
        chart.removeAxis(axis)

    has_data = any(p.revenue > 0 for p in points)
    if not points or not has_data:
        return False

    set_rev = QBarSet("Revenue")
    set_rev.setColor(QColor("#2d6cdf"))
    
    set_profit = QBarSet("Gross Profit")
    set_profit.setColor(QColor("#20c997"))

    categories: list[str] = []
    max_val = Decimal("0")

    for pt in points:
        set_rev.append(float(pt.revenue))
        set_profit.append(float(pt.profit))
        categories.append(pt.label)
        max_val = max(max_val, pt.revenue, pt.profit)

    series = QBarSeries()
    series.append(set_rev)
    series.append(set_profit)
    chart.addSeries(series)

    # X Axis
    axis_x = QBarCategoryAxis()
    axis_x.append(categories)
    axis_x.setLabelsColor(QColor("#9ca3af"))
    axis_x.setGridLineColor(QColor("#2d3139"))
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    # Y Axis
    axis_y = QValueAxis()
    axis_y.setRange(0, float(max_val) * 1.15 if max_val > 0 else 100)
    axis_y.setLabelsColor(QColor("#9ca3af"))
    axis_y.setGridLineColor(QColor("#2d3139"))
    axis_y.setLabelFormat("Rs. %.0f")
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    # Legend
    chart.legend().setVisible(True)
    chart.legend().setLabelColor(QColor("#e8eaed"))
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)

    return True


def build_top_products_chart(
    chart: QChart, products: list[TopProductItem], metric: str = "units"
) -> bool:
    """Builds Horizontal Bar Chart for Top Selling Products."""
    chart.removeAllSeries()
    for axis in chart.axes():
        chart.removeAxis(axis)

    if not products or not any(p.units_sold > 0 or p.revenue > 0 for p in products):
        return False

    bar_set = QBarSet("Sales")
    bar_set.setColor(QColor("#2d6cdf"))

    categories: list[str] = []
    max_val = 0.0

    # Reverse order so top item appears at top of Y-axis
    for p in reversed(products):
        val = float(p.revenue if metric == "revenue" else (p.profit if metric == "profit" else p.units_sold))
        bar_set.append(val)
        categories.append(p.name[:20] + "..." if len(p.name) > 22 else p.name)
        if val > max_val:
            max_val = val

    series = QHorizontalBarSeries()
    series.append(bar_set)
    chart.addSeries(series)

    # Y Axis (Product Names)
    axis_y = QBarCategoryAxis()
    axis_y.append(categories)
    axis_y.setLabelsColor(QColor("#e8eaed"))
    axis_y.setGridLineColor(QColor("#2d3139"))
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    # X Axis (Quantity or PKR)
    axis_x = QValueAxis()
    axis_x.setRange(0, max_val * 1.15 if max_val > 0 else 10)
    axis_x.setLabelsColor(QColor("#9ca3af"))
    axis_x.setGridLineColor(QColor("#2d3139"))
    if metric in ("revenue", "profit"):
        axis_x.setLabelFormat("Rs. %.0f")
    else:
        axis_x.setLabelFormat("%.0f")
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    return True


def build_donut_chart(
    chart: QChart, items: list[CategoryPerformanceItem] | list[PaymentMethodItem], title: str = ""
) -> bool:
    """Builds a Donut Chart for Categories or Payment Methods."""
    chart.removeAllSeries()

    if not items or not any(getattr(i, "revenue", getattr(i, "amount", Decimal("0"))) > 0 for i in items):
        return False

    series = QPieSeries()
    series.setHoleSize(0.45)  # Make it a donut chart

    colors = [
        QColor("#2d6cdf"), QColor("#20c997"), QColor("#d97706"),
        QColor("#e83e8c"), QColor("#6f42c1"), QColor("#17a2b8")
    ]

    for idx, item in enumerate(items):
        name = getattr(item, "category_name", getattr(item, "label", "Item"))
        val = float(getattr(item, "revenue", getattr(item, "amount", Decimal("0"))))
        pct = getattr(item, "percentage", 0.0)

        if val > 0:
            slice_item = series.append(f"{name} ({pct:.1f}%)", val)
            color = colors[idx % len(colors)]
            slice_item.setColor(color)
            slice_item.setLabelColor(QColor("#e8eaed"))
            slice_item.setLabelVisible(True)

    chart.addSeries(series)
    chart.legend().setVisible(True)
    chart.legend().setLabelColor(QColor("#9ca3af"))
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)

    return True
