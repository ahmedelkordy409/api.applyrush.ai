"""
Job Search repository implementation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.repositories import BaseMongoRepository
from jobhire.domains.job.domain.entities.job_search import JobSearch, JobSearchStatus


class JobSearchRepository(BaseMongoRepository[JobSearch]):
    """Repository for job search management."""

    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, "job_searches", JobSearch)

    async def create(self, job_search: JobSearch) -> None:
        """Create a new job search."""
        document = {
            "_id": str(job_search.id),
            "user_id": str(job_search.user_id),
            "query": job_search.query,
            "status": job_search.status.value,
            "initiated_at": job_search.initiated_at,
            "started_at": job_search.started_at,
            "completed_at": job_search.completed_at,
            "search_results": job_search.search_results,
            "total_jobs_found": job_search.total_jobs_found,
            "qualified_jobs_count": job_search.qualified_jobs_count,
            "jobs_above_threshold": job_search.jobs_above_threshold,
            "error_message": job_search.error_message,
            "created_at": job_search.created_at,
            "updated_at": job_search.updated_at,
            "version": job_search.version
        }
        await self.collection.insert_one(document)

    async def update(self, job_search: JobSearch) -> None:
        """Update an existing job search."""
        document = {
            "user_id": str(job_search.user_id),
            "query": job_search.query,
            "status": job_search.status.value,
            "initiated_at": job_search.initiated_at,
            "started_at": job_search.started_at,
            "completed_at": job_search.completed_at,
            "search_results": job_search.search_results,
            "total_jobs_found": job_search.total_jobs_found,
            "qualified_jobs_count": job_search.qualified_jobs_count,
            "jobs_above_threshold": job_search.jobs_above_threshold,
            "error_message": job_search.error_message,
            "updated_at": job_search.updated_at,
            "version": job_search.version
        }

        await self.collection.update_one(
            {"_id": str(job_search.id)},
            {"$set": document}
        )

    async def find_by_id(self, search_id: EntityId) -> Optional[JobSearch]:
        """Find job search by ID."""
        document = await self.collection.find_one({"_id": str(search_id)})
        if not document:
            return None
        return self._document_to_entity(document)

    async def find_by_user_id(
        self,
        user_id: EntityId,
        status: Optional[JobSearchStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[JobSearch]:
        """Find job searches for a user."""
        filters = {"user_id": str(user_id)}
        if status:
            filters["status"] = status.value

        cursor = self.collection.find(filters).sort("initiated_at", -1).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)

        return [self._document_to_entity(doc) for doc in documents]

    async def find_recent_searches(
        self,
        user_id: EntityId,
        days: int = 30,
        limit: int = 20
    ) -> List[JobSearch]:
        """Find recent job searches for analytics."""
        since_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        since_date = since_date.replace(day=since_date.day - days)

        filters = {
            "user_id": str(user_id),
            "initiated_at": {"$gte": since_date}
        }

        cursor = self.collection.find(filters).sort("initiated_at", -1).limit(limit)
        documents = await cursor.to_list(length=limit)

        return [self._document_to_entity(doc) for doc in documents]

    async def get_search_analytics(self, user_id: EntityId, days: int = 30) -> Dict[str, Any]:
        """Get search analytics for a user."""
        since_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        since_date = since_date.replace(day=since_date.day - days)

        pipeline = [
            {"$match": {
                "user_id": str(user_id),
                "initiated_at": {"$gte": since_date}
            }},
            {"$group": {
                "_id": None,
                "total_searches": {"$sum": 1},
                "completed_searches": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                "failed_searches": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                "total_jobs_found": {"$sum": "$total_jobs_found"},
                "total_qualified_jobs": {"$sum": "$qualified_jobs_count"},
                "avg_jobs_per_search": {"$avg": "$total_jobs_found"}
            }}
        ]

        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)

        if not results:
            return {
                "total_searches": 0,
                "completed_searches": 0,
                "failed_searches": 0,
                "total_jobs_found": 0,
                "total_qualified_jobs": 0,
                "avg_jobs_per_search": 0.0,
                "success_rate": 0.0
            }

        result = results[0]
        success_rate = 0.0
        if result["total_searches"] > 0:
            success_rate = result["completed_searches"] / result["total_searches"] * 100

        return {
            "total_searches": result["total_searches"],
            "completed_searches": result["completed_searches"],
            "failed_searches": result["failed_searches"],
            "total_jobs_found": result["total_jobs_found"],
            "total_qualified_jobs": result["total_qualified_jobs"],
            "avg_jobs_per_search": round(result["avg_jobs_per_search"], 1),
            "success_rate": round(success_rate, 1)
        }

    def _document_to_entity(self, document: Dict[str, Any]) -> JobSearch:
        """Convert MongoDB document to JobSearch entity."""
        search_id = EntityId.from_string(document["_id"])
        user_id = EntityId.from_string(document["user_id"])

        job_search = JobSearch.__new__(JobSearch)
        job_search._id = search_id
        job_search.user_id = user_id
        job_search.query = document["query"]
        job_search.status = JobSearchStatus(document["status"])
        job_search.initiated_at = document["initiated_at"]
        job_search.started_at = document.get("started_at")
        job_search.completed_at = document.get("completed_at")
        job_search.search_results = document.get("search_results", [])
        job_search.total_jobs_found = document.get("total_jobs_found", 0)
        job_search.qualified_jobs_count = document.get("qualified_jobs_count", 0)
        job_search.jobs_above_threshold = document.get("jobs_above_threshold", 0)
        job_search.error_message = document.get("error_message")
        job_search.created_at = document["created_at"]
        job_search.updated_at = document["updated_at"]
        job_search.version = document.get("version", 1)
        job_search._domain_events = []

        return job_search