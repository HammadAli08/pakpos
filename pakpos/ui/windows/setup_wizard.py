"""
SetupWizard — First-Run Setup Wizard.

Guided 3-step setup:
1. Welcome & Shop Profile (Name, Address, Phone)
2. Create Admin Account (Username, Password)
3. Confirm & Finish
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QMessageBox
)

from pakpos.database.engine import get_session
from pakpos.database.models.setting import SettingKey
from pakpos.database.models.user import UserRole
from pakpos.services.auth_service import AuthService
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class ShopInfoPage(QWizardPage):
    """Step 1: Shop details."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("PakPOS Setup — Step 1: Shop Details")
        self.setSubTitle("Enter your shop name and contact details for printed receipts.")

        layout = QFormLayout(self)
        self.input_shop_name = QLineEdit()
        self.input_shop_name.setPlaceholderText("e.g. Al-Madina Super Store")

        self.input_address = QLineEdit()
        self.input_address.setPlaceholderText("e.g. Main Market, Gulberg, Lahore")

        self.input_phone = QLineEdit()
        self.input_phone.setPlaceholderText("e.g. 0300-1234567")

        form_layout = layout
        form_layout.addRow("Shop Name *:", self.input_shop_name)
        form_layout.addRow("Address *:", self.input_address)
        form_layout.addRow("Phone Number *:", self.input_phone)

        self.registerField("shop_name*", self.input_shop_name)
        self.registerField("address*", self.input_address)
        self.registerField("phone*", self.input_phone)


class AdminAccountPage(QWizardPage):
    """Step 2: Admin user account."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("PakPOS Setup — Step 2: Create Owner Account")
        self.setSubTitle("Create the main administrator account. Password must be at least 6 characters.")

        layout = QFormLayout(self)
        self.input_username = QLineEdit("admin")
        self.input_fullname = QLineEdit()
        self.input_fullname.setPlaceholderText("e.g. Haji Muhammad Ali")

        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.input_confirm = QLineEdit()
        self.input_confirm.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addRow("Username *:", self.input_username)
        layout.addRow("Full Name *:", self.input_fullname)
        layout.addRow("Password (min 6 chars) *:", self.input_password)
        layout.addRow("Confirm Password *:", self.input_confirm)

        self.registerField("username*", self.input_username)
        self.registerField("fullname*", self.input_fullname)
        self.registerField("password*", self.input_password)

    def validatePage(self) -> bool:
        pwd = self.input_password.text()
        conf = self.input_confirm.text()
        if len(pwd) < 6:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters.")
            return False
        if pwd != conf:
            QMessageBox.warning(self, "Validation Error", "Passwords do not match.")
            return False
        return True


class SetupWizard(QWizard):
    """First-Run Wizard."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PakPOS — First-Run Setup Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.resize(550, 400)

        self.addPage(ShopInfoPage())
        self.addPage(AdminAccountPage())

        self.finished.connect(self._on_finished)

    def _on_finished(self, result: int) -> None:
        if result == QWizard.DialogCode.Accepted:
            shop_name = self.field("shop_name")
            address = self.field("address")
            phone = self.field("phone")
            username = self.field("username")
            fullname = self.field("fullname")
            password = self.field("password")

            with get_session() as session:
                # Save settings
                from pakpos.database.models.setting import Setting
                session.add(Setting(key=SettingKey.SHOP_NAME, value=shop_name))
                session.add(Setting(key=SettingKey.SHOP_ADDRESS, value=address))
                session.add(Setting(key=SettingKey.SHOP_PHONE, value=phone))

                # Create owner account
                auth = AuthService(session)
                auth.create_user(username, fullname, password, UserRole.OWNER)

                session.commit()
                logger.info("Setup wizard completed successfully.")

            # Launch Login Window
            from pakpos.ui.windows.login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.show()
