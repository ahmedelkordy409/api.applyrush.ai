"""
Job and application related database models
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from enum import Enum

Base = declarative_base()


class JobType(str, Enum):
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"


class JobSource(str, Enum):
    MANUAL = "manual"
    JSEARCH = "jsearch"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    SCRAPER = "scraper"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    VIEWED = "viewed"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Job(Base):
    """Job postings model"""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic job information
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    requirements = Column(JSON, nullable=True)  # List of requirements
    benefits = Column(JSON, nullable=True)  # List of benefits

    # Salary information
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(3), default="USD", nullable=False)

    # Job details
    job_type = Column(String(20), default=JobType.FULL_TIME, nullable=False)
    remote = Column(Boolean, default=False, nullable=False)

    # Application information
    apply_url = Column(String(500), nullable=False)
    company_logo_url = Column(String(500), nullable=True)

    # Source tracking
    source = Column(String(50), default=JobSource.MANUAL, nullable=False)
    source_job_id = Column(String(255), nullable=True)  # External job ID from source

    # SEO and categorization
    keywords = Column(JSON, nullable=True)  # Extracted keywords
    skills_required = Column(JSON, nullable=True)  # Required skills
    experience_level = Column(String(50), nullable=True)  # entry, mid, senior
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)

    # Status and moderation
    active = Column(Boolean, default=True, nullable=False)
    featured = Column(Boolean, default=False, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)

    # Analytics
    view_count = Column(Integer, default=0, nullable=False)
    application_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    date_posted = Column(DateTime, nullable=False)
    date_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")


class Application(Base):
    """User job applications model"""
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    # Application details
    status = Column(String(20), default=ApplicationStatus.PENDING, nullable=False, index=True)
    cover_letter = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Application tracking
    applied_at = Column(DateTime, nullable=True)
    viewed_at = Column(DateTime, nullable=True)
    response_received_at = Column(DateTime, nullable=True)

    # AI-generated content tracking
    ai_generated_cover_letter = Column(Boolean, default=False, nullable=False)
    ai_auto_applied = Column(Boolean, default=False, nullable=False)

    # External tracking
    external_application_id = Column(String(255), nullable=True)
    application_method = Column(String(50), default="manual", nullable=False)  # manual, auto, bulk

    # Analytics
    resume_version_used = Column(String(100), nullable=True)
    time_to_apply_minutes = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    interview = relationship("Interview", back_populates="application", uselist=False)


class Interview(Base):
    """Interview scheduling and tracking model"""
    __tablename__ = "interviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Interview details
    interview_type = Column(String(50), nullable=False)  # phone, video, in-person, technical
    scheduled_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)  # Address or video link

    # Interviewer information
    interviewer_name = Column(String(255), nullable=True)
    interviewer_email = Column(String(255), nullable=True)
    interviewer_title = Column(String(255), nullable=True)

    # Interview preparation
    preparation_notes = Column(Text, nullable=True)
    questions_prepared = Column(JSON, nullable=True)  # List of prepared questions
    research_notes = Column(Text, nullable=True)

    # Interview outcome
    status = Column(String(50), default="scheduled", nullable=False)  # scheduled, completed, cancelled, rescheduled
    feedback = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # 1-5 rating
    next_steps = Column(Text, nullable=True)

    # AI assistance
    ai_prep_generated = Column(Boolean, default=False, nullable=False)
    ai_questions_suggested = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="interview")
    user = relationship("User", back_populates="interviews")


class Resume(Base):
    """User resumes model"""
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Resume details
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    content_type = Column(String(100), nullable=False)

    # Resume metadata
    version = Column(String(50), default="1.0", nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    extracted_text = Column(Text, nullable=True)

    # AI analysis
    ai_analyzed = Column(Boolean, default=False, nullable=False)
    skills_extracted = Column(JSON, nullable=True)
    experience_summary = Column(Text, nullable=True)
    improvements_suggested = Column(JSON, nullable=True)
    ats_score = Column(Integer, nullable=True)  # ATS compatibility score 0-100

    # Usage tracking
    application_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="resumes")


# Pydantic models for API serialization
class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: str
    requirements: Optional[List[str]] = None
    benefits: Optional[List[str]] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    job_type: JobType = JobType.FULL_TIME
    remote: bool = False
    apply_url: str

    class Config:
        from_attributes = True


class JobCreate(JobBase):
    source: JobSource = JobSource.MANUAL
    source_job_id: Optional[str] = None
    date_posted: datetime


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[List[str]] = None
    benefits: Optional[List[str]] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    active: Optional[bool] = None

    class Config:
        from_attributes = True


class JobResponse(JobBase):
    id: str
    source: str
    active: bool
    view_count: int
    application_count: int
    date_posted: datetime
    created_at: datetime

    # Optional fields for detailed view
    applications: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class ApplicationBase(BaseModel):
    job_id: str
    cover_letter: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    cover_letter: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ApplicationResponse(ApplicationBase):
    id: str
    user_id: str
    status: str
    applied_at: Optional[datetime] = None
    ai_generated_cover_letter: bool
    ai_auto_applied: bool
    created_at: datetime
    updated_at: datetime

    # Nested job information
    job: Optional[JobResponse] = None

    class Config:
        from_attributes = True


class InterviewBase(BaseModel):
    interview_type: str
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None

    class Config:
        from_attributes = True


class InterviewCreate(InterviewBase):
    application_id: str


class InterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    preparation_notes: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None

    class Config:
        from_attributes = True


class InterviewResponse(InterviewBase):
    id: str
    application_id: str
    user_id: str
    status: str
    preparation_notes: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    original_filename: str
    file_url: str
    version: str
    is_default: bool
    ai_analyzed: bool
    ats_score: Optional[int] = None
    application_count: int
    created_at: datetime

    class Config:
        from_attributes = True