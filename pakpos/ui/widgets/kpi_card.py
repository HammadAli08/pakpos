"""
KPICardWidget — Custom dark styled visual card for financial and inventory KPIs.
Displays title, primary value, trend indicator (with arrow & color), and subtitle.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel

from pakpos.analytics.metrics import KPICardData


class KPICardWidget(QFrame):
    """Visual KPI summary card."""

    def __init__(self, data: KPICardData | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet("""
            QFrame#card {
                background-color: #22252c;
                border: 1px solid #2d3139;
                border-radius: 10px;
                padding: 12px 14px;
            }
            QFrame#card:hover {
                border: 1px solid #3a404d;
                background-color: #262931;
            }
        """)
        self._setup_ui()
        if data:
            self.update_data(data)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Title Label
        self.lbl_title = QLabel("KPI TITLE")
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #9ca3af; letter-spacing: 0.5px;")

        # Value Label
        self.lbl_value = QLabel("Rs. 0")
        self.lbl_value.setStyleSheet("font-size: 22px; font-weight: 800; color: #f3f4f6;")

        # Trend / Comparison Row
        trend_layout = QHBoxLayout()
        trend_layout.setContentsMargins(0, 0, 0, 0)
        trend_layout.setSpacing(6)

        self.lbl_trend = QLabel("")
        self.lbl_trend.setStyleSheet("font-size: 11px; font-weight: 600;")

        trend_layout.addWidget(self.lbl_trend)
        trend_layout.addStretch()

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addLayout(trend_layout)

    def update_data(self, data: KPICardData) -> None:
        self.lbl_title.setText(data.title.upper())
        self.lbl_value.setText(str(data.value_formatted))

        comp_text = data.comparison_text
        if data.subtitle:
            comp_text = f"{comp_text} • {data.subtitle}" if comp_text else data.subtitle

        self.lbl_trend.setText(comp_text)

        if data.is_positive is True:
            self.lbl_trend.setStyleSheet("font-size: 11px; font-weight: 600; color: #34d399;")  # Green
        elif data.is_positive is False:
            self.lbl_trend.setStyleSheet("font-size: 11px; font-weight: 600; color: #f87171;")  # Red
        else:
            self.lbl_trend.setStyleSheet("font-size: 11px; font-weight: 500; color: #9ca3af;")  # Muted grey
