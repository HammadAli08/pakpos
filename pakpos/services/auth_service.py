"""
Authentication Service.
Handles password hashing (bcrypt), user creation, and login.
Never stores plaintext passwords. Never logs passwords.
"""
from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
from sqlalchemy.orm import Session

from pakpos.database.models.user import User, UserRole
from pakpos.utils.logger import get_logger
from pakpos.utils.validators import validate_name, ValidationError

logger = get_logger(__name__)

BCRYPT_ROUNDS = 12


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost factor 12."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        if not password or not hashed:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as e:
        logger.error("Bcrypt password verification failed with error: %s", e, exc_info=True)
        return False


class AuthService:
    """Handles user authentication and account management."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(
        self,
        username: str,
        full_name: str,
        password: str,
        role: str = UserRole.CASHIER,
    ) -> User:
        """Create a new user. Raises ValueError if username exists."""
        username = username.strip().lower()
        if not username:
            raise ValidationError("username", "Cannot be empty")
        full_name = validate_name(full_name, "full_name")

        if len(password) < 6:
            raise ValidationError("password", "Minimum 6 characters")

        existing = self._session.query(User).filter(User.username == username).first()
        if existing:
            raise ValueError(f"Username '{username}' is already taken")

        user = User(
            username=username,
            full_name=full_name,
            password_hash=_hash_password(password),
            role=role,
            is_active=True,
        )
        self._session.add(user)
        self._session.flush()
        logger.info("Created user: %s (role=%s)", username, role)
        return user

    def authenticate(self, username: str, password: str) -> User | None:
        """
        Verify credentials. Returns User on success, None on failure.
        Never raise on bad credentials — return None silently.
        """
        username = username.strip().lower()
        user = (
            self._session.query(User)
            .filter(User.username == username, User.is_active == True)  # noqa: E712
            .first()
        )
        if user is None:
            logger.warning("Login attempt for unknown user: %s", username)
            return None
        if not _verify_password(password, user.password_hash):
            logger.warning("Failed login attempt for user: %s", username)
            return None
        user.last_login = datetime.now(timezone.utc)
        self._session.commit()
        logger.info("User logged in: %s", username)
        return user

    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        user = self._session.get(User, user_id)
        if user is None:
            return False
        if not _verify_password(old_password, user.password_hash):
            return False
        if len(new_password) < 6:
            raise ValidationError("password", "Minimum 6 characters")
        user.password_hash = _hash_password(new_password)
        self._session.flush()
        logger.info("Password changed for user_id=%d", user_id)
        return True

    def has_any_user(self) -> bool:
        return self._session.query(User).count() > 0

    def deactivate_user(self, user_id: int) -> None:
        user = self._session.get(User, user_id)
        if user:
            user.is_active = False
            self._session.flush()

    def get_all_users(self) -> list[User]:
        return self._session.query(User).filter(User.is_active == True).all()  # noqa: E712
