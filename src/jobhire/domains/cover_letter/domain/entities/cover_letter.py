"""
Cover Letter domain entity - represents the main aggregate root.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import uuid

from jobhire.shared.domain.base import AggregateRoot, EntityId
from jobhire.shared.domain.events import DomainEvent
from ..value_objects.cover_letter_config import WritingStyle, CoverLetterMetadata
from ..events.cover_letter_events import (
    CoverLetterGenerated, CoverLetterSaved, CoverLetterExported
)


@dataclass
class PersonalInfo:
    """Personal information for cover letter generation."""
    full_name: str
    email_address: str
    phone_number: str
    city: str
    linkedin_profile: Optional[str] = None
    website: Optional[str] = None

    def __post_init__(self):
        if not self.full_name or not self.full_name.strip():
            raise ValueError("Full name is required")
        if not self.email_address or "@" not in self.email_address:
            raise ValueError("Valid email address is required")


@dataclass
class JobContext:
    """Job and company context for cover letter generation."""
    desired_position: str
    company_name: str
    job_details: str
    hiring_manager_name: Optional[str] = None
    department: Optional[str] = None
    job_source: Optional[str] = None  # LinkedIn, company website, etc.

    def __post_init__(self):
        if not self.desired_position or not self.desired_position.strip():
            raise ValueError("Desired position is required")
        if not self.company_name or not self.company_name.strip():
            raise ValueError("Company name is required")
        if not self.job_details or len(self.job_details.strip()) < 50:
            raise ValueError("Job details must be at least 50 characters")


@dataclass
class GenerationSettings:
    """Settings for cover letter generation."""
    writing_style: WritingStyle
    tone: str = "professional"  # professional, enthusiastic, confident, etc.
    length: str = "medium"  # short, medium, long
    focus_areas: List[str] = field(default_factory=list)  # skills, experience, passion, etc.
    include_salary_expectations: bool = False
    custom_instructions: Optional[str] = None


@dataclass
class CoverLetterContent:
    """Generated cover letter content."""
    content: str
    word_count: int
    paragraph_count: int
    key_highlights: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.content or len(self.content.strip()) < 100:
            raise ValueError("Cover letter content must be at least 100 characters")

        # Auto-calculate metrics if not provided
        if self.word_count == 0:
            self.word_count = len(self.content.split())
        if self.paragraph_count == 0:
            self.paragraph_count = len([p for p in self.content.split('\n\n') if p.strip()])


class CoverLetter(AggregateRoot[EntityId]):
    """Cover Letter aggregate root."""

    def __init__(
        self,
        cover_letter_id: EntityId,
        user_id: str,
        personal_info: PersonalInfo,
        job_context: JobContext,
        generation_settings: GenerationSettings
    ):
        super().__init__(cover_letter_id)
        self.user_id = user_id
        self.personal_info = personal_info
        self.job_context = job_context
        self.generation_settings = generation_settings

        # State
        self.content: Optional[CoverLetterContent] = None
        self.status = "pending"  # pending, generated, saved, exported
        self.metadata = CoverLetterMetadata()

        # Timestamps
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.generated_at: Optional[datetime] = None

        # Generation details
        self.generation_id: Optional[str] = None
        self.ai_model_used: Optional[str] = None
        self.generation_time_ms: Optional[int] = None

        # Export tracking
        self.export_history: List[Dict[str, Any]] = []

        # Tags and categorization
        self.tags: List[str] = []
        self.industry_sector: Optional[str] = None

        # Quality metrics
        self.quality_score: Optional[float] = None
        self.feedback_received: Optional[str] = None

    def generate_content(
        self,
        content: str,
        ai_model: str,
        generation_time_ms: int,
        key_highlights: Optional[List[str]] = None
    ) -> None:
        """Generate cover letter content."""
        if self.status != "pending":
            raise ValueError(f"Cannot generate content for cover letter in {self.status} status")

        self.content = CoverLetterContent(
            content=content,
            word_count=len(content.split()),
            paragraph_count=len([p for p in content.split('\n\n') if p.strip()]),
            key_highlights=key_highlights or []
        )

        self.status = "generated"
        self.generated_at = datetime.now(timezone.utc)
        self.generation_id = str(uuid.uuid4())
        self.ai_model_used = ai_model
        self.generation_time_ms = generation_time_ms
        self.updated_at = self.generated_at

        # Determine industry sector from job details
        self._analyze_industry_sector()

        # Add generation event
        event = CoverLetterGenerated(
            cover_letter_id=str(self.id),
            user_id=self.user_id,
            generation_id=self.generation_id,
            position=self.job_context.desired_position,
            company=self.job_context.company_name,
            writing_style=self.generation_settings.writing_style.value,
            word_count=self.content.word_count,
            generated_at=self.generated_at
        )
        self.add_domain_event(event)

    def save_cover_letter(self, save_to_history: bool = True) -> None:
        """Save the cover letter to user's history."""
        if self.status != "generated":
            raise ValueError("Can only save generated cover letters")

        self.status = "saved"
        self.updated_at = datetime.now(timezone.utc)

        if save_to_history:
            # Add save event
            event = CoverLetterSaved(
                cover_letter_id=str(self.id),
                user_id=self.user_id,
                position=self.job_context.desired_position,
                company=self.job_context.company_name,
                saved_at=self.updated_at
            )
            self.add_domain_event(event)

    def export_cover_letter(self, export_format: str, file_path: str) -> str:
        """Export cover letter in specified format."""
        if not self.content:
            raise ValueError("Cannot export cover letter without content")

        export_id = str(uuid.uuid4())
        export_record = {
            "export_id": export_id,
            "format": export_format,
            "file_path": file_path,
            "exported_at": datetime.now(timezone.utc),
            "file_size_bytes": len(self.content.content.encode('utf-8'))
        }

        self.export_history.append(export_record)
        self.status = "exported"
        self.updated_at = export_record["exported_at"]

        # Add export event
        event = CoverLetterExported(
            cover_letter_id=str(self.id),
            user_id=self.user_id,
            export_id=export_id,
            export_format=export_format,
            file_path=file_path,
            exported_at=export_record["exported_at"]
        )
        self.add_domain_event(event)

        return export_id

    def add_feedback(self, feedback: str, quality_score: Optional[float] = None) -> None:
        """Add user feedback for the cover letter."""
        self.feedback_received = feedback
        if quality_score is not None:
            self.quality_score = max(0.0, min(10.0, quality_score))  # 0-10 scale
        self.updated_at = datetime.now(timezone.utc)

    def add_tags(self, tags: List[str]) -> None:
        """Add tags to categorize the cover letter."""
        self.tags.extend([tag.lower().strip() for tag in tags if tag.strip()])
        self.tags = list(set(self.tags))  # Remove duplicates
        self.updated_at = datetime.now(timezone.utc)

    def update_content(self, new_content: str) -> None:
        """Update cover letter content (for manual edits)."""
        if not self.content:
            raise ValueError("Cannot update content that doesn't exist")

        self.content.content = new_content
        self.content.word_count = len(new_content.split())
        self.content.paragraph_count = len([p for p in new_content.split('\n\n') if p.strip()])
        self.updated_at = datetime.now(timezone.utc)

    def get_generation_summary(self) -> Dict[str, Any]:
        """Get summary of generation details."""
        return {
            "generation_id": self.generation_id,
            "ai_model": self.ai_model_used,
            "generation_time_ms": self.generation_time_ms,
            "word_count": self.content.word_count if self.content else 0,
            "writing_style": self.generation_settings.writing_style.value,
            "generated_at": self.generated_at,
            "quality_score": self.quality_score
        }

    def _analyze_industry_sector(self) -> None:
        """Analyze and set industry sector based on job details."""
        job_text = f"{self.job_context.job_details} {self.job_context.desired_position}".lower()

        industry_keywords = {
            "technology": ["software", "tech", "engineer", "developer", "programming", "ai", "data"],
            "finance": ["finance", "banking", "investment", "financial", "accounting", "fintech"],
            "healthcare": ["healthcare", "medical", "hospital", "nurse", "doctor", "pharma"],
            "education": ["education", "teaching", "university", "school", "academic"],
            "marketing": ["marketing", "advertising", "social media", "brand", "digital marketing"],
            "sales": ["sales", "business development", "account manager", "revenue"],
            "consulting": ["consulting", "consultant", "advisory", "strategy"],
            "retail": ["retail", "customer service", "store", "merchandise"],
            "manufacturing": ["manufacturing", "production", "factory", "operations"],
            "nonprofit": ["nonprofit", "charity", "foundation", "social impact"]
        }

        for sector, keywords in industry_keywords.items():
            if any(keyword in job_text for keyword in keywords):
                self.industry_sector = sector
                break

        if not self.industry_sector:
            self.industry_sector = "general"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "personal_info": {
                "full_name": self.personal_info.full_name,
                "email_address": self.personal_info.email_address,
                "phone_number": self.personal_info.phone_number,
                "city": self.personal_info.city,
                "linkedin_profile": self.personal_info.linkedin_profile,
                "website": self.personal_info.website
            },
            "job_context": {
                "desired_position": self.job_context.desired_position,
                "company_name": self.job_context.company_name,
                "job_details": self.job_context.job_details,
                "hiring_manager_name": self.job_context.hiring_manager_name,
                "department": self.job_context.department,
                "job_source": self.job_context.job_source
            },
            "generation_settings": {
                "writing_style": self.generation_settings.writing_style.value,
                "tone": self.generation_settings.tone,
                "length": self.generation_settings.length,
                "focus_areas": self.generation_settings.focus_areas,
                "include_salary_expectations": self.generation_settings.include_salary_expectations,
                "custom_instructions": self.generation_settings.custom_instructions
            },
            "content": {
                "content": self.content.content if self.content else None,
                "word_count": self.content.word_count if self.content else 0,
                "paragraph_count": self.content.paragraph_count if self.content else 0,
                "key_highlights": self.content.key_highlights if self.content else [],
                "generated_at": self.content.generated_at.isoformat() if self.content else None
            } if self.content else None,
            "status": self.status,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "generation_id": self.generation_id,
            "ai_model_used": self.ai_model_used,
            "generation_time_ms": self.generation_time_ms,
            "export_history": self.export_history,
            "tags": self.tags,
            "industry_sector": self.industry_sector,
            "quality_score": self.quality_score,
            "feedback_received": self.feedback_received
        }