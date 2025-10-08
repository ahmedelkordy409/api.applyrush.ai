"""
Onboarding models for guest profiles and progressive data collection
"""

from beanie import Document, Indexed
from pydantic import Field, BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from bson import ObjectId
import secrets
import string


class OnboardingStatus(str, Enum):
    """Onboarding session status"""
    IN_PROGRESS = "in_progress"
    EMAIL_PROVIDED = "email_provided"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    CONVERTED = "converted"


class GuestProfile(Document):
    """Guest profile for anonymous onboarding sessions"""

    # Session identification
    session_id: Indexed(str, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=30))

    # Session status
    status: OnboardingStatus = OnboardingStatus.IN_PROGRESS
    current_step: int = 0
    completed_steps: List[str] = []

    # Collected data (progressively filled)
    answers: Dict[str, Any] = {}

    # Conversion tracking
    email: Optional[EmailStr] = None
    converted_user_id: Optional[ObjectId] = None
    converted_at: Optional[datetime] = None

    # Analytics
    time_spent_seconds: int = 0
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    abandoned_at_step: Optional[str] = None

    class Settings:
        name = "guest_profiles"
        indexes = [
            "session_id",
            "email",
            "status",
            "created_at",
            "expires_at"
        ]

    @classmethod
    def generate_session_id(cls) -> str:
        """Generate a unique session ID for guest users"""
        alphabet = string.ascii_letters + string.digits
        return 'guest_' + ''.join(secrets.choice(alphabet) for _ in range(32))

    def update_answer(self, step_id: str, answer_data: Dict[str, Any]):
        """Update or add an answer for a specific step"""
        self.answers[step_id] = {
            **answer_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.updated_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)

    def __repr__(self):
        return f"<GuestProfile {self.session_id} - {self.status}>"


class OnboardingAnswer(Document):
    """Individual answer storage for better querying and analytics"""

    # Association
    guest_session_id: Indexed(str)
    user_id: Optional[ObjectId] = None

    # Question details
    step_id: Indexed(str)
    question_type: str
    question_text: Optional[str] = None

    # Answer data
    answer: Dict[str, Any]

    # Metadata
    answered_at: datetime = Field(default_factory=datetime.utcnow)
    time_to_answer_seconds: Optional[int] = None

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = []

    class Settings:
        name = "onboarding_answers"
        indexes = [
            "guest_session_id",
            "user_id",
            "step_id",
            [("guest_session_id", 1), ("step_id", 1)]
        ]

    def __repr__(self):
        return f"<OnboardingAnswer {self.step_id} for {self.guest_session_id}>"


class OnboardingConfiguration(Document):
    """Configuration for onboarding flow questions and steps"""

    name: str
    version: str
    is_active: bool = True

    # Steps configuration
    steps: List[Dict[str, Any]] = []

    # Rules and branching logic
    branching_rules: Optional[Dict[str, Any]] = {}

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "onboarding_configurations"
        indexes = [
            "name",
            "version",
            "is_active"
        ]

    def __repr__(self):
        return f"<OnboardingConfiguration {self.name} v{self.version}>"


class OnboardingConversion(Document):
    """Track guest to user conversions"""

    # IDs
    guest_session_id: Indexed(str)
    user_id: ObjectId

    # Conversion details
    email: EmailStr
    temporary_password: Optional[str] = None

    # Timing
    session_started_at: datetime
    email_provided_at: datetime
    conversion_completed_at: datetime = Field(default_factory=datetime.utcnow)
    total_duration_seconds: int

    # Data transfer
    answers_transferred: int
    data_migrated: bool = False

    class Settings:
        name = "onboarding_conversions"
        indexes = [
            "guest_session_id",
            "user_id",
            "email",
            "conversion_completed_at"
        ]

    def __repr__(self):
        return f"<OnboardingConversion {self.guest_session_id} -> {self.email}>"


# DTOs for API requests/responses
class CreateGuestSessionRequest(BaseModel):
    """Request to create a new guest session"""
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class CreateGuestSessionResponse(BaseModel):
    """Response with new guest session details"""
    session_id: str
    created_at: datetime
    expires_at: datetime


class SaveAnswerRequest(BaseModel):
    """Request to save an answer for a step"""
    session_id: str
    step_id: str
    answer: Dict[str, Any]
    time_spent_seconds: Optional[int] = None


class SaveAnswerResponse(BaseModel):
    """Response after saving an answer"""
    success: bool
    session_id: str
    step_id: str
    completed_steps: List[str]
    current_step: int


class ConvertGuestRequest(BaseModel):
    """Request to convert guest to user"""
    session_id: str
    email: EmailStr
    password: Optional[str] = None
    generate_temp_password: bool = True


class ConvertGuestResponse(BaseModel):
    """Response after guest conversion"""
    success: bool
    user_id: str
    email: str
    temporary_password: Optional[str] = None
    answers_transferred: int