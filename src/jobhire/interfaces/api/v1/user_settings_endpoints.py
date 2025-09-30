"""
Comprehensive user settings API endpoints.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.security import HTTPBearer
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.shared.application.exceptions import BusinessRuleException, NotFoundException

from jobhire.domains.user.application.services import UserProfileService
from jobhire.shared.infrastructure.container import get_user_profile_service
from jobhire.domains.user.domain.value_objects.application_settings import (
    JobApplicationConfiguration, MatchLevel, ApprovalMode, ServiceStatus, UserTier
)


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/users", tags=["👤 User Settings"])


# User Settings Endpoints

@router.get("/{user_id}/settings")
@router.get("/{user_id}/settings/all")
@measure_http_request("/users/settings/get-all")
async def get_all_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get all user settings."""
    try:
        # Validate user access
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        logger.info("Getting all settings", user_id=user_id)

        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Get application configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            config = JobApplicationConfiguration.create_default(user.email)

        return {
            "success": True,
            "data": config.to_dict(),
            "message": "Settings retrieved successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get all settings", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        elif isinstance(e, BusinessRuleException):
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve settings")


@router.get("/{user_id}/settings/search")
@measure_http_request("/users/settings/search/get")
async def get_search_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get search settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            config = JobApplicationConfiguration.create_default(user.email)

        return {
            "success": True,
            "data": {
                "matchLevel": config.search_settings.match_level.value,
                "matchPercentage": config.search_settings.match_percentage,
                "generateCoverLetter": config.search_settings.generate_cover_letter,
                "generateAIResume": config.search_settings.generate_ai_resume
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get search settings", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve search settings")


@router.put("/{user_id}/settings/search")
@router.patch("/{user_id}/settings/search")
@measure_http_request("/users/settings/search/update")
async def update_search_settings(
    search_settings: Dict[str, Any],
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update search settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Updating search settings", user_id=user_id, settings=search_settings)

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update search settings
        updated_data = current_config.to_dict()
        updated_data["searchSettings"].update(search_settings)

        # Validate and save
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Search settings updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update search settings", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update search settings")


@router.get("/{user_id}/settings/application")
@measure_http_request("/users/settings/application/get")
async def get_application_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get application settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            config = JobApplicationConfiguration.create_default(user.email)

        return {
            "success": True,
            "data": {
                "approvalMode": config.application_settings.approval_mode.value,
                "autoSubmitDelayHours": config.application_settings.auto_submit_delay_hours
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get application settings", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve application settings")


@router.put("/{user_id}/settings/application")
@router.patch("/{user_id}/settings/application")
@measure_http_request("/users/settings/application/update")
async def update_application_settings(
    application_settings: Dict[str, Any],
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update application settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Updating application settings", user_id=user_id, settings=application_settings)

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update application settings
        updated_data = current_config.to_dict()
        updated_data["applicationSettings"].update(application_settings)

        # Validate and save
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Application settings updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update application settings", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update application settings")


@router.get("/{user_id}/settings/notifications")
@measure_http_request("/users/settings/notifications/get")
async def get_notification_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get email notification settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            config = JobApplicationConfiguration.create_default(user.email)

        return {
            "success": True,
            "data": {
                "interviewInvitation": config.email_notifications.interview_invitation,
                "additionalInfoRequest": config.email_notifications.additional_info_request,
                "applicationAcknowledgement": config.email_notifications.application_acknowledgement,
                "positionStatusUpdate": config.email_notifications.position_status_update,
                "rejectionNotification": config.email_notifications.rejection_notification,
                "systemApplication": config.email_notifications.system_application,
                "other": config.email_notifications.other
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get notification settings", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve notification settings")


@router.put("/{user_id}/settings/notifications")
@router.patch("/{user_id}/settings/notifications")
@measure_http_request("/users/settings/notifications/update")
async def update_notification_settings(
    notification_settings: Dict[str, Any],
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update email notification settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Updating notification settings", user_id=user_id, settings=notification_settings)

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update notification settings
        updated_data = current_config.to_dict()
        updated_data["emailNotifications"].update(notification_settings)

        # Validate and save
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Notification settings updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update notification settings", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update notification settings")


# Alternative endpoint using email as identifier
@router.get("/settings")
@measure_http_request("/users/settings/by-email")
async def get_settings_by_email(
    email: str = Query(..., description="User email"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get settings by email address."""
    try:
        # This would require a method to find user by email
        # For now, we'll require admin access for this endpoint
        require_permission(current_user.role, Permission.ADMIN_READ)

        logger.info("Getting settings by email", email=email)

        # Implementation would find user by email first
        # user = await user_service.find_by_email(email)
        # For now, return a placeholder response

        return {
            "success": True,
            "message": "Email-based lookup not yet implemented",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get settings by email", email=email, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve settings by email")


@router.put("/settings")
@measure_http_request("/users/settings/update-by-email")
async def update_settings_by_email(
    settings_data: Dict[str, Any],
    email: str = Query(..., description="User email"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update settings by email address."""
    try:
        require_permission(current_user.role, Permission.ADMIN_WRITE)

        logger.info("Updating settings by email", email=email)

        # Implementation would find user by email and update
        return {
            "success": True,
            "message": "Email-based update not yet implemented",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update settings by email", email=email, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update settings by email")