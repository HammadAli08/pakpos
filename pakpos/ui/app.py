"""
PySide6 Application — creates QApplication, sets theme, and shows the appropriate window.
On first run (no users exist), shows Setup Wizard.
Otherwise shows Login Window.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import QApplication

from pakpos.config.settings import APP_NAME, APP_VERSION
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────
# PakPOS Dark Professional Theme
# High contrast, readable at shop counter
# ──────────────────────────────────────────────
DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1a1d23;
    color: #e8eaed;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #141619;
    color: #e8eaed;
    border-bottom: 1px solid #2d3139;
}
QMenuBar::item:selected {
    background-color: #2d6cdf;
}
QMenu {
    background-color: #22252c;
    color: #e8eaed;
    border: 1px solid #2d3139;
}
QMenu::item:selected {
    background-color: #2d6cdf;
}
QPushButton {
    background-color: #2d6cdf;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 32px;
}
QPushButton:hover {
    background-color: #3d7ef0;
}
QPushButton:pressed {
    background-color: #1d5cbf;
}
QPushButton:disabled {
    background-color: #3a3d45;
    color: #6b7280;
}
QPushButton#btn_danger {
    background-color: #dc3545;
}
QPushButton#btn_danger:hover {
    background-color: #e9505f;
}
QPushButton#btn_success {
    background-color: #198754;
}
QPushButton#btn_success:hover {
    background-color: #1fa863;
}
QPushButton#btn_warning {
    background-color: #d97706;
    color: white;
}
QPushButton#btn_secondary {
    background-color: #374151;
    color: #e8eaed;
}
QPushButton#btn_secondary:hover {
    background-color: #4b5563;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #22252c;
    color: #e8eaed;
    border: 1px solid #3a3d45;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 28px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #2d6cdf;
}
QLineEdit:read-only {
    background-color: #1a1d23;
    color: #9ca3af;
}
QComboBox {
    background-color: #22252c;
    color: #e8eaed;
    border: 1px solid #3a3d45;
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 28px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #22252c;
    color: #e8eaed;
    selection-background-color: #2d6cdf;
}
QTableWidget, QTableView {
    background-color: #1e2128;
    color: #e8eaed;
    gridline-color: #2d3139;
    border: 1px solid #2d3139;
    border-radius: 4px;
    alternate-background-color: #22252c;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #2d4a80;
    color: white;
}
QHeaderView::section {
    background-color: #141619;
    color: #9ca3af;
    padding: 8px 6px;
    border: none;
    border-right: 1px solid #2d3139;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
}
QScrollBar:vertical {
    background: #1a1d23;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3a3d45;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #4b5563;
}
QScrollBar:horizontal {
    height: 8px;
    background: #1a1d23;
}
QScrollBar::handle:horizontal {
    background: #3a3d45;
    border-radius: 4px;
}
QLabel#label_title {
    font-size: 22px;
    font-weight: 700;
    color: #e8eaed;
}
QLabel#label_subtitle {
    font-size: 14px;
    color: #9ca3af;
}
QLabel#label_amount {
    font-size: 28px;
    font-weight: 700;
    color: #34d399;
}
QGroupBox {
    border: 1px solid #2d3139;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
    color: #9ca3af;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #9ca3af;
}
QTabWidget::pane {
    border: 1px solid #2d3139;
    border-radius: 4px;
    background-color: #1a1d23;
}
QTabBar::tab {
    background-color: #22252c;
    color: #9ca3af;
    padding: 8px 20px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #2d6cdf;
    border-bottom: 2px solid #2d6cdf;
    background-color: #1a1d23;
}
QTabBar::tab:hover {
    color: #e8eaed;
}
QSplitter::handle {
    background-color: #2d3139;
}
QStatusBar {
    background-color: #141619;
    color: #6b7280;
    border-top: 1px solid #2d3139;
}
QProgressBar {
    border: 1px solid #3a3d45;
    border-radius: 4px;
    background-color: #22252c;
    color: white;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #2d6cdf;
    border-radius: 3px;
}
QCheckBox {
    color: #e8eaed;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #3a3d45;
    border-radius: 3px;
    background-color: #22252c;
}
QCheckBox::indicator:checked {
    background-color: #2d6cdf;
    border-color: #2d6cdf;
}
QSpinBox, QDoubleSpinBox {
    background-color: #22252c;
    color: #e8eaed;
    border: 1px solid #3a3d45;
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 28px;
}
QFrame#card {
    background-color: #22252c;
    border: 1px solid #2d3139;
    border-radius: 10px;
    padding: 12px;
}
QListWidget {
    background-color: #1e2128;
    color: #e8eaed;
    border: 1px solid #2d3139;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #2d4a80;
}
QToolTip {
    background-color: #22252c;
    color: #e8eaed;
    border: 1px solid #3a3d45;
    border-radius: 4px;
    padding: 4px;
}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the PakPOS dark professional theme."""
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    font = QFont("Segoe UI", 10)
    app.setFont(font)


def run_app(argv: list[str]) -> int:
    """Create QApplication and show the appropriate starting window."""
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("PakPOS")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    apply_theme(app)

    # Determine which window to show
    from pakpos.services.auth_service import AuthService
    from pakpos.database.engine import get_session

    with get_session() as session:
        auth = AuthService(session)
        first_run = not auth.has_any_user()

    if first_run:
        from pakpos.ui.windows.setup_wizard import SetupWizard
        window = SetupWizard()
        app._main_window = window
        window.show()
    else:
        from pakpos.ui.windows.login_window import LoginWindow
        window = LoginWindow()
        app._main_window = window
        window.show()

    logger.info("UI launched (first_run=%s)", first_run)
    return app.exec()
