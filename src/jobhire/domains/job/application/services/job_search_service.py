"""
Job search application service.
Orchestrates job search operations following domain-driven design patterns.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.exceptions import BusinessRuleException, ValidationException
from jobhire.shared.infrastructure.monitoring.metrics import MetricsCollector, get_metrics_collector

from jobhire.domains.user.domain.value_objects.preferences import (
    JobSearchPreferences, SearchConfiguration, SearchStatus
)
from jobhire.domains.job.domain.entities.job_search import JobSearch, JobSearchStatus
from jobhire.domains.job.application.dto.job_search_dto import (
    JobSearchRequestDTO, JobSearchResultDTO, SearchFiltersDTO
)


logger = structlog.get_logger(__name__)


class JobSearchService:
    """
    Application service for job search operations.
    Coordinates between domain entities and infrastructure services.
    """

    def __init__(
        self,
        job_fetching_service,
        job_matching_service,
        user_repository,
        job_search_repository,
        event_bus,
        metrics_collector: Optional[MetricsCollector] = None
    ):
        self.job_fetching_service = job_fetching_service
        self.job_matching_service = job_matching_service
        self.user_repository = user_repository
        self.job_search_repository = job_search_repository
        self.event_bus = event_bus
        self.metrics = metrics_collector or get_metrics_collector()
        self.logger = logger.bind(service="JobSearchService")

    async def execute_job_search(
        self,
        user_id: EntityId,
        search_request: JobSearchRequestDTO
    ) -> JobSearchResultDTO:
        """
        Execute a complete job search for a user.
        """
        search_start_time = datetime.utcnow()
        self.logger.info("Starting job search", user_id=str(user_id), query=search_request.query)

        try:
            # Get user and validate search permissions
            user = await self.user_repository.find_by_id(user_id)
            if not user:
                raise ValidationException("User not found")

            if not self._can_user_perform_search(user):
                raise BusinessRuleException("User has exceeded search limits")

            # Get user's search preferences
            search_preferences = user.get_search_preferences()
            search_configuration = user.get_search_configuration()

            # Validate search is allowed
            if search_configuration.status != SearchStatus.ACTIVE:
                raise BusinessRuleException("User search is not active")

            # Create job search aggregate
            search_id = EntityId.generate()
            job_search = JobSearch(
                search_id=search_id,
                user_id=user_id,
                search_preferences=search_preferences,
                search_configuration=search_configuration,
                query=search_request.query
            )

            # Build search filters from preferences and request
            search_filters = self._build_search_filters(search_preferences, search_request)

            # Start the search
            job_search.start_search(search_filters.dict())

            # Save search entity
            await self.job_search_repository.save(job_search)

            # Execute search with external service
            raw_jobs = await self._fetch_jobs_from_external_sources(
                search_request, search_filters
            )

            # Process and score jobs
            processed_jobs = await self._process_and_score_jobs(
                raw_jobs, user, search_preferences
            )

            # Add results to search aggregate
            job_search.add_search_results(processed_jobs, api_calls_made=1)

            # Complete the search
            search_duration = (datetime.utcnow() - search_start_time).total_seconds()
            job_search.complete_search(search_duration)

            # Save updated search
            await self.job_search_repository.save(job_search)

            # Publish domain events
            await self._publish_search_events(job_search)

            # Record metrics
            self.metrics.record_database_operation(
                operation="job_search",
                collection="job_searches",
                duration=search_duration,
                success=True
            )

            # Update user search history
            await self._update_user_search_history(user, job_search)

            self.logger.info(
                "Job search completed successfully",
                user_id=str(user_id),
                search_id=str(search_id),
                total_jobs=job_search.total_jobs_found,
                qualified_jobs=job_search.qualified_jobs_count,
                duration=search_duration
            )

            return JobSearchResultDTO.from_job_search(job_search)

        except Exception as e:
            # Handle search failure
            if 'job_search' in locals():
                job_search.fail_search(str(e))
                await self.job_search_repository.save(job_search)

            self.metrics.record_error(
                error_type=type(e).__name__,
                component="job_search"
            )

            self.logger.error(
                "Job search failed",
                user_id=str(user_id),
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def get_user_search_history(
        self,
        user_id: EntityId,
        limit: int = 20,
        include_failed: bool = False
    ) -> List[JobSearchResultDTO]:
        """Get user's job search history."""
        try:
            search_history = await self.job_search_repository.find_by_user_id(
                user_id, limit=limit, include_failed=include_failed
            )

            return [
                JobSearchResultDTO.from_job_search(search)
                for search in search_history
            ]

        except Exception as e:
            self.logger.error(
                "Failed to get search history",
                user_id=str(user_id),
                error=str(e)
            )
            raise

    async def cancel_search(self, search_id: EntityId, reason: str) -> None:
        """Cancel an ongoing job search."""
        try:
            job_search = await self.job_search_repository.find_by_id(search_id)
            if not job_search:
                raise ValidationException("Job search not found")

            job_search.cancel_search(reason)
            await self.job_search_repository.save(job_search)

            await self._publish_search_events(job_search)

            self.logger.info(
                "Job search cancelled",
                search_id=str(search_id),
                reason=reason
            )

        except Exception as e:
            self.logger.error(
                "Failed to cancel search",
                search_id=str(search_id),
                error=str(e)
            )
            raise

    async def retry_failed_search(self, search_id: EntityId) -> JobSearchResultDTO:
        """Retry a failed job search."""
        try:
            job_search = await self.job_search_repository.find_by_id(search_id)
            if not job_search:
                raise ValidationException("Job search not found")

            job_search.retry_search()
            await self.job_search_repository.save(job_search)

            # Create new search request from original search
            search_request = JobSearchRequestDTO(
                query=job_search.query,
                filters=SearchFiltersDTO.from_preferences(job_search.search_preferences)
            )

            # Execute the search again
            return await self.execute_job_search(job_search.user_id, search_request)

        except Exception as e:
            self.logger.error(
                "Failed to retry search",
                search_id=str(search_id),
                error=str(e)
            )
            raise

    def _can_user_perform_search(self, user) -> bool:
        """Check if user can perform job search based on subscription limits."""
        # Implementation would check user's subscription tier and usage
        # For now, always allow
        return True

    def _build_search_filters(
        self,
        preferences: JobSearchPreferences,
        request: JobSearchRequestDTO
    ) -> SearchFiltersDTO:
        """Build comprehensive search filters."""
        return SearchFiltersDTO(
            keywords=request.filters.keywords or preferences.keywords,
            excluded_keywords=preferences.excluded_keywords,
            locations=request.filters.locations or preferences.preferred_locations,
            remote_only=request.filters.remote_only,
            employment_types=request.filters.employment_types or [
                et.value for et in preferences.employment_types
            ],
            experience_levels=request.filters.experience_levels or [
                el.value for el in preferences.experience_levels
            ],
            salary_min=request.filters.salary_min or (
                preferences.minimum_salary.amount if preferences.minimum_salary else None
            ),
            salary_max=request.filters.salary_max or (
                preferences.maximum_salary.amount if preferences.maximum_salary else None
            ),
            company_sizes=request.filters.company_sizes or [
                cs.value for cs in preferences.preferred_company_sizes
            ],
            industries=request.filters.industries or preferences.preferred_industries,
            benefits=preferences.required_benefits,
            visa_sponsorship=preferences.requires_visa_sponsorship
        )

    async def _fetch_jobs_from_external_sources(
        self,
        search_request: JobSearchRequestDTO,
        search_filters: SearchFiltersDTO
    ) -> List[Dict[str, Any]]:
        """Fetch jobs from external job boards."""
        return await self.job_fetching_service.search_jobs(
            query=search_request.query,
            filters=search_filters,
            limit=search_request.limit or 50
        )

    async def _process_and_score_jobs(
        self,
        raw_jobs: List[Dict[str, Any]],
        user,
        preferences: JobSearchPreferences
    ) -> List[Dict[str, Any]]:
        """Process raw jobs and add matching scores."""
        processed_jobs = []

        for job_data in raw_jobs:
            try:
                # Calculate match score
                match_score = await self.job_matching_service.calculate_match_score(
                    job_data, user.get_profile(), preferences
                )

                # Add score to job data
                job_data["match_score"] = match_score
                job_data["processed_at"] = datetime.utcnow().isoformat()

                processed_jobs.append(job_data)

            except Exception as e:
                self.logger.warning(
                    "Failed to process job",
                    job_id=job_data.get("id"),
                    error=str(e)
                )
                continue

        return processed_jobs

    async def _publish_search_events(self, job_search: JobSearch) -> None:
        """Publish domain events for the job search."""
        for event in job_search.events:
            await self.event_bus.publish(event)
        job_search.clear_events()

    async def _update_user_search_history(self, user, job_search: JobSearch) -> None:
        """Update user's search history and statistics."""
        # This would update user's search statistics
        # Implementation depends on user repository interface
        pass