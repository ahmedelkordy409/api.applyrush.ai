"""
Bulk operations and validation API endpoints.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
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
    JobApplicationConfiguration, UserTier
)


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/users", tags=["📦 Bulk Operations"])


# Request models
class SaveAllSettingsRequest(BaseModel):
    searchSettings: Optional[Dict[str, Any]] = None
    applicationSettings: Optional[Dict[str, Any]] = None
    emailNotifications: Optional[Dict[str, Any]] = None
    serviceOperation: Optional[Dict[str, Any]] = None


class SettingsValidationRequest(BaseModel):
    userEmail: str = Field(..., description="User email")
    searchSettings: Optional[Dict[str, Any]] = None
    applicationSettings: Optional[Dict[str, Any]] = None
    emailNotifications: Optional[Dict[str, Any]] = None
    serviceOperation: Optional[Dict[str, Any]] = None


# Bulk Save Operations
@router.post("/{user_id}/settings/save-all")
@measure_http_request("/users/settings/save-all")
async def save_all_settings(
    settings_data: SaveAllSettingsRequest,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Save all user settings in a single operation."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info(
            "Saving all settings",
            user_id=user_id,
            sections=list(settings_data.dict(exclude_none=True).keys())
        )

        # Get current configuration
        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Build updated configuration
        updated_data = current_config.to_dict()

        # Update each section if provided
        if settings_data.searchSettings:
            updated_data["searchSettings"].update(settings_data.searchSettings)

        if settings_data.applicationSettings:
            updated_data["applicationSettings"].update(settings_data.applicationSettings)

        if settings_data.emailNotifications:
            updated_data["emailNotifications"].update(settings_data.emailNotifications)

        if settings_data.serviceOperation:
            updated_data["serviceOperation"].update(settings_data.serviceOperation)

        # Validate and create new configuration
        try:
            new_config = JobApplicationConfiguration.from_user_input(updated_data)

            # Validate premium features
            user_tier = getattr(user, 'user_tier', UserTier.FREE)
            if isinstance(user_tier, str):
                user_tier = UserTier(user_tier)

            new_config.validate_premium_features(user_tier)
        except ValueError as e:
            raise BusinessRuleException(str(e))

        # Save updated configuration
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("All settings saved successfully", user_id=user_id)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "All settings saved successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to save all settings", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        elif isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to save all settings")


# Reset Operations
@router.post("/{user_id}/settings/reset")
@measure_http_request("/users/settings/reset-all")
async def reset_all_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Reset all settings to default values."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Resetting all settings to defaults", user_id=user_id)

        # Get user profile
        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Create default configuration
        default_config = JobApplicationConfiguration.create_default(user.email)

        # Save default configuration
        await user_service.update_application_configuration(EntityId.from_string(user_id), default_config.to_dict())

        logger.info("All settings reset to defaults successfully", user_id=user_id)

        return {
            "success": True,
            "data": default_config.to_dict(),
            "message": "All settings reset to default values successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to reset all settings", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to reset all settings")


@router.post("/{user_id}/settings/reset/search")
@measure_http_request("/users/settings/reset-search")
async def reset_search_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Reset only search settings to default values."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Resetting search settings to defaults", user_id=user_id)

        # Get current configuration
        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Reset only search settings
        default_config = JobApplicationConfiguration.create_default(user.email)
        updated_data = current_config.to_dict()
        updated_data["searchSettings"] = default_config.to_dict()["searchSettings"]

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Search settings reset to defaults successfully", user_id=user_id)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Search settings reset to default values successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to reset search settings", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to reset search settings")


@router.post("/{user_id}/settings/reset/application")
@measure_http_request("/users/settings/reset-application")
async def reset_application_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Reset only application settings to default values."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Resetting application settings to defaults", user_id=user_id)

        # Get current configuration
        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Reset only application settings
        default_config = JobApplicationConfiguration.create_default(user.email)
        updated_data = current_config.to_dict()
        updated_data["applicationSettings"] = default_config.to_dict()["applicationSettings"]

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Application settings reset to defaults successfully", user_id=user_id)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Application settings reset to default values successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to reset application settings", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to reset application settings")


@router.post("/{user_id}/settings/reset/notifications")
@measure_http_request("/users/settings/reset-notifications")
async def reset_notification_settings(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Reset only notification settings to default values."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Resetting notification settings to defaults", user_id=user_id)

        # Get current configuration
        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Reset only notification settings
        default_config = JobApplicationConfiguration.create_default(user.email)
        updated_data = current_config.to_dict()
        updated_data["emailNotifications"] = default_config.to_dict()["emailNotifications"]

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Notification settings reset to defaults successfully", user_id=user_id)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Notification settings reset to default values successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to reset notification settings", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to reset notification settings")


# Validation Operations
@router.post("/{user_id}/settings/validate")
@measure_http_request("/users/settings/validate")
async def validate_settings(
    validation_data: SettingsValidationRequest,
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Validate settings without saving them."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        logger.info("Validating settings", user_id=user_id, email=validation_data.userEmail)

        # Get user for tier validation
        user = await user_service.get_user_profile(EntityId.from_string(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Build configuration from validation data
        config_dict = {
            "userEmail": validation_data.userEmail,
            "searchSettings": validation_data.searchSettings or {},
            "applicationSettings": validation_data.applicationSettings or {},
            "emailNotifications": validation_data.emailNotifications or {},
            "serviceOperation": validation_data.serviceOperation or {}
        }

        # Fill in missing fields with defaults
        default_config = JobApplicationConfiguration.create_default(validation_data.userEmail)
        default_dict = default_config.to_dict()

        for section in ["searchSettings", "applicationSettings", "emailNotifications", "serviceOperation"]:
            if not config_dict[section]:
                config_dict[section] = default_dict[section]
            else:
                # Merge with defaults to ensure all required fields are present
                merged_section = default_dict[section].copy()
                merged_section.update(config_dict[section])
                config_dict[section] = merged_section

        validation_errors = []
        warnings = []

        try:
            # Validate configuration structure
            config = JobApplicationConfiguration.from_user_input(config_dict)

            # Validate premium features
            user_tier = getattr(user, 'user_tier', UserTier.FREE)
            if isinstance(user_tier, str):
                user_tier = UserTier(user_tier)

            try:
                config.validate_premium_features(user_tier)
            except ValueError as e:
                validation_errors.append(str(e))

            # Additional validation checks
            search_settings = config.search_settings
            if search_settings.generate_cover_letter or search_settings.generate_ai_resume:
                if user_tier == UserTier.FREE:
                    warnings.append("Premium features selected but user has free tier")

            if config.application_settings.approval_mode.value == "instant":
                warnings.append("Instant approval mode selected - applications will be submitted immediately")

        except Exception as e:
            validation_errors.append(f"Configuration validation failed: {str(e)}")

        # Determine overall validation status
        is_valid = len(validation_errors) == 0
        has_warnings = len(warnings) > 0

        logger.info(
            "Settings validation completed",
            user_id=user_id,
            is_valid=is_valid,
            error_count=len(validation_errors),
            warning_count=len(warnings)
        )

        return {
            "success": True,
            "data": {
                "isValid": is_valid,
                "hasWarnings": has_warnings,
                "errors": validation_errors,
                "warnings": warnings,
                "validatedSettings": config_dict if is_valid else None
            },
            "message": "Settings validation completed",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to validate settings", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to validate settings")