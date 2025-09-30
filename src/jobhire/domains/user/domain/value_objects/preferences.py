"""
User job search preferences and settings value objects.
"""

from datetime import time, datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from jobhire.shared.domain.base import ValueObject
from jobhire.shared.domain.types import Money
from jobhire.shared.domain.exceptions import ValidationException


class SearchStatus(str, Enum):
    """Job search status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class RemotePreference(str, Enum):
    """Remote work preference."""
    REMOTE_ONLY = "remote_only"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    NO_PREFERENCE = "no_preference"


class EmploymentType(str, Enum):
    """Employment type preferences."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class ExperienceLevel(str, Enum):
    """Experience level categories."""
    ENTRY_LEVEL = "entry_level"
    MID_LEVEL = "mid_level"
    SENIOR_LEVEL = "senior_level"
    EXECUTIVE = "executive"


class CompanySize(str, Enum):
    """Company size preferences."""
    STARTUP = "startup"          # 1-50 employees
    SMALL = "small"              # 51-200 employees
    MEDIUM = "medium"            # 201-1000 employees
    LARGE = "large"              # 1001-10000 employees
    ENTERPRISE = "enterprise"    # 10000+ employees


class JobSearchPreferences(ValueObject):
    """Comprehensive job search preferences."""

    # Search keywords and filters
    keywords: List[str] = []
    excluded_keywords: List[str] = []
    job_titles: List[str] = []
    excluded_titles: List[str] = []

    # Location preferences
    preferred_locations: List[str] = []
    remote_preference: RemotePreference = RemotePreference.NO_PREFERENCE
    max_commute_distance: Optional[int] = None  # in miles
    willing_to_relocate: bool = False

    # Company preferences
    target_companies: List[str] = []
    excluded_companies: List[str] = []
    preferred_company_sizes: List[CompanySize] = []
    preferred_industries: List[str] = []

    # Job criteria
    employment_types: List[EmploymentType] = [EmploymentType.FULL_TIME]
    experience_levels: List[ExperienceLevel] = []
    minimum_salary: Optional[Money] = None
    maximum_salary: Optional[Money] = None

    # Benefits and culture
    required_benefits: List[str] = []
    culture_preferences: List[str] = []

    # Visa and legal requirements
    requires_visa_sponsorship: bool = False
    security_clearance_required: Optional[str] = None

    def __post_init__(self):
        """Validate preferences after initialization."""
        if self.minimum_salary and self.maximum_salary:
            if self.minimum_salary.amount > self.maximum_salary.amount:
                raise ValidationException("Minimum salary cannot be greater than maximum salary")

        if self.max_commute_distance and self.max_commute_distance < 0:
            raise ValidationException("Commute distance cannot be negative")


class SearchConfiguration(ValueObject):
    """Search automation and filtering configuration."""

    # Search status and control
    status: SearchStatus = SearchStatus.ACTIVE
    auto_search_enabled: bool = True
    search_frequency_hours: int = 4  # How often to search

    # Matching and filtering
    minimum_match_score: float = 70.0
    auto_apply_threshold: float = 85.0
    require_manual_review: bool = True

    # Application limits
    max_applications_per_day: int = 10
    max_applications_per_week: int = 50
    max_applications_per_month: int = 200

    # Time restrictions
    search_active_hours_start: time = time(9, 0)  # 9:00 AM
    search_active_hours_end: time = time(17, 0)   # 5:00 PM
    search_active_days: List[str] = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    timezone: str = "UTC"

    # Platform settings
    enabled_platforms: List[str] = ["linkedin", "indeed", "glassdoor"]

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not (0 <= self.minimum_match_score <= 100):
            raise ValidationException("Minimum match score must be between 0 and 100")

        if not (0 <= self.auto_apply_threshold <= 100):
            raise ValidationException("Auto apply threshold must be between 0 and 100")

        if self.minimum_match_score > self.auto_apply_threshold:
            raise ValidationException("Minimum match score cannot be greater than auto apply threshold")

        if self.max_applications_per_day <= 0:
            raise ValidationException("Max applications per day must be positive")

        if self.search_frequency_hours <= 0:
            raise ValidationException("Search frequency must be positive")


class NotificationPreferences(ValueObject):
    """User notification preferences for job search."""

    # Email notifications
    email_enabled: bool = True
    daily_digest: bool = True
    instant_matches: bool = False
    application_updates: bool = True

    # SMS notifications
    sms_enabled: bool = False
    urgent_only: bool = True

    # In-app notifications
    push_enabled: bool = True
    match_notifications: bool = True
    application_status_updates: bool = True

    # Frequency settings
    max_notifications_per_day: int = 10
    quiet_hours_start: time = time(22, 0)  # 10:00 PM
    quiet_hours_end: time = time(8, 0)     # 8:00 AM


class SearchHistory(ValueObject):
    """Track search history and performance."""

    total_searches_performed: int = 0
    last_search_date: Optional[datetime] = None
    total_jobs_found: int = 0
    total_applications_submitted: int = 0

    # Performance metrics
    average_match_score: float = 0.0
    success_rate: float = 0.0  # Applications that led to interviews
    response_rate: float = 0.0  # Applications that got responses

    # Most successful criteria
    best_keywords: List[str] = []
    best_locations: List[str] = []
    best_companies: List[str] = []


class JobSearchSettings(ValueObject):
    """Complete job search settings combining all preferences."""

    preferences: JobSearchPreferences
    configuration: SearchConfiguration
    notifications: NotificationPreferences
    history: SearchHistory = SearchHistory()

    # Metadata
    created_at: datetime
    updated_at: datetime
    version: int = 1

    @classmethod
    def create_default(cls) -> "JobSearchSettings":
        """Create default job search settings for new users."""
        return cls(
            preferences=JobSearchPreferences(),
            configuration=SearchConfiguration(),
            notifications=NotificationPreferences(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def update_preferences(self, new_preferences: JobSearchPreferences) -> "JobSearchSettings":
        """Update search preferences and return new settings."""
        return JobSearchSettings(
            preferences=new_preferences,
            configuration=self.configuration,
            notifications=self.notifications,
            history=self.history,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
            version=self.version + 1
        )

    def update_configuration(self, new_config: SearchConfiguration) -> "JobSearchSettings":
        """Update search configuration and return new settings."""
        return JobSearchSettings(
            preferences=self.preferences,
            configuration=new_config,
            notifications=self.notifications,
            history=self.history,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
            version=self.version + 1
        )

    def is_search_active(self) -> bool:
        """Check if search is currently active."""
        return (
            self.configuration.status == SearchStatus.ACTIVE and
            self.configuration.auto_search_enabled
        )

    def can_apply_automatically(self, match_score: float) -> bool:
        """Check if a job can be automatically applied to."""
        return (
            self.is_search_active() and
            match_score >= self.configuration.auto_apply_threshold and
            not self.configuration.require_manual_review
        )

    def should_notify_user(self, match_score: float) -> bool:
        """Check if user should be notified about a match."""
        return (
            self.notifications.match_notifications and
            match_score >= self.configuration.minimum_match_score
        )