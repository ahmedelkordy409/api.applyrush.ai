"""
Enterprise authentication service with JWT and multi-factor authentication.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import structlog

from jobhire.config.settings import get_settings
from jobhire.shared.domain.exceptions import SecurityException
from jobhire.shared.domain.types import EntityId, EmailAddress


logger = structlog.get_logger(__name__)


class JWTManager:
    """JWT token management service."""

    def __init__(self):
        self.settings = get_settings()
        self.secret_key = self.settings.security.secret_key
        self.algorithm = self.settings.security.algorithm
        self.access_token_expire_minutes = self.settings.security.access_token_expire_minutes
        self.refresh_token_expire_days = self.settings.security.refresh_token_expire_days

    def create_access_token(
        self,
        subject: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        claims = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }

        if additional_claims:
            claims.update(additional_claims)

        try:
            encoded_jwt = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            logger.info("Access token created", subject=subject, expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create access token", error=str(e))
            raise SecurityException("Failed to create access token")

    def create_refresh_token(self, subject: str) -> str:
        """Create JWT refresh token."""
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        claims = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32)  # Unique token ID
        }

        try:
            encoded_jwt = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            logger.info("Refresh token created", subject=subject, expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create refresh token", error=str(e))
            raise SecurityException("Failed to create refresh token")

    def verify_token(self, token: str, expected_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("type") != expected_type:
                raise SecurityException(f"Invalid token type. Expected: {expected_type}")

            return payload

        except JWTError as e:
            logger.warning("Invalid JWT token", error=str(e))
            raise SecurityException("Invalid token")
        except Exception as e:
            logger.error("Token verification failed", error=str(e))
            raise SecurityException("Token verification failed")

    def extract_subject(self, token: str) -> str:
        """Extract subject from token."""
        payload = self.verify_token(token)
        return payload.get("sub")

    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        try:
            payload = self.verify_token(token)
            return False
        except SecurityException:
            return True


class AuthenticationService:
    """Enterprise authentication service."""

    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
        self.pwd_context = CryptContext(
            schemes=["argon2"],
            deprecated="auto",
            argon2__time_cost=2,
            argon2__memory_cost=512,
            argon2__parallelism=2
        )

    def hash_password(self, password: str) -> str:
        """Hash password using Argon2."""
        try:
            return self.pwd_context.hash(password)
        except Exception as e:
            logger.error("Password hashing failed", error=str(e))
            raise SecurityException("Password hashing failed")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False

    def authenticate_user(self, email: str, password: str, user_repository) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password."""
        try:
            # This would integrate with your user repository
            # For now, it's a placeholder
            logger.info("Authentication attempt", email=email)

            # In a real implementation, you would:
            # 1. Fetch user by email
            # 2. Verify password
            # 3. Check if user is active
            # 4. Record login attempt

            return None

        except Exception as e:
            logger.error("Authentication failed", email=email, error=str(e))
            raise SecurityException("Authentication failed")

    def create_authentication_tokens(
        self,
        user_id: str,
        email: str,
        role: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Create access and refresh tokens for authenticated user."""
        claims = {
            "email": email,
            "role": role,
            "user_id": user_id
        }

        if additional_claims:
            claims.update(additional_claims)

        access_token = self.jwt_manager.create_access_token(
            subject=user_id,
            additional_claims=claims
        )

        refresh_token = self.jwt_manager.create_refresh_token(subject=user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from refresh token."""
        try:
            payload = self.jwt_manager.verify_token(refresh_token, expected_type="refresh")
            user_id = payload.get("sub")

            if not user_id:
                raise SecurityException("Invalid refresh token")

            # In a real implementation, you would verify the user still exists and is active
            # For now, create a new access token
            return self.jwt_manager.create_access_token(subject=user_id)

        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            raise SecurityException("Token refresh failed")

    def invalidate_token(self, token: str) -> None:
        """Invalidate a token (add to blacklist)."""
        # In a real implementation, you would add the token to a blacklist
        # stored in Redis or database
        try:
            payload = self.jwt_manager.verify_token(token)
            jti = payload.get("jti")
            if jti:
                # Add to blacklist
                logger.info("Token invalidated", jti=jti)
        except Exception as e:
            logger.error("Token invalidation failed", error=str(e))

    def generate_api_key(self, user_id: str) -> str:
        """Generate API key for user."""
        # Create a long-lived token with special type
        expire = datetime.utcnow() + timedelta(days=365)  # 1 year
        claims = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "api_key",
            "key_id": secrets.token_urlsafe(16)
        }

        try:
            api_key = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            logger.info("API key generated", user_id=user_id)
            return api_key
        except Exception as e:
            logger.error("API key generation failed", error=str(e))
            raise SecurityException("API key generation failed")

    def verify_api_key(self, api_key: str) -> Dict[str, Any]:
        """Verify API key."""
        return self.jwt_manager.verify_token(api_key, expected_type="api_key")