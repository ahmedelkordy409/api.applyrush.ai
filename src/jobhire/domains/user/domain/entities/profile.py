"""
User profile entity and related domain objects.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

from jobhire.shared.domain.entities import AggregateRoot
from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.events import DomainEvent
from jobhire.domains.user.domain.value_objects.skills import SkillSet


class ProfileCompleteness(Enum):
    """Profile completeness levels."""
    MINIMAL = "minimal"      # Basic info only
    BASIC = "basic"          # Basic + some work experience
    COMPLETE = "complete"    # Most sections filled
    COMPREHENSIVE = "comprehensive"  # All sections filled


class ProfileVisibility(Enum):
    """Profile visibility settings."""
    PRIVATE = "private"
    RECRUITER_ONLY = "recruiter_only"
    PUBLIC = "public"


@dataclass(frozen=True)
class WorkExperience:
    """Work experience value object."""
    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None  # None for current position
    description: Optional[str] = None
    is_current: bool = False

    def __post_init__(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("Start date cannot be after end date")

        if self.is_current and self.end_date:
            raise ValueError("Current position cannot have end date")


@dataclass(frozen=True)
class Education:
    """Education value object."""
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    gpa: Optional[float] = None
    description: Optional[str] = None

    def __post_init__(self):
        if self.gpa is not None:
            if not (0.0 <= self.gpa <= 4.0):
                raise ValueError("GPA must be between 0.0 and 4.0")

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("Start date cannot be after end date")


@dataclass(frozen=True)
class ContactInfo:
    """Contact information value object."""
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    website_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class ProfileUpdatedEvent(DomainEvent):
    """Event raised when profile is updated."""
    pass


class ProfileCompletenessChangedEvent(DomainEvent):
    """Event raised when profile completeness changes."""
    pass


class UserProfile(AggregateRoot[EntityId]):
    """User profile aggregate root."""

    def __init__(
        self,
        profile_id: EntityId,
        user_id: EntityId,
        first_name: str,
        last_name: str
    ):
        super().__init__(profile_id)
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.bio: Optional[str] = None
        self.location: Optional[str] = None
        self.title: Optional[str] = None  # Current job title
        self.summary: Optional[str] = None
        self.skills: SkillSet = SkillSet(set())
        self.work_experiences: List[WorkExperience] = []
        self.education: List[Education] = []
        self.contact_info: Optional[ContactInfo] = None
        self.resume_url: Optional[str] = None
        self.profile_picture_url: Optional[str] = None
        self.visibility = ProfileVisibility.PRIVATE
        self.completeness = ProfileCompleteness.MINIMAL
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.is_verified = False
        self.is_job_seeking = False
        self.available_date: Optional[date] = None

    def update_basic_info(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        location: Optional[str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None
    ) -> None:
        """Update basic profile information."""
        if first_name:
            self.first_name = first_name
        if last_name:
            self.last_name = last_name
        if bio is not None:
            self.bio = bio
        if location is not None:
            self.location = location
        if title is not None:
            self.title = title
        if summary is not None:
            self.summary = summary

        self._update_metadata()
        self._recalculate_completeness()

        self.add_domain_event(ProfileUpdatedEvent({
            "profile_id": str(self.id),
            "user_id": str(self.user_id),
            "updated_fields": ["basic_info"]
        }))

    def update_skills(self, skills: SkillSet) -> None:
        """Update skills."""
        self.skills = skills
        self._update_metadata()
        self._recalculate_completeness()

        self.add_domain_event(ProfileUpdatedEvent({
            "profile_id": str(self.id),
            "user_id": str(self.user_id),
            "updated_fields": ["skills"]
        }))

    def add_work_experience(self, experience: WorkExperience) -> None:
        """Add work experience."""
        self.work_experiences.append(experience)
        self._update_metadata()
        self._recalculate_completeness()

        self.add_domain_event(ProfileUpdatedEvent({
            "profile_id": str(self.id),
            "user_id": str(self.user_id),
            "updated_fields": ["work_experience"]
        }))

    def remove_work_experience(self, index: int) -> None:
        """Remove work experience by index."""
        if 0 <= index < len(self.work_experiences):
            self.work_experiences.pop(index)
            self._update_metadata()
            self._recalculate_completeness()

    def add_education(self, education: Education) -> None:
        """Add education."""
        self.education.append(education)
        self._update_metadata()
        self._recalculate_completeness()

        self.add_domain_event(ProfileUpdatedEvent({
            "profile_id": str(self.id),
            "user_id": str(self.user_id),
            "updated_fields": ["education"]
        }))

    def remove_education(self, index: int) -> None:
        """Remove education by index."""
        if 0 <= index < len(self.education):
            self.education.pop(index)
            self._update_metadata()
            self._recalculate_completeness()

    def update_contact_info(self, contact_info: ContactInfo) -> None:
        """Update contact information."""
        self.contact_info = contact_info
        self._update_metadata()

        self.add_domain_event(ProfileUpdatedEvent({
            "profile_id": str(self.id),
            "user_id": str(self.user_id),
            "updated_fields": ["contact_info"]
        }))

    def set_visibility(self, visibility: ProfileVisibility) -> None:
        """Set profile visibility."""
        self.visibility = visibility
        self._update_metadata()

    def set_job_seeking_status(self, is_seeking: bool, available_date: Optional[date] = None) -> None:
        """Set job seeking status."""
        self.is_job_seeking = is_seeking
        self.available_date = available_date
        self._update_metadata()

    def verify_profile(self) -> None:
        """Mark profile as verified."""
        self.is_verified = True
        self._update_metadata()

    def update_resume_url(self, resume_url: str) -> None:
        """Update resume URL."""
        self.resume_url = resume_url
        self._update_metadata()
        self._recalculate_completeness()

    def update_profile_picture(self, picture_url: str) -> None:
        """Update profile picture URL."""
        self.profile_picture_url = picture_url
        self._update_metadata()

    def get_full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    def get_years_of_experience(self) -> int:
        """Calculate total years of experience."""
        total_months = 0
        today = date.today()

        for exp in self.work_experiences:
            if exp.start_date:
                end_date = exp.end_date or today
                months = (end_date.year - exp.start_date.year) * 12 + \
                        (end_date.month - exp.start_date.month)
                total_months += max(0, months)

        return total_months // 12

    def _update_metadata(self) -> None:
        """Update metadata."""
        self.updated_at = datetime.utcnow()
        self.increment_version()

    def _recalculate_completeness(self) -> None:
        """Recalculate profile completeness."""
        old_completeness = self.completeness
        score = 0

        # Basic info (30 points)
        if self.first_name and self.last_name:
            score += 10
        if self.bio:
            score += 10
        if self.location:
            score += 5
        if self.title:
            score += 5

        # Skills (20 points)
        if self.skills.skill_count() > 0:
            score += 10
        if self.skills.skill_count() >= 5:
            score += 10

        # Experience (25 points)
        if self.work_experiences:
            score += 15
        if len(self.work_experiences) >= 2:
            score += 10

        # Education (15 points)
        if self.education:
            score += 15

        # Additional (10 points)
        if self.resume_url:
            score += 5
        if self.contact_info:
            score += 5

        # Determine completeness level
        if score >= 85:
            self.completeness = ProfileCompleteness.COMPREHENSIVE
        elif score >= 70:
            self.completeness = ProfileCompleteness.COMPLETE
        elif score >= 40:
            self.completeness = ProfileCompleteness.BASIC
        else:
            self.completeness = ProfileCompleteness.MINIMAL

        if old_completeness != self.completeness:
            self.add_domain_event(ProfileCompletenessChangedEvent({
                "profile_id": str(self.id),
                "user_id": str(self.user_id),
                "old_completeness": old_completeness.value,
                "new_completeness": self.completeness.value,
                "score": score
            }))

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.get_full_name(),
            "bio": self.bio,
            "location": self.location,
            "title": self.title,
            "summary": self.summary,
            "visibility": self.visibility.value,
            "completeness": self.completeness.value,
            "is_verified": self.is_verified,
            "is_job_seeking": self.is_job_seeking,
            "available_date": self.available_date.isoformat() if self.available_date else None,
            "years_of_experience": self.get_years_of_experience(),
            "resume_url": self.resume_url,
            "profile_picture_url": self.profile_picture_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "skills": [skill.to_dict() for skill in self.skills.to_list()] if hasattr(self.skills, 'to_list') else [],
            "work_experiences": [
                {
                    "title": exp.title,
                    "company": exp.company,
                    "location": exp.location,
                    "start_date": exp.start_date.isoformat() if exp.start_date else None,
                    "end_date": exp.end_date.isoformat() if exp.end_date else None,
                    "description": exp.description,
                    "is_current": exp.is_current
                } for exp in self.work_experiences
            ],
            "education": [
                {
                    "institution": edu.institution,
                    "degree": edu.degree,
                    "field_of_study": edu.field_of_study,
                    "start_date": edu.start_date.isoformat() if edu.start_date else None,
                    "end_date": edu.end_date.isoformat() if edu.end_date else None,
                    "gpa": edu.gpa,
                    "description": edu.description
                } for edu in self.education
            ],
            "contact_info": {
                "phone": self.contact_info.phone,
                "linkedin_url": self.contact_info.linkedin_url,
                "github_url": self.contact_info.github_url,
                "website_url": self.contact_info.website_url,
                "portfolio_url": self.contact_info.portfolio_url
            } if self.contact_info else None
        }