"""
Job Queue domain entity.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from jobhire.shared.domain.entities import AggregateRoot
from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.events import DomainEvent


class QueuePriority(str, Enum):
    """Queue priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class QueueStatus(str, Enum):
    """Queue status options."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class UserAction(str, Enum):
    """User actions on queue items."""
    APPLY = "apply"
    SKIP = "skip"
    SAVE_FOR_LATER = "save_for_later"
    MANUAL_REVIEW = "manual_review"


class JobQueuedEvent(DomainEvent):
    """Event fired when a job is added to the queue."""

    def __init__(self, queue_id: EntityId, user_id: EntityId, job_id: str, priority: QueuePriority):
        super().__init__()
        self.queue_id = queue_id
        self.user_id = user_id
        self.job_id = job_id
        self.priority = priority


class JobProcessingStartedEvent(DomainEvent):
    """Event fired when job processing starts."""

    def __init__(self, queue_id: EntityId, user_id: EntityId, job_id: str):
        super().__init__()
        self.queue_id = queue_id
        self.user_id = user_id
        self.job_id = job_id


class JobProcessingCompletedEvent(DomainEvent):
    """Event fired when job processing completes."""

    def __init__(self, queue_id: EntityId, user_id: EntityId, job_id: str, application_submitted: bool):
        super().__init__()
        self.queue_id = queue_id
        self.user_id = user_id
        self.job_id = job_id
        self.application_submitted = application_submitted


class JobProcessingFailedEvent(DomainEvent):
    """Event fired when job processing fails."""

    def __init__(self, queue_id: EntityId, user_id: EntityId, job_id: str, error: str):
        super().__init__()
        self.queue_id = queue_id
        self.user_id = user_id
        self.job_id = job_id
        self.error = error


class JobQueue(AggregateRoot[EntityId]):
    """
    Job Queue aggregate root representing a queued job application.

    This aggregate manages the lifecycle of job applications in the user's queue,
    from initial queueing through processing and completion.
    """

    def __init__(
        self,
        queue_id: EntityId,
        user_id: EntityId,
        job_id: str,
        job_data: Dict[str, Any],
        priority: QueuePriority = QueuePriority.NORMAL,
        scheduled_for: Optional[datetime] = None,
        match_score: Optional[float] = None
    ):
        super().__init__(queue_id)
        self.user_id = user_id
        self.job_id = job_id
        self.job_data = job_data
        self.priority = priority
        self.scheduled_for = scheduled_for
        self.match_score = match_score

        # Queue management
        self.status = QueueStatus.QUEUED
        self.queued_at = datetime.utcnow()
        self.processed_at: Optional[datetime] = None
        self.workflow_execution_id: Optional[EntityId] = None

        # Processing results
        self.application_submitted = False
        self.application_id: Optional[EntityId] = None
        self.processing_error: Optional[str] = None

        # User actions
        self.user_flagged = False
        self.user_notes: Optional[str] = None
        self.user_action: Optional[UserAction] = None

        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # Fire domain event
        self.add_domain_event(JobQueuedEvent(self.id, self.user_id, self.job_id, self.priority))

    def start_processing(self, workflow_execution_id: EntityId) -> None:
        """Start processing this queue item."""
        if self.status != QueueStatus.QUEUED:
            raise ValueError(f"Cannot start processing item in status: {self.status}")

        self.status = QueueStatus.PROCESSING
        self.workflow_execution_id = workflow_execution_id
        self.updated_at = datetime.utcnow()

        self.add_domain_event(JobProcessingStartedEvent(self.id, self.user_id, self.job_id))

    def complete_processing(
        self,
        application_submitted: bool,
        application_id: Optional[EntityId] = None
    ) -> None:
        """Mark processing as completed."""
        if self.status != QueueStatus.PROCESSING:
            raise ValueError(f"Cannot complete processing for item in status: {self.status}")

        self.status = QueueStatus.COMPLETED
        self.application_submitted = application_submitted
        self.application_id = application_id
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self.add_domain_event(
            JobProcessingCompletedEvent(self.id, self.user_id, self.job_id, application_submitted)
        )

    def fail_processing(self, error: str) -> None:
        """Mark processing as failed."""
        if self.status != QueueStatus.PROCESSING:
            raise ValueError(f"Cannot fail processing for item in status: {self.status}")

        self.status = QueueStatus.FAILED
        self.processing_error = error
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self.add_domain_event(JobProcessingFailedEvent(self.id, self.user_id, self.job_id, error))

    def skip_item(self, reason: Optional[str] = None) -> None:
        """Skip this queue item."""
        if self.status not in [QueueStatus.QUEUED, QueueStatus.PROCESSING]:
            raise ValueError(f"Cannot skip item in status: {self.status}")

        self.status = QueueStatus.SKIPPED
        self.user_action = UserAction.SKIP
        if reason:
            self.user_notes = reason
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel_item(self, reason: Optional[str] = None) -> None:
        """Cancel this queue item."""
        if self.status in [QueueStatus.COMPLETED, QueueStatus.FAILED]:
            raise ValueError(f"Cannot cancel item in status: {self.status}")

        self.status = QueueStatus.CANCELLED
        if reason:
            self.user_notes = reason
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def set_user_action(self, action: UserAction, notes: Optional[str] = None) -> None:
        """Set user action for this queue item."""
        self.user_action = action
        if notes:
            self.user_notes = notes
        self.updated_at = datetime.utcnow()

    def flag_for_review(self, notes: Optional[str] = None) -> None:
        """Flag this item for manual review."""
        self.user_flagged = True
        self.user_action = UserAction.MANUAL_REVIEW
        if notes:
            self.user_notes = notes
        self.updated_at = datetime.utcnow()

    def update_priority(self, new_priority: QueuePriority) -> None:
        """Update the priority of this queue item."""
        if self.status != QueueStatus.QUEUED:
            raise ValueError(f"Cannot update priority for item in status: {self.status}")

        self.priority = new_priority
        self.updated_at = datetime.utcnow()

    def reschedule(self, new_scheduled_time: datetime) -> None:
        """Reschedule this queue item."""
        if self.status != QueueStatus.QUEUED:
            raise ValueError(f"Cannot reschedule item in status: {self.status}")

        self.scheduled_for = new_scheduled_time
        self.updated_at = datetime.utcnow()

    def is_ready_for_processing(self) -> bool:
        """Check if this item is ready for processing."""
        if self.status != QueueStatus.QUEUED:
            return False

        if self.scheduled_for and self.scheduled_for > datetime.utcnow():
            return False

        return True

    def get_processing_metrics(self) -> Dict[str, Any]:
        """Get processing metrics for this queue item."""
        processing_time = None
        if self.processed_at and self.status == QueueStatus.PROCESSING:
            # Calculate time from when processing started
            processing_time = (self.processed_at - self.queued_at).total_seconds()

        queue_time = None
        if self.processed_at:
            queue_time = (self.processed_at - self.queued_at).total_seconds()

        return {
            "queue_id": str(self.id),
            "user_id": str(self.user_id),
            "job_id": self.job_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "match_score": self.match_score,
            "application_submitted": self.application_submitted,
            "user_flagged": self.user_flagged,
            "user_action": self.user_action.value if self.user_action else None,
            "processing_time_seconds": processing_time,
            "queue_time_seconds": queue_time,
            "queued_at": self.queued_at,
            "processed_at": self.processed_at,
            "has_error": bool(self.processing_error)
        }