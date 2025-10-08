"""
Background Jobs API Endpoints
Provides admin control over background jobs
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging

from app.core.security import get_current_user
from app.core.scheduler import get_scheduler_status
from app.services.background_jobs import background_job_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_jobs_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get status of all background jobs"""
    try:
        jobs = get_scheduler_status()
        return {
            "success": True,
            "jobs": jobs,
            "total_jobs": len(jobs)
        }
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/trigger/find-matches")
async def trigger_find_matches(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger job matching for active users"""
    try:
        await background_job_service.find_matches_for_active_users()
        return {
            "success": True,
            "message": "Job matching completed successfully"
        }
    except Exception as e:
        logger.error(f"Error triggering find matches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/trigger/auto-apply")
async def trigger_auto_apply(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger auto-apply queue processing"""
    try:
        await background_job_service.process_auto_apply_queue()
        return {
            "success": True,
            "message": "Auto-apply queue processed successfully"
        }
    except Exception as e:
        logger.error(f"Error triggering auto-apply: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/trigger/cleanup")
async def trigger_cleanup(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger cleanup of expired queue items"""
    try:
        await background_job_service.cleanup_expired_queue_items()
        return {
            "success": True,
            "message": "Cleanup completed successfully"
        }
    except Exception as e:
        logger.error(f"Error triggering cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/trigger/update-stats")
async def trigger_update_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger stats update"""
    try:
        await background_job_service.update_application_stats()
        return {
            "success": True,
            "message": "Stats updated successfully"
        }
    except Exception as e:
        logger.error(f"Error triggering stats update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
