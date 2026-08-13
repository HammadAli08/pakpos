"""
ReportsScreen — Business Summary and Deterministic Insights.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QListWidget, QListWidgetItem, QGridLayout
)

from pakpos.database.engine import get_session
from pakpos.services.report_service import ReportService
from pakpos.utils.formatters import format_currency


class ReportsScreen(QWidget):
    """
    Dashboard screen displaying financial summaries and business insights.
    """

    def __init__(self, current_user, parent=None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        lbl_header = QLabel("Financial Summary & Insights")
        lbl_header.setObjectName("label_title")
        layout.addWidget(lbl_header)

        # Summary Cards Grid
        grid = QGridLayout()

        self.card_rev = self._create_card("TODAY'S REVENUE", "Rs. 0.00")
        self.card_profit = self._create_card("GROSS PROFIT", "Rs. 0.00")
        self.card_trans = self._create_card("TRANSACTIONS", "0")
        self.card_khata = self._create_card("OUTSTANDING KHATA", "Rs. 0.00")

        grid.addWidget(self.card_rev["frame"], 0, 0)
        grid.addWidget(self.card_profit["frame"], 0, 1)
        grid.addWidget(self.card_trans["frame"], 1, 0)
        grid.addWidget(self.card_khata["frame"], 1, 1)

        layout.addLayout(grid)

        # Insights List
        lbl_insights = QLabel("Automated Insights & Alerts")
        lbl_insights.setObjectName("label_subtitle")
        layout.addWidget(lbl_insights)

        self.list_insights = QListWidget()
        layout.addWidget(self.list_insights)

        btn_refresh = QPushButton("Refresh Data")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._load_reports)
        layout.addWidget(btn_refresh)

        self._load_reports()

    def _create_card(self, title: str, initial_value: str) -> dict:
        frame = QFrame()
        frame.setObjectName("card")
        l = QVBoxLayout(frame)

        lbl_t = QLabel(title)
        lbl_t.setObjectName("label_subtitle")
        lbl_v = QLabel(initial_value)
        lbl_v.setObjectName("label_amount")

        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return {"frame": frame, "value": lbl_v}

    def _load_reports(self) -> None:
        with get_session() as session:
            service = ReportService(session)
            summary = service.get_today_summary()
            khata = service.get_total_outstanding_khata()
            insights = service.get_business_insights()

            self.card_rev["value"].setText(format_currency(summary.total_revenue))
            self.card_profit["value"].setText(format_currency(summary.gross_profit))
            self.card_trans["value"].setText(str(summary.total_transactions))
            self.card_khata["value"].setText(format_currency(khata))

            self.list_insights.clear()
            for insight in insights:
                item = QListWidgetItem(f"[{insight.category.upper()}] {insight.message}")
                if insight.severity == "critical":
                    item.setForeground(Qt.GlobalColor.red)
                elif insight.severity == "warning":
                    item.setForeground(Qt.GlobalColor.yellow)
                self.list_insights.addItem(item)
