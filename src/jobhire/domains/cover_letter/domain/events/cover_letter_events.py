"""
Domain events for cover letter operations.
"""

from datetime import datetime
from dataclasses import dataclass
from jobhire.shared.domain.events import DomainEvent


@dataclass
class CoverLetterGenerated(DomainEvent):
    """Event fired when a cover letter is generated."""
    cover_letter_id: str
    user_id: str
    generation_id: str
    position: str
    company: str
    writing_style: str
    word_count: int
    generated_at: datetime

    @property
    def event_type(self) -> str:
        return "cover_letter.generated"


@dataclass
class CoverLetterSaved(DomainEvent):
    """Event fired when a cover letter is saved to history."""
    cover_letter_id: str
    user_id: str
    position: str
    company: str
    saved_at: datetime

    @property
    def event_type(self) -> str:
        return "cover_letter.saved"


@dataclass
class CoverLetterExported(DomainEvent):
    """Event fired when a cover letter is exported."""
    cover_letter_id: str
    user_id: str
    export_id: str
    export_format: str
    file_path: str
    exported_at: datetime

    @property
    def event_type(self) -> str:
        return "cover_letter.exported"


@dataclass
class CoverLetterFeedbackReceived(DomainEvent):
    """Event fired when user provides feedback on a cover letter."""
    cover_letter_id: str
    user_id: str
    feedback: str
    quality_score: float
    feedback_at: datetime

    @property
    def event_type(self) -> str:
        return "cover_letter.feedback_received"


@dataclass
class CoverLetterShared(DomainEvent):
    """Event fired when a cover letter is shared."""
    cover_letter_id: str
    user_id: str
    share_method: str  # email, link, social
    shared_at: datetime

    @property
    def event_type(self) -> str:
        return "cover_letter.shared"