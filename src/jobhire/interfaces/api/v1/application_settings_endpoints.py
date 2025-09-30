"""
Enterprise application settings API endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
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
router = APIRouter(prefix="/application-settings", tags=["📱 Application Settings"])


@router.get("/")
@measure_http_request("/application-settings/get")
async def get_application_settings(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get user's job application settings."""
    try:
        logger.info(
            "Getting application settings",
            user_id=current_user.id
        )

        require_permission(current_user.role, Permission.PROFILE_READ)

        # Get user to access their configuration
        user = await user_service.get_user_profile(
            user_id=EntityId.from_string(current_user.id)
        )

        if not user:
            raise NotFoundException(f"User {current_user.id} not found")

        # Get application configuration from user profile
        # This would typically be stored in a separate field or computed from preferences
        config = JobApplicationConfiguration.create_default(user.email)

        # If user has existing settings, load them
        if hasattr(user, 'application_configuration') and user.application_configuration:
            config = JobApplicationConfiguration.from_user_input(user.application_configuration)

        return {
            "success": True,
            "settings": config.to_dict()
        }

    except Exception as e:
        logger.error(
            "Failed to get application settings",
            user_id=current_user.id,
            error=str(e),
            error_type=type(e).__name__
        )

        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve application settings")


@router.put("/")
@measure_http_request("/application-settings/update")
async def update_application_settings(
    settings_data: Dict[str, Any],
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Update user's job application settings."""
    try:
        logger.info(
            "Updating application settings",
            user_id=current_user.id,
            settings_keys=list(settings_data.keys())
        )

        require_permission(current_user.role, Permission.PROFILE_WRITE)

        # Get user to check tier for premium features
        user = await user_service.get_user_profile(
            user_id=EntityId.from_string(current_user.id)
        )

        if not user:
            raise NotFoundException(f"User {current_user.id} not found")

        # Create configuration from input
        try:
            config = JobApplicationConfiguration.from_user_input(settings_data)
        except Exception as e:
            raise BusinessRuleException(f"Invalid settings data: {str(e)}")

        # Validate premium features based on user tier
        user_tier = getattr(user, 'user_tier', UserTier.FREE)
        if isinstance(user_tier, str):
            user_tier = UserTier(user_tier)

        try:
            config.validate_premium_features(user_tier)
        except ValueError as e:
            raise BusinessRuleException(str(e))

        # Update user's application configuration
        await user_service.update_application_configuration(
            user_id=EntityId.from_string(current_user.id),
            configuration=config.to_dict()
        )

        logger.info(
            "Application settings updated successfully",
            user_id=current_user.id,
            match_level=config.search_settings.match_level,
            approval_mode=config.application_settings.approval_mode,
            service_status=config.service_operation.status
        )

        return {
            "success": True,
            "message": "Application settings updated successfully",
            "settings": config.to_dict()
        }

    except Exception as e:
        logger.error(
            "Failed to update application settings",
            user_id=current_user.id,
            error=str(e),
            error_type=type(e).__name__
        )

        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        elif isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update application settings")


@router.post("/service/pause")
@measure_http_request("/application-settings/pause")
async def pause_application_service(
    reason: str = "User requested pause",
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Pause the job application service for the user."""
    try:
        logger.info(
            "Pausing application service",
            user_id=current_user.id,
            reason=reason
        )

        require_permission(current_user.role, Permission.PROFILE_WRITE)

        # Get current settings
        user = await user_service.get_user_profile(
            user_id=EntityId.from_string(current_user.id)
        )

        if not user:
            raise NotFoundException(f"User {current_user.id} not found")

        # Get current configuration or create default
        current_config_data = getattr(user, 'application_configuration', None)
        if current_config_data:
            config = JobApplicationConfiguration.from_user_input(current_config_data)
        else:
            config = JobApplicationConfiguration.create_default(user.email)

        # Update service operation to paused
        updated_data = config.to_dict()
        updated_data["serviceOperation"] = {
            "status": ServiceStatus.PAUSED.value,
            "isPaused": True
        }

        # Create new configuration
        updated_config = JobApplicationConfiguration.from_user_input(updated_data)

        # Save updated configuration
        await user_service.update_application_configuration(
            user_id=EntityId.from_string(current_user.id),
            configuration=updated_config.to_dict()
        )

        logger.info(
            "Application service paused",
            user_id=current_user.id,
            reason=reason
        )

        return {
            "success": True,
            "message": "Application service paused successfully",
            "status": ServiceStatus.PAUSED.value,
            "reason": reason
        }

    except Exception as e:
        logger.error(
            "Failed to pause application service",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to pause application service")


@router.post("/service/resume")
@measure_http_request("/application-settings/resume")
async def resume_application_service(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Resume the job application service for the user."""
    try:
        logger.info(
            "Resuming application service",
            user_id=current_user.id
        )

        require_permission(current_user.role, Permission.PROFILE_WRITE)

        # Get current settings
        user = await user_service.get_user_profile(
            user_id=EntityId.from_string(current_user.id)
        )

        if not user:
            raise NotFoundException(f"User {current_user.id} not found")

        # Get current configuration or create default
        current_config_data = getattr(user, 'application_configuration', None)
        if current_config_data:
            config = JobApplicationConfiguration.from_user_input(current_config_data)
        else:
            config = JobApplicationConfiguration.create_default(user.email)

        # Update service operation to active
        updated_data = config.to_dict()
        updated_data["serviceOperation"] = {
            "status": ServiceStatus.ACTIVE.value,
            "isPaused": False
        }

        # Create new configuration
        updated_config = JobApplicationConfiguration.from_user_input(updated_data)

        # Save updated configuration
        await user_service.update_application_configuration(
            user_id=EntityId.from_string(current_user.id),
            configuration=updated_config.to_dict()
        )

        logger.info(
            "Application service resumed",
            user_id=current_user.id
        )

        return {
            "success": True,
            "message": "Application service resumed successfully",
            "status": ServiceStatus.ACTIVE.value
        }

    except Exception as e:
        logger.error(
            "Failed to resume application service",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to resume application service")


@router.get("/options/match-levels")
@measure_http_request("/application-settings/match-levels")
async def get_match_level_options(
    current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """Get available match level options with descriptions."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        options = [
            {
                "value": MatchLevel.RELAXED.value,
                "label": "Open to Almost Everything",
                "description": "Apply to jobs with >30% match",
                "percentage": 30
            },
            {
                "value": MatchLevel.BALANCED.value,
                "label": "Looking for a Good Fit",
                "description": "Apply to jobs with >55% match",
                "percentage": 55
            },
            {
                "value": MatchLevel.STRICT.value,
                "label": "Only Top Matches",
                "description": "Apply to jobs with >80% match",
                "percentage": 80
            }
        ]

        return {
            "success": True,
            "options": options
        }

    except Exception as e:
        logger.error(
            "Failed to get match level options",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve match level options")


@router.get("/options/approval-modes")
@measure_http_request("/application-settings/approval-modes")
async def get_approval_mode_options(
    current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """Get available approval mode options with descriptions."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        options = [
            {
                "value": ApprovalMode.MANUAL.value,
                "label": "Manual Approval",
                "description": "Apply only with your approval"
            },
            {
                "value": ApprovalMode.AUTO_24H.value,
                "label": "24-Hour Delay",
                "description": "Apply automatically after 24 hours"
            },
            {
                "value": ApprovalMode.INSTANT.value,
                "label": "Instant Apply",
                "description": "Apply instantly without approval"
            }
        ]

        return {
            "success": True,
            "options": options
        }

    except Exception as e:
        logger.error(
            "Failed to get approval mode options",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve approval mode options")


@router.get("/premium-features")
@measure_http_request("/application-settings/premium-features")
async def get_premium_features_info(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get information about premium features and user's access."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        # Get user tier
        user = await user_service.get_user_profile(
            user_id=EntityId.from_string(current_user.id)
        )

        if not user:
            raise NotFoundException(f"User {current_user.id} not found")

        user_tier = getattr(user, 'user_tier', UserTier.FREE)
        if isinstance(user_tier, str):
            user_tier = UserTier(user_tier)

        has_premium = user_tier in [UserTier.PREMIUM, UserTier.ENTERPRISE]

        features = [
            {
                "feature": "generateCoverLetter",
                "name": "AI Cover Letter Generation",
                "description": "Automatically generate personalized cover letters for each application",
                "available": has_premium,
                "tier_required": "premium"
            },
            {
                "feature": "generateAIResume",
                "name": "AI Resume Optimization",
                "description": "Automatically optimize your resume for each job posting",
                "available": has_premium,
                "tier_required": "premium"
            }
        ]

        return {
            "success": True,
            "user_tier": user_tier.value,
            "has_premium": has_premium,
            "features": features
        }

    except Exception as e:
        logger.error(
            "Failed to get premium features info",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve premium features information")