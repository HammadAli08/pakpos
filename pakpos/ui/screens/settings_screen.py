"""
SettingsScreen — Application configuration screen.
Provides full control over printer backends, hardware parameters, shop details, and receipt options.
Persists all choices cleanly into the SQLite settings table via SettingRepository.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QSpinBox, QGroupBox,
    QMessageBox, QScrollArea, QFrame
)

from pakpos.database.engine import get_session
from pakpos.database.repositories.setting_repo import SettingRepository
from pakpos.database.models.setting import SettingKey
from pakpos.hardware.printer.printer_manager import PrinterManager
from pakpos.ui.dialogs.printer_test_dialog import PrinterTestDialog
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsScreen(QWidget):
    """Configuration management UI for PakPOS."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.manager = PrinterManager()
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Title Banner
        lbl_title = QLabel("Application & Printer Settings")
        lbl_title.setObjectName("label_title")
        main_layout.addWidget(lbl_title)

        # Scroll Area for Form Sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # ─── SECTION 1: Shop Information ───
        box_shop = QGroupBox("Shop Information & Header")
        shop_layout = QVBoxLayout(box_shop)

        self.txt_shop_name = QLineEdit()
        self.txt_shop_name.setPlaceholderText("e.g. PakPOS Retail Superstore")

        self.txt_shop_address = QLineEdit()
        self.txt_shop_address.setPlaceholderText("e.g. Main Commercial Market, Lahore")

        self.txt_shop_phone = QLineEdit()
        self.txt_shop_phone.setPlaceholderText("e.g. 0300-1234567")

        self.txt_tax_number = QLineEdit()
        self.txt_tax_number.setPlaceholderText("e.g. NTN 1234567-8 / STRN 3277874")

        self.txt_receipt_footer = QLineEdit()
        self.txt_receipt_footer.setPlaceholderText("e.g. Thank you for shopping with us!")

        shop_layout.addWidget(QLabel("Shop Name:"))
        shop_layout.addWidget(self.txt_shop_name)
        shop_layout.addWidget(QLabel("Address:"))
        shop_layout.addWidget(self.txt_shop_address)
        shop_layout.addWidget(QLabel("Phone Number(s):"))
        shop_layout.addWidget(self.txt_shop_phone)
        shop_layout.addWidget(QLabel("Tax / NTN Number:"))
        shop_layout.addWidget(self.txt_tax_number)
        shop_layout.addWidget(QLabel("Receipt Footer Message:"))
        shop_layout.addWidget(self.txt_receipt_footer)

        layout.addWidget(box_shop)

        # ─── SECTION 2: Printer Backend & Connection ───
        box_printer = QGroupBox("Receipt Printer Backend Configuration")
        prn_layout = QVBoxLayout(box_printer)

        self.combo_backend = QComboBox()
        self.combo_backend.addItem("Mock / File Output (Dev & Testing)", "mock")
        self.combo_backend.addItem("Thermal ESC/POS Printer (USB / Network)", "thermal_escpos")
        self.combo_backend.addItem("Windows System Printer (A4 / Driver)", "windows_a4")
        self.combo_backend.addItem("Export PDF Files Only", "pdf")
        self.combo_backend.currentIndexChanged.connect(self._on_backend_changed)

        self.combo_paper_width = QComboBox()
        self.combo_paper_width.addItem("80mm (Standard POS Receipt - 48 columns)", "80")
        self.combo_paper_width.addItem("58mm (Compact POS Receipt - 40 columns)", "58")

        self.combo_connection = QComboBox()
        self.combo_connection.addItem("USB Thermal Printer", "usb")
        self.combo_connection.addItem("Network / Ethernet IP Printer", "network")
        self.combo_connection.currentIndexChanged.connect(self._on_connection_changed)

        prn_layout.addWidget(QLabel("Active Printer Driver:"))
        prn_layout.addWidget(self.combo_backend)
        prn_layout.addWidget(QLabel("Paper Width:"))
        prn_layout.addWidget(self.combo_paper_width)
        prn_layout.addWidget(QLabel("Connection Interface:"))
        prn_layout.addWidget(self.combo_connection)

        # Sub-group: USB Settings
        self.box_usb = QGroupBox("USB Hardware Parameters")
        usb_lay = QHBoxLayout(self.box_usb)
        self.txt_usb_vendor = QLineEdit("0x04b8")
        self.txt_usb_product = QLineEdit("0x0e15")
        usb_lay.addWidget(QLabel("Vendor ID (Hex):"))
        usb_lay.addWidget(self.txt_usb_vendor)
        usb_lay.addWidget(QLabel("Product ID (Hex):"))
        usb_lay.addWidget(self.txt_usb_product)
        prn_layout.addWidget(self.box_usb)

        # Sub-group: Network Settings
        self.box_net = QGroupBox("Network / Ethernet Parameters")
        net_lay = QHBoxLayout(self.box_net)
        self.txt_net_host = QLineEdit("192.168.1.100")
        self.txt_net_port = QLineEdit("9100")
        net_lay.addWidget(QLabel("IP Address:"))
        net_lay.addWidget(self.txt_net_host)
        net_lay.addWidget(QLabel("Port:"))
        net_lay.addWidget(self.txt_net_port)
        prn_layout.addWidget(self.box_net)

        # Sub-group: Windows Printers
        self.box_win = QGroupBox("Windows System Printer Selection")
        win_lay = QHBoxLayout(self.box_win)
        self.combo_win_printers = QComboBox()
        btn_detect_printers = QPushButton("Refresh Printers")
        btn_detect_printers.clicked.connect(self._on_detect_printers)
        win_lay.addWidget(self.combo_win_printers, stretch=1)
        win_lay.addWidget(btn_detect_printers)
        prn_layout.addWidget(self.box_win)

        layout.addWidget(box_printer)

        # ─── SECTION 3: Receipt & Hardware Options ───
        box_options = QGroupBox("Receipt Features & Hardware Controls")
        opt_layout = QVBoxLayout(box_options)

        self.chk_auto_cut = QCheckBox("Enable Automatic Paper Cutter (ESC/POS)")
        self.chk_open_drawer = QCheckBox("Automatically Open Cash Drawer on Cash Sale")
        self.chk_print_logo = QCheckBox("Include Shop Logo Header on Receipts")
        self.chk_print_qr = QCheckBox("Print Verification QR Code on Receipts")

        copies_layout = QHBoxLayout()
        copies_layout.addWidget(QLabel("Default Receipt Copies:"))
        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 5)
        self.spin_copies.setValue(1)
        copies_layout.addWidget(self.spin_copies)
        copies_layout.addStretch()

        opt_layout.addWidget(self.chk_auto_cut)
        opt_layout.addWidget(self.chk_open_drawer)
        opt_layout.addWidget(self.chk_print_logo)
        opt_layout.addWidget(self.chk_print_qr)
        opt_layout.addLayout(copies_layout)

        layout.addWidget(box_options)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # ─── Bottom Actions Bar ───
        actions_layout = QHBoxLayout()

        btn_test = QPushButton("Test Printer & Layouts")
        btn_test.setObjectName("btn_secondary")
        btn_test.clicked.connect(self._on_test_dialog)
        actions_layout.addWidget(btn_test)

        actions_layout.addStretch()

        btn_save = QPushButton("Save All Settings")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self.save_settings)
        actions_layout.addWidget(btn_save)

        main_layout.addLayout(actions_layout)

    def _on_backend_changed(self) -> None:
        backend_key = self.combo_backend.currentData()
        self.combo_connection.setVisible(backend_key == "thermal_escpos")
        self._on_connection_changed()

    def _on_connection_changed(self) -> None:
        backend_key = self.combo_backend.currentData()
        conn_key = self.combo_connection.currentData()

        show_esc = (backend_key == "thermal_escpos")
        self.box_usb.setVisible(show_esc and conn_key == "usb")
        self.box_net.setVisible(show_esc and conn_key == "network")
        self.box_win.setVisible(backend_key == "windows_a4")

    def _on_detect_printers(self) -> None:
        self.combo_win_printers.clear()
        printers = self.manager.discover_windows_printers()
        if printers:
            for p in printers:
                self.combo_win_printers.addItem(p, p)
        else:
            self.combo_win_printers.addItem("(No Windows printers detected)", "")

    def load_settings(self) -> None:
        try:
            with get_session() as session:
                repo = SettingRepository(session)
                s = repo.get_printer_settings()

                self.txt_shop_name.setText(s.get(SettingKey.SHOP_NAME, "PakPOS Retail Store"))
                self.txt_shop_address.setText(s.get(SettingKey.SHOP_ADDRESS, "Main Market, Lahore"))
                self.txt_shop_phone.setText(s.get(SettingKey.SHOP_PHONE, "0300-1234567"))
                self.txt_tax_number.setText(s.get(SettingKey.TAX_NUMBER, ""))
                self.txt_receipt_footer.setText(s.get(SettingKey.RECEIPT_FOOTER, "Thank you for shopping with us!"))

                # Set dropdown values
                b_idx = self.combo_backend.findData(s.get(SettingKey.PRINTER_BACKEND, "mock"))
                if b_idx >= 0:
                    self.combo_backend.setCurrentIndex(b_idx)

                w_idx = self.combo_paper_width.findData(s.get(SettingKey.PRINTER_PAPER_WIDTH, "80"))
                if w_idx >= 0:
                    self.combo_paper_width.setCurrentIndex(w_idx)

                c_idx = self.combo_connection.findData(s.get(SettingKey.PRINTER_CONNECTION, "usb"))
                if c_idx >= 0:
                    self.combo_connection.setCurrentIndex(c_idx)

                self.txt_usb_vendor.setText(s.get(SettingKey.PRINTER_USB_VENDOR, "0x04b8"))
                self.txt_usb_product.setText(s.get(SettingKey.PRINTER_USB_PRODUCT, "0x0e15"))
                self.txt_net_host.setText(s.get(SettingKey.PRINTER_NETWORK_HOST, "192.168.1.100"))
                self.txt_net_port.setText(s.get(SettingKey.PRINTER_NETWORK_PORT, "9100"))

                self.chk_auto_cut.setChecked(s.get(SettingKey.PRINTER_AUTO_CUT, "true").lower() == "true")
                self.chk_open_drawer.setChecked(s.get(SettingKey.PRINTER_OPEN_DRAWER, "true").lower() == "true")
                self.chk_print_logo.setChecked(s.get(SettingKey.PRINTER_PRINT_LOGO, "false").lower() == "true")
                self.chk_print_qr.setChecked(s.get(SettingKey.PRINTER_PRINT_QR, "false").lower() == "true")
                self.spin_copies.setValue(int(s.get(SettingKey.PRINTER_COPIES, "1")))

                self._on_detect_printers()
                win_name = s.get(SettingKey.PRINTER_NAME, "")
                w_prn_idx = self.combo_win_printers.findData(win_name)
                if w_prn_idx >= 0:
                    self.combo_win_printers.setCurrentIndex(w_prn_idx)

                self._on_backend_changed()
        except Exception as e:
            logger.error("Failed to load settings in SettingsScreen: %s", e, exc_info=True)

    def save_settings(self) -> None:
        try:
            with SessionLocal() as session:
                repo = SettingRepository(session)

                repo.set_value(SettingKey.SHOP_NAME, self.txt_shop_name.text().strip())
                repo.set_value(SettingKey.SHOP_ADDRESS, self.txt_shop_address.text().strip())
                repo.set_value(SettingKey.SHOP_PHONE, self.txt_shop_phone.text().strip())
                repo.set_value(SettingKey.TAX_NUMBER, self.txt_tax_number.text().strip())
                repo.set_value(SettingKey.RECEIPT_FOOTER, self.txt_receipt_footer.text().strip())

                repo.set_value(SettingKey.PRINTER_BACKEND, self.combo_backend.currentData())
                repo.set_value(SettingKey.PRINTER_PAPER_WIDTH, self.combo_paper_width.currentData())
                repo.set_value(SettingKey.PRINTER_CONNECTION, self.combo_connection.currentData())

                repo.set_value(SettingKey.PRINTER_USB_VENDOR, self.txt_usb_vendor.text().strip())
                repo.set_value(SettingKey.PRINTER_USB_PRODUCT, self.txt_usb_product.text().strip())
                repo.set_value(SettingKey.PRINTER_NETWORK_HOST, self.txt_net_host.text().strip())
                repo.set_value(SettingKey.PRINTER_NETWORK_PORT, self.txt_net_port.text().strip())
                repo.set_value(SettingKey.PRINTER_NAME, self.combo_win_printers.currentData() or "")

                repo.set_value(SettingKey.PRINTER_AUTO_CUT, "true" if self.chk_auto_cut.isChecked() else "false")
                repo.set_value(SettingKey.PRINTER_OPEN_DRAWER, "true" if self.chk_open_drawer.isChecked() else "false")
                repo.set_value(SettingKey.PRINTER_PRINT_LOGO, "true" if self.chk_print_logo.isChecked() else "false")
                repo.set_value(SettingKey.PRINTER_PRINT_QR, "true" if self.chk_print_qr.isChecked() else "false")
                repo.set_value(SettingKey.PRINTER_COPIES, str(self.spin_copies.value()))

                session.commit()

                # Reload PrinterManager singleton
                self.manager.load_from_settings(session)

                QMessageBox.information(self, "Settings Saved", "Application and printer settings saved successfully.")
        except Exception as e:
            logger.error("Failed to save settings: %s", e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"Failed to save settings:\n{e}")

    def _on_test_dialog(self) -> None:
        dlg = PrinterTestDialog(parent=self)
        dlg.exec()
