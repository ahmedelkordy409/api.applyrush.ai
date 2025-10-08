"""
User document management models
Handles CV/resumes, cover letters, and document templates
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Integer, Float, Text, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
import uuid

try:
    from ..core.database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class DocumentType(str, Enum):
    """Document type enumeration"""
    RESUME = "resume"
    CV = "cv"
    COVER_LETTER = "cover_letter"
    PORTFOLIO = "portfolio"
    TRANSCRIPT = "transcript"
    CERTIFICATE = "certificate"
    REFERENCE = "reference"


class DocumentStatus(str, Enum):
    """Document status enumeration"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class FileFormat(str, Enum):
    """Supported file formats"""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    HTML = "html"


# Database Models
class UserDocument(Base):
    """User document storage and management"""
    __tablename__ = "user_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    
    # Document metadata
    document_type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default=DocumentStatus.ACTIVE.value)
    
    # File information
    file_format = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)  # In bytes
    file_url = Column(String, nullable=True)  # S3/storage URL
    file_content = Column(LargeBinary, nullable=True)  # For small files
    
    # Document content
    extracted_text = Column(Text, nullable=True)  # Extracted text content
    structured_data = Column(JSON, nullable=True)  # Parsed resume/CV data
    
    # Versioning
    version = Column(Integer, default=1)
    parent_document_id = Column(UUID(as_uuid=True), nullable=True)  # For versions
    is_latest_version = Column(Boolean, default=True)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)  # How many times used
    last_used_at = Column(DateTime, nullable=True)
    
    # AI optimization data
    ai_optimized = Column(Boolean, default=False)
    optimization_data = Column(JSON, nullable=True)  # AI suggestions/improvements
    keywords = Column(JSON, nullable=True)  # Extracted keywords
    skills_identified = Column(JSON, nullable=True)  # AI-identified skills
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CoverLetterTemplate(Base):
    """Cover letter templates and variations"""
    __tablename__ = "cover_letter_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    
    # Template metadata
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template_type = Column(String, default="general")  # general, industry-specific, company-specific
    
    # Template content
    content = Column(Text, nullable=False)  # Template with placeholders
    variables = Column(JSON, nullable=True)  # Available variables/placeholders
    
    # Usage and performance
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, nullable=True)  # Response rate when used
    
    # Targeting
    industries = Column(JSON, nullable=True)  # Which industries this works for
    job_types = Column(JSON, nullable=True)  # Which job types
    company_sizes = Column(JSON, nullable=True)  # startup, enterprise, etc.
    
    # AI enhancement
    ai_generated = Column(Boolean, default=False)
    ai_optimization_score = Column(Float, nullable=True)
    
    is_default = Column(Boolean, default=False)
    status = Column(String, default=DocumentStatus.ACTIVE.value)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GeneratedDocument(Base):
    """AI-generated documents for specific applications"""
    __tablename__ = "generated_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=False, index=True)
    
    # Source information
    template_id = Column(UUID(as_uuid=True), nullable=True)  # Source template if used
    base_document_id = Column(UUID(as_uuid=True), nullable=True)  # Source resume/CV
    
    # Document details
    document_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    file_format = Column(String, default=FileFormat.PDF.value)
    file_url = Column(String, nullable=True)
    
    # Generation metadata
    ai_model_used = Column(String, nullable=True)
    generation_prompt = Column(Text, nullable=True)
    generation_cost = Column(Float, nullable=True)
    generation_time = Column(Float, nullable=True)  # Seconds
    
    # Customization data
    job_data = Column(JSON, nullable=True)  # Job posting data used
    company_research = Column(JSON, nullable=True)  # Company info used
    customizations = Column(JSON, nullable=True)  # Specific customizations made
    
    # Quality metrics
    quality_score = Column(Float, nullable=True)  # AI quality assessment
    keyword_match_score = Column(Float, nullable=True)
    readability_score = Column(Float, nullable=True)
    
    # Usage tracking
    submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    application_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Performance tracking
    employer_opened = Column(Boolean, nullable=True)
    employer_downloaded = Column(Boolean, nullable=True)
    led_to_interview = Column(Boolean, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentAnalysis(Base):
    """AI analysis results for documents"""
    __tablename__ = "document_analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Analysis results
    analysis_type = Column(String, nullable=False)  # skills, keywords, format, etc.
    results = Column(JSON, nullable=False)  # Analysis results
    confidence_score = Column(Float, nullable=True)
    
    # Improvement suggestions
    suggestions = Column(JSON, nullable=True)  # AI improvement suggestions
    missing_elements = Column(JSON, nullable=True)  # What's missing
    strengths = Column(JSON, nullable=True)  # Document strengths
    weaknesses = Column(JSON, nullable=True)  # Areas for improvement
    
    # Benchmarking
    industry_benchmark_score = Column(Float, nullable=True)
    role_relevance_score = Column(Float, nullable=True)
    ats_compatibility_score = Column(Float, nullable=True)  # ATS system compatibility
    
    # Analysis metadata
    ai_model_used = Column(String, nullable=True)
    analysis_cost = Column(Float, nullable=True)
    processing_time = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic Models for API
class DocumentUpload(BaseModel):
    """Model for document upload"""
    name: str = Field(..., min_length=1, max_length=255)
    document_type: DocumentType
    description: Optional[str] = None
    file_format: FileFormat
    content: Optional[str] = None  # For text content
    file_data: Optional[bytes] = None  # For binary files


class DocumentUpdate(BaseModel):
    """Model for updating document metadata"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[DocumentStatus] = None


class CoverLetterTemplateCreate(BaseModel):
    """Model for creating cover letter templates"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    content: str = Field(..., min_length=10)
    template_type: str = Field(default="general")
    industries: Optional[List[str]] = None
    job_types: Optional[List[str]] = None
    company_sizes: Optional[List[str]] = None
    is_default: bool = Field(default=False)


class DocumentGenerationRequest(BaseModel):
    """Model for requesting document generation"""
    document_type: DocumentType
    job_id: str
    template_id: Optional[str] = None
    base_document_id: Optional[str] = None
    customizations: Optional[Dict[str, Any]] = None
    ai_model_preference: Optional[str] = "balanced"


class DocumentAnalysisRequest(BaseModel):
    """Model for requesting document analysis"""
    document_id: str
    analysis_types: List[str] = Field(default=["skills", "keywords", "format", "ats"])
    target_role: Optional[str] = None
    target_industry: Optional[str] = None


class ResumeData(BaseModel):
    """Structured resume data model"""
    personal_info: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    languages: List[Dict[str, Any]] = Field(default_factory=list)
    references: List[Dict[str, Any]] = Field(default_factory=list)


class CoverLetterData(BaseModel):
    """Structured cover letter data"""
    header: Dict[str, Any] = Field(default_factory=dict)
    salutation: str = "Dear Hiring Manager"
    opening_paragraph: str = ""
    body_paragraphs: List[str] = Field(default_factory=list)
    closing_paragraph: str = ""
    signature: str = "Sincerely"
    customizations: Dict[str, Any] = Field(default_factory=dict)


class DocumentOptimizationSuggestion(BaseModel):
    """Document optimization suggestion"""
    type: str  # keyword, format, content, structure
    priority: str  # high, medium, low
    suggestion: str
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None
    impact_score: Optional[float] = None


class DocumentPerformanceMetrics(BaseModel):
    """Document performance metrics"""
    usage_count: int = 0
    success_rate: Optional[float] = None
    average_match_score: Optional[float] = None
    interview_rate: Optional[float] = None
    response_rate: Optional[float] = None
    last_updated: datetime


# Export all models
__all__ = [
    "UserDocument",
    "CoverLetterTemplate",
    "GeneratedDocument", 
    "DocumentAnalysis",
    "DocumentUpload",
    "DocumentUpdate",
    "CoverLetterTemplateCreate",
    "DocumentGenerationRequest",
    "DocumentAnalysisRequest",
    "ResumeData",
    "CoverLetterData",
    "DocumentOptimizationSuggestion",
    "DocumentPerformanceMetrics",
    "DocumentType",
    "DocumentStatus",
    "FileFormat"
]