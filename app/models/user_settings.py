"""
User settings and preferences models
Handles search settings, onboarding data, and queue configurations
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, time
from enum import Enum
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Integer, Float, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

try:
    from ..core.database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class SearchStatus(str, Enum):
    """Search status options"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class QueuePriority(str, Enum):
    """Queue priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class OnboardingStatus(str, Enum):
    """User onboarding status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


# Database Models
class UserProfile(Base):
    """Enhanced user profile with onboarding and preferences"""
    __tablename__ = "user_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, unique=True, nullable=False, index=True)
    
    # Basic info
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    # Onboarding status
    onboarding_status = Column(String, default=OnboardingStatus.NOT_STARTED.value)
    onboarding_completed_at = Column(DateTime, nullable=True)
    onboarding_data = Column(JSON, nullable=True)  # Stores onboarding responses
    
    # Profile data
    skills = Column(JSON, nullable=True)  # List of skills with proficiency levels
    experience_years = Column(Integer, nullable=True)
    education = Column(JSON, nullable=True)  # Education history
    certifications = Column(JSON, nullable=True)  # Professional certifications
    
    # Resume and documents
    resume_text = Column(Text, nullable=True)
    resume_file_url = Column(String, nullable=True)
    cover_letter_template = Column(Text, nullable=True)
    
    # Location and remote preferences
    location = Column(JSON, nullable=True)  # City, state, country, timezone
    remote_preference = Column(String, default="hybrid")  # remote, hybrid, onsite
    willing_to_relocate = Column(Boolean, default=False)
    
    # Career preferences
    target_roles = Column(JSON, nullable=True)  # List of desired job titles
    industries = Column(JSON, nullable=True)  # Preferred industries
    company_sizes = Column(JSON, nullable=True)  # startup, mid-size, enterprise
    
    # Salary expectations
    salary_minimum = Column(Float, nullable=True)
    salary_target = Column(Float, nullable=True)
    salary_currency = Column(String, default="USD")
    
    # Work preferences
    work_visa_required = Column(Boolean, default=False)
    security_clearance = Column(String, nullable=True)
    availability = Column(String, default="immediate")  # immediate, 2weeks, 1month, etc.
    
    # Culture preferences
    culture_preferences = Column(JSON, nullable=True)  # innovation, collaboration, etc.
    benefits_priorities = Column(JSON, nullable=True)  # health, 401k, pto, etc.
    
    # Account settings
    user_tier = Column(String, default="free")  # free, premium, enterprise
    ai_model_preference = Column(String, default="balanced")  # fast, balanced, premium
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSearchSettings(Base):
    """User-specific job search settings and preferences"""
    __tablename__ = "user_search_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    
    # Search status and control
    search_status = Column(String, default=SearchStatus.ACTIVE.value)
    search_paused_at = Column(DateTime, nullable=True)
    search_pause_reason = Column(String, nullable=True)
    auto_resume_at = Column(DateTime, nullable=True)
    
    # Search parameters
    keywords = Column(JSON, nullable=True)  # List of search keywords
    excluded_keywords = Column(JSON, nullable=True)  # Keywords to avoid
    job_titles = Column(JSON, nullable=True)  # Specific job titles to search
    excluded_titles = Column(JSON, nullable=True)  # Titles to avoid
    
    # Location filters
    locations = Column(JSON, nullable=True)  # Cities/regions to search
    remote_only = Column(Boolean, default=False)
    max_commute_distance = Column(Integer, nullable=True)  # In miles/km
    
    # Company filters
    target_companies = Column(JSON, nullable=True)  # Specific companies
    excluded_companies = Column(JSON, nullable=True)  # Companies to avoid
    company_size_filters = Column(JSON, nullable=True)  # Size preferences
    industry_filters = Column(JSON, nullable=True)  # Industry preferences
    
    # Job criteria
    experience_level = Column(JSON, nullable=True)  # entry, mid, senior, executive
    employment_type = Column(JSON, nullable=True)  # full-time, contract, etc.
    minimum_salary = Column(Float, nullable=True)
    maximum_salary = Column(Float, nullable=True)
    
    # Application filters
    minimum_match_score = Column(Float, default=70.0)  # Don't apply below this score
    auto_apply_threshold = Column(Float, default=85.0)  # Auto-apply above this score
    require_manual_review = Column(Boolean, default=True)  # Manual review required
    
    # Search frequency and limits
    max_applications_per_day = Column(Integer, default=10)
    max_applications_per_week = Column(Integer, default=50)
    search_frequency_hours = Column(Integer, default=4)  # How often to search
    
    # Time restrictions
    search_active_hours = Column(JSON, nullable=True)  # {"start": "09:00", "end": "17:00"}
    search_active_days = Column(JSON, nullable=True)  # ["monday", "tuesday", ...]
    timezone = Column(String, default="UTC")
    
    # Platform settings
    enabled_platforms = Column(JSON, nullable=True)  # linkedin, indeed, glassdoor, etc.
    platform_credentials = Column(JSON, nullable=True)  # Encrypted platform logins
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserQueue(Base):
    """User's job application queue with priority and scheduling"""
    __tablename__ = "user_queues"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=False, index=True)
    
    # Queue management
    priority = Column(String, default=QueuePriority.NORMAL.value)
    queued_at = Column(DateTime, default=datetime.utcnow)
    scheduled_for = Column(DateTime, nullable=True)  # When to process this job
    
    # Job data snapshot
    job_data = Column(JSON, nullable=False)  # Full job posting data
    match_score = Column(Float, nullable=True)
    
    # Queue status
    status = Column(String, default="queued")  # queued, processing, completed, failed, skipped
    processed_at = Column(DateTime, nullable=True)
    workflow_execution_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Processing results
    application_submitted = Column(Boolean, default=False)
    application_id = Column(UUID(as_uuid=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    
    # User actions
    user_flagged = Column(Boolean, default=False)  # User manually flagged for review
    user_notes = Column(Text, nullable=True)
    user_action = Column(String, nullable=True)  # apply, skip, save_for_later
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OnboardingStep(Base):
    """Tracks user onboarding progress"""
    __tablename__ = "onboarding_steps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    
    step_name = Column(String, nullable=False)  # profile, preferences, resume, etc.
    step_order = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending, completed, skipped
    
    # Step data
    step_data = Column(JSON, nullable=True)  # User responses for this step
    completion_percentage = Column(Float, default=0.0)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic Models for API
class SearchSettingsUpdate(BaseModel):
    """Model for updating search settings"""
    keywords: Optional[List[str]] = None
    excluded_keywords: Optional[List[str]] = None
    job_titles: Optional[List[str]] = None
    excluded_titles: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    remote_only: Optional[bool] = None
    target_companies: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None
    minimum_salary: Optional[float] = None
    maximum_salary: Optional[float] = None
    minimum_match_score: Optional[float] = Field(None, ge=0, le=100)
    auto_apply_threshold: Optional[float] = Field(None, ge=0, le=100)
    max_applications_per_day: Optional[int] = Field(None, ge=1, le=100)
    max_applications_per_week: Optional[int] = Field(None, ge=1, le=500)
    search_frequency_hours: Optional[int] = Field(None, ge=1, le=24)
    enabled_platforms: Optional[List[str]] = None


class SearchControlRequest(BaseModel):
    """Model for search control actions"""
    action: str = Field(..., pattern="^(pause|resume|stop|start)$")
    reason: Optional[str] = None
    auto_resume_at: Optional[datetime] = None


class QueueItemRequest(BaseModel):
    """Model for adding items to queue"""
    job_id: str
    job_data: Dict[str, Any]
    priority: QueuePriority = QueuePriority.NORMAL
    scheduled_for: Optional[datetime] = None
    user_notes: Optional[str] = None


class OnboardingStepData(BaseModel):
    """Model for onboarding step data"""
    step_name: str
    step_data: Dict[str, Any]
    completion_percentage: float = Field(default=0.0, ge=0, le=100)


class UserPreferencesUpdate(BaseModel):
    """Model for updating user preferences"""
    target_roles: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    company_sizes: Optional[List[str]] = None
    remote_preference: Optional[str] = None
    salary_minimum: Optional[float] = None
    salary_target: Optional[float] = None
    location: Optional[Dict[str, Any]] = None
    culture_preferences: Optional[Dict[str, Any]] = None
    benefits_priorities: Optional[List[str]] = None
    ai_model_preference: Optional[str] = None


class QueueFilters(BaseModel):
    """Model for filtering queue items"""
    status: Optional[str] = None
    priority: Optional[QueuePriority] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    flagged_only: Optional[bool] = None
    min_match_score: Optional[float] = None


# Export all models
__all__ = [
    "UserProfile",
    "UserSearchSettings", 
    "UserQueue",
    "OnboardingStep",
    "SearchSettingsUpdate",
    "SearchControlRequest",
    "QueueItemRequest",
    "OnboardingStepData",
    "UserPreferencesUpdate",
    "QueueFilters",
    "SearchStatus",
    "QueuePriority", 
    "OnboardingStatus"
]