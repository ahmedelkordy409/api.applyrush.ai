"""
Specific configuration API endpoints.
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.security import HTTPBearer
import structlog
from pydantic import BaseModel, Field

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.shared.application.exceptions import BusinessRuleException, NotFoundException

from jobhire.domains.user.application.services import UserProfileService
from jobhire.shared.infrastructure.container import get_user_profile_service
from jobhire.domains.user.domain.value_objects.application_settings import (
    JobApplicationConfiguration, MatchLevel, ApprovalMode
)


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/users", tags=["⚙️ Specific Configuration"])


# Request models
class MatchLevelUpdate(BaseModel):
    matchLevel: MatchLevel = Field(..., description="Match level setting")
    matchPercentage: int = Field(..., ge=1, le=100, description="Match percentage")


class DocumentGenerationUpdate(BaseModel):
    generateCoverLetter: bool = Field(..., description="Generate cover letter")
    generateAIResume: bool = Field(..., description="Generate AI resume")


class ApprovalModeUpdate(BaseModel):
    approvalMode: ApprovalMode = Field(..., description="Approval mode")
    autoSubmitDelayHours: int = Field(..., ge=0, description="Auto submit delay in hours")


class NotificationUpdate(BaseModel):
    enabled: bool = Field(..., description="Notification enabled status")


# Match Level Configuration
@router.put("/{user_id}/settings/match-level")
@measure_http_request("/users/settings/match-level")
async def update_match_level(
    match_level_data: MatchLevelUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update match level configuration."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info(
            "Updating match level",
            user_id=user_id,
            match_level=match_level_data.matchLevel,
            percentage=match_level_data.matchPercentage
        )

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update match level settings
        updated_data = current_config.to_dict()
        updated_data["searchSettings"]["matchLevel"] = match_level_data.matchLevel.value
        updated_data["searchSettings"]["matchPercentage"] = match_level_data.matchPercentage

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Match level updated successfully", user_id=user_id)

        return {
            "success": True,
            "data": {
                "matchLevel": match_level_data.matchLevel.value,
                "matchPercentage": match_level_data.matchPercentage
            },
            "message": "Match level updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update match level", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update match level")


# Document Generation Configuration
@router.put("/{user_id}/settings/document-generation")
@measure_http_request("/users/settings/document-generation")
async def update_document_generation(
    document_settings: DocumentGenerationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update document generation settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info(
            "Updating document generation settings",
            user_id=user_id,
            cover_letter=document_settings.generateCoverLetter,
            ai_resume=document_settings.generateAIResume
        )

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Check user tier for premium features
        user_profile = await user_service.get_user_profile(EntityId.from_string(user_id))
        user_tier = getattr(user_profile, 'user_tier', 'free')

        # Update document generation settings
        updated_data = current_config.to_dict()
        updated_data["searchSettings"]["generateCoverLetter"] = document_settings.generateCoverLetter
        updated_data["searchSettings"]["generateAIResume"] = document_settings.generateAIResume

        # Validate premium features
        try:
            new_config = JobApplicationConfiguration.from_user_input(updated_data)
            from jobhire.domains.user.domain.value_objects.application_settings import UserTier
            new_config.validate_premium_features(UserTier(user_tier))
        except ValueError as e:
            raise BusinessRuleException(str(e))

        # Save updated configuration
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Document generation settings updated successfully", user_id=user_id)

        return {
            "success": True,
            "data": {
                "generateCoverLetter": document_settings.generateCoverLetter,
                "generateAIResume": document_settings.generateAIResume
            },
            "message": "Document generation settings updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update document generation settings", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update document generation settings")


# Approval Mode Configuration
@router.put("/{user_id}/settings/approval-mode")
@measure_http_request("/users/settings/approval-mode")
async def update_approval_mode(
    approval_data: ApprovalModeUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update approval mode configuration."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info(
            "Updating approval mode",
            user_id=user_id,
            approval_mode=approval_data.approvalMode,
            delay_hours=approval_data.autoSubmitDelayHours
        )

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update approval mode settings
        updated_data = current_config.to_dict()
        updated_data["applicationSettings"]["approvalMode"] = approval_data.approvalMode.value
        updated_data["applicationSettings"]["autoSubmitDelayHours"] = approval_data.autoSubmitDelayHours

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Approval mode updated successfully", user_id=user_id)

        return {
            "success": True,
            "data": {
                "approvalMode": approval_data.approvalMode.value,
                "autoSubmitDelayHours": approval_data.autoSubmitDelayHours
            },
            "message": "Approval mode updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to update approval mode", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update approval mode")


# Individual Email Notification Endpoints
@router.put("/{user_id}/settings/notifications/interview-invitation")
@measure_http_request("/users/settings/notifications/interview-invitation")
async def update_interview_invitation_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update interview invitation notification setting."""
    return await _update_individual_notification(
        user_id, "interviewInvitation", notification_data.enabled,
        current_user, user_service, "Interview invitation"
    )


@router.put("/{user_id}/settings/notifications/info-request")
@measure_http_request("/users/settings/notifications/info-request")
async def update_info_request_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update additional info request notification setting."""
    return await _update_individual_notification(
        user_id, "additionalInfoRequest", notification_data.enabled,
        current_user, user_service, "Additional info request"
    )


@router.put("/{user_id}/settings/notifications/acknowledgement")
@measure_http_request("/users/settings/notifications/acknowledgement")
async def update_acknowledgement_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update application acknowledgement notification setting."""
    return await _update_individual_notification(
        user_id, "applicationAcknowledgement", notification_data.enabled,
        current_user, user_service, "Application acknowledgement"
    )


@router.put("/{user_id}/settings/notifications/status-update")
@measure_http_request("/users/settings/notifications/status-update")
async def update_status_update_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update position status update notification setting."""
    return await _update_individual_notification(
        user_id, "positionStatusUpdate", notification_data.enabled,
        current_user, user_service, "Position status update"
    )


@router.put("/{user_id}/settings/notifications/rejection")
@measure_http_request("/users/settings/notifications/rejection")
async def update_rejection_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update rejection notification setting."""
    return await _update_individual_notification(
        user_id, "rejectionNotification", notification_data.enabled,
        current_user, user_service, "Rejection notification"
    )


@router.put("/{user_id}/settings/notifications/system")
@measure_http_request("/users/settings/notifications/system")
async def update_system_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update system application notification setting."""
    return await _update_individual_notification(
        user_id, "systemApplication", notification_data.enabled,
        current_user, user_service, "System application"
    )


@router.put("/{user_id}/settings/notifications/other")
@measure_http_request("/users/settings/notifications/other")
async def update_other_notification(
    notification_data: NotificationUpdate,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update other notification setting."""
    return await _update_individual_notification(
        user_id, "other", notification_data.enabled,
        current_user, user_service, "Other notification"
    )


# Helper function for individual notification updates
async def _update_individual_notification(
    user_id: str,
    notification_field: str,
    enabled: bool,
    current_user,
    user_service: UserProfileService,
    notification_name: str
) -> Dict[str, Any]:
    """Helper function to update individual notification settings."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info(
            f"Updating {notification_name} notification",
            user_id=user_id,
            enabled=enabled
        )

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update specific notification setting
        updated_data = current_config.to_dict()
        updated_data["emailNotifications"][notification_field] = enabled

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info(f"{notification_name} notification updated successfully", user_id=user_id)

        return {
            "success": True,
            "data": {
                notification_field: enabled
            },
            "message": f"{notification_name} notification updated successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error(f"Failed to update {notification_name} notification", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update {notification_name} notification")