"""
Security dependencies for FastAPI endpoints.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)

security = HTTPBearer()


class Permission(Enum):
    """Permission enumeration."""
    READ_PROFILE = "read_profile"
    WRITE_PROFILE = "write_profile"
    READ_JOBS = "read_jobs"
    WRITE_JOBS = "write_jobs"
    READ_APPLICATIONS = "read_applications"
    WRITE_APPLICATIONS = "write_applications"
    ADMIN = "admin"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Get current authenticated user."""
    # This is a simplified implementation
    # In production, you would validate the JWT token and return the user
    try:
        token = credentials.credentials
        # For now, return a mock user
        return {
            "user_id": "mock_user_id",
            "email": "user@example.com",
            "role": "user"
        }
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[dict]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_permission(permission: Permission):
    """Decorator to require specific permission."""
    def permission_checker(current_user: dict = Depends(get_current_user)) -> dict:
        # In a real implementation, check if user has the required permission
        # For now, just return the user
        return current_user

    return permission_checker


def require_admin():
    """Require admin permission."""
    return require_permission(Permission.ADMIN)