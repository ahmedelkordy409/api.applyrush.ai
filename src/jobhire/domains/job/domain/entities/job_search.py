"""
Job search aggregate root entity.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from jobhire.shared.domain.base import AggregateRoot, DomainEvent
from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.exceptions import BusinessRuleException
from jobhire.domains.user.domain.value_objects.preferences import (
    JobSearchPreferences, SearchConfiguration, SearchStatus
)


class JobSearchStatus(str, Enum):
    """Job search execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSearchResultsQuality(str, Enum):
    """Quality assessment of search results."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class JobSearch(AggregateRoot[EntityId]):
    """Job search aggregate root representing a single search execution."""

    def __init__(
        self,
        search_id: EntityId,
        user_id: EntityId,
        search_preferences: JobSearchPreferences,
        search_configuration: SearchConfiguration,
        query: str,
        initiated_at: Optional[datetime] = None
    ):
        super().__init__(search_id)
        self._user_id = user_id
        self._search_preferences = search_preferences
        self._search_configuration = search_configuration
        self._query = query
        self._status = JobSearchStatus.PENDING
        self._initiated_at = initiated_at or datetime.utcnow()
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None

        # Search results
        self._total_jobs_found = 0
        self._qualified_jobs_count = 0
        self._jobs_above_threshold = 0
        self._search_results: List[Dict[str, Any]] = []

        # Performance metrics
        self._search_duration_seconds: Optional[float] = None
        self._api_calls_made = 0
        self._results_quality: Optional[JobSearchResultsQuality] = None

        # Error handling
        self._error_message: Optional[str] = None
        self._retry_count = 0
        self._max_retries = 3

        # Filters applied
        self._filters_applied: Dict[str, Any] = {}

        # Add domain event
        self.add_event(JobSearchInitiated(
            event_type="JobSearchInitiated",
            entity_id=str(self.id),
            data={
                "user_id": str(self._user_id),
                "query": self._query,
                "search_preferences": self._search_preferences.dict(),
                "initiated_at": self._initiated_at.isoformat()
            }
        ))

    @property
    def user_id(self) -> EntityId:
        return self._user_id

    @property
    def query(self) -> str:
        return self._query

    @property
    def status(self) -> JobSearchStatus:
        return self._status

    @property
    def search_preferences(self) -> JobSearchPreferences:
        return self._search_preferences

    @property
    def search_configuration(self) -> SearchConfiguration:
        return self._search_configuration

    @property
    def initiated_at(self) -> datetime:
        return self._initiated_at

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at

    @property
    def completed_at(self) -> Optional[datetime]:
        return self._completed_at

    @property
    def total_jobs_found(self) -> int:
        return self._total_jobs_found

    @property
    def qualified_jobs_count(self) -> int:
        return self._qualified_jobs_count

    @property
    def jobs_above_threshold(self) -> int:
        return self._jobs_above_threshold

    @property
    def search_results(self) -> List[Dict[str, Any]]:
        return self._search_results.copy()

    @property
    def search_duration_seconds(self) -> Optional[float]:
        return self._search_duration_seconds

    @property
    def results_quality(self) -> Optional[JobSearchResultsQuality]:
        return self._results_quality

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @property
    def is_completed(self) -> bool:
        return self._status in [JobSearchStatus.COMPLETED, JobSearchStatus.FAILED, JobSearchStatus.CANCELLED]

    @property
    def is_successful(self) -> bool:
        return self._status == JobSearchStatus.COMPLETED and self._qualified_jobs_count > 0

    def start_search(self, filters_applied: Dict[str, Any]) -> None:
        """Start the job search execution."""
        if self._status != JobSearchStatus.PENDING:
            raise BusinessRuleException("Job search can only be started from pending status")

        self._status = JobSearchStatus.IN_PROGRESS
        self._started_at = datetime.utcnow()
        self._filters_applied = filters_applied
        self.increment_version()

        self.add_event(JobSearchStarted(
            event_type="JobSearchStarted",
            entity_id=str(self.id),
            data={
                "user_id": str(self._user_id),
                "started_at": self._started_at.isoformat(),
                "filters_applied": filters_applied
            }
        ))

    def add_search_results(self, jobs: List[Dict[str, Any]], api_calls_made: int) -> None:
        """Add jobs found during search."""
        if self._status != JobSearchStatus.IN_PROGRESS:
            raise BusinessRuleException("Can only add results to in-progress search")

        self._search_results.extend(jobs)
        self._total_jobs_found = len(self._search_results)
        self._api_calls_made += api_calls_made

        # Count qualified jobs (those meeting minimum criteria)
        min_score = self._search_configuration.minimum_match_score
        threshold_score = self._search_configuration.auto_apply_threshold

        self._qualified_jobs_count = sum(
            1 for job in self._search_results
            if job.get("match_score", 0) >= min_score
        )

        self._jobs_above_threshold = sum(
            1 for job in self._search_results
            if job.get("match_score", 0) >= threshold_score
        )

        self.increment_version()

    def complete_search(self, duration_seconds: float) -> None:
        """Mark search as completed successfully."""
        if self._status != JobSearchStatus.IN_PROGRESS:
            raise BusinessRuleException("Can only complete in-progress search")

        self._status = JobSearchStatus.COMPLETED
        self._completed_at = datetime.utcnow()
        self._search_duration_seconds = duration_seconds
        self._results_quality = self._assess_results_quality()
        self.increment_version()

        self.add_event(JobSearchCompleted(
            event_type="JobSearchCompleted",
            entity_id=str(self.id),
            data={
                "user_id": str(self._user_id),
                "completed_at": self._completed_at.isoformat(),
                "total_jobs_found": self._total_jobs_found,
                "qualified_jobs_count": self._qualified_jobs_count,
                "jobs_above_threshold": self._jobs_above_threshold,
                "duration_seconds": self._search_duration_seconds,
                "results_quality": self._results_quality.value if self._results_quality else None
            }
        ))

    def fail_search(self, error_message: str) -> None:
        """Mark search as failed."""
        if self._status != JobSearchStatus.IN_PROGRESS:
            raise BusinessRuleException("Can only fail in-progress search")

        self._status = JobSearchStatus.FAILED
        self._completed_at = datetime.utcnow()
        self._error_message = error_message

        if self._started_at:
            self._search_duration_seconds = (self._completed_at - self._started_at).total_seconds()

        self.increment_version()

        self.add_event(JobSearchFailed(
            event_type="JobSearchFailed",
            entity_id=str(self.id),
            data={
                "user_id": str(self._user_id),
                "failed_at": self._completed_at.isoformat(),
                "error_message": error_message,
                "retry_count": self._retry_count
            }
        ))

    def cancel_search(self, reason: str) -> None:
        """Cancel the job search."""
        if self.is_completed:
            raise BusinessRuleException("Cannot cancel completed search")

        self._status = JobSearchStatus.CANCELLED
        self._completed_at = datetime.utcnow()
        self._error_message = f"Cancelled: {reason}"

        if self._started_at:
            self._search_duration_seconds = (self._completed_at - self._started_at).total_seconds()

        self.increment_version()

        self.add_event(JobSearchCancelled(
            event_type="JobSearchCancelled",
            entity_id=str(self.id),
            data={
                "user_id": str(self._user_id),
                "cancelled_at": self._completed_at.isoformat(),
                "reason": reason
            }
        ))

    def retry_search(self) -> None:
        """Retry a failed search."""
        if self._status != JobSearchStatus.FAILED:
            raise BusinessRuleException("Can only retry failed searches")

        if self._retry_count >= self._max_retries:
            raise BusinessRuleException("Maximum retry attempts exceeded")

        self._retry_count += 1
        self._status = JobSearchStatus.PENDING
        self._error_message = None
        self._search_results.clear()
        self._total_jobs_found = 0
        self._qualified_jobs_count = 0
        self._jobs_above_threshold = 0
        self.increment_version()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get search performance metrics."""
        return {
            "total_jobs_found": self._total_jobs_found,
            "qualified_jobs_count": self._qualified_jobs_count,
            "jobs_above_threshold": self._jobs_above_threshold,
            "qualification_rate": (
                self._qualified_jobs_count / self._total_jobs_found
                if self._total_jobs_found > 0 else 0
            ),
            "threshold_rate": (
                self._jobs_above_threshold / self._total_jobs_found
                if self._total_jobs_found > 0 else 0
            ),
            "search_duration_seconds": self._search_duration_seconds,
            "api_calls_made": self._api_calls_made,
            "results_quality": self._results_quality.value if self._results_quality else None,
            "retry_count": self._retry_count
        }

    def _assess_results_quality(self) -> JobSearchResultsQuality:
        """Assess the quality of search results."""
        if self._total_jobs_found == 0:
            return JobSearchResultsQuality.POOR

        qualification_rate = self._qualified_jobs_count / self._total_jobs_found
        threshold_rate = self._jobs_above_threshold / self._total_jobs_found

        if threshold_rate >= 0.3:  # 30% or more above threshold
            return JobSearchResultsQuality.EXCELLENT
        elif qualification_rate >= 0.5:  # 50% or more qualified
            return JobSearchResultsQuality.GOOD
        elif qualification_rate >= 0.2:  # 20% or more qualified
            return JobSearchResultsQuality.FAIR
        else:
            return JobSearchResultsQuality.POOR

    def apply_event(self, event: DomainEvent) -> None:
        """Apply domain event to the aggregate."""
        # Implementation for event sourcing if needed
        pass


# Domain Events
class JobSearchInitiated(DomainEvent):
    """Event raised when a job search is initiated."""
    pass


class JobSearchStarted(DomainEvent):
    """Event raised when a job search starts execution."""
    pass


class JobSearchCompleted(DomainEvent):
    """Event raised when a job search completes successfully."""
    pass


class JobSearchFailed(DomainEvent):
    """Event raised when a job search fails."""
    pass


class JobSearchCancelled(DomainEvent):
    """Event raised when a job search is cancelled."""
    pass