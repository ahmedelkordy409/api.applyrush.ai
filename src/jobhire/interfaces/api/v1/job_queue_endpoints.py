"""
Enterprise job queue API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.security import HTTPBearer
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.shared.application.exceptions import ValidationException, BusinessRuleException, NotFoundException

from jobhire.domains.job.application.services import JobQueueService
from jobhire.shared.infrastructure.container import get_job_queue_service
from jobhire.domains.job.application.dto import (
    JobQueueCreateDTO, JobQueueUpdateDTO, JobQueueResponseDTO,
    QueueStatsDTO, QueueBulkActionDTO, QueueFilterDTO, JobQueueMetricsDTO
)
from jobhire.domains.job.domain.entities.job_queue import QueuePriority, QueueStatus, UserAction


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/queue", tags=["📋 Job Queue"])


@router.post("/", response_model=JobQueueResponseDTO)
@measure_http_request("/queue/create")
async def add_job_to_queue(
    create_request: JobQueueCreateDTO,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> JobQueueResponseDTO:
    """Add a job to the user's application queue."""
    try:
        logger.info(
            "Adding job to queue",
            user_id=current_user.id,
            job_id=create_request.job_id,
            priority=create_request.priority
        )

        require_permission(current_user.role, Permission.PROFILE_WRITE)

        result = await job_queue_service.add_job_to_queue(
            user_id=EntityId.from_string(current_user.id),
            create_request=create_request
        )

        logger.info(
            "Job added to queue successfully",
            user_id=current_user.id,
            job_id=create_request.job_id,
            queue_id=result.id
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to add job to queue",
            user_id=current_user.id,
            job_id=create_request.job_id,
            error=str(e),
            error_type=type(e).__name__
        )

        if isinstance(e, (ValidationException, BusinessRuleException)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to add job to queue")


@router.get("/", response_model=List[JobQueueResponseDTO])
@measure_http_request("/queue/list")
async def get_user_queue(
    status: Optional[QueueStatus] = Query(None),
    priority: Optional[QueuePriority] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> List[JobQueueResponseDTO]:
    """Get user's job application queue with filtering."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        queue_items = await job_queue_service.get_user_queue(
            user_id=EntityId.from_string(current_user.id),
            status=status,
            priority=priority,
            limit=limit,
            offset=offset
        )

        return queue_items

    except Exception as e:
        logger.error(
            "Failed to get user queue",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve queue")


@router.get("/{queue_id}", response_model=JobQueueResponseDTO)
@measure_http_request("/queue/get")
async def get_queue_item(
    queue_id: str,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> JobQueueResponseDTO:
    """Get a specific queue item."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        queue_item = await job_queue_service.get_queue_item(
            user_id=EntityId.from_string(current_user.id),
            queue_id=EntityId.from_string(queue_id)
        )

        return queue_item

    except Exception as e:
        logger.error(
            "Failed to get queue item",
            user_id=current_user.id,
            queue_id=queue_id,
            error=str(e)
        )

        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        elif isinstance(e, BusinessRuleException):
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve queue item")


@router.put("/{queue_id}", response_model=JobQueueResponseDTO)
@measure_http_request("/queue/update")
async def update_queue_item(
    queue_id: str,
    update_request: JobQueueUpdateDTO,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> JobQueueResponseDTO:
    """Update a queue item."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        result = await job_queue_service.update_queue_item(
            user_id=EntityId.from_string(current_user.id),
            queue_id=EntityId.from_string(queue_id),
            update_request=update_request
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to update queue item",
            user_id=current_user.id,
            queue_id=queue_id,
            error=str(e)
        )

        if isinstance(e, NotFoundException):
            raise HTTPException(status_code=404, detail=str(e))
        elif isinstance(e, BusinessRuleException):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to update queue item")


@router.post("/{queue_id}/skip", response_model=JobQueueResponseDTO)
@measure_http_request("/queue/skip")
async def skip_queue_item(
    queue_id: str,
    reason: Optional[str] = None,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> JobQueueResponseDTO:
    """Skip a queue item."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        result = await job_queue_service.skip_queue_item(
            user_id=EntityId.from_string(current_user.id),
            queue_id=EntityId.from_string(queue_id),
            reason=reason
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to skip queue item",
            user_id=current_user.id,
            queue_id=queue_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to skip queue item")


@router.post("/{queue_id}/cancel", response_model=JobQueueResponseDTO)
@measure_http_request("/queue/cancel")
async def cancel_queue_item(
    queue_id: str,
    reason: Optional[str] = None,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> JobQueueResponseDTO:
    """Cancel a queue item."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        result = await job_queue_service.cancel_queue_item(
            user_id=EntityId.from_string(current_user.id),
            queue_id=EntityId.from_string(queue_id),
            reason=reason
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to cancel queue item",
            user_id=current_user.id,
            queue_id=queue_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to cancel queue item")


@router.delete("/{queue_id}")
@measure_http_request("/queue/delete")
async def remove_queue_item(
    queue_id: str,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
):
    """Remove a queue item permanently."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        success = await job_queue_service.remove_queue_item(
            user_id=EntityId.from_string(current_user.id),
            queue_id=EntityId.from_string(queue_id)
        )

        if success:
            return {"success": True, "message": "Queue item removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Queue item not found")

    except Exception as e:
        logger.error(
            "Failed to remove queue item",
            user_id=current_user.id,
            queue_id=queue_id,
            error=str(e)
        )

        if isinstance(e, (NotFoundException, BusinessRuleException)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to remove queue item")


@router.get("/flagged/items", response_model=List[JobQueueResponseDTO])
@measure_http_request("/queue/flagged")
async def get_flagged_items(
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> List[JobQueueResponseDTO]:
    """Get flagged items for manual review."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        flagged_items = await job_queue_service.get_flagged_items(
            user_id=EntityId.from_string(current_user.id),
            limit=limit
        )

        return flagged_items

    except Exception as e:
        logger.error(
            "Failed to get flagged items",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve flagged items")


@router.get("/stats/summary", response_model=QueueStatsDTO)
@measure_http_request("/queue/stats")
async def get_queue_stats(
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> QueueStatsDTO:
    """Get queue statistics for the user."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        stats = await job_queue_service.get_queue_stats(
            user_id=EntityId.from_string(current_user.id)
        )

        return stats

    except Exception as e:
        logger.error(
            "Failed to get queue stats",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve queue statistics")


@router.post("/bulk/cancel")
@measure_http_request("/queue/bulk-cancel")
async def bulk_cancel_queued_items(
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
):
    """Cancel all queued items for the user."""
    try:
        require_permission(current_user.role, Permission.PROFILE_WRITE)

        cancelled_count = await job_queue_service.bulk_cancel_queued_items(
            user_id=EntityId.from_string(current_user.id)
        )

        logger.info(
            "Bulk cancelled items",
            user_id=current_user.id,
            cancelled_count=cancelled_count
        )

        return {
            "success": True,
            "message": f"Cancelled {cancelled_count} queued items",
            "cancelled_count": cancelled_count
        }

    except Exception as e:
        logger.error(
            "Failed to bulk cancel items",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to cancel queued items")


@router.get("/ready/processing", response_model=List[JobQueueResponseDTO])
@measure_http_request("/queue/ready")
async def get_ready_for_processing(
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> List[JobQueueResponseDTO]:
    """Get queue items ready for processing (admin/system endpoint)."""
    try:
        require_permission(current_user.role, Permission.ADMIN_READ)

        ready_items = await job_queue_service.get_ready_for_processing(limit=limit)
        return ready_items

    except Exception as e:
        logger.error(
            "Failed to get ready items",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve ready items")


@router.get("/metrics/{queue_id}", response_model=JobQueueMetricsDTO)
@measure_http_request("/queue/metrics")
async def get_queue_item_metrics(
    queue_id: str,
    current_user=Depends(get_current_user),
    job_queue_service: JobQueueService = Depends(get_job_queue_service)
) -> JobQueueMetricsDTO:
    """Get processing metrics for a queue item."""
    try:
        require_permission(current_user.role, Permission.PROFILE_READ)

        queue_item = await job_queue_service.get_queue_item(
            user_id=EntityId.from_string(current_user.id),
            queue_id=EntityId.from_string(queue_id)
        )

        # Convert to entity to get metrics
        from jobhire.domains.job.domain.entities.job_queue import JobQueue

        # This is a simplified conversion - in practice you'd use the repository
        metrics = JobQueueMetricsDTO(
            queue_id=queue_item.id,
            user_id=queue_item.user_id,
            job_id=queue_item.job_id,
            status=queue_item.status,
            priority=queue_item.priority,
            match_score=queue_item.match_score,
            application_submitted=queue_item.application_submitted,
            user_flagged=queue_item.user_flagged,
            user_action=queue_item.user_action,
            queued_at=queue_item.queued_at,
            processed_at=queue_item.processed_at,
            has_error=bool(queue_item.processing_error)
        )

        return metrics

    except Exception as e:
        logger.error(
            "Failed to get queue metrics",
            user_id=current_user.id,
            queue_id=queue_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve queue metrics")