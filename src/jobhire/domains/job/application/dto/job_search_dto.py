"""
Data Transfer Objects for Job Search operations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from jobhire.domains.user.domain.value_objects.preferences import JobSearchPreferences
from jobhire.domains.job.domain.entities.job_search import JobSearch, JobSearchStatus


class SearchFiltersDTO(BaseModel):
    """DTO for job search filters."""

    keywords: List[str] = []
    excluded_keywords: List[str] = []
    locations: List[str] = []
    remote_only: bool = False
    employment_types: List[str] = ["full_time"]
    experience_levels: List[str] = []
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    company_sizes: List[str] = []
    industries: List[str] = []
    benefits: List[str] = []
    visa_sponsorship: bool = False
    date_posted: str = "all"  # all, today, 3days, week, month

    @classmethod
    def from_preferences(cls, preferences: JobSearchPreferences) -> "SearchFiltersDTO":
        """Create filters from user preferences."""
        return cls(
            keywords=preferences.keywords,
            excluded_keywords=preferences.excluded_keywords,
            locations=preferences.preferred_locations,
            remote_only=preferences.remote_preference.value == "remote_only",
            employment_types=[et.value for et in preferences.employment_types],
            experience_levels=[el.value for el in preferences.experience_levels],
            salary_min=preferences.minimum_salary.amount if preferences.minimum_salary else None,
            salary_max=preferences.maximum_salary.amount if preferences.maximum_salary else None,
            company_sizes=[cs.value for cs in preferences.preferred_company_sizes],
            industries=preferences.preferred_industries,
            benefits=preferences.required_benefits,
            visa_sponsorship=preferences.requires_visa_sponsorship
        )


class JobSearchRequestDTO(BaseModel):
    """DTO for job search requests."""

    query: str = Field(..., description="Main search query")
    filters: SearchFiltersDTO = Field(default_factory=SearchFiltersDTO)
    limit: Optional[int] = Field(50, ge=1, le=200, description="Maximum number of jobs to return")
    page: Optional[int] = Field(1, ge=1, description="Page number for pagination")
    sort_by: str = Field("relevance", description="Sort criteria: relevance, date, salary")
    include_similar: bool = Field(False, description="Include similar job recommendations")


class JobDTO(BaseModel):
    """DTO for job data."""

    id: str
    external_id: str
    title: str
    company_name: str
    company_logo: Optional[str] = None
    description: str
    location: Dict[str, Any]
    remote_option: str
    employment_type: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: str = "USD"
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    benefits: List[str] = []
    posted_date: Optional[datetime] = None
    application_url: Optional[str] = None
    source: str
    match_score: Optional[float] = None
    match_reasons: List[str] = []
    missing_skills: List[str] = []


class SearchPerformanceDTO(BaseModel):
    """DTO for search performance metrics."""

    total_jobs_found: int
    qualified_jobs_count: int
    jobs_above_threshold: int
    qualification_rate: float
    threshold_rate: float
    search_duration_seconds: Optional[float] = None
    api_calls_made: int
    results_quality: Optional[str] = None
    retry_count: int = 0


class JobSearchResultDTO(BaseModel):
    """DTO for job search results."""

    search_id: str
    user_id: str
    query: str
    status: str
    initiated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    jobs: List[JobDTO] = []
    total_jobs_found: int = 0
    qualified_jobs_count: int = 0
    jobs_above_threshold: int = 0

    # Performance metrics
    performance: SearchPerformanceDTO

    # Search parameters
    filters_applied: Dict[str, Any] = {}

    # Error information
    error_message: Optional[str] = None

    # Metadata
    version: int = 1

    @classmethod
    def from_job_search(cls, job_search: JobSearch) -> "JobSearchResultDTO":
        """Create DTO from JobSearch aggregate."""
        # Convert search results to JobDTOs
        job_dtos = []
        for job_data in job_search.search_results:
            job_dto = JobDTO(
                id=job_data.get("id", ""),
                external_id=job_data.get("external_id", ""),
                title=job_data.get("title", ""),
                company_name=job_data.get("company", {}).get("name", ""),
                company_logo=job_data.get("company", {}).get("logo"),
                description=job_data.get("description", ""),
                location=job_data.get("location", {}),
                remote_option=job_data.get("remote_option", "no"),
                employment_type=job_data.get("employment_type", ""),
                salary_min=job_data.get("salary_min"),
                salary_max=job_data.get("salary_max"),
                currency=job_data.get("currency", "USD"),
                required_skills=job_data.get("required_skills", []),
                preferred_skills=job_data.get("preferred_skills", []),
                benefits=job_data.get("benefits", []),
                posted_date=job_data.get("posted_date"),
                application_url=job_data.get("application_url"),
                source=job_data.get("source", ""),
                match_score=job_data.get("match_score"),
                match_reasons=job_data.get("match_reasons", []),
                missing_skills=job_data.get("missing_skills", [])
            )
            job_dtos.append(job_dto)

        # Create performance metrics
        performance_metrics = job_search.get_performance_metrics()
        performance = SearchPerformanceDTO(**performance_metrics)

        return cls(
            search_id=str(job_search.id),
            user_id=str(job_search.user_id),
            query=job_search.query,
            status=job_search.status.value,
            initiated_at=job_search.initiated_at,
            started_at=job_search.started_at,
            completed_at=job_search.completed_at,
            jobs=job_dtos,
            total_jobs_found=job_search.total_jobs_found,
            qualified_jobs_count=job_search.qualified_jobs_count,
            jobs_above_threshold=job_search.jobs_above_threshold,
            performance=performance,
            error_message=job_search.error_message,
            version=job_search.version
        )


class JobSearchHistoryDTO(BaseModel):
    """DTO for job search history."""

    searches: List[JobSearchResultDTO]
    total_count: int
    successful_searches: int
    failed_searches: int
    average_jobs_found: float
    average_qualification_rate: float
    most_successful_query: Optional[str] = None


class SearchPreferencesUpdateDTO(BaseModel):
    """DTO for updating search preferences."""

    keywords: Optional[List[str]] = None
    excluded_keywords: Optional[List[str]] = None
    job_titles: Optional[List[str]] = None
    excluded_titles: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    remote_preference: Optional[str] = None
    max_commute_distance: Optional[int] = None
    willing_to_relocate: Optional[bool] = None
    target_companies: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None
    preferred_company_sizes: Optional[List[str]] = None
    preferred_industries: Optional[List[str]] = None
    employment_types: Optional[List[str]] = None
    experience_levels: Optional[List[str]] = None
    minimum_salary: Optional[int] = None
    maximum_salary: Optional[int] = None
    required_benefits: Optional[List[str]] = None
    culture_preferences: Optional[List[str]] = None
    requires_visa_sponsorship: Optional[bool] = None


class SearchConfigurationUpdateDTO(BaseModel):
    """DTO for updating search configuration."""

    status: Optional[str] = None
    auto_search_enabled: Optional[bool] = None
    search_frequency_hours: Optional[int] = None
    minimum_match_score: Optional[float] = None
    auto_apply_threshold: Optional[float] = None
    require_manual_review: Optional[bool] = None
    max_applications_per_day: Optional[int] = None
    max_applications_per_week: Optional[int] = None
    max_applications_per_month: Optional[int] = None
    enabled_platforms: Optional[List[str]] = None