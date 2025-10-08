"""
Job entity and related domain objects.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

from jobhire.shared.domain.entities import AggregateRoot
from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.events import DomainEvent


class JobStatus(Enum):
    """Job posting status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    EXPIRED = "expired"


class EmploymentType(Enum):
    """Employment type enumeration."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class ExperienceLevel(Enum):
    """Experience level enumeration."""
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


@dataclass(frozen=True)
class JobRequirements:
    """Job requirements value object."""
    skills: List[str]
    experience_years: int
    education_level: Optional[str] = None
    certifications: Optional[List[str]] = None
    languages: Optional[List[str]] = None

    def __post_init__(self):
        if self.experience_years < 0:
            raise ValueError("Experience years cannot be negative")


@dataclass(frozen=True)
class JobCompensation:
    """Job compensation value object."""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: str = "USD"
    equity_min: Optional[float] = None
    equity_max: Optional[float] = None
    benefits: Optional[List[str]] = None

    def __post_init__(self):
        if self.salary_min and self.salary_max:
            if self.salary_min > self.salary_max:
                raise ValueError("Minimum salary cannot exceed maximum salary")

        if self.equity_min and self.equity_max:
            if self.equity_min > self.equity_max:
                raise ValueError("Minimum equity cannot exceed maximum equity")


class JobCreatedEvent(DomainEvent):
    """Event raised when a job is created."""
    pass


class JobUpdatedEvent(DomainEvent):
    """Event raised when a job is updated."""
    pass


class JobStatusChangedEvent(DomainEvent):
    """Event raised when job status changes."""
    pass


class Job(AggregateRoot[EntityId]):
    """Job aggregate root."""

    def __init__(
        self,
        job_id: EntityId,
        title: str,
        company: str,
        location: str,
        description: str,
        requirements: JobRequirements,
        employment_type: EmploymentType,
        experience_level: ExperienceLevel,
        compensation: Optional[JobCompensation] = None,
        remote_allowed: bool = False,
        posted_by: Optional[EntityId] = None
    ):
        super().__init__(job_id)
        self.title = title
        self.company = company
        self.location = location
        self.description = description
        self.requirements = requirements
        self.employment_type = employment_type
        self.experience_level = experience_level
        self.compensation = compensation
        self.remote_allowed = remote_allowed
        self.posted_by = posted_by
        self.status = JobStatus.DRAFT
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.expires_at: Optional[datetime] = None
        self.application_count = 0

        # Raise domain event
        self.add_domain_event(JobCreatedEvent({
            "job_id": str(job_id),
            "title": title,
            "company": company
        }))

    def update_details(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        compensation: Optional[JobCompensation] = None
    ) -> None:
        """Update job details."""
        if title:
            self.title = title
        if description:
            self.description = description
        if location:
            self.location = location
        if compensation:
            self.compensation = compensation

        self.updated_at = datetime.utcnow()
        self.increment_version()

        self.add_domain_event(JobUpdatedEvent({
            "job_id": str(self.id),
            "updated_fields": {
                "title": title,
                "description": bool(description),
                "location": location,
                "compensation": bool(compensation)
            }
        }))

    def activate(self, expires_in_days: int = 30) -> None:
        """Activate the job posting."""
        if self.status == JobStatus.DRAFT:
            self.status = JobStatus.ACTIVE
            self.expires_at = datetime.utcnow().replace(
                day=datetime.utcnow().day + expires_in_days
            )
            self.updated_at = datetime.utcnow()
            self.increment_version()

            self.add_domain_event(JobStatusChangedEvent({
                "job_id": str(self.id),
                "old_status": JobStatus.DRAFT.value,
                "new_status": JobStatus.ACTIVE.value
            }))

    def pause(self) -> None:
        """Pause the job posting."""
        if self.status == JobStatus.ACTIVE:
            self.status = JobStatus.PAUSED
            self.updated_at = datetime.utcnow()
            self.increment_version()

            self.add_domain_event(JobStatusChangedEvent({
                "job_id": str(self.id),
                "old_status": JobStatus.ACTIVE.value,
                "new_status": JobStatus.PAUSED.value
            }))

    def close(self) -> None:
        """Close the job posting."""
        old_status = self.status
        self.status = JobStatus.CLOSED
        self.updated_at = datetime.utcnow()
        self.increment_version()

        self.add_domain_event(JobStatusChangedEvent({
            "job_id": str(self.id),
            "old_status": old_status.value,
            "new_status": JobStatus.CLOSED.value
        }))

    def increment_application_count(self) -> None:
        """Increment the application count."""
        self.application_count += 1
        self.updated_at = datetime.utcnow()

    def is_active(self) -> bool:
        """Check if job is active."""
        return self.status == JobStatus.ACTIVE

    def is_expired(self) -> bool:
        """Check if job has expired."""
        return (
            self.expires_at is not None and
            datetime.utcnow() > self.expires_at
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            "id": str(self.id),
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "employment_type": self.employment_type.value,
            "experience_level": self.experience_level.value,
            "remote_allowed": self.remote_allowed,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "application_count": self.application_count,
            "requirements": {
                "skills": self.requirements.skills,
                "experience_years": self.requirements.experience_years,
                "education_level": self.requirements.education_level,
                "certifications": self.requirements.certifications,
                "languages": self.requirements.languages
            },
            "compensation": {
                "salary_min": self.compensation.salary_min,
                "salary_max": self.compensation.salary_max,
                "currency": self.compensation.currency,
                "equity_min": self.compensation.equity_min,
                "equity_max": self.compensation.equity_max,
                "benefits": self.compensation.benefits
            } if self.compensation else None
        }