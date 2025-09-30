"""
Cover Letter DTOs for API requests and responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class CreateCoverLetterDTO(BaseModel):
    """DTO for creating a new cover letter."""
    # Personal Information
    full_name: str = Field(..., min_length=2, max_length=100, description="Candidate's full name")
    email_address: EmailStr = Field(..., description="Candidate's email address")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Phone number")
    city: str = Field(..., min_length=2, max_length=100, description="City/location")
    linkedin_profile: Optional[str] = Field(None, description="LinkedIn profile URL")
    website: Optional[str] = Field(None, description="Personal website URL")

    # Job Context
    desired_position: str = Field(..., min_length=2, max_length=200, description="Target job position")
    company_name: str = Field(..., min_length=2, max_length=200, description="Company name")
    job_details: str = Field(..., min_length=50, description="Full job description")
    hiring_manager_name: Optional[str] = Field(None, description="Hiring manager name if known")
    department: Optional[str] = Field(None, description="Department or team")
    job_source: Optional[str] = Field(None, description="Where job was found")

    # Generation Settings
    writing_style: str = Field(default="professional", description="Writing style preference")
    tone: str = Field(default="professional", description="Tone preference")
    length: str = Field(default="medium", description="Desired length (short/medium/long)")
    focus_areas: List[str] = Field(default_factory=list, description="Areas to emphasize")
    include_salary_expectations: bool = Field(default=False, description="Include salary discussion")
    custom_instructions: Optional[str] = Field(None, description="Additional instructions")

    class Config:
        schema_extra = {
            "example": {
                "full_name": "John Smith",
                "email_address": "john.smith@email.com",
                "phone_number": "+1-555-123-4567",
                "city": "San Francisco, CA",
                "desired_position": "Senior Software Engineer",
                "company_name": "TechCorp",
                "job_details": "We are seeking a Senior Software Engineer with 5+ years of experience in Python and cloud technologies...",
                "writing_style": "professional",
                "tone": "confident",
                "length": "medium",
                "focus_areas": ["experience", "technical_skills", "leadership"]
            }
        }


class CoverLetterResponseDTO(BaseModel):
    """DTO for cover letter generation response."""
    cover_letter_id: str = Field(..., description="Unique cover letter ID")
    cover_letter: str = Field(..., description="Generated cover letter content")
    generation_id: str = Field(..., description="Generation session ID")
    word_count: int = Field(..., description="Number of words")
    paragraph_count: int = Field(..., description="Number of paragraphs")
    key_highlights: List[str] = Field(default_factory=list, description="Key points emphasized")
    confidence_score: float = Field(..., description="AI confidence score")
    generation_time_ms: int = Field(..., description="Generation time in milliseconds")
    timestamp: datetime = Field(..., description="Generation timestamp")

    class Config:
        schema_extra = {
            "example": {
                "cover_letter_id": "cl_abc123",
                "cover_letter": "Dear Hiring Manager,\n\nI am writing to express my strong interest...",
                "generation_id": "gen_xyz789",
                "word_count": 287,
                "paragraph_count": 4,
                "key_highlights": ["5+ years Python experience", "Cloud architecture expertise"],
                "confidence_score": 92.5,
                "generation_time_ms": 3450,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class SaveCoverLetterDTO(BaseModel):
    """DTO for saving cover letter to history."""
    cover_letter_id: str = Field(..., description="Cover letter ID to save")
    save_to_history: bool = Field(default=True, description="Add to user history")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    class Config:
        schema_extra = {
            "example": {
                "cover_letter_id": "cl_abc123",
                "save_to_history": True,
                "tags": ["software_engineer", "fintech", "senior_level"]
            }
        }


class ExportCoverLetterDTO(BaseModel):
    """DTO for exporting cover letter."""
    cover_letter_id: str = Field(..., description="Cover letter ID to export")
    format: str = Field(..., description="Export format (pdf/docx/txt/html)")
    include_contact_info: bool = Field(default=True, description="Include contact information")
    letterhead_style: Optional[str] = Field(None, description="Letterhead style preference")

    class Config:
        schema_extra = {
            "example": {
                "cover_letter_id": "cl_abc123",
                "format": "pdf",
                "include_contact_info": True,
                "letterhead_style": "modern"
            }
        }


class ExportResponseDTO(BaseModel):
    """DTO for export response."""
    export_id: str = Field(..., description="Export session ID")
    download_url: str = Field(..., description="Download URL")
    file_name: str = Field(..., description="Generated file name")
    file_size_bytes: int = Field(..., description="File size in bytes")
    format: str = Field(..., description="File format")
    expires_at: datetime = Field(..., description="URL expiration time")

    class Config:
        schema_extra = {
            "example": {
                "export_id": "exp_def456",
                "download_url": "https://api.applyrush.ai/exports/cl_abc123.pdf",
                "file_name": "John_Smith_Cover_Letter_TechCorp.pdf",
                "file_size_bytes": 45678,
                "format": "pdf",
                "expires_at": "2024-01-15T22:30:00Z"
            }
        }


class CoverLetterHistoryDTO(BaseModel):
    """DTO for cover letter history item."""
    cover_letter_id: str = Field(..., description="Cover letter ID")
    position: str = Field(..., description="Job position")
    company: str = Field(..., description="Company name")
    writing_style: str = Field(..., description="Writing style used")
    word_count: int = Field(..., description="Word count")
    quality_score: Optional[float] = Field(None, description="Quality score if assessed")
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    status: str = Field(..., description="Cover letter status")

    class Config:
        schema_extra = {
            "example": {
                "cover_letter_id": "cl_abc123",
                "position": "Senior Software Engineer",
                "company": "TechCorp",
                "writing_style": "professional",
                "word_count": 287,
                "quality_score": 92.5,
                "tags": ["software_engineer", "fintech"],
                "created_at": "2024-01-15T10:30:00Z",
                "status": "saved"
            }
        }


class CoverLetterHistoryResponseDTO(BaseModel):
    """DTO for cover letter history response."""
    cover_letters: List[CoverLetterHistoryDTO] = Field(..., description="List of cover letters")
    total_count: int = Field(..., description="Total number of cover letters")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")

    class Config:
        schema_extra = {
            "example": {
                "cover_letters": [
                    {
                        "cover_letter_id": "cl_abc123",
                        "position": "Senior Software Engineer",
                        "company": "TechCorp",
                        "writing_style": "professional",
                        "word_count": 287,
                        "quality_score": 92.5,
                        "tags": ["software_engineer"],
                        "created_at": "2024-01-15T10:30:00Z",
                        "status": "saved"
                    }
                ],
                "total_count": 15,
                "page": 1,
                "page_size": 10,
                "has_next": True
            }
        }


class WritingStyleOptionDTO(BaseModel):
    """DTO for writing style option."""
    id: str = Field(..., description="Style identifier")
    label: str = Field(..., description="Display name")
    description: str = Field(..., description="Style description")

    class Config:
        schema_extra = {
            "example": {
                "id": "professional",
                "label": "Professional",
                "description": "Traditional business writing with formal tone"
            }
        }


class CoverLetterFeedbackDTO(BaseModel):
    """DTO for submitting cover letter feedback."""
    cover_letter_id: str = Field(..., description="Cover letter ID")
    quality_score: float = Field(..., ge=1, le=10, description="Quality rating (1-10)")
    feedback_text: Optional[str] = Field(None, description="Written feedback")
    helpful_features: List[str] = Field(default_factory=list, description="Most helpful features")
    improvement_suggestions: List[str] = Field(default_factory=list, description="Suggestions for improvement")

    class Config:
        schema_extra = {
            "example": {
                "cover_letter_id": "cl_abc123",
                "quality_score": 8.5,
                "feedback_text": "Great cover letter, very professional and targeted",
                "helpful_features": ["keyword_optimization", "company_research"],
                "improvement_suggestions": ["more_specific_examples"]
            }
        }


class CoverLetterAnalyticsDTO(BaseModel):
    """DTO for cover letter analytics."""
    total_generated: int = Field(..., description="Total cover letters generated")
    this_month: int = Field(..., description="Generated this month")
    average_quality_score: float = Field(..., description="Average quality score")
    most_used_style: str = Field(..., description="Most frequently used writing style")
    top_industries: List[Dict[str, Any]] = Field(..., description="Top industries applied to")
    success_metrics: Dict[str, Any] = Field(..., description="Success tracking metrics")

    class Config:
        schema_extra = {
            "example": {
                "total_generated": 45,
                "this_month": 12,
                "average_quality_score": 87.3,
                "most_used_style": "professional",
                "top_industries": [
                    {"industry": "technology", "count": 18},
                    {"industry": "finance", "count": 12}
                ],
                "success_metrics": {
                    "response_rate": 23.5,
                    "interview_rate": 8.2
                }
            }
        }


class CustomizeCoverLetterDTO(BaseModel):
    """DTO for customizing existing cover letter for new role."""
    base_cover_letter_id: str = Field(..., description="ID of base cover letter to customize")
    new_position: str = Field(..., description="New target position")
    new_company: str = Field(..., description="New target company")
    new_job_details: str = Field(..., description="New job description")
    customization_focus: List[str] = Field(default_factory=list, description="Areas to focus customization")
    maintain_style: bool = Field(default=True, description="Keep original writing style")

    class Config:
        schema_extra = {
            "example": {
                "base_cover_letter_id": "cl_abc123",
                "new_position": "Lead Software Engineer",
                "new_company": "StartupTech",
                "new_job_details": "We need a Lead Software Engineer to build our platform...",
                "customization_focus": ["leadership", "startup_experience"],
                "maintain_style": True
            }
        }