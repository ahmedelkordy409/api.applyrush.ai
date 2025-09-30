"""
Company entity and related domain objects.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

from jobhire.shared.domain.entities import AggregateRoot
from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.events import DomainEvent


class CompanySize(Enum):
    """Company size enumeration."""
    STARTUP = "startup"  # 1-10
    SMALL = "small"      # 11-50
    MEDIUM = "medium"    # 51-200
    LARGE = "large"      # 201-1000
    ENTERPRISE = "enterprise"  # 1000+


class Industry(Enum):
    """Industry enumeration."""
    TECHNOLOGY = "technology"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    CONSULTING = "consulting"
    MEDIA = "media"
    NONPROFIT = "nonprofit"
    GOVERNMENT = "government"
    OTHER = "other"


@dataclass(frozen=True)
class CompanyLocation:
    """Company location value object."""
    address: str
    city: str
    state: Optional[str] = None
    country: str = "US"
    postal_code: Optional[str] = None
    is_headquarters: bool = False


@dataclass(frozen=True)
class CompanyBenefits:
    """Company benefits value object."""
    health_insurance: bool = False
    dental_insurance: bool = False
    vision_insurance: bool = False
    retirement_plan: bool = False
    paid_time_off: int = 0  # days per year
    remote_work: bool = False
    flexible_hours: bool = False
    professional_development: bool = False
    stock_options: bool = False
    gym_membership: bool = False
    free_meals: bool = False
    transportation: bool = False
    childcare: bool = False
    other_benefits: Optional[List[str]] = None


class CompanyCreatedEvent(DomainEvent):
    """Event raised when a company is created."""
    pass


class CompanyUpdatedEvent(DomainEvent):
    """Event raised when a company is updated."""
    pass


class Company(AggregateRoot[EntityId]):
    """Company aggregate root."""

    def __init__(
        self,
        company_id: EntityId,
        name: str,
        industry: Industry,
        size: CompanySize,
        description: Optional[str] = None,
        website: Optional[str] = None,
        logo_url: Optional[str] = None,
        founded_year: Optional[int] = None,
        headquarters: Optional[CompanyLocation] = None
    ):
        super().__init__(company_id)
        self.name = name
        self.industry = industry
        self.size = size
        self.description = description
        self.website = website
        self.logo_url = logo_url
        self.founded_year = founded_year
        self.headquarters = headquarters
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.is_verified = False
        self.locations: List[CompanyLocation] = []
        self.benefits: Optional[CompanyBenefits] = None
        self.job_count = 0
        self.employee_count: Optional[int] = None

        # Raise domain event
        self.add_domain_event(CompanyCreatedEvent({
            "company_id": str(company_id),
            "name": name,
            "industry": industry.value,
            "size": size.value
        }))

    def update_details(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        website: Optional[str] = None,
        logo_url: Optional[str] = None
    ) -> None:
        """Update company details."""
        if name:
            self.name = name
        if description:
            self.description = description
        if website:
            self.website = website
        if logo_url:
            self.logo_url = logo_url

        self.updated_at = datetime.utcnow()
        self.increment_version()

        self.add_domain_event(CompanyUpdatedEvent({
            "company_id": str(self.id),
            "updated_fields": {
                "name": bool(name),
                "description": bool(description),
                "website": bool(website),
                "logo_url": bool(logo_url)
            }
        }))

    def add_location(self, location: CompanyLocation) -> None:
        """Add a company location."""
        self.locations.append(location)
        self.updated_at = datetime.utcnow()
        self.increment_version()

    def set_benefits(self, benefits: CompanyBenefits) -> None:
        """Set company benefits."""
        self.benefits = benefits
        self.updated_at = datetime.utcnow()
        self.increment_version()

    def verify(self) -> None:
        """Mark company as verified."""
        self.is_verified = True
        self.updated_at = datetime.utcnow()
        self.increment_version()

    def increment_job_count(self) -> None:
        """Increment the job count."""
        self.job_count += 1
        self.updated_at = datetime.utcnow()

    def decrement_job_count(self) -> None:
        """Decrement the job count."""
        if self.job_count > 0:
            self.job_count -= 1
        self.updated_at = datetime.utcnow()

    def set_employee_count(self, count: int) -> None:
        """Set the employee count."""
        if count < 0:
            raise ValueError("Employee count cannot be negative")

        self.employee_count = count
        self.updated_at = datetime.utcnow()

    def get_size_description(self) -> str:
        """Get human-readable size description."""
        size_map = {
            CompanySize.STARTUP: "1-10 employees",
            CompanySize.SMALL: "11-50 employees",
            CompanySize.MEDIUM: "51-200 employees",
            CompanySize.LARGE: "201-1000 employees",
            CompanySize.ENTERPRISE: "1000+ employees"
        }
        return size_map.get(self.size, "Unknown size")

    def to_dict(self) -> Dict[str, Any]:
        """Convert company to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "industry": self.industry.value,
            "size": self.size.value,
            "size_description": self.get_size_description(),
            "description": self.description,
            "website": self.website,
            "logo_url": self.logo_url,
            "founded_year": self.founded_year,
            "is_verified": self.is_verified,
            "job_count": self.job_count,
            "employee_count": self.employee_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "headquarters": {
                "address": self.headquarters.address,
                "city": self.headquarters.city,
                "state": self.headquarters.state,
                "country": self.headquarters.country,
                "postal_code": self.headquarters.postal_code,
                "is_headquarters": self.headquarters.is_headquarters
            } if self.headquarters else None,
            "locations": [
                {
                    "address": loc.address,
                    "city": loc.city,
                    "state": loc.state,
                    "country": loc.country,
                    "postal_code": loc.postal_code,
                    "is_headquarters": loc.is_headquarters
                } for loc in self.locations
            ],
            "benefits": {
                "health_insurance": self.benefits.health_insurance,
                "dental_insurance": self.benefits.dental_insurance,
                "vision_insurance": self.benefits.vision_insurance,
                "retirement_plan": self.benefits.retirement_plan,
                "paid_time_off": self.benefits.paid_time_off,
                "remote_work": self.benefits.remote_work,
                "flexible_hours": self.benefits.flexible_hours,
                "professional_development": self.benefits.professional_development,
                "stock_options": self.benefits.stock_options,
                "gym_membership": self.benefits.gym_membership,
                "free_meals": self.benefits.free_meals,
                "transportation": self.benefits.transportation,
                "childcare": self.benefits.childcare,
                "other_benefits": self.benefits.other_benefits
            } if self.benefits else None
        }