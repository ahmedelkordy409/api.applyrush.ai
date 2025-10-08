"""
Encryption and decryption services.
"""

import base64
import hashlib
import secrets
from typing import Tuple, Optional
import structlog

logger = structlog.get_logger(__name__)


class EncryptionService:
    """Service for data encryption and decryption."""

    def __init__(self, secret_key: Optional[str] = None):
        """Initialize with a secret key."""
        if secret_key:
            self.key = self._derive_key(secret_key)
        else:
            self.key = secrets.token_bytes(32)

    @staticmethod
    def _derive_key(password: str) -> bytes:
        """Derive encryption key from password."""
        return hashlib.pbkdf2_hmac('sha256', password.encode(), b'salt_', 100000)

    def encrypt(self, data: str) -> str:
        """Encrypt data using simple XOR encryption."""
        try:
            data_bytes = data.encode('utf-8')
            encrypted = bytearray()

            for i, byte in enumerate(data_bytes):
                key_byte = self.key[i % len(self.key)]
                encrypted.append(byte ^ key_byte)

            # Add random salt for uniqueness
            salt = secrets.token_bytes(16)
            result = salt + bytes(encrypted)
            return base64.b64encode(result).decode('utf-8')

        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))

            # Extract salt (first 16 bytes)
            salt = encrypted_bytes[:16]
            actual_data = encrypted_bytes[16:]

            decrypted = bytearray()
            for i, byte in enumerate(actual_data):
                key_byte = self.key[i % len(self.key)]
                decrypted.append(byte ^ key_byte)

            return decrypted.decode('utf-8')

        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise

    @staticmethod
    def hash_data(data: str) -> str:
        """Create a hash of data."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        return f"jobhire_{secrets.token_urlsafe(32)}"

    def encrypt_sensitive_field(self, value: str) -> str:
        """Encrypt a sensitive field like email or phone."""
        if not value:
            return value
        return self.encrypt(value)

    def decrypt_sensitive_field(self, encrypted_value: str) -> str:
        """Decrypt a sensitive field."""
        if not encrypted_value:
            return encrypted_value
        return self.decrypt(encrypted_value)