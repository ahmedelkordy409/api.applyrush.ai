"""
MongoDB models for JobHire.AI using Beanie ODM
"""

from beanie import Document, Indexed
from pydantic import Field, BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId


class JobStatus(str, Enum):
    """Job application status enumeration"""
    DISCOVERED = "discovered"
    EVALUATING = "evaluating"
    QUEUED = "queued"
    APPLYING = "applying"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    SCREENING = "screening"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class MatchRecommendation(str, Enum):
    """Job matching recommendation levels"""
    STRONG_MATCH = "strong_match"
    GOOD_MATCH = "good_match"
    POSSIBLE_MATCH = "possible_match"
    WEAK_MATCH = "weak_match"


class User(Document):
    """User profile model"""

    # Basic Info
    email: Indexed(str, unique=True)
    full_name: Optional[str] = None
    external_id: Optional[str] = None  # For linking with external auth systems

    # Profile information
    resume_text: Optional[str] = None
    skills: Optional[List[str]] = []
    experience_years: Optional[int] = None
    education: Optional[Dict[str, Any]] = {}
    preferences: Optional[Dict[str, Any]] = {}

    # Settings
    auto_apply_enabled: bool = False
    auto_apply_rules: Optional[Dict[str, Any]] = {}
    notification_settings: Optional[Dict[str, Any]] = {}

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            "email",
            "external_id",
            "created_at"
        ]

    def __repr__(self):
        return f"<User {self.email}>"


class Company(Document):
    """Company information model"""

    name: Indexed(str)
    industry: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None

    # Metadata
    culture_keywords: Optional[List[str]] = []
    benefits: Optional[List[str]] = []
    remote_policy: Optional[str] = None

    # Analytics
    avg_response_time_days: Optional[float] = None
    hire_rate: Optional[float] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "companies"
        indexes = [
            "name",
            "industry"
        ]

    def __repr__(self):
        return f"<Company {self.name}>"


class Job(Document):
    """Job listing model"""

    external_id: Indexed(str, unique=True)  # ID from job board
    title: Indexed(str)
    description: str

    # Company reference
    company_id: Optional[ObjectId] = None
    company_name: Optional[str] = None  # Denormalized for faster queries

    # Job details
    location: Optional[Dict[str, Any]] = {}
    remote_option: Optional[str] = None  # full, hybrid, no
    employment_type: Optional[str] = None  # full-time, part-time, contract

    # Requirements
    required_skills: Optional[List[str]] = []
    preferred_skills: Optional[List[str]] = []
    experience_level: Optional[str] = None
    education_requirements: Optional[str] = None

    # Compensation
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: str = "USD"
    benefits: Optional[List[str]] = []

    # Metadata
    source: Optional[str] = None  # LinkedIn, Indeed, Glassdoor
    posted_date: Optional[datetime] = None
    application_deadline: Optional[datetime] = None
    applicant_count: Optional[int] = None

    # Flags
    is_active: bool = True
    is_vetted: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "jobs"
        indexes = [
            "external_id",
            "title",
            "company_id",
            "company_name",
            "source",
            "is_active",
            "posted_date",
            "created_at"
        ]

    def __repr__(self):
        return f"<Job {self.title} at {self.company_name}>"


class JobMatch(Document):
    """Job matching analysis model"""

    # References
    user_id: Indexed(ObjectId)
    job_id: Indexed(ObjectId)

    # Matching scores
    overall_score: Optional[float] = None  # 0-100
    skill_match_score: Optional[float] = None
    experience_score: Optional[float] = None
    education_score: Optional[float] = None
    location_score: Optional[float] = None
    salary_score: Optional[float] = None
    culture_score: Optional[float] = None

    # Analysis results
    recommendation: Optional[MatchRecommendation] = None
    apply_priority: Optional[int] = None  # 1-10
    success_probability: Optional[float] = None  # 0.0-1.0

    # Details
    matched_skills: Optional[List[str]] = []
    missing_skills: Optional[List[str]] = []
    improvement_suggestions: Optional[List[str]] = []
    red_flags: Optional[List[str]] = []
    competitive_advantage: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "job_matches"
        indexes = [
            "user_id",
            "job_id",
            [("user_id", 1), ("job_id", 1)],  # Compound index
            "overall_score",
            "recommendation",
            "created_at"
        ]

    def __repr__(self):
        return f"<JobMatch {self.user_id} -> {self.job_id} ({self.overall_score}%)>"


class JobApplication(Document):
    """Job application tracking model"""

    # References
    user_id: Indexed(ObjectId)
    job_id: Indexed(ObjectId)
    job_match_id: Optional[ObjectId] = None

    # Application details
    status: JobStatus = JobStatus.DISCOVERED
    applied_via: Optional[str] = None  # website, email, platform
    application_url: Optional[str] = None

    # Documents
    resume_version: Optional[str] = None  # Customized resume
    cover_letter: Optional[str] = None  # Generated cover letter

    # Tracking
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None

    # Analytics
    response_time_hours: Optional[float] = None
    interview_count: int = 0

    # Metadata
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "job_applications"
        indexes = [
            "user_id",
            "job_id",
            "job_match_id",
            [("user_id", 1), ("job_id", 1)],  # Compound index
            "status",
            "submitted_at",
            "created_at"
        ]

    def __repr__(self):
        return f"<JobApplication {self.user_id} -> {self.job_id} ({self.status})>"


