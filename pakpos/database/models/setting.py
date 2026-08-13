"""Application Settings stored in database."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pakpos.database.engine import Base


class SettingKey:
    """Well-known keys for application settings."""
    SHOP_NAME = "shop_name"
    SHOP_ADDRESS = "shop_address"
    SHOP_PHONE = "shop_phone"
    RECEIPT_PRINTER = "receipt_printer"
    RECEIPT_FOOTER = "receipt_footer"
    TAX_NUMBER = "tax_number"


class Setting(Base):
    """Key-value store for application settings."""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Setting key={self.key!r} value={self.value!r}>"
