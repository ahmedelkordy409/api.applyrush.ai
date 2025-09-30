"""
User profile API endpoints.
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.security import HTTPBearer
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.shared.application.exceptions import NotFoundException

from jobhire.domains.user.application.services import UserProfileService
from jobhire.shared.infrastructure.container import get_user_profile_service


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/users", tags=["👤 User Profile"])


@router.get("/{user_id}/profile")
@measure_http_request("/users/profile/get")
async def get_user_profile(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get user profile information."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        logger.info("Getting user profile", user_id=user_id)

        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Extract relevant profile information
        profile_data = {
            "id": str(user.id),
            "email": user.email,
            "username": getattr(user, 'username', None),
            "full_name": getattr(user, 'full_name', None),
            "user_tier": getattr(user, 'user_tier', 'free'),
            "is_active": getattr(user, 'is_active', True),
            "created_at": getattr(user, 'created_at', None),
            "updated_at": getattr(user, 'updated_at', None),
            "last_login": getattr(user, 'last_login', None)
        }

        return {
            "success": True,
            "data": profile_data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get user profile", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve user profile")


@router.get("/{user_id}/email")
@measure_http_request("/users/email/get")
async def get_user_email(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get user email address."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        logger.info("Getting user email", user_id=user_id)

        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "email": user.email
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get user email", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve user email")