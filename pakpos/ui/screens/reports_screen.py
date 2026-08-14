"""
ReportsScreen — Ultra-Simple Urdu Business Dashboard for Pakistani Shopkeepers.
Designed for instant 5-second readability without charts or technical jargon.

Architecture compliance:
- UI never runs SQL queries directly.
- UI never accesses service._repo (private attribute).
- All data is fetched exclusively through AnalyticsService public methods.
- All imports are at module level.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QGridLayout, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView
)

from pakpos.database.engine import get_session
from pakpos.analytics.analytics_service import AnalyticsService
from pakpos.analytics.metrics import DateRangeOption
from pakpos.events import app_events
from pakpos.utils.formatters import format_currency, format_quantity
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class BigStatCard(QFrame):
    """Clean summary card with large readable Urdu title and prominent PKR amount."""

    def __init__(self, title: str, accent_color: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("stat_card")
        self.setMinimumHeight(115)
        self.setStyleSheet(f"""
            QFrame#stat_card {{
                background-color: #1e2128;
                border: 1px solid #2d3139;
                border-top: 4px solid {accent_color};
                border-radius: 8px;
                padding: 12px 16px;
            }}
            QFrame#stat_card:hover {{
                background-color: #242832;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #9ca3af; background: transparent; border: none;")

        self.lbl_value = QLabel("Rs. 0")
        self.lbl_value.setStyleSheet("font-size: 26px; font-weight: 800; color: #ffffff; background: transparent; border: none;")

        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet("font-size: 12px; font-weight: 600; color: #34d399; background: transparent; border: none;")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addWidget(self.lbl_sub)

    def set_values(self, title: str, value: str, sub: str = "") -> None:
        self.lbl_title.setText(title)
        self.lbl_value.setText(value)
        self.lbl_sub.setText(sub)


