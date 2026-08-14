"""
KPICardWidget & UrduSummaryCard — High impact visual card for Pakistani shopkeeper dashboard.
Displays Urdu title, large prominent numbers (Rs. X,XXX), and simple comparison status.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel

from pakpos.analytics.metrics import KPICardData


class KPICardWidget(QFrame):
    """
    Visual summary card designed for simplicity and maximum readability.
    Supports both Urdu titles and numeric formatting.
    """

    def __init__(
        self,
        title: str = "",
        value: str = "Rs. 0",
        accent_color: str = "#2d6cdf",
        data: KPICardData | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._accent_color = accent_color
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: #22252c;
                border: 1px solid #2d3139;
                border-left: 4px solid {accent_color};
                border-radius: 10px;
                padding: 14px 16px;
            }}
            QFrame#card:hover {{
                border: 1px solid #3a404d;
                border-left: 4px solid {accent_color};
                background-color: #262931;
            }}
        """)
        self._setup_ui(title, value)
        if data:
            self.update_data(data)

    def _setup_ui(self, title: str, value: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Title Label (Urdu or English)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #9ca3af;")

        # Primary Value Label (Large, 26px bold)
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("font-size: 26px; font-weight: 800; color: #f3f4f6;")

        # Status / Comparison Row
        trend_layout = QHBoxLayout()
        trend_layout.setContentsMargins(0, 0, 0, 0)
        trend_layout.setSpacing(6)

        self.lbl_trend = QLabel("")
        self.lbl_trend.setStyleSheet("font-size: 12px; font-weight: 600;")

        trend_layout.addWidget(self.lbl_trend)
        trend_layout.addStretch()

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addLayout(trend_layout)

    def set_content(self, title: str, value: str, trend: str = "", is_positive: bool | None = None) -> None:
        self.lbl_title.setText(title)
        self.lbl_value.setText(value)
        self.lbl_trend.setText(trend)
        if is_positive is True:
            self.lbl_trend.setStyleSheet("font-size: 12px; font-weight: 600; color: #34d399;")
        elif is_positive is False:
            self.lbl_trend.setStyleSheet("font-size: 12px; font-weight: 600; color: #f87171;")
        else:
            self.lbl_trend.setStyleSheet("font-size: 12px; font-weight: 500; color: #9ca3af;")

    def update_data(self, data: KPICardData, urdu_title: str | None = None) -> None:
        title = urdu_title if urdu_title else data.title
        self.set_content(
            title=title,
            value=str(data.value_formatted),
            trend=data.comparison_text,
            is_positive=data.is_positive,
        )


# Alias for clarity
UrduSummaryCard = KPICardWidget
