"""
Data Transfer Objects for Job Queue operations.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from jobhire.domains.job.domain.entities.job_queue import JobQueue, QueuePriority, QueueStatus, UserAction


class JobQueueCreateDTO(BaseModel):
    """DTO for creating a job queue item."""

    job_id: str = Field(..., description="Unique job identifier")
    job_data: Dict[str, Any] = Field(..., description="Complete job posting data")
    priority: QueuePriority = Field(QueuePriority.NORMAL, description="Queue priority level")
    scheduled_for: Optional[datetime] = Field(None, description="When to process this job")
    match_score: Optional[float] = Field(None, ge=0, le=100, description="AI match score")
    user_notes: Optional[str] = Field(None, description="User notes for this job")


class JobQueueUpdateDTO(BaseModel):
    """DTO for updating a job queue item."""

    priority: Optional[QueuePriority] = None
    scheduled_for: Optional[datetime] = None
    user_action: Optional[UserAction] = None
    user_flagged: Optional[bool] = None
    user_notes: Optional[str] = None


class JobQueueResponseDTO(BaseModel):
    """DTO for job queue item responses."""

    id: str
    user_id: str
    job_id: str
    job_data: Dict[str, Any]
    priority: str
    scheduled_for: Optional[datetime] = None
    match_score: Optional[float] = None

    # Status and timestamps
    status: str
    queued_at: datetime
    processed_at: Optional[datetime] = None

    # Processing information
    workflow_execution_id: Optional[str] = None
    application_submitted: bool = False
    application_id: Optional[str] = None
    processing_error: Optional[str] = None

    # User actions
    user_flagged: bool = False
    user_notes: Optional[str] = None
    user_action: Optional[str] = None

    # Metadata
    created_at: datetime
    updated_at: datetime
    version: int = 1

    @classmethod
    def from_job_queue(cls, job_queue: JobQueue) -> "JobQueueResponseDTO":
        """Create DTO from JobQueue entity."""
        return cls(
            id=str(job_queue.id),
            user_id=str(job_queue.user_id),
            job_id=job_queue.job_id,
            job_data=job_queue.job_data,
            priority=job_queue.priority.value,
            scheduled_for=job_queue.scheduled_for,
            match_score=job_queue.match_score,
            status=job_queue.status.value,
            queued_at=job_queue.queued_at,
            processed_at=job_queue.processed_at,
            workflow_execution_id=str(job_queue.workflow_execution_id) if job_queue.workflow_execution_id else None,
            application_submitted=job_queue.application_submitted,
            application_id=str(job_queue.application_id) if job_queue.application_id else None,
            processing_error=job_queue.processing_error,
            user_flagged=job_queue.user_flagged,
            user_notes=job_queue.user_notes,
            user_action=job_queue.user_action.value if job_queue.user_action else None,
            created_at=job_queue.created_at,
            updated_at=job_queue.updated_at,
            version=job_queue.version
        )


class QueueStatsDTO(BaseModel):
    """DTO for queue statistics."""

    total_queued: int
    by_status: Dict[str, int]
    avg_scores_by_status: Dict[str, float]
    total_applications_submitted: int
    today_queued: int


class QueueBulkActionDTO(BaseModel):
    """DTO for bulk queue actions."""

    action: str = Field(..., pattern="^(cancel|skip|flag|unflag)$")
    queue_ids: Optional[list[str]] = None  # If None, applies to all eligible items
    reason: Optional[str] = None


class QueueFilterDTO(BaseModel):
    """DTO for filtering queue items."""

    status: Optional[QueueStatus] = None
    priority: Optional[QueuePriority] = None
    user_action: Optional[UserAction] = None
    flagged_only: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_match_score: Optional[float] = Field(None, ge=0, le=100)
    max_match_score: Optional[float] = Field(None, ge=0, le=100)
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0)


class JobQueueMetricsDTO(BaseModel):
    """DTO for job queue processing metrics."""

    queue_id: str
    user_id: str
    job_id: str
    status: str
    priority: str
    match_score: Optional[float] = None
    application_submitted: bool = False
    user_flagged: bool = False
    user_action: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    queue_time_seconds: Optional[float] = None
    queued_at: datetime
    processed_at: Optional[datetime] = None
    has_error: bool = False

    @classmethod
    def from_job_queue(cls, job_queue: JobQueue) -> "JobQueueMetricsDTO":
        """Create metrics DTO from JobQueue entity."""
        metrics = job_queue.get_processing_metrics()
        return cls(**metrics)