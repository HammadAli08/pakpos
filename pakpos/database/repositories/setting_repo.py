"""SettingRepository — Access and manage application key-value settings."""
from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session
from pakpos.database.models.setting import Setting, SettingKey
from pakpos.database.repositories.base import BaseRepository


class SettingRepository(BaseRepository[Setting]):
    """Repository for key-value application settings."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Setting)

    def get_value(self, key: str, default: str | None = None) -> str | None:
        """Get setting value by key string."""
        setting = self._session.query(Setting).filter(Setting.key == key).first()
        if setting and setting.value is not None:
            return setting.value
        return default

    def set_value(self, key: str, value: str | None, description: str | None = None) -> Setting:
        """Set or update setting key-value pair."""
        setting = self._session.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = str(value) if value is not None else None
            if description:
                setting.description = description
        else:
            setting = Setting(key=key, value=str(value) if value is not None else None, description=description)
            self._session.add(setting)
        self._session.flush()
        return setting

    def get_all_settings(self) -> dict[str, str]:
        """Return dict of all key-values."""
        settings = self._session.query(Setting).all()
        return {s.key: s.value or "" for s in settings}

    def get_printer_settings(self) -> dict[str, str]:
        """Return dictionary of all printer settings with defaults."""
        all_s = self.get_all_settings()
        return {
            SettingKey.PRINTER_BACKEND: all_s.get(SettingKey.PRINTER_BACKEND, "mock"),
            SettingKey.PRINTER_NAME: all_s.get(SettingKey.PRINTER_NAME, ""),
            SettingKey.PRINTER_TYPE: all_s.get(SettingKey.PRINTER_TYPE, "thermal"),
            SettingKey.PRINTER_PAPER_WIDTH: all_s.get(SettingKey.PRINTER_PAPER_WIDTH, "80"),
            SettingKey.PRINTER_CONNECTION: all_s.get(SettingKey.PRINTER_CONNECTION, "usb"),
            SettingKey.PRINTER_USB_VENDOR: all_s.get(SettingKey.PRINTER_USB_VENDOR, "0x04b8"),
            SettingKey.PRINTER_USB_PRODUCT: all_s.get(SettingKey.PRINTER_USB_PRODUCT, "0x0e15"),
            SettingKey.PRINTER_NETWORK_HOST: all_s.get(SettingKey.PRINTER_NETWORK_HOST, "192.168.1.100"),
            SettingKey.PRINTER_NETWORK_PORT: all_s.get(SettingKey.PRINTER_NETWORK_PORT, "9100"),
            SettingKey.PRINTER_AUTO_CUT: all_s.get(SettingKey.PRINTER_AUTO_CUT, "true"),
            SettingKey.PRINTER_OPEN_DRAWER: all_s.get(SettingKey.PRINTER_OPEN_DRAWER, "true"),
            SettingKey.PRINTER_PRINT_LOGO: all_s.get(SettingKey.PRINTER_PRINT_LOGO, "false"),
            SettingKey.PRINTER_PRINT_QR: all_s.get(SettingKey.PRINTER_PRINT_QR, "false"),
            SettingKey.PRINTER_COPIES: all_s.get(SettingKey.PRINTER_COPIES, "1"),
            SettingKey.SHOP_NAME: all_s.get(SettingKey.SHOP_NAME, "PakPOS Retail Store"),
            SettingKey.SHOP_ADDRESS: all_s.get(SettingKey.SHOP_ADDRESS, "Main Market, Lahore"),
            SettingKey.SHOP_PHONE: all_s.get(SettingKey.SHOP_PHONE, "0300-1234567"),
            SettingKey.RECEIPT_FOOTER: all_s.get(SettingKey.RECEIPT_FOOTER, "Thank you for shopping with us!"),
            SettingKey.TAX_NUMBER: all_s.get(SettingKey.TAX_NUMBER, ""),
            SettingKey.SHOP_LOGO_PATH: all_s.get(SettingKey.SHOP_LOGO_PATH, ""),
        }
