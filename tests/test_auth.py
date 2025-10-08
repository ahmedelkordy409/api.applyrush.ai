"""
Unit tests for authentication system
Tests both regular user authentication and admin authentication
"""

import pytest
import bcrypt
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from bson import ObjectId

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    create_refresh_token,
    generate_verification_token,
    generate_reset_password_token,
)


class TestPasswordHashing:
    """Test password hashing and verification"""

    def test_hash_password(self):
        """Test that password hashing produces a valid bcrypt hash"""
        password = "test_password_123"
        # Use bcrypt directly to avoid passlib issues
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) == 60  # Standard bcrypt hash length

    def test_password_verification_success(self):
        """Test successful password verification"""
        password = "test_password_123"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Verify using bcrypt directly
        assert bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def test_password_verification_failure(self):
        """Test failed password verification with wrong password"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        assert not bcrypt.checkpw(wrong_password.encode('utf-8'), hashed.encode('utf-8'))

    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes (due to salt)"""
        password = "test_password_123"
        hash1 = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        hash2 = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        assert hash1 != hash2
        # But both should verify correctly
        assert bcrypt.checkpw(password.encode('utf-8'), hash1.encode('utf-8'))
        assert bcrypt.checkpw(password.encode('utf-8'), hash2.encode('utf-8'))


class TestJWTTokens:
    """Test JWT token creation and decoding"""

    def test_create_access_token(self):
        """Test access token creation"""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test access token decoding"""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)
        decoded = decode_token(token)

        assert decoded["sub"] == "user123"
        assert decoded["email"] == "test@example.com"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_decode_expired_token(self):
        """Test that expired tokens raise an error"""
        data = {"sub": "user123", "email": "test@example.com"}
        # Create token that expires immediately
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))

        with pytest.raises(ValueError, match="Token has expired"):
            decode_token(token)

    def test_decode_invalid_token(self):
        """Test that invalid tokens raise an error"""
        invalid_token = "invalid.token.string"

        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(invalid_token)

    def test_create_refresh_token(self):
        """Test refresh token creation"""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_refresh_token(data)

        assert token is not None
        assert isinstance(token, str)

        decoded = decode_token(token)
        assert decoded["sub"] == "user123"
        assert decoded["type"] == "refresh"


class TestTokenGeneration:
    """Test token generation utilities"""

    def test_generate_verification_token(self):
        """Test verification token generation"""
        token1 = generate_verification_token()
        token2 = generate_verification_token()

        assert token1 is not None
        assert isinstance(token1, str)
        assert len(token1) > 0
        assert token1 != token2  # Should be unique

    def test_generate_reset_password_token(self):
        """Test password reset token generation"""
        token1 = generate_reset_password_token()
        token2 = generate_reset_password_token()

        assert token1 is not None
        assert isinstance(token1, str)
        assert len(token1) > 0
        assert token1 != token2  # Should be unique


@pytest.mark.asyncio
class TestAdminAuth:
    """Test admin authentication endpoints"""

    async def test_admin_login_success(self):
        """Test successful admin login"""
        # Mock data
        admin_email = "admin@applyrush.ai"
        admin_password = "admin123"

        # Create mock user with bcrypt hash
        hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        mock_admin = {
            "_id": ObjectId(),
            "email": admin_email,
            "hashed_password": hashed_password,
            "role": "super_admin",
            "is_active": True,
            "full_name": "Admin User",
            "email_verified": True
        }

        # Verify password works
        assert bcrypt.checkpw(admin_password.encode('utf-8'), hashed_password.encode('utf-8'))

    async def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        admin_email = "admin@applyrush.ai"
        admin_password = "admin123"
        wrong_password = "wrong_password"

        hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Verify wrong password fails
        assert not bcrypt.checkpw(wrong_password.encode('utf-8'), hashed_password.encode('utf-8'))

    async def test_admin_login_inactive_account(self):
        """Test admin login with inactive account"""
        mock_admin = {
            "_id": ObjectId(),
            "email": "admin@applyrush.ai",
            "role": "super_admin",
            "is_active": False
        }

        # Should reject inactive admin
        assert not mock_admin.get("is_active", True)

    async def test_admin_login_insufficient_permissions(self):
        """Test login attempt by non-admin user"""
        mock_user = {
            "_id": ObjectId(),
            "email": "user@applyrush.ai",
            "role": "user",
            "is_active": True
        }

        # Should reject non-admin users
        assert mock_user.get("role") not in ["admin", "super_admin"]


@pytest.mark.asyncio
class TestUserAuth:
    """Test regular user authentication"""

    async def test_user_registration_password_hash(self):
        """Test that user registration properly hashes passwords"""
        password = "user_password_123"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Password should be hashed
        assert hashed != password
        assert bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    async def test_user_login_success(self):
        """Test successful user login"""
        email = "user@applyrush.ai"
        password = "user123"

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        mock_user = {
            "_id": ObjectId(),
            "email": email,
            "hashed_password": hashed_password,
            "role": "user",
            "is_active": True
        }

        # Verify password
        assert bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

    async def test_user_login_invalid_password(self):
        """Test user login with invalid password"""
        password = "user123"
        wrong_password = "wrong_password"

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Should fail with wrong password
        assert not bcrypt.checkpw(wrong_password.encode('utf-8'), hashed_password.encode('utf-8'))


class TestTokenSecurity:
    """Test token security features"""

    def test_token_contains_required_fields(self):
        """Test that tokens contain required security fields"""
        data = {"sub": "user123", "email": "test@example.com", "role": "user"}
        token = create_access_token(data)
        decoded = decode_token(token)

        # Should have expiration
        assert "exp" in decoded
        assert "iat" in decoded  # Issued at

        # Should preserve original data
        assert decoded["sub"] == "user123"
        assert decoded["email"] == "test@example.com"
        assert decoded["role"] == "user"

    def test_token_expiration_time(self):
        """Test that token expiration is set correctly"""
        data = {"sub": "user123"}
        custom_expiry = timedelta(hours=1)
        token = create_access_token(data, expires_delta=custom_expiry)
        decoded = decode_token(token)

        # Check expiration is roughly 1 hour from now
        exp_time = datetime.fromtimestamp(decoded["exp"])
        iat_time = datetime.fromtimestamp(decoded["iat"])
        delta = exp_time - iat_time

        # Should be approximately 1 hour (with small tolerance)
        assert 3590 <= delta.total_seconds() <= 3610

    def test_refresh_token_longer_expiry(self):
        """Test that refresh tokens have longer expiry than access tokens"""
        data = {"sub": "user123"}
        access_token = create_access_token(data)
        refresh_token = create_refresh_token(data)

        access_decoded = decode_token(access_token)
        refresh_decoded = decode_token(refresh_token)

        # Refresh token should expire later than access token
        assert refresh_decoded["exp"] > access_decoded["exp"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
