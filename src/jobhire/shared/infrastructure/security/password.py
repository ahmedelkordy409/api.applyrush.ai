"""
Password hashing and verification services.
"""

import hashlib
import secrets
from typing import Tuple
import structlog

logger = structlog.get_logger(__name__)


class PasswordService:
    """Service for password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with salt."""
        salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return f"{salt}:{password_hash.hex()}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, stored_hash = hashed.split(':')
            password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
            return stored_hash == password_hash.hex()
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def generate_password(length: int = 12) -> str:
        """Generate a secure random password."""
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """Validate password strength."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"

        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"

        return True, "Password is strong"