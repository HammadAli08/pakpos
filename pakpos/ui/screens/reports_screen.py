"""
ReportsScreen — Professional Offline Retail Business Analytics & Insights Dashboard.
Displays multi-level hierarchy: KPIs, Trends, Product/Category Performance, Inventory Health,
Payment Breakdown, and Deterministic Business Insights.

Two-phase initialization:
  Phase 1 (_setup_ui)       — pure QWidget skeleton, no QChart objects. Safe at construction time.
  Phase 2 (_setup_charts)   — builds all ChartContainer / QChart objects after the Qt event loop
                               is running (triggered via QTimer.singleShot(0, ...)).
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QDateEdit, QScrollArea, QGridLayout,
    QListWidget, QListWidgetItem, QSizePolicy
)

from pakpos.database.engine import get_session
from pakpos.analytics.analytics_service import AnalyticsService
from pakpos.analytics.metrics import DateRangeOption
from pakpos.ui.widgets.kpi_card import KPICardWidget
from pakpos.events import app_events
from pakpos.utils.formatters import format_currency
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_card(padding: int = 14) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    card.setStyleSheet(f"""
        QFrame#card {{
            background-color: #22252c;
            border: 1px solid #2d3139;
            border-radius: 10px;
            padding: {padding}px;
        }}
    """)
    return card


# ── screen ───────────────────────────────────────────────────────────────────

class ReportsScreen(QWidget):
    """
    Main Analytics & Retail Management Dashboard Screen.

    QChart objects are intentionally NOT created in __init__ / _setup_ui.
    They are created in _setup_charts(), which fires after the Qt event loop
    starts, preventing the SIGSEGV (exit 139) that occurs when QChart is
    instantiated before the platform plugin is fully initialised.
    """

    def __init__(self, current_user, parent=None) -> None:
        super().__init__(parent)
        self.current_user = current_user

        # Chart containers — populated in Phase 2
        self.chart_revenue_trend = None
        self.chart_rev_vs_profit = None
        self.chart_top_products = None
        self.chart_category = None
        self.chart_payments = None
        self._charts_ready = False

        # Phase 1: build everything except QChart objects
        self._setup_ui()
        self._wire_events()

        # Phase 2: build QChart objects + first data load (after event loop starts)
        QTimer.singleShot(0, self._setup_charts_and_load)

    # ── Phase 1 ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── TOP HEADER BAR ───
        header_frame = QFrame()
        header_frame.setObjectName("card")
        header_frame.setStyleSheet("""
            QFrame#card {
                background-color: #141619;
                border-bottom: 1px solid #2d3139;
                border-radius: 0px;
                padding: 10px 18px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 10, 16, 10)

        lbl_title = QLabel("Reports & Business Insights")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f3f4f6;")

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        lbl_range = QLabel("Filter:")
        lbl_range.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 600;")

        self.combo_range = QComboBox()
        self.combo_range.addItems([
            "Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month", "Custom Range"
        ])
        self.combo_range.currentIndexChanged.connect(self._on_range_changed)

        self.date_start = QDateEdit(QDate.currentDate())
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("dd-MMM-yyyy")
        self.date_start.setVisible(False)
        self.date_start.dateChanged.connect(self._load_reports)

        self.date_end = QDateEdit(QDate.currentDate())
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("dd-MMM-yyyy")
        self.date_end.setVisible(False)
        self.date_end.dateChanged.connect(self._load_reports)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self._load_reports)

        controls_layout.addWidget(lbl_range)
        controls_layout.addWidget(self.combo_range)
        controls_layout.addWidget(self.date_start)
        controls_layout.addWidget(self.date_end)
        controls_layout.addWidget(btn_refresh)

        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addLayout(controls_layout)
        main_layout.addWidget(header_frame)

        # Error banner (hidden by default)
        self.lbl_error_banner = QLabel("")
        self.lbl_error_banner.setStyleSheet("""
            background-color: rgba(220, 53, 69, 0.15);
            color: #f87171;
            font-size: 12px;
            font-weight: 600;
            padding: 6px 16px;
            border-bottom: 1px solid #dc3545;
        """)
        self.lbl_error_banner.setVisible(False)
        main_layout.addWidget(self.lbl_error_banner)

        # ─── SCROLLABLE CONTENT ───
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #1a1d23; }")

        content_widget = QWidget()
        self._content_layout = QVBoxLayout(content_widget)
        self._content_layout.setContentsMargins(18, 16, 18, 16)
        self._content_layout.setSpacing(16)

        # ── KPI Cards (no charts — safe) ──
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)
        self.kpi_cards: list[KPICardWidget] = [KPICardWidget() for _ in range(6)]
        for col, card in enumerate(self.kpi_cards[:3]):
            kpi_grid.addWidget(card, 0, col)
        for col, card in enumerate(self.kpi_cards[3:]):
            kpi_grid.addWidget(card, 1, col)
        self._content_layout.addLayout(kpi_grid)

        # ── Placeholder rows — charts inserted here in Phase 2 ──
        self._trend_row = QHBoxLayout()
        self._trend_row.setSpacing(12)
        self._content_layout.addLayout(self._trend_row)

        self._perf_row = QHBoxLayout()
        self._perf_row.setSpacing(12)
        self._content_layout.addLayout(self._perf_row)

        # ── Inventory Health (no charts) ──
        self._level4_row = QHBoxLayout()
        self._level4_row.setSpacing(12)

        card_inv = _make_card()
        inv_layout = QVBoxLayout(card_inv)
        inv_layout.setSpacing(8)

        lbl_inv_title = QLabel("INVENTORY HEALTH & VALUATION")
        lbl_inv_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #e8eaed;")
        inv_layout.addWidget(lbl_inv_title)

        inv_grid = QGridLayout()
        inv_grid.setSpacing(10)

        self.lbl_inv_total   = QLabel("Total Products: 0")
        self.lbl_inv_healthy = QLabel("Healthy Stock: 0")
        self.lbl_inv_low     = QLabel("Low Stock: 0")
        self.lbl_inv_out     = QLabel("Out of Stock: 0")
        self.lbl_inv_cost    = QLabel("Inventory Cost: Rs. 0")
        self.lbl_inv_retail  = QLabel("Retail Value: Rs. 0")
        self.lbl_inv_margin  = QLabel("Potential Profit: Rs. 0")

        self.lbl_inv_healthy.setStyleSheet("color: #34d399; font-weight: 600;")
        self.lbl_inv_low.setStyleSheet("color: #fbbf24; font-weight: 600;")
        self.lbl_inv_out.setStyleSheet("color: #f87171; font-weight: 600;")
        self.lbl_inv_cost.setStyleSheet("color: #9ca3af;")
        self.lbl_inv_retail.setStyleSheet("color: #e8eaed; font-weight: 600;")
        self.lbl_inv_margin.setStyleSheet("color: #20c997; font-weight: 700;")

        inv_grid.addWidget(self.lbl_inv_total,   0, 0)
        inv_grid.addWidget(self.lbl_inv_cost,    0, 1)
        inv_grid.addWidget(self.lbl_inv_healthy, 1, 0)
        inv_grid.addWidget(self.lbl_inv_retail,  1, 1)
        inv_grid.addWidget(self.lbl_inv_low,     2, 0)
        inv_grid.addWidget(self.lbl_inv_margin,  2, 1)
        inv_grid.addWidget(self.lbl_inv_out,     3, 0)
        inv_layout.addLayout(inv_grid)

        # Payment chart placeholder — filled in Phase 2
        self._payment_placeholder = QFrame()
        self._payment_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._level4_row.addWidget(card_inv, 1)
        self._level4_row.addWidget(self._payment_placeholder, 1)
        self._content_layout.addLayout(self._level4_row)

        # ── Insights List (no charts) ──
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        card_insights = _make_card()
        ins_layout = QVBoxLayout(card_insights)

        lbl_ins_title = QLabel("AUTOMATED BUSINESS INSIGHTS")
        lbl_ins_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #e8eaed;")
        ins_layout.addWidget(lbl_ins_title)

        self.list_insights = QListWidget()
        self.list_insights.setStyleSheet("""
            QListWidget {
                background-color: #1e2128;
                border: 1px solid #2d3139;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #282c34;
            }
        """)
        ins_layout.addWidget(self.list_insights)
        bottom_row.addWidget(card_insights, 1)
        self._content_layout.addLayout(bottom_row)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)

    # ── Phase 2 ──────────────────────────────────────────────────────────────

    def _setup_charts_and_load(self) -> None:
        """
        Create QChart / ChartContainer objects — must run AFTER the event loop starts.
        Called exactly once via QTimer.singleShot(0, ...).
        """
        try:
            from pakpos.ui.widgets.chart_widget import (
                ChartContainer,
                build_revenue_trend_chart, build_revenue_vs_profit_chart,
                build_top_products_chart, build_donut_chart,
            )
            self._build_revenue_trend_chart = build_revenue_trend_chart
            self._build_revenue_vs_profit_chart = build_revenue_vs_profit_chart
            self._build_top_products_chart = build_top_products_chart
            self._build_donut_chart = build_donut_chart

            # ── Trend row ──
            self.chart_revenue_trend = ChartContainer("REVENUE TREND")
            self.chart_rev_vs_profit = ChartContainer("REVENUE VS GROSS PROFIT")
            self._trend_row.addWidget(self.chart_revenue_trend, 2)
            self._trend_row.addWidget(self.chart_rev_vs_profit, 1)

            # ── Products / Category row ──
            self.chart_top_products = ChartContainer("TOP SELLING PRODUCTS")

            # Metric toggle embedded in the top-products header
            top_header = QHBoxLayout()
            top_header.addWidget(self.chart_top_products.lbl_title)
            top_header.addStretch()
            self.combo_top_metric = QComboBox()
            self.combo_top_metric.addItems(["Units Sold", "Revenue", "Profit"])
            self.combo_top_metric.setFixedWidth(110)
            self.combo_top_metric.currentIndexChanged.connect(self._load_reports)
            top_header.addWidget(self.combo_top_metric)
            self.chart_top_products.layout().insertLayout(0, top_header)

            self.chart_category = ChartContainer("SALES BY CATEGORY")
            self._perf_row.addWidget(self.chart_top_products, 1)
            self._perf_row.addWidget(self.chart_category, 1)

            # ── Payment methods chart (replaces placeholder) ──
            self.chart_payments = ChartContainer("PAYMENT METHODS")
            # Swap placeholder for real chart container in the level4 row
            idx = self._level4_row.indexOf(self._payment_placeholder)
            self._level4_row.removeWidget(self._payment_placeholder)
            self._payment_placeholder.deleteLater()
            self._level4_row.insertWidget(idx, self.chart_payments, 1)

            self._charts_ready = True
            logger.info("QtCharts widgets created successfully.")
        except Exception as e:
            logger.error("Failed to create QtCharts widgets: %s", e, exc_info=True)
            self.lbl_error_banner.setText(f"Charts unavailable: {e}")
            self.lbl_error_banner.setVisible(True)
            return

        # Now safe to load data for the first time
        self._load_reports()

    # ── Events ───────────────────────────────────────────────────────────────

    def _wire_events(self) -> None:
        app_events.sale_completed.connect(self._on_app_data_changed)
        app_events.inventory_changed.connect(self._on_app_data_changed)
        app_events.customer_changed.connect(self._on_app_data_changed)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(45000)
        self.refresh_timer.timeout.connect(self._load_reports)
        self.refresh_timer.start()

    def _on_app_data_changed(self) -> None:
        AnalyticsService.invalidate_cache()
        self._load_reports()

    def _on_range_changed(self) -> None:
        is_custom = self.combo_range.currentText() == "Custom Range"
        self.date_start.setVisible(is_custom)
        self.date_end.setVisible(is_custom)
        self._load_reports()

    def _get_current_date_range_option(self) -> tuple[str, date | None, date | None]:
        text = self.combo_range.currentText()
        mapping = {
            "Today":        DateRangeOption.TODAY.value,
            "Yesterday":    DateRangeOption.YESTERDAY.value,
            "Last 7 Days":  DateRangeOption.LAST_7_DAYS.value,
            "Last 30 Days": DateRangeOption.LAST_30_DAYS.value,
            "This Month":   DateRangeOption.THIS_MONTH.value,
            "Custom Range": DateRangeOption.CUSTOM.value,
        }
        option_val = mapping.get(text, DateRangeOption.TODAY.value)
        c_start = c_end = None
        if option_val == DateRangeOption.CUSTOM.value:
            c_start = self.date_start.date().toPython()
            c_end   = self.date_end.date().toPython()
        return option_val, c_start, c_end

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_reports(self) -> None:
        """Fetch metrics from AnalyticsService and update all UI widgets."""
        if not self._charts_ready:
            # Charts not built yet — called by timer before Phase 2 finished; ignore.
            return

        self.lbl_error_banner.setVisible(False)
        try:
            option_val, c_start, c_end = self._get_current_date_range_option()

            with get_session() as session:
                service = AnalyticsService(session)

                # 1. KPI Cards
                kpi_data_list = service.get_kpi_cards(option_val, c_start, c_end)
                for idx, kpi_data in enumerate(kpi_data_list):
                    if idx < len(self.kpi_cards):
                        self.kpi_cards[idx].update_data(kpi_data)

                # 2. Revenue Trend
                trend_points = service.get_revenue_trend(option_val, c_start, c_end)
                has_rev = self._build_revenue_trend_chart(self.chart_revenue_trend.chart, trend_points)
                self.chart_revenue_trend.show_empty_state(not has_rev)

                # 3. Revenue vs Profit
                has_profit = self._build_revenue_vs_profit_chart(self.chart_rev_vs_profit.chart, trend_points)
                self.chart_rev_vs_profit.show_empty_state(not has_profit)

                # 4. Top Products
                top_metric_code = "units"
                top_text = self.combo_top_metric.currentText()
                if top_text == "Revenue":
                    top_metric_code = "revenue"
                elif top_text == "Profit":
                    top_metric_code = "profit"

                top_products = service.get_top_products(
                    option_val, c_start, c_end, limit=5, sort_by=top_metric_code
                )
                has_top = self._build_top_products_chart(
                    self.chart_top_products.chart, top_products, metric=top_metric_code
                )
                self.chart_top_products.show_empty_state(not has_top)

                # 5. Category Performance
                cat_perf = service.get_category_performance(option_val, c_start, c_end)
                has_cat = self._build_donut_chart(self.chart_category.chart, cat_perf)
                self.chart_category.show_empty_state(not has_cat)

                # 6. Payment Methods
                pay_breakdown = service.get_payment_breakdown(option_val, c_start, c_end)
                has_pay = self._build_donut_chart(self.chart_payments.chart, pay_breakdown)
                self.chart_payments.show_empty_state(not has_pay)

                # 7. Inventory Health
                inv = service.get_inventory_health()
                self.lbl_inv_total.setText(f"Total Products: {inv.total_products}")
                self.lbl_inv_healthy.setText(f"Healthy Stock: {inv.healthy_count}")
                self.lbl_inv_low.setText(f"Low Stock: {inv.low_stock_count}")
                self.lbl_inv_out.setText(f"Out of Stock: {inv.out_of_stock_count}")
                self.lbl_inv_cost.setText(f"Inventory Cost: {format_currency(inv.stock_cost_value)}")
                self.lbl_inv_retail.setText(f"Retail Value: {format_currency(inv.stock_retail_value)}")
                self.lbl_inv_margin.setText(f"Potential Margin: {format_currency(inv.potential_margin)}")

                # 8. Business Insights
                insights = service.get_insights(option_val, c_start, c_end)
                self.list_insights.clear()
                for ins in insights:
                    item = QListWidgetItem(f"• {ins.message}")
                    if ins.severity == "critical":
                        item.setForeground(Qt.GlobalColor.red)
                    elif ins.severity == "warning":
                        item.setForeground(Qt.GlobalColor.yellow)
                    else:
                        item.setForeground(Qt.GlobalColor.cyan)
                    self.list_insights.addItem(item)

        except Exception as e:
            logger.error("Failed to refresh analytics dashboard: %s", e, exc_info=True)
            self.lbl_error_banner.setText(f"Notice: Analytics updates partially restricted ({e})")
            self.lbl_error_banner.setVisible(True)
