"""
Application settings value objects for user preferences.
"""

from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator

from jobhire.shared.domain.value_objects import ValueObject


class MatchLevel(str, Enum):
    """Match level options for job applications."""
    RELAXED = "relaxed"  # >30% Match - Open to Almost Everything
    BALANCED = "balanced"  # >55% Match - Looking for a Good Fit
    STRICT = "strict"  # >80% Match - Only Top Matches


class ApprovalMode(str, Enum):
    """Application approval modes."""
    MANUAL = "manual"  # Apply only with user approval
    AUTO_24H = "auto_24h"  # Apply automatically after 24 hours
    INSTANT = "instant"  # Apply instantly without approval


class ServiceStatus(str, Enum):
    """Service operation status."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class UserTier(str, Enum):
    """User subscription tiers."""
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class SearchSettings(ValueObject):
    """Search settings configuration."""

    match_level: MatchLevel = MatchLevel.BALANCED
    match_percentage: int = 55
    generate_cover_letter: bool = False  # Premium feature
    generate_ai_resume: bool = False  # Premium feature

    def __init__(self, **data):
        super().__init__(**data)
        # Set match percentage based on match level
        if self.match_level == MatchLevel.RELAXED:
            object.__setattr__(self, 'match_percentage', 30)
        elif self.match_level == MatchLevel.BALANCED:
            object.__setattr__(self, 'match_percentage', 55)
        elif self.match_level == MatchLevel.STRICT:
            object.__setattr__(self, 'match_percentage', 80)

    @validator('generate_cover_letter', 'generate_ai_resume')
    def validate_premium_features(cls, v, values, field):
        """Validate premium features based on user tier."""
        # Note: This validation would typically be done at the service level
        # with access to user tier information
        return v

    def is_premium_feature_enabled(self) -> bool:
        """Check if any premium features are enabled."""
        return self.generate_cover_letter or self.generate_ai_resume

    class Config:
        frozen = True


class ApplicationSettings(ValueObject):
    """Application submission settings."""

    approval_mode: ApprovalMode = ApprovalMode.MANUAL
    auto_submit_delay_hours: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        # Set delay based on approval mode
        if self.approval_mode == ApprovalMode.AUTO_24H:
            object.__setattr__(self, 'auto_submit_delay_hours', 24)
        elif self.approval_mode == ApprovalMode.INSTANT:
            object.__setattr__(self, 'auto_submit_delay_hours', 0)
        else:  # MANUAL
            object.__setattr__(self, 'auto_submit_delay_hours', 0)

    def requires_approval(self) -> bool:
        """Check if applications require manual approval."""
        return self.approval_mode == ApprovalMode.MANUAL

    def is_auto_submit_enabled(self) -> bool:
        """Check if auto-submit is enabled."""
        return self.approval_mode in [ApprovalMode.AUTO_24H, ApprovalMode.INSTANT]

    class Config:
        frozen = True


class EmailNotifications(ValueObject):
    """Email notification preferences."""

    interview_invitation: bool = True
    additional_info_request: bool = True
    application_acknowledgement: bool = False
    position_status_update: bool = False
    rejection_notification: bool = False
    system_application: bool = False
    other: bool = False

    def get_enabled_notifications(self) -> list[str]:
        """Get list of enabled notification types."""
        enabled = []
        for field_name, value in self.__dict__.items():
            if value and isinstance(value, bool):
                enabled.append(field_name)
        return enabled

    def is_notification_enabled(self, notification_type: str) -> bool:
        """Check if a specific notification type is enabled."""
        return getattr(self, notification_type, False)

    class Config:
        frozen = True


class ServiceOperation(ValueObject):
    """Service operation settings."""

    status: ServiceStatus = ServiceStatus.ACTIVE
    is_paused: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        # Sync is_paused with status
        object.__setattr__(self, 'is_paused', self.status == ServiceStatus.PAUSED)

    def is_active(self) -> bool:
        """Check if service is active."""
        return self.status == ServiceStatus.ACTIVE and not self.is_paused

    def can_process_jobs(self) -> bool:
        """Check if service can process jobs."""
        return self.status == ServiceStatus.ACTIVE

    class Config:
        frozen = True


class JobApplicationConfiguration(ValueObject):
    """Complete job application configuration."""

    user_email: str
    search_settings: SearchSettings
    application_settings: ApplicationSettings
    email_notifications: EmailNotifications
    service_operation: ServiceOperation

    @classmethod
    def create_default(cls, user_email: str) -> "JobApplicationConfiguration":
        """Create default configuration for a new user."""
        return cls(
            user_email=user_email,
            search_settings=SearchSettings(),
            application_settings=ApplicationSettings(),
            email_notifications=EmailNotifications(),
            service_operation=ServiceOperation()
        )

    @classmethod
    def from_user_input(cls, user_data: Dict[str, Any]) -> "JobApplicationConfiguration":
        """Create configuration from user input data."""
        return cls(
            user_email=user_data["userEmail"],
            search_settings=SearchSettings(**user_data["searchSettings"]),
            application_settings=ApplicationSettings(**user_data["applicationSettings"]),
            email_notifications=EmailNotifications(**user_data["emailNotifications"]),
            service_operation=ServiceOperation(**user_data["serviceOperation"])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "userEmail": self.user_email,
            "searchSettings": {
                "matchLevel": self.search_settings.match_level.value,
                "matchPercentage": self.search_settings.match_percentage,
                "generateCoverLetter": self.search_settings.generate_cover_letter,
                "generateAIResume": self.search_settings.generate_ai_resume
            },
            "applicationSettings": {
                "approvalMode": self.application_settings.approval_mode.value,
                "autoSubmitDelayHours": self.application_settings.auto_submit_delay_hours
            },
            "emailNotifications": {
                "interviewInvitation": self.email_notifications.interview_invitation,
                "additionalInfoRequest": self.email_notifications.additional_info_request,
                "applicationAcknowledgement": self.email_notifications.application_acknowledgement,
                "positionStatusUpdate": self.email_notifications.position_status_update,
                "rejectionNotification": self.email_notifications.rejection_notification,
                "systemApplication": self.email_notifications.system_application,
                "other": self.email_notifications.other
            },
            "serviceOperation": {
                "status": self.service_operation.status.value,
                "isPaused": self.service_operation.is_paused
            }
        }

    def validate_premium_features(self, user_tier: UserTier) -> None:
        """Validate that premium features are only used by premium users."""
        if user_tier == UserTier.FREE:
            if self.search_settings.generate_cover_letter:
                raise ValueError("Cover letter generation requires premium subscription")
            if self.search_settings.generate_ai_resume:
                raise ValueError("AI resume generation requires premium subscription")

    def get_minimum_match_score(self) -> float:
        """Get the minimum match score based on settings."""
        return float(self.search_settings.match_percentage)

    def should_auto_apply(self, match_score: float) -> bool:
        """Determine if a job should be auto-applied based on settings and score."""
        if not self.application_settings.is_auto_submit_enabled():
            return False

        if not self.service_operation.is_active():
            return False

        return match_score >= self.get_minimum_match_score()

    class Config:
        frozen = True