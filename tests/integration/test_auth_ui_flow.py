"""
Integration tests for authentication flow, UI feedback, and user creation via setup wizard.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from pakpos.config.settings import _get_app_data_dir, DB_PATH, paths
from pakpos.database.engine import init_database, get_session
from pakpos.database.models.setting import SettingKey
from pakpos.database.models.user import UserRole
from pakpos.services.auth_service import AuthService
from pakpos.ui.windows.login_window import LoginWindow
from pakpos.ui.windows.setup_wizard import SetupWizard
from pakpos.ui.windows.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    yield app


class TestAuthUIFlow:

    def test_correct_credentials_succeed(self, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        with get_session() as session:
            auth = AuthService(session)
            auth.create_user("owneruser", "Owner Name", "validpassword123", UserRole.OWNER)
            session.commit()

        with get_session() as session:
            auth = AuthService(session)
            user = auth.authenticate("owneruser", "validpassword123")
            assert user is not None
            assert user.username == "owneruser"
            assert user.role == UserRole.OWNER

    def test_incorrect_password_fails(self, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        with get_session() as session:
            auth = AuthService(session)
            auth.create_user("owneruser", "Owner Name", "validpassword123", UserRole.OWNER)
            session.commit()

        with get_session() as session:
            auth = AuthService(session)
            assert auth.authenticate("owneruser", "wrongpassword") is None

    def test_unknown_username_fails(self, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        with get_session() as session:
            auth = AuthService(session)
            assert auth.authenticate("nonexistentuser", "somepassword") is None

    def test_disabled_user_fails(self, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        with get_session() as session:
            auth = AuthService(session)
            user = auth.create_user("disableduser", "Disabled User", "validpassword123", UserRole.CASHIER)
            auth.deactivate_user(user.id)
            session.commit()

        with get_session() as session:
            auth = AuthService(session)
            assert auth.authenticate("disableduser", "validpassword123") is None

    def test_setup_wizard_created_user_can_authenticate(self, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        with get_session() as session:
            auth = AuthService(session)
            auth.create_user("wizardadmin", "Wizard Admin", "wizardpass123", UserRole.OWNER)
            session.commit()

        with get_session() as session:
            auth = AuthService(session)
            user = auth.authenticate("wizardadmin", "wizardpass123")
            assert user is not None
            assert user.username == "wizardadmin"

    def test_login_window_empty_fields_warning(self, qapp, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        login = LoginWindow()
        login.input_username.setText("")
        login.input_password.setText("")

        with patch("pakpos.ui.windows.login_window.QMessageBox.warning") as mock_warn:
            login._on_login()
            mock_warn.assert_called_once()

    def test_login_window_invalid_credentials_error(self, qapp, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        login = LoginWindow()
        login.input_username.setText("nonexistent")
        login.input_password.setText("wrongpassword")

        with patch("pakpos.ui.windows.login_window.QMessageBox.critical") as mock_crit:
            login._on_login()
            mock_crit.assert_called_once()

    def test_login_window_success_opens_main_window(self, qapp, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        with get_session() as session:
            auth = AuthService(session)
            auth.create_user("validuser", "Valid User", "validpass123", UserRole.OWNER)
            session.commit()

        login = LoginWindow()
        login.input_username.setText("validuser")
        login.input_password.setText("validpass123")

        login._on_login()
        app = QApplication.instance()
        assert app is not None
        assert hasattr(app, "_main_window")
        assert isinstance(app._main_window, MainWindow)
        assert app._main_window.current_user.username == "validuser"

    def test_login_window_catches_and_logs_unexpected_exception(self, qapp, tmp_path):
        db_url = f"sqlite:///{tmp_path / 'pos_test.db'}"
        init_database(db_url)

        login = LoginWindow()
        login.input_username.setText("admin")
        login.input_password.setText("password123")

        with patch("pakpos.ui.windows.login_window.AuthService") as mock_auth_cls:
            mock_auth = MagicMock()
            mock_auth.authenticate.side_effect = RuntimeError("Database connection interrupted")
            mock_auth_cls.return_value = mock_auth

            with patch("pakpos.ui.windows.login_window.QMessageBox.critical") as mock_crit, \
                 patch("pakpos.ui.windows.login_window.logger.critical") as mock_log:
                login._on_login()
                mock_crit.assert_called_once()
                mock_log.assert_called_once()

    def test_database_path_uses_programdata_on_windows(self):
        with patch("platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"PROGRAMDATA": "C:\\ProgramData"}):
                app_data_dir = _get_app_data_dir()
                assert "ProgramData" in str(app_data_dir)
                assert "Program Files" not in str(app_data_dir)
