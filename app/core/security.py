"""
Security utilities for authentication and authorization
Handles password hashing, JWT tokens, and security middleware
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from app.core.config import settings
import secrets
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token with longer expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def generate_verification_token() -> str:
    """Generate a secure random verification token"""
    return secrets.token_urlsafe(32)


def generate_reset_password_token() -> str:
    """Generate a secure random password reset token"""
    return secrets.token_urlsafe(32)


class PermissionChecker:
    """Check user permissions for various operations"""

    @staticmethod
    def has_permission(user: Dict[str, Any], resource: str, action: str) -> bool:
        """Check if user has permission for a specific resource and action"""
        # Admin has all permissions
        if user.get("role") == "admin":
            return True

        # Define permission matrix
        permissions = {
            "user": {
                "profile": ["read", "update"],
                "applications": ["create", "read", "update", "delete"],
                "jobs": ["read"],
                "resumes": ["create", "read", "update", "delete"],
                "interviews": ["read", "update"],
                "cover_letters": ["create", "read", "update"],
                "subscriptions": ["read", "update"],
                "analytics": ["read"]
            },
            "premium_user": {
                "profile": ["read", "update"],
                "applications": ["create", "read", "update", "delete"],
                "jobs": ["read", "premium_search"],
                "resumes": ["create", "read", "update", "delete"],
                "interviews": ["read", "update", "schedule"],
                "cover_letters": ["create", "read", "update", "generate"],
                "auto_apply": ["create", "read", "update", "delete"],
                "subscriptions": ["read", "update", "cancel"],
                "analytics": ["read", "advanced"]
            }
        }

        user_role = user.get("role", "user")
        if user.get("subscription_status") == "active":
            user_role = "premium_user"

        role_permissions = permissions.get(user_role, {})
        resource_permissions = role_permissions.get(resource, [])

        return action in resource_permissions


class RateLimiter:
    """Rate limiting for API endpoints"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}

    def is_allowed(self, user_id: str) -> bool:
        """Check if user is allowed to make a request"""
        current_minute = datetime.utcnow().replace(second=0, microsecond=0)
        key = f"{user_id}:{current_minute}"

        if key not in self.request_counts:
            self.request_counts[key] = 0

        self.request_counts[key] += 1

        # Clean old entries
        cutoff_time = current_minute - timedelta(minutes=2)
        old_keys = [k for k in self.request_counts.keys()
                   if datetime.fromisoformat(k.split(":")[1]) < cutoff_time]
        for k in old_keys:
            del self.request_counts[k]

        return self.request_counts[key] <= self.requests_per_minute


def validate_api_key(api_key: str) -> bool:
    """Validate an API key for external integrations"""
    # This would typically check against a database of valid API keys
    # For now, we'll use a simple check against environment variable
    valid_api_keys = settings.API_KEYS.split(",") if settings.API_KEYS else []
    return api_key in valid_api_keys


def sanitize_input(input_string: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    # Remove or escape potentially dangerous characters
    dangerous_chars = ["<", ">", "&", "'", '"', "\\", "/", "=", "(", ")", ";"]
    sanitized = input_string
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    return sanitized.strip()


def encrypt_sensitive_data(data: str) -> str:
    """Encrypt sensitive data for storage"""
    # This would use a proper encryption library like cryptography
    # For now, returning a placeholder
    # TODO: Implement proper encryption
    return f"encrypted_{data}"


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    # This would use a proper decryption method
    # For now, returning a placeholder
    # TODO: Implement proper decryption
    if encrypted_data.startswith("encrypted_"):
        return encrypted_data.replace("encrypted_", "")
    return encrypted_data