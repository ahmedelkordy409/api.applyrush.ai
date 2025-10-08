"""
Job Queue repository implementation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.repositories import BaseMongoRepository
from jobhire.domains.job.domain.entities.job_queue import JobQueue, QueuePriority, QueueStatus, UserAction


class JobQueueRepository(BaseMongoRepository[JobQueue]):
    """Repository for job queue management."""

    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, "job_queues", JobQueue)

    async def create(self, job_queue: JobQueue) -> None:
        """Create a new job queue item."""
        document = {
            "_id": str(job_queue.id),
            "user_id": str(job_queue.user_id),
            "job_id": job_queue.job_id,
            "job_data": job_queue.job_data,
            "priority": job_queue.priority.value,
            "scheduled_for": job_queue.scheduled_for,
            "match_score": job_queue.match_score,
            "status": job_queue.status.value,
            "queued_at": job_queue.queued_at,
            "processed_at": job_queue.processed_at,
            "workflow_execution_id": str(job_queue.workflow_execution_id) if job_queue.workflow_execution_id else None,
            "application_submitted": job_queue.application_submitted,
            "application_id": str(job_queue.application_id) if job_queue.application_id else None,
            "processing_error": job_queue.processing_error,
            "user_flagged": job_queue.user_flagged,
            "user_notes": job_queue.user_notes,
            "user_action": job_queue.user_action.value if job_queue.user_action else None,
            "created_at": job_queue.created_at,
            "updated_at": job_queue.updated_at,
            "version": job_queue.version
        }
        await self.collection.insert_one(document)

    async def update(self, job_queue: JobQueue) -> None:
        """Update an existing job queue item."""
        document = {
            "user_id": str(job_queue.user_id),
            "job_id": job_queue.job_id,
            "job_data": job_queue.job_data,
            "priority": job_queue.priority.value,
            "scheduled_for": job_queue.scheduled_for,
            "match_score": job_queue.match_score,
            "status": job_queue.status.value,
            "queued_at": job_queue.queued_at,
            "processed_at": job_queue.processed_at,
            "workflow_execution_id": str(job_queue.workflow_execution_id) if job_queue.workflow_execution_id else None,
            "application_submitted": job_queue.application_submitted,
            "application_id": str(job_queue.application_id) if job_queue.application_id else None,
            "processing_error": job_queue.processing_error,
            "user_flagged": job_queue.user_flagged,
            "user_notes": job_queue.user_notes,
            "user_action": job_queue.user_action.value if job_queue.user_action else None,
            "updated_at": job_queue.updated_at,
            "version": job_queue.version
        }

        await self.collection.update_one(
            {"_id": str(job_queue.id)},
            {"$set": document}
        )

    async def find_by_id(self, queue_id: EntityId) -> Optional[JobQueue]:
        """Find job queue item by ID."""
        document = await self.collection.find_one({"_id": str(queue_id)})
        if not document:
            return None
        return self._document_to_entity(document)

    async def find_by_user_id(
        self,
        user_id: EntityId,
        status: Optional[QueueStatus] = None,
        priority: Optional[QueuePriority] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[JobQueue]:
        """Find job queue items for a user with optional filtering."""
        filters = {"user_id": str(user_id)}

        if status:
            filters["status"] = status.value
        if priority:
            filters["priority"] = priority.value

        cursor = self.collection.find(filters).sort("queued_at", -1).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)

        return [self._document_to_entity(doc) for doc in documents]

    async def find_ready_for_processing(
        self,
        limit: int = 50,
        priority_order: bool = True
    ) -> List[JobQueue]:
        """Find queue items ready for processing."""
        filters = {
            "status": QueueStatus.QUEUED.value,
            "$or": [
                {"scheduled_for": {"$lte": datetime.utcnow()}},
                {"scheduled_for": None}
            ]
        }

        sort_criteria = []
        if priority_order:
            # Sort by priority: urgent, high, normal, low
            priority_map = {
                QueuePriority.URGENT.value: 4,
                QueuePriority.HIGH.value: 3,
                QueuePriority.NORMAL.value: 2,
                QueuePriority.LOW.value: 1
            }
            # MongoDB doesn't support direct enum sorting, so we'll sort by queued_at for now
            # In a production system, you'd add a priority_order field
            sort_criteria.append(("queued_at", 1))
        else:
            sort_criteria.append(("queued_at", 1))

        cursor = self.collection.find(filters).sort(sort_criteria).limit(limit)
        documents = await cursor.to_list(length=limit)

        # Sort by priority in Python if needed
        queue_items = [self._document_to_entity(doc) for doc in documents]
        if priority_order:
            priority_order_map = {
                QueuePriority.URGENT: 4,
                QueuePriority.HIGH: 3,
                QueuePriority.NORMAL: 2,
                QueuePriority.LOW: 1
            }
            queue_items.sort(key=lambda x: priority_order_map[x.priority], reverse=True)

        return queue_items

    async def find_by_job_id(self, user_id: EntityId, job_id: str) -> Optional[JobQueue]:
        """Find queue item by user and job ID."""
        document = await self.collection.find_one({
            "user_id": str(user_id),
            "job_id": job_id
        })
        if not document:
            return None
        return self._document_to_entity(document)

    async def find_flagged_items(self, user_id: EntityId, limit: int = 50) -> List[JobQueue]:
        """Find flagged items for manual review."""
        filters = {
            "user_id": str(user_id),
            "user_flagged": True
        }

        cursor = self.collection.find(filters).sort("queued_at", -1).limit(limit)
        documents = await cursor.to_list(length=limit)

        return [self._document_to_entity(doc) for doc in documents]

    async def get_user_queue_stats(self, user_id: EntityId) -> Dict[str, Any]:
        """Get queue statistics for a user."""
        pipeline = [
            {"$match": {"user_id": str(user_id)}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "avg_match_score": {"$avg": "$match_score"}
            }}
        ]

        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        stats = {status.value: 0 for status in QueueStatus}
        avg_scores = {}

        for result in results:
            status = result["_id"]
            count = result["count"]
            avg_score = result.get("avg_match_score")

            stats[status] = count
            if avg_score:
                avg_scores[status] = avg_score

        # Calculate total applications submitted
        total_submitted = await self.collection.count_documents({
            "user_id": str(user_id),
            "application_submitted": True
        })

        # Calculate today's activity
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_queued = await self.collection.count_documents({
            "user_id": str(user_id),
            "queued_at": {"$gte": today_start}
        })

        return {
            "total_queued": sum(stats.values()),
            "by_status": stats,
            "avg_scores_by_status": avg_scores,
            "total_applications_submitted": total_submitted,
            "today_queued": today_queued
        }

    async def delete_by_id(self, queue_id: EntityId) -> bool:
        """Delete a queue item by ID."""
        result = await self.collection.delete_one({"_id": str(queue_id)})
        return result.deleted_count > 0

    async def bulk_update_status(
        self,
        user_id: EntityId,
        current_status: QueueStatus,
        new_status: QueueStatus
    ) -> int:
        """Bulk update status for user's queue items."""
        result = await self.collection.update_many(
            {
                "user_id": str(user_id),
                "status": current_status.value
            },
            {
                "$set": {
                    "status": new_status.value,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count

    def _document_to_entity(self, document: Dict[str, Any]) -> JobQueue:
        """Convert MongoDB document to JobQueue entity."""
        queue_id = EntityId.from_string(document["_id"])
        user_id = EntityId.from_string(document["user_id"])

        job_queue = JobQueue.__new__(JobQueue)
        job_queue._id = queue_id
        job_queue.user_id = user_id
        job_queue.job_id = document["job_id"]
        job_queue.job_data = document["job_data"]
        job_queue.priority = QueuePriority(document["priority"])
        job_queue.scheduled_for = document.get("scheduled_for")
        job_queue.match_score = document.get("match_score")
        job_queue.status = QueueStatus(document["status"])
        job_queue.queued_at = document["queued_at"]
        job_queue.processed_at = document.get("processed_at")
        job_queue.workflow_execution_id = EntityId.from_string(document["workflow_execution_id"]) if document.get("workflow_execution_id") else None
        job_queue.application_submitted = document.get("application_submitted", False)
        job_queue.application_id = EntityId.from_string(document["application_id"]) if document.get("application_id") else None
        job_queue.processing_error = document.get("processing_error")
        job_queue.user_flagged = document.get("user_flagged", False)
        job_queue.user_notes = document.get("user_notes")
        job_queue.user_action = UserAction(document["user_action"]) if document.get("user_action") else None
        job_queue.created_at = document["created_at"]
        job_queue.updated_at = document["updated_at"]
        job_queue.version = document.get("version", 1)
        job_queue._domain_events = []

        return job_queue