class ApplicationStatusHistory(Document):
    """Track status changes in job applications"""

    application_id: Indexed(ObjectId)
    from_status: Optional[JobStatus] = None
    to_status: JobStatus
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    class Settings:
        name = "application_status_history"
        indexes = [
            "application_id",
            "changed_at"
        ]

    def __repr__(self):
        return f"<StatusHistory {self.application_id}: {self.from_status} -> {self.to_status}>"


class AIProcessingLog(Document):
    """Log AI processing activities"""

    # Request details
    user_id: Indexed(ObjectId)
    operation: str  # job_matching, cover_letter, resume_optimization
    model_used: str

    # Processing metrics
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    processing_time_ms: Optional[float] = None
    cost_usd: Optional[float] = None

    # Results
    success: bool = True
    error_message: Optional[str] = None
    output_quality_score: Optional[float] = None

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ai_processing_logs"
        indexes = [
            "user_id",
            "operation",
            "model_used",
            "success",
            "created_at"
        ]

    def __repr__(self):
        return f"<AILog {self.operation} for {self.user_id}>"


class UserAnalytics(Document):
    """User behavior and performance analytics"""

    user_id: Indexed(ObjectId)

    # Application metrics
    total_applications: int = 0
    successful_applications: int = 0
    interview_rate: float = 0.0
    offer_rate: float = 0.0

    # AI performance
    avg_match_score: Optional[float] = None
    ai_accuracy: Optional[float] = None

    # Usage patterns
    preferred_job_sources: Optional[List[str]] = []
    most_successful_times: Optional[Dict[str, Any]] = {}  # Days/hours
    avg_response_time: Optional[float] = None

    # Timestamps
    last_calculated: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "user_analytics"
        indexes = [
            "user_id",
            "last_calculated"
        ]

    def __repr__(self):
        return f"<UserAnalytics {self.user_id}>"


# For workflow integration
class WorkflowExecution(Document):
    """Database model for workflow executions"""

    workflow_id: Indexed(str, unique=True)
    workflow_type: Indexed(str)
    user_id: Indexed(str)
    job_id: Optional[str] = None

    status: str = "pending"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    current_node: Optional[str] = None

    # JSON fields for flexible data storage
    initial_state: Optional[Dict[str, Any]] = {}
    final_state: Optional[Dict[str, Any]] = {}
    user_profile: Optional[Dict[str, Any]] = {}
    job_data: Optional[Dict[str, Any]] = {}
    company_data: Optional[Dict[str, Any]] = {}

    # Results and metrics
    analysis_results: Optional[Dict[str, Any]] = {}
    decisions: Optional[Dict[str, Any]] = {}
    actions_taken: Optional[List[str]] = []
    results: Optional[Dict[str, Any]] = {}

    # Performance metrics
    match_score: Optional[float] = None
    processing_time_seconds: Optional[float] = None
    ai_cost_usd: float = 0.0

    # Error handling
    errors: Optional[List[str]] = []
    warnings: Optional[List[str]] = []

    # Metadata
    user_tier: str = "free"
    config: Optional[Dict[str, Any]] = {}

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "workflow_executions"
        indexes = [
            "workflow_id",
            "workflow_type",
            "user_id",
            "job_id",
            "status",
            "created_at"
        ]


class WorkflowJobApplication(Document):
    """Database model for workflow job applications"""

    user_id: Indexed(str)
    job_id: Indexed(str)
    workflow_execution_id: Optional[ObjectId] = None

    # Application details
    application_status: str = "pending"
    applied_at: Optional[datetime] = None
    application_method: Optional[str] = None

    # Generated content
    cover_letter: Optional[Dict[str, Any]] = {}
    resume_optimizations: Optional[Dict[str, Any]] = {}

    # Matching and scoring
    match_score: Optional[float] = None
    success_probability: Optional[float] = None
    recommendation: Optional[str] = None

    # Follow-up tracking
    follow_up_scheduled: bool = False
    follow_up_timeline: Optional[Dict[str, Any]] = {}
    last_follow_up: Optional[datetime] = None

    # Response tracking
    employer_response: Optional[str] = None
    response_received_at: Optional[datetime] = None
    interview_scheduled: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "workflow_job_applications"
        indexes = [
            "user_id",
            "job_id",
            "workflow_execution_id",
            "application_status",
            "created_at"
        ]


class WorkflowAnalytics(Document):
    """Database model for workflow analytics"""

    workflow_execution_id: Indexed(ObjectId)
    user_id: Indexed(str)

    # Performance metrics
    total_processing_time: Optional[float] = None
    ai_processing_time: Optional[float] = None
    node_count: Optional[int] = None
    error_count: Optional[int] = None
    warning_count: Optional[int] = None

    # AI usage metrics
    ai_calls_made: int = 0
    total_tokens_used: int = 0
    total_ai_cost: float = 0.0

    # Success metrics
    workflow_success: Optional[bool] = None
    application_submitted: Optional[bool] = None
    match_quality_score: Optional[float] = None

    # User tier for cost analysis
    user_tier: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "workflow_analytics"
        indexes = [
            "workflow_execution_id",
            "user_id",
            "created_at"
        ]