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
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    Main Application Window container with tab/sidebar navigation.
    """

    def __init__(self, current_user=None) -> None:
        super().__init__()
        self.current_user = current_user
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Offline POS")
        self.resize(1180, 720)
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
        sidebar.setFixedWidth(200)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(10, 15, 10, 15)

        # App Logo Label
        lbl_app = QLabel("PakPOS")
        lbl_app.setObjectName("label_title")
        lbl_app.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(lbl_app)

        lbl_role = QLabel(f"User: {self.current_user.username if self.current_user else 'Guest'}")
        lbl_role.setObjectName("label_subtitle")
        lbl_role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(lbl_role)
        nav_layout.addSpacing(20)

        # Navigation Buttons
        self.btn_pos = QPushButton("Checkout (F1)")
        self.btn_pos.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        self.btn_products = QPushButton("Products & Stock")
        self.btn_products.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        self.btn_reports = QPushButton("Reports & Insights")
        self.btn_reports.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        self.btn_backup = QPushButton("Backups")
        self.btn_backup.clicked.connect(lambda: self.stack.setCurrentIndex(3))

        nav_layout.addWidget(self.btn_pos)
        nav_layout.addWidget(self.btn_products)
        nav_layout.addWidget(self.btn_reports)
        nav_layout.addWidget(self.btn_backup)
        nav_layout.addStretch()

        # Sign Out Button
        btn_logout = QPushButton("Sign Out")
        btn_logout.setObjectName("btn_danger")
        btn_logout.clicked.connect(self._on_logout)
        nav_layout.addWidget(btn_logout)

        # ─── STACKED SCREENS ───
        self.stack = QStackedWidget()
        self.screen_pos = PosScreen(current_user=self.current_user)
        self.screen_products = ProductsScreen(current_user=self.current_user)
        self.screen_reports = ReportsScreen(current_user=self.current_user)
        self.screen_backup = BackupScreen(current_user=self.current_user)

        self.stack.addWidget(self.screen_pos)
        self.stack.addWidget(self.screen_products)
        self.stack.addWidget(self.screen_reports)
        self.stack.addWidget(self.screen_backup)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("PakPOS Ready | Local SQLite Database Active (WAL Mode)")

    def _on_logout(self) -> None:
        from pakpos.ui.windows.login_window import LoginWindow
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()
