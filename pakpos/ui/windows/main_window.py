"""
MainWindow — Main application container window.
Navigation bar with screen switching:
- POS (Checkout)
- Products & Stock
- Financial Reports & Insights
- Database Backup
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QMessageBox, QStatusBar
)

from pakpos.config.settings import APP_NAME, APP_VERSION
from pakpos.ui.screens.pos_screen import PosScreen
from pakpos.ui.screens.products_screen import ProductsScreen
from pakpos.ui.screens.reports_screen import ReportsScreen
from pakpos.ui.screens.backup_screen import BackupScreen
from pakpos.ui.screens.settings_screen import SettingsScreen
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    Main Application Window container with sidebar navigation.
    """

    def __init__(self, current_user=None) -> None:
        super().__init__()
        self.current_user = current_user
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Offline POS Terminal")
        self.setMinimumSize(1280, 768)
        self.resize(1366, 768)
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── NAV SIDEBAR ───
        sidebar = QFrame()
        sidebar.setObjectName("card")
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame#card {
                background-color: #141619;
                border-right: 1px solid #2d3139;
            }
        """)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(12, 18, 12, 18)
        nav_layout.setSpacing(10)

        # App Logo & Status Header
        lbl_app = QLabel("PakPOS")
        lbl_app.setStyleSheet("font-weight: 900; font-size: 22px; color: #20c997; letter-spacing: 1px;")
        lbl_app.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_offline = QLabel("● Offline Mode")
        lbl_offline.setStyleSheet("font-size: 11px; font-weight: 600; color: #20c997; background-color: rgba(32, 201, 151, 0.12); border-radius: 4px; padding: 2px 8px;")
        lbl_offline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_role = QLabel(f"Cashier: {self.current_user.username if self.current_user else 'Guest'}")
        lbl_role.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 500;")
        lbl_role.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nav_layout.addWidget(lbl_app)
        nav_layout.addWidget(lbl_offline, 0, Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(lbl_role)
        nav_layout.addSpacing(15)

        # Navigation Buttons
        self.nav_buttons: list[QPushButton] = []

        self.btn_pos = QPushButton("Checkout (F1)")
        self.btn_pos.clicked.connect(lambda: self._set_active_screen(0))

        self.btn_products = QPushButton("Products && Stock")
        self.btn_products.clicked.connect(lambda: self._set_active_screen(1))

        self.btn_reports = QPushButton("Reports && Insights")
        self.btn_reports.clicked.connect(lambda: self._set_active_screen(2))

        self.btn_backup = QPushButton("Backups")
        self.btn_backup.clicked.connect(lambda: self._set_active_screen(3))

        self.btn_settings = QPushButton("Printer Settings")
        self.btn_settings.clicked.connect(lambda: self._set_active_screen(4))

        self.nav_buttons = [self.btn_pos, self.btn_products, self.btn_reports, self.btn_backup, self.btn_settings]

        for btn in self.nav_buttons:
            btn.setFixedHeight(40)
            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        # Sign Out Button
        btn_logout = QPushButton("Sign Out")
        btn_logout.setObjectName("btn_danger")
        btn_logout.setFixedHeight(36)
        btn_logout.clicked.connect(self._on_logout)
        nav_layout.addWidget(btn_logout)

        # ─── STACKED SCREENS ───
        self.stack = QStackedWidget()
        self.screen_pos = PosScreen(current_user=self.current_user)
        self.screen_products = ProductsScreen(current_user=self.current_user)
        self.screen_reports = ReportsScreen(current_user=self.current_user)
        self.screen_backup = BackupScreen(current_user=self.current_user)
        self.screen_settings = SettingsScreen()

        self.stack.addWidget(self.screen_pos)
        self.stack.addWidget(self.screen_products)
        self.stack.addWidget(self.screen_reports)
        self.stack.addWidget(self.screen_backup)
        self.stack.addWidget(self.screen_settings)


        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack, 1)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("PakPOS Ready | Local SQLite Database Active (WAL Mode)")

        self._set_active_screen(0)

    def _set_active_screen(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        widget = self.stack.widget(index)
        if hasattr(widget, "refresh") and callable(widget.refresh):
            try:
                widget.refresh()
            except Exception as e:
                logger.error("Error refreshing screen at index %d: %s", index, e)

        for idx, btn in enumerate(self.nav_buttons):
            if idx == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2d6cdf;
                        color: white;
                        font-weight: 700;
                        text-align: left;
                        padding-left: 16px;
                        border-radius: 6px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #9ca3af;
                        font-weight: 500;
                        text-align: left;
                        padding-left: 16px;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #22252c;
                        color: #e8eaed;
                    }
                """)

    def _on_logout(self) -> None:
        try:
            from pakpos.ui.windows.login_window import LoginWindow
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            login_window = LoginWindow()
            if app is not None:
                app._main_window = login_window

            login_window.show()
            self.close()
        except Exception as e:
            logger.critical("Error during logout: %s", e, exc_info=True)
            QMessageBox.critical(self, "Logout Error", f"Failed to log out: {e}")
