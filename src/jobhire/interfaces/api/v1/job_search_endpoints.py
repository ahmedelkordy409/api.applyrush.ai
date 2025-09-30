"""
Enterprise job search API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.security import HTTPBearer
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request

from jobhire.domains.job.application.services import JobSearchService
from jobhire.shared.infrastructure.container import get_job_search_service, get_user_profile_service
from jobhire.domains.job.application.dto import (
    JobSearchRequestDTO, JobSearchResultDTO, SearchFiltersDTO,
    SearchPreferencesUpdateDTO, SearchConfigurationUpdateDTO
)
from jobhire.domains.user.application.services import UserProfileService


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/jobs", tags=["🔍 Job Search"])


@router.post("/search", response_model=JobSearchResultDTO)
@measure_http_request("/jobs/search")
async def search_jobs(
    search_request: JobSearchRequestDTO,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    job_search_service: JobSearchService = Depends(get_job_search_service)
) -> JobSearchResultDTO:
    """
    Execute a comprehensive job search with user preferences.

    This endpoint:
    - Validates user permissions and subscription limits
    - Applies user's saved search preferences
    - Fetches jobs from multiple sources
    - Calculates match scores using AI
    - Returns ranked results with detailed matching information
    """
    try:
        logger.info(
            "Job search requested",
            user_id=current_user.id,
            query=search_request.query,
            limit=search_request.limit
        )

        # Check permissions
        require_permission(current_user.role, Permission.JOB_READ)

        # Execute job search
        result = await job_search_service.execute_job_search(
            user_id=EntityId.from_string(current_user.id),
            search_request=search_request
        )

        # Queue background tasks for similar job recommendations
        if search_request.include_similar and result.jobs:
            background_tasks.add_task(
                _queue_similar_job_search,
                current_user.id,
                result.jobs[:3]  # Use top 3 matches
            )

        logger.info(
            "Job search completed",
            user_id=current_user.id,
            search_id=result.search_id,
            total_jobs=result.total_jobs_found,
            qualified_jobs=result.qualified_jobs_count
        )

        return result

    except Exception as e:
        logger.error(
            "Job search failed",
            user_id=current_user.id,
            error=str(e),
            error_type=type(e).__name__
        )

        if isinstance(e, (ValidationException, BusinessRuleException)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Job search failed")


@router.get("/search/history", response_model=List[JobSearchResultDTO])
@measure_http_request("/jobs/search/history")
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    include_failed: bool = Query(False),
    current_user=Depends(get_current_user),
    job_search_service: JobSearchService = Depends(get_job_search_service)
) -> List[JobSearchResultDTO]:
    """Get user's job search history with filtering options."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        history = await job_search_service.get_user_search_history(
            user_id=EntityId.from_string(current_user.id),
            limit=limit,
            include_failed=include_failed
        )

        return history

    except Exception as e:
        logger.error(
            "Failed to get search history",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve search history")


@router.post("/search/{search_id}/cancel")
@measure_http_request("/jobs/search/cancel")
async def cancel_search(
    search_id: str,
    reason: str = "User requested cancellation",
    current_user=Depends(get_current_user),
    job_search_service: JobSearchService = Depends(get_job_search_service)
):
    """Cancel an ongoing job search."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        await job_search_service.cancel_search(
            search_id=EntityId.from_string(search_id),
            reason=reason
        )

        return {"success": True, "message": "Search cancelled successfully"}

    except Exception as e:
        logger.error(
            "Failed to cancel search",
            user_id=current_user.id,
            search_id=search_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to cancel search")


@router.post("/search/{search_id}/retry", response_model=JobSearchResultDTO)
@measure_http_request("/jobs/search/retry")
async def retry_search(
    search_id: str,
    current_user=Depends(get_current_user),
    job_search_service: JobSearchService = Depends(get_job_search_service)
) -> JobSearchResultDTO:
    """Retry a failed job search."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        result = await job_search_service.retry_failed_search(
            search_id=EntityId.from_string(search_id)
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to retry search",
            user_id=current_user.id,
            search_id=search_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retry search")


@router.get("/preferences")
@measure_http_request("/jobs/preferences")
async def get_search_preferences(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
):
    """Get user's job search preferences."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        preferences = await user_service.get_search_preferences(
            user_id=EntityId.from_string(current_user.id)
        )

        return {"success": True, "preferences": preferences}

    except Exception as e:
        logger.error(
            "Failed to get search preferences",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")


@router.put("/preferences")
@measure_http_request("/jobs/preferences")
async def update_search_preferences(
    preferences_update: SearchPreferencesUpdateDTO,
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
):
    """Update user's job search preferences."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        await user_service.update_search_preferences(
            user_id=EntityId.from_string(current_user.id),
            preferences_update=preferences_update
        )

        logger.info(
            "Search preferences updated",
            user_id=current_user.id
        )

        return {"success": True, "message": "Preferences updated successfully"}

    except Exception as e:
        logger.error(
            "Failed to update search preferences",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to update preferences")


@router.get("/configuration")
@measure_http_request("/jobs/configuration")
async def get_search_configuration(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
):
    """Get user's job search configuration."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        configuration = await user_service.get_search_configuration(
            user_id=EntityId.from_string(current_user.id)
        )

        return {"success": True, "configuration": configuration}

    except Exception as e:
        logger.error(
            "Failed to get search configuration",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")


@router.put("/configuration")
@measure_http_request("/jobs/configuration")
async def update_search_configuration(
    config_update: SearchConfigurationUpdateDTO,
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
):
    """Update user's job search configuration."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        await user_service.update_search_configuration(
            user_id=EntityId.from_string(current_user.id),
            config_update=config_update
        )

        logger.info(
            "Search configuration updated",
            user_id=current_user.id
        )

        return {"success": True, "message": "Configuration updated successfully"}

    except Exception as e:
        logger.error(
            "Failed to update search configuration",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@router.post("/search/automated")
@measure_http_request("/jobs/search/automated")
async def start_automated_search(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Start automated job search based on user preferences."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        # Queue automated search task
        background_tasks.add_task(
            _queue_automated_search,
            current_user.id
        )

        logger.info(
            "Automated search started",
            user_id=current_user.id
        )

        return {
            "success": True,
            "message": "Automated search started successfully"
        }

    except Exception as e:
        logger.error(
            "Failed to start automated search",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to start automated search")


@router.post("/search/automated/stop")
@measure_http_request("/jobs/search/automated/stop")
async def stop_automated_search(
    current_user=Depends(get_current_user),
    user_service: UserProfileService = Depends(get_user_profile_service)
):
    """Stop automated job search for user."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        await user_service.stop_automated_search(
            user_id=EntityId.from_string(current_user.id)
        )

        logger.info(
            "Automated search stopped",
            user_id=current_user.id
        )

        return {
            "success": True,
            "message": "Automated search stopped successfully"
        }

    except Exception as e:
        logger.error(
            "Failed to stop automated search",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to stop automated search")


@router.get("/analytics")
@measure_http_request("/jobs/analytics")
async def get_search_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user=Depends(get_current_user),
    job_search_service: JobSearchService = Depends(get_job_search_service)
):
    """Get user's job search analytics and performance metrics."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        analytics = await job_search_service.get_user_search_analytics(
            user_id=EntityId.from_string(current_user.id),
            days=days
        )

        return {"success": True, "analytics": analytics}

    except Exception as e:
        logger.error(
            "Failed to get search analytics",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")


# Background task functions
async def _queue_similar_job_search(user_id: str, top_matches: List[dict]):
    """Queue similar job search based on top matches."""
    # Implementation for finding similar jobs
    pass


async def _queue_automated_search(user_id: str):
    """Queue automated job search for user."""
    # Implementation for automated search scheduling
    pass