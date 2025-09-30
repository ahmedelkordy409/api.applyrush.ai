"""
Service operation API endpoints.
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.security import HTTPBearer
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.shared.application.exceptions import BusinessRuleException, NotFoundException

from jobhire.domains.user.application.services import UserProfileService
from jobhire.shared.infrastructure.container import get_user_profile_service
from jobhire.domains.user.domain.value_objects.application_settings import (
    JobApplicationConfiguration, ServiceStatus
)


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/users", tags=["🔧 Service Operations"])


@router.get("/{user_id}/service/status")
@measure_http_request("/users/service/status")
async def get_service_status(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Get current service status for user."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_READ)
        else:
            require_permission(current_user.role, Permission.PROFILE_READ)

        logger.info("Getting service status", user_id=user_id)

        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            config = JobApplicationConfiguration.create_default(user.email)

        return {
            "success": True,
            "data": {
                "status": config.service_operation.status.value,
                "isPaused": config.service_operation.is_paused,
                "canProcessJobs": config.service_operation.can_process_jobs(),
                "isActive": config.service_operation.is_active()
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to get service status", user_id=user_id, error=str(e))
        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve service status")


@router.post("/{user_id}/service/pause")
@measure_http_request("/users/service/pause")
async def pause_service(
    user_id: str = Path(..., description="User ID"),
    reason: Dict[str, Any] = None,
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Pause the job application service for user."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        pause_reason = reason.get("reason", "User requested pause") if reason else "User requested pause"

        logger.info("Pausing service", user_id=user_id, reason=pause_reason)

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update service operation to paused
        updated_data = current_config.to_dict()
        updated_data["serviceOperation"] = {
            "status": ServiceStatus.PAUSED.value,
            "isPaused": True
        }

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Service paused successfully", user_id=user_id, reason=pause_reason)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Service paused successfully",
            "reason": pause_reason,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to pause service", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to pause service")


@router.post("/{user_id}/service/resume")
@measure_http_request("/users/service/resume")
async def resume_service(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Resume the job application service for user."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Resuming service", user_id=user_id)

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Update service operation to active
        updated_data = current_config.to_dict()
        updated_data["serviceOperation"] = {
            "status": ServiceStatus.ACTIVE.value,
            "isPaused": False
        }

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        logger.info("Service resumed successfully", user_id=user_id)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": "Service resumed successfully",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to resume service", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to resume service")


@router.put("/{user_id}/service/toggle")
@measure_http_request("/users/service/toggle")
async def toggle_service(
    user_id: str = Path(..., description="User ID"),
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
) -> Dict[str, Any]:
    """Toggle service status (active/paused) for user."""
    try:
        if current_user.id != user_id:
            require_permission(current_user.role, Permission.ADMIN_WRITE)
        else:
            require_permission(current_user.role, Permission.PROFILE_WRITE)

        logger.info("Toggling service status", user_id=user_id)

        # Get current configuration
        config_data = await user_service.get_application_configuration(EntityId.from_string(user_id))
        if config_data:
            current_config = JobApplicationConfiguration.from_user_input(config_data)
        else:
            user = await user_service.get_user_profile(EntityId.from_string(user_id))
            current_config = JobApplicationConfiguration.create_default(user.email)

        # Toggle status
        current_status = current_config.service_operation.status
        new_status = ServiceStatus.PAUSED if current_status == ServiceStatus.ACTIVE else ServiceStatus.ACTIVE
        new_is_paused = new_status == ServiceStatus.PAUSED

        # Update service operation
        updated_data = current_config.to_dict()
        updated_data["serviceOperation"] = {
            "status": new_status.value,
            "isPaused": new_is_paused
        }

        # Save updated configuration
        new_config = JobApplicationConfiguration.from_user_input(updated_data)
        await user_service.update_application_configuration(EntityId.from_string(user_id), new_config.to_dict())

        action = "paused" if new_status == ServiceStatus.PAUSED else "resumed"
        logger.info(f"Service {action} via toggle", user_id=user_id, new_status=new_status.value)

        return {
            "success": True,
            "data": new_config.to_dict(),
            "message": f"Service {action} successfully",
            "previousStatus": current_status.value,
            "newStatus": new_status.value,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error("Failed to toggle service", user_id=user_id, error=str(e))
        if isinstance(e, (BusinessRuleException, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to toggle service")