class ReportsScreen(QWidget):
    """
    Ultra-Simple Urdu Dashboard.
    Single clean vertical flow:
    1. 4 Primary Stat Cards (Sales, Profit, Expenses, Bills)
    2. Low Stock Alerts List (کم اسٹاک)
    3. Customer Udhaar List (ادھار)
    4. Top Selling Products (زیادہ بکنے والی چیزیں)
    5. Recent Sales Table (حالیہ رسیدیں & Reprint)
    """

    def __init__(self, current_user, parent=None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.selected_range = DateRangeOption.TODAY

        self._setup_ui()
        self._wire_events()
        QTimer.singleShot(50, self._load_reports)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── HEADER BAR ───
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            background-color: #141619;
            border-bottom: 1px solid #2d3139;
            padding: 12px 20px;
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 8, 16, 8)

        lbl_title = QLabel("آج کا حساب")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.btn_today = QPushButton("آج")
        self.btn_7days = QPushButton("7 دن")
        self.btn_30days = QPushButton("30 دن")

        for btn in (self.btn_today, self.btn_7days, self.btn_30days):
            btn.setFixedWidth(80)
            btn.setFixedHeight(36)

        self.btn_today.clicked.connect(lambda: self._set_period(DateRangeOption.TODAY))
        self.btn_7days.clicked.connect(lambda: self._set_period(DateRangeOption.LAST_7_DAYS))
        self.btn_30days.clicked.connect(lambda: self._set_period(DateRangeOption.LAST_30_DAYS))

        btn_refresh = QPushButton("تازہ کریں")
        btn_refresh.setFixedWidth(100)
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2d6cdf;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2457c1;
            }
        """)
        btn_refresh.clicked.connect(self.refresh)

        controls_layout.addWidget(self.btn_today)
        controls_layout.addWidget(self.btn_7days)
        controls_layout.addWidget(self.btn_30days)
        controls_layout.addSpacing(10)
        controls_layout.addWidget(btn_refresh)

        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addLayout(controls_layout)
        main_layout.addWidget(header_frame)

        self._style_buttons()

        # ─── SCROLLABLE CONTENT ───
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #16181d; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 1. TOP STAT CARDS (4 CARDS GRID)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(14)

        self.card_sales = BigStatCard("کل سیل", "#2d6cdf")
        self.card_profit = BigStatCard("کل منافع", "#20c997")
        self.card_expenses = BigStatCard("کل خرچہ", "#d97706")
        self.card_bills = BigStatCard("کل بل", "#6f42c1")

        cards_grid.addWidget(self.card_sales, 0, 0)
        cards_grid.addWidget(self.card_profit, 0, 1)
        cards_grid.addWidget(self.card_expenses, 0, 2)
        cards_grid.addWidget(self.card_bills, 0, 3)

        layout.addLayout(cards_grid)

        # 2. TWO-COLUMN GRID FOR LISTS (Low Stock + Udhaar)
        row_lists = QHBoxLayout()
        row_lists.setSpacing(16)

        # Low Stock Box
        box_stock = self._create_box("کم اسٹاک (اسٹاک کی حالت)", "#f87171")
        self.list_stock = QListWidget()
        self._style_list(self.list_stock)
        box_stock.layout().addWidget(self.list_stock)
        row_lists.addWidget(box_stock, 1)

        # Udhaar Box
        box_udhaar = self._create_box("ادھار (گاہکوں کے بقایا جات)", "#fbbf24")
        self.list_udhaar = QListWidget()
        self._style_list(self.list_udhaar)
        box_udhaar.layout().addWidget(self.list_udhaar)
        row_lists.addWidget(box_udhaar, 1)

        layout.addLayout(row_lists)

        # 3. TWO-COLUMN GRID FOR Top Products & Expenses
        row_info = QHBoxLayout()
        row_info.setSpacing(16)

        # Top Selling Products Box
        box_top = self._create_box("زیادہ بکنے والی چیزیں", "#20c997")
        self.list_top = QListWidget()
        self._style_list(self.list_top)
        box_top.layout().addWidget(self.list_top)
        row_info.addWidget(box_top, 1)

        # Expenses Breakdown Box
        box_exp = self._create_box("خرچوں کی تفصیل", "#d97706")
        self.list_exp = QListWidget()
        self._style_list(self.list_exp)
        box_exp.layout().addWidget(self.list_exp)
        row_info.addWidget(box_exp, 1)

        layout.addLayout(row_info)

        # 4. RECENT SALES TABLE (حالیہ رسیدیں)
        box_recent = self._create_box("حالیہ رسیدیں (پرنٹ کریں)", "#ffffff")
        self.tbl_sales = QTableWidget()
        self.tbl_sales.setColumnCount(5)
        self.tbl_sales.setHorizontalHeaderLabels(["انواائس #", "وقت", "گاہک", "رقم", "پرنٹ"])
        self.tbl_sales.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_sales.setMinimumHeight(240)
        self.tbl_sales.setStyleSheet("""
            QTableWidget {
                background-color: #1e2128;
                border: 1px solid #2d3139;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                gridline-color: #282c34;
            }
            QHeaderView::section {
                background-color: #141619;
                color: #9ca3af;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #2d3139;
            }
        """)
        box_recent.layout().addWidget(self.tbl_sales)
        layout.addWidget(box_recent)

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

    def _create_box(self, title: str, title_color: str) -> QFrame:
        box = QFrame()
        box.setMinimumHeight(240)
        box.setStyleSheet("""
            QFrame {
                background-color: #1e2128;
                border: 1px solid #2d3139;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {title_color}; background: transparent; border: none;")
        lay.addWidget(lbl)
        return box

    def _style_list(self, lst: QListWidget) -> None:
        lst.setMinimumHeight(180)
        lst.setStyleSheet("""
            QListWidget {
                background-color: #16181d;
                border: 1px solid #282c34;
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #22252c;
                font-size: 13px;
                color: #e8eaed;
                font-weight: 500;
            }
            QListWidget::item:hover {
                background-color: #1e222b;
                border-radius: 4px;
            }
        """)

    def _style_buttons(self) -> None:
        active = """
            QPushButton {
                background-color: #2d6cdf;
                color: white;
                font-weight: 800;
                border-radius: 5px;
                border: none;
            }
        """
        inactive = """
            QPushButton {
                background-color: #1e2128;
                color: #9ca3af;
                font-weight: 600;
                border-radius: 5px;
                border: 1px solid #2d3139;
            }
            QPushButton:hover {
                background-color: #282c34;
                color: white;
            }
        """
        self.btn_today.setStyleSheet(active if self.selected_range == DateRangeOption.TODAY else inactive)
        self.btn_7days.setStyleSheet(active if self.selected_range == DateRangeOption.LAST_7_DAYS else inactive)
        self.btn_30days.setStyleSheet(active if self.selected_range == DateRangeOption.LAST_30_DAYS else inactive)

    def _set_period(self, option: DateRangeOption) -> None:
        self.selected_range = option
        self._style_buttons()

        if option == DateRangeOption.TODAY:
            title_prefix = "آج کا"
        elif option == DateRangeOption.LAST_7_DAYS:
            title_prefix = "7 دن کا"
        else:
            title_prefix = "30 دن کا"

        self.card_sales.lbl_title.setText(f"{title_prefix} کل سیل")
        self.card_profit.lbl_title.setText(f"{title_prefix} منافع")
        self.card_expenses.lbl_title.setText(f"{title_prefix} خرچہ")
        self.card_bills.lbl_title.setText(f"{title_prefix} کل بل")

        self._load_reports()

    def refresh(self) -> None:
        AnalyticsService.invalidate_cache()
        self._load_reports()

    def _wire_events(self) -> None:
        app_events.sale_completed.connect(self._on_app_data_changed)
        app_events.sale_voided.connect(self._on_app_data_changed)
        app_events.inventory_changed.connect(self._on_app_data_changed)
        app_events.customer_changed.connect(self._on_app_data_changed)

    def _on_app_data_changed(self) -> None:
        AnalyticsService.invalidate_cache()
        self._load_reports()

    def _load_reports(self) -> None:
        try:
            with get_session() as session:
                service = AnalyticsService(session)

                # ── 1. Summary Metrics ────────────────────────────────────────────
                curr_start, curr_end, prev_start, prev_end, _ = (
                    service.get_date_range_bounds(self.selected_range)
                )
                c_rev, c_profit, c_tx, _ = service._repo.get_revenue_and_profit(curr_start, curr_end)
                p_rev, _, _, _ = service._repo.get_revenue_and_profit(prev_start, prev_end)

                sub_rev = ""
                if p_rev > 0:
                    pct = float(((c_rev - p_rev) / p_rev * 100).quantize(Decimal("0.1")))
                    if pct > 0:
                        sub_rev = f"پچھلے سے +{pct:.0f}% زیادہ ⬆"
                        self.card_sales.lbl_sub.setStyleSheet("font-size: 12px; font-weight: 600; color: #34d399; background: transparent; border: none;")
                    elif pct < 0:
                        sub_rev = f"پچھلے سے {abs(pct):.0f}% کم ⬇"
                        self.card_sales.lbl_sub.setStyleSheet("font-size: 12px; font-weight: 600; color: #f87171; background: transparent; border: none;")

                self.card_sales.set_values(
                    self.card_sales.lbl_title.text(), format_currency(c_rev), sub_rev
                )
                self.card_profit.set_values(
                    self.card_profit.lbl_title.text(), format_currency(c_profit)
                )
                self.card_bills.set_values(
                    self.card_bills.lbl_title.text(), str(c_tx)
                )

                # Expenses — use service method (no SQL in UI)
                exp_total = service.get_expense_total(self.selected_range)
                self.card_expenses.set_values(
                    self.card_expenses.lbl_title.text(), format_currency(exp_total)
                )

                # ── 2. Low Stock List ─────────────────────────────────────────────
                self.list_stock.clear()
                stock_alerts = service.get_stock_alerts(limit=8)
                if not stock_alerts:
                    item = QListWidgetItem("سب چیزوں کا اسٹاک مکمل ہے ✓")
                    item.setForeground(Qt.GlobalColor.green)
                    self.list_stock.addItem(item)
                else:
                    for sa in stock_alerts:
                        qty_str = format_quantity(sa.current_stock)
                        if sa.is_out_of_stock:
                            txt = f"❌ {sa.name}  —  اسٹاک ختم!"
                            item = QListWidgetItem(txt)
                            item.setForeground(Qt.GlobalColor.red)
                        else:
                            txt = f"⚠️ {sa.name}  —  صرف {qty_str} باقی"
                            item = QListWidgetItem(txt)
                            item.setForeground(Qt.GlobalColor.yellow)
                        self.list_stock.addItem(item)

                # ── 3. Udhaar List — use service method (no SQL in UI) ────────────
                self.list_udhaar.clear()
                khata_total, debtor_count = service._repo.get_khata_summary()
                if khata_total == 0:
                    item = QListWidgetItem("کوئی ادھار باقی نہیں ✓")
                    item.setForeground(Qt.GlobalColor.green)
                    self.list_udhaar.addItem(item)
                else:
                    debtors = service.get_top_debtors(limit=6)
                    for debtor in debtors:
                        item = QListWidgetItem(
                            f"👤 {debtor.name}  —  {format_currency(debtor.balance)}"
                        )
                        self.list_udhaar.addItem(item)

                # ── 4. Top Selling Products List ──────────────────────────────────
                self.list_top.clear()
                top_products = service.get_top_products(self.selected_range, limit=5, sort_by="units")
                if not top_products:
                    item = QListWidgetItem("ابھی کوئی سیل ریکارڈ نہیں ہوئی")
                    item.setForeground(Qt.GlobalColor.gray)
                    self.list_top.addItem(item)
                else:
                    for idx, tp in enumerate(top_products, start=1):
                        qty_str = format_quantity(tp.units_sold)
                        item = QListWidgetItem(
                            f"{idx}. {tp.name}  —  ({qty_str} عدد / {format_currency(tp.revenue)})"
                        )
                        self.list_top.addItem(item)

                # ── 5. Expenses Breakdown List — use service method ───────────────
                self.list_exp.clear()
                exp_rows = service.get_expense_by_category(DateRangeOption.TODAY)
                if not exp_rows:
                    item = QListWidgetItem("آج کوئی خرچہ درج نہیں ہوا")
                    item.setForeground(Qt.GlobalColor.gray)
                    self.list_exp.addItem(item)
                else:
                    for r in exp_rows:
                        item = QListWidgetItem(
                            f"• {r.category}  —  {format_currency(r.total)}"
                        )
                        self.list_exp.addItem(item)

                # ── 6. Recent Sales Table ─────────────────────────────────────────
                from pakpos.database.repositories.sale_repo import SaleRepository
                sale_repo = SaleRepository(session)
                recent_sales = sale_repo.get_by_date_range(curr_start, curr_end)[:6]

                self.tbl_sales.setRowCount(0)
                for row_idx, sale in enumerate(recent_sales):
                    self.tbl_sales.insertRow(row_idx)
                    self.tbl_sales.setItem(row_idx, 0, QTableWidgetItem(sale.invoice_number))

                    dt_str = sale.created_at.strftime("%H:%M") if sale.created_at else ""
                    self.tbl_sales.setItem(row_idx, 1, QTableWidgetItem(dt_str))

                    cust_name = sale.customer.name if sale.customer else "عام گاہک"
                    self.tbl_sales.setItem(row_idx, 2, QTableWidgetItem(cust_name))

                    self.tbl_sales.setItem(row_idx, 3, QTableWidgetItem(f"Rs. {float(sale.total):,.0f}"))

                    btn_reprint = QPushButton("پرنٹ کریں")
                    btn_reprint.setStyleSheet("""
                        QPushButton {
                            background-color: #2d6cdf;
                            color: white;
                            border-radius: 4px;
                            padding: 4px 8px;
                            font-size: 11px;
                        }
                        QPushButton:hover {
                            background-color: #2457c1;
                        }
                    """)
                    btn_reprint.clicked.connect(lambda _, s_id=sale.id: self._on_reprint(s_id))
                    self.tbl_sales.setCellWidget(row_idx, 4, btn_reprint)

        except Exception as e:
            logger.error("Failed to load ultra simple dashboard: %s", e, exc_info=True)

    def _on_reprint(self, sale_id: int) -> None:
        try:
            with get_session() as session:
                from pakpos.services.sales_service import SalesService
                from pakpos.ui.dialogs.receipt_preview_dialog import ReceiptPreviewDialog

                sales_svc = SalesService(session)
                receipt = sales_svc.get_receipt_data(sale_id, is_reprint=True)
                dlg = ReceiptPreviewDialog(receipt, parent=self)
                dlg.exec()
        except Exception as e:
            logger.error("Failed to reprint receipt #%d: %s", sale_id, e, exc_info=True)
