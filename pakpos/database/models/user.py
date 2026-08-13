"""User model with role-based access control."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from pakpos.database.engine import Base


class UserRole(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
    CASHIER = "cashier"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.CASHIER)
    pin: Mapped[str | None] = mapped_column(String(255), nullable=True)  # optional PIN hash

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"

    @property
    def is_owner(self) -> bool:
        return self.role == UserRole.OWNER

    @property
    def is_manager(self) -> bool:
        return self.role in (UserRole.OWNER, UserRole.MANAGER)

    @property
    def can_edit_prices(self) -> bool:
        return self.role in (UserRole.OWNER, UserRole.MANAGER)

    @property
    def can_view_reports(self) -> bool:
        return self.role in (UserRole.OWNER, UserRole.MANAGER)

    @property
    def can_manage_products(self) -> bool:
        return self.role in (UserRole.OWNER, UserRole.MANAGER)
