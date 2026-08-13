"""
LoginWindow — Authenticate cashier/owner.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame
)

from pakpos.config.settings import APP_NAME, APP_VERSION
from pakpos.database.engine import get_session
from pakpos.services.auth_service import AuthService
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class LoginWindow(QMainWindow):
    """
    Application Login Window.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Sign In")
        self.setFixedSize(400, 420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)

        # Card container
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        # Title Banner
        title = QLabel("PakPOS")
        title.setObjectName("label_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Offline Retail Point of Sale")
        subtitle.setObjectName("label_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(20)

        # Form
        form = QFormLayout()
        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Enter username")

        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_password.setPlaceholderText("Enter password")
        self.input_password.returnPressed.connect(self._on_login)

        form.addRow("Username:", self.input_username)
        form.addRow("Password:", self.input_password)
        card_layout.addLayout(form)
        card_layout.addSpacing(20)

        # Login Button
        btn_login = QPushButton("Sign In (Enter)")
        btn_login.setObjectName("btn_success")
        btn_login.clicked.connect(self._on_login)
        card_layout.addWidget(btn_login)

        layout.addWidget(card)

    def _on_login(self) -> None:
        username = self.input_username.text().strip()
        password = self.input_password.text()

        if not username or not password:
            QMessageBox.warning(self, "Sign In Failed", "Please enter both username and password.")
            return

        try:
            logger.info("Sign-in attempt initiated for username: %s", username)
            with get_session() as session:
                auth = AuthService(session)
                user = auth.authenticate(username, password)
                if user is None:
                    logger.warning("Sign-in failed for username: %s (invalid credentials or inactive)", username)
                    QMessageBox.critical(
                        self, "Sign In Failed", "Invalid username or password.\n\nPlease check your credentials."
                    )
                    self.input_password.clear()
                    return

                logger.info("User '%s' authenticated successfully (role=%s).", user.username, user.role)

            # Open Main Window and prevent GC of window reference
            from pakpos.ui.windows.main_window import MainWindow
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            main_window = MainWindow(current_user=user)
            if app is not None:
                app._main_window = main_window

            main_window.show()
            self.close()

        except Exception as e:
            logger.critical("Unexpected error during login for user '%s': %s", username, e, exc_info=True)
            from pakpos.config.settings import paths
            QMessageBox.critical(
                self,
                "Sign In Error",
                f"An unexpected error occurred while signing in:\n{e}\n\nPlease check the log file at:\n{paths.logs}"
            )
