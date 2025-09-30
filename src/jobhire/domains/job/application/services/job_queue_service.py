"""
Job Queue application service.
"""

import structlog
from datetime import datetime
from typing import List, Optional, Dict, Any

from jobhire.shared.domain.types import EntityId
from jobhire.shared.application.exceptions import BusinessRuleException, NotFoundException
from jobhire.shared.infrastructure.events import DomainEventPublisher

from jobhire.domains.job.domain.entities.job_queue import (
    JobQueue, QueuePriority, QueueStatus, UserAction
)
from jobhire.domains.job.infrastructure.repositories.job_queue_repository import JobQueueRepository
from jobhire.domains.job.application.dto.job_queue_dto import (
    JobQueueCreateDTO, JobQueueUpdateDTO, JobQueueResponseDTO, QueueStatsDTO
)
from jobhire.domains.user.infrastructure.repositories.user_repository import UserRepository


logger = structlog.get_logger(__name__)


class JobQueueService:
    """Application service for job queue management."""

    def __init__(
        self,
        job_queue_repository: JobQueueRepository,
        user_repository: UserRepository,
        event_publisher: DomainEventPublisher
    ):
        self.job_queue_repository = job_queue_repository
        self.user_repository = user_repository
        self.event_publisher = event_publisher

    async def add_job_to_queue(
        self,
        user_id: EntityId,
        create_request: JobQueueCreateDTO
    ) -> JobQueueResponseDTO:
        """Add a job to the user's queue."""
        logger.info(
            "Adding job to queue",
            user_id=str(user_id),
            job_id=create_request.job_id,
            priority=create_request.priority
        )

        # Verify user exists
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Check if job is already in queue
        existing_queue_item = await self.job_queue_repository.find_by_job_id(
            user_id, create_request.job_id
        )
        if existing_queue_item:
            raise BusinessRuleException(
                f"Job {create_request.job_id} is already in queue with status: {existing_queue_item.status}"
            )

        # Check user's daily queue limits
        await self._check_queue_limits(user_id)

        # Create queue item
        queue_id = EntityId.generate()
        job_queue = JobQueue(
            queue_id=queue_id,
            user_id=user_id,
            job_id=create_request.job_id,
            job_data=create_request.job_data,
            priority=create_request.priority,
            scheduled_for=create_request.scheduled_for,
            match_score=create_request.match_score
        )

        if create_request.user_notes:
            job_queue.user_notes = create_request.user_notes

        # Save to repository
        await self.job_queue_repository.create(job_queue)

        # Publish domain events
        await self.event_publisher.publish_events(job_queue.get_domain_events())

        logger.info(
            "Job added to queue successfully",
            user_id=str(user_id),
            job_id=create_request.job_id,
            queue_id=str(queue_id)
        )

        return JobQueueResponseDTO.from_job_queue(job_queue)

    async def get_user_queue(
        self,
        user_id: EntityId,
        status: Optional[QueueStatus] = None,
        priority: Optional[QueuePriority] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[JobQueueResponseDTO]:
        """Get user's job queue with optional filtering."""
        queue_items = await self.job_queue_repository.find_by_user_id(
            user_id, status, priority, limit, offset
        )

        return [JobQueueResponseDTO.from_job_queue(item) for item in queue_items]

    async def get_queue_item(self, user_id: EntityId, queue_id: EntityId) -> JobQueueResponseDTO:
        """Get a specific queue item."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        if queue_item.user_id != user_id:
            raise BusinessRuleException("Queue item does not belong to user")

        return JobQueueResponseDTO.from_job_queue(queue_item)

    async def update_queue_item(
        self,
        user_id: EntityId,
        queue_id: EntityId,
        update_request: JobQueueUpdateDTO
    ) -> JobQueueResponseDTO:
        """Update a queue item."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        if queue_item.user_id != user_id:
            raise BusinessRuleException("Queue item does not belong to user")

        # Update priority if provided
        if update_request.priority:
            queue_item.update_priority(update_request.priority)

        # Update scheduled time if provided
        if update_request.scheduled_for:
            queue_item.reschedule(update_request.scheduled_for)

        # Update user action if provided
        if update_request.user_action:
            queue_item.set_user_action(update_request.user_action, update_request.user_notes)

        # Update flagged status if provided
        if update_request.user_flagged is not None:
            if update_request.user_flagged:
                queue_item.flag_for_review(update_request.user_notes)
            else:
                queue_item.user_flagged = False

        # Save changes
        await self.job_queue_repository.update(queue_item)

        # Publish domain events
        await self.event_publisher.publish_events(queue_item.get_domain_events())

        logger.info(
            "Queue item updated",
            user_id=str(user_id),
            queue_id=str(queue_id),
            updates=update_request.dict(exclude_none=True)
        )

        return JobQueueResponseDTO.from_job_queue(queue_item)

    async def process_queue_item(self, queue_id: EntityId, workflow_execution_id: EntityId) -> None:
        """Start processing a queue item."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        queue_item.start_processing(workflow_execution_id)
        await self.job_queue_repository.update(queue_item)

        # Publish domain events
        await self.event_publisher.publish_events(queue_item.get_domain_events())

        logger.info(
            "Queue item processing started",
            queue_id=str(queue_id),
            user_id=str(queue_item.user_id),
            workflow_execution_id=str(workflow_execution_id)
        )

    async def complete_queue_processing(
        self,
        queue_id: EntityId,
        application_submitted: bool,
        application_id: Optional[EntityId] = None
    ) -> None:
        """Complete processing of a queue item."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        queue_item.complete_processing(application_submitted, application_id)
        await self.job_queue_repository.update(queue_item)

        # Publish domain events
        await self.event_publisher.publish_events(queue_item.get_domain_events())

        logger.info(
            "Queue item processing completed",
            queue_id=str(queue_id),
            user_id=str(queue_item.user_id),
            application_submitted=application_submitted
        )

    async def fail_queue_processing(self, queue_id: EntityId, error: str) -> None:
        """Mark queue processing as failed."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        queue_item.fail_processing(error)
        await self.job_queue_repository.update(queue_item)

        # Publish domain events
        await self.event_publisher.publish_events(queue_item.get_domain_events())

        logger.error(
            "Queue item processing failed",
            queue_id=str(queue_id),
            user_id=str(queue_item.user_id),
            error=error
        )

    async def skip_queue_item(
        self,
        user_id: EntityId,
        queue_id: EntityId,
        reason: Optional[str] = None
    ) -> JobQueueResponseDTO:
        """Skip a queue item."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        if queue_item.user_id != user_id:
            raise BusinessRuleException("Queue item does not belong to user")

        queue_item.skip_item(reason)
        await self.job_queue_repository.update(queue_item)

        logger.info(
            "Queue item skipped",
            user_id=str(user_id),
            queue_id=str(queue_id),
            reason=reason
        )

        return JobQueueResponseDTO.from_job_queue(queue_item)

    async def cancel_queue_item(
        self,
        user_id: EntityId,
        queue_id: EntityId,
        reason: Optional[str] = None
    ) -> JobQueueResponseDTO:
        """Cancel a queue item."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        if queue_item.user_id != user_id:
            raise BusinessRuleException("Queue item does not belong to user")

        queue_item.cancel_item(reason)
        await self.job_queue_repository.update(queue_item)

        logger.info(
            "Queue item cancelled",
            user_id=str(user_id),
            queue_id=str(queue_id),
            reason=reason
        )

        return JobQueueResponseDTO.from_job_queue(queue_item)

    async def get_ready_for_processing(self, limit: int = 50) -> List[JobQueueResponseDTO]:
        """Get queue items ready for processing."""
        queue_items = await self.job_queue_repository.find_ready_for_processing(
            limit=limit, priority_order=True
        )

        return [JobQueueResponseDTO.from_job_queue(item) for item in queue_items]

    async def get_flagged_items(self, user_id: EntityId, limit: int = 50) -> List[JobQueueResponseDTO]:
        """Get flagged items for manual review."""
        queue_items = await self.job_queue_repository.find_flagged_items(user_id, limit)
        return [JobQueueResponseDTO.from_job_queue(item) for item in queue_items]

    async def get_queue_stats(self, user_id: EntityId) -> QueueStatsDTO:
        """Get queue statistics for a user."""
        stats = await self.job_queue_repository.get_user_queue_stats(user_id)
        return QueueStatsDTO(**stats)

    async def bulk_cancel_queued_items(self, user_id: EntityId) -> int:
        """Cancel all queued items for a user."""
        cancelled_count = await self.job_queue_repository.bulk_update_status(
            user_id, QueueStatus.QUEUED, QueueStatus.CANCELLED
        )

        logger.info(
            "Bulk cancelled queued items",
            user_id=str(user_id),
            cancelled_count=cancelled_count
        )

        return cancelled_count

    async def remove_queue_item(self, user_id: EntityId, queue_id: EntityId) -> bool:
        """Remove a queue item permanently."""
        queue_item = await self.job_queue_repository.find_by_id(queue_id)
        if not queue_item:
            raise NotFoundException(f"Queue item {queue_id} not found")

        if queue_item.user_id != user_id:
            raise BusinessRuleException("Queue item does not belong to user")

        # Only allow deletion of completed, failed, skipped, or cancelled items
        if queue_item.status not in [
            QueueStatus.COMPLETED, QueueStatus.FAILED,
            QueueStatus.SKIPPED, QueueStatus.CANCELLED
        ]:
            raise BusinessRuleException(
                f"Cannot delete queue item in status: {queue_item.status}"
            )

        success = await self.job_queue_repository.delete_by_id(queue_id)

        if success:
            logger.info(
                "Queue item deleted",
                user_id=str(user_id),
                queue_id=str(queue_id)
            )

        return success

    async def _check_queue_limits(self, user_id: EntityId) -> None:
        """Check if user has exceeded their queue limits."""
        # Get today's queue count
        stats = await self.job_queue_repository.get_user_queue_stats(user_id)
        today_queued = stats.get("today_queued", 0)

        # Get user settings to check limits
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            return

        # Check daily limits (this would be based on user's search settings)
        daily_limit = 50  # Default limit, should come from user settings
        if today_queued >= daily_limit:
            raise BusinessRuleException(
                f"Daily queue limit of {daily_limit} items exceeded"
            )