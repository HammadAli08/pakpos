"""
Unit tests for authentication service.
"""
from __future__ import annotations

import pytest
from pakpos.services.auth_service import AuthService
from pakpos.database.models.user import UserRole
from pakpos.utils.validators import ValidationError


class TestAuthService:

    def test_create_user_succeeds(self, db_session):
        auth = AuthService(db_session)
        user = auth.create_user("shopowner", "Shop Owner", "securepass123", UserRole.OWNER)
        assert user.id is not None
        assert user.username == "shopowner"
        assert user.role == UserRole.OWNER
        assert "securepass123" not in user.password_hash  # never stored plaintext

    def test_passwords_are_hashed(self, db_session):
        auth = AuthService(db_session)
        user = auth.create_user("testuser", "Test User", "mypassword")
        assert user.password_hash != "mypassword"
        assert len(user.password_hash) > 20

    def test_duplicate_username_raises(self, db_session):
        auth = AuthService(db_session)
        auth.create_user("duplicate", "User One", "pass123")
        with pytest.raises(ValueError, match="already taken"):
            auth.create_user("duplicate", "User Two", "pass456")

    def test_authenticate_correct_password(self, db_session):
        auth = AuthService(db_session)
        auth.create_user("ali", "Ali Khan", "correctpass")
        user = auth.authenticate("ali", "correctpass")
        assert user is not None
        assert user.username == "ali"

    def test_authenticate_wrong_password_returns_none(self, db_session):
        auth = AuthService(db_session)
        auth.create_user("bob", "Bob", "rightpass")
        result = auth.authenticate("bob", "wrongpass")
        assert result is None

    def test_authenticate_unknown_user_returns_none(self, db_session):
        auth = AuthService(db_session)
        result = auth.authenticate("nobody", "pass")
        assert result is None

    def test_authenticate_inactive_user_returns_none(self, db_session):
        auth = AuthService(db_session)
        user = auth.create_user("inactive", "Inactive", "pass123")
        auth.deactivate_user(user.id)
        result = auth.authenticate("inactive", "pass123")
        assert result is None

    def test_short_password_raises(self, db_session):
        auth = AuthService(db_session)
        with pytest.raises(ValidationError):
            auth.create_user("shortpass", "Test", "abc")

    def test_has_any_user_false_initially(self, db_session):
        auth = AuthService(db_session)
        assert auth.has_any_user() is False

    def test_has_any_user_true_after_creation(self, db_session):
        auth = AuthService(db_session)
        auth.create_user("first", "First User", "password123")
        assert auth.has_any_user() is True

    def test_change_password_success(self, db_session):
        auth = AuthService(db_session)
        user = auth.create_user("changer", "Change User", "oldpass123")
        result = auth.change_password(user.id, "oldpass123", "newpass456")
        assert result is True
        # Old password no longer works
        assert auth.authenticate("changer", "oldpass123") is None
        # New password works
        assert auth.authenticate("changer", "newpass456") is not None

    def test_user_role_permissions(self, db_session):
        auth = AuthService(db_session)
        owner = auth.create_user("owner1", "Owner", "pass123", UserRole.OWNER)
        manager = auth.create_user("mgr1", "Manager", "pass123", UserRole.MANAGER)
        cashier = auth.create_user("cash1", "Cashier", "pass123", UserRole.CASHIER)

        assert owner.is_owner is True
        assert owner.can_edit_prices is True
        assert owner.can_view_reports is True

        assert manager.is_owner is False
        assert manager.is_manager is True
        assert manager.can_edit_prices is True

        assert cashier.is_owner is False
        assert cashier.is_manager is False
        assert cashier.can_edit_prices is False
        assert cashier.can_view_reports is False
