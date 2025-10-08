"""
ApplyRush.AI - Comprehensive MongoDB Schema Design
AI-Powered Job Application Platform with MongoDB Collections
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId
from enum import Enum

# =========================================
# BASE MODELS AND UTILITIES
# =========================================

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class BaseDocument(BaseModel):
    """Base document with common fields"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# =========================================
# ENUMS FOR TYPE SAFETY
# =========================================

class SubscriptionStatus(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class ApprovalMode(str, Enum):
    APPROVAL = "approval"
    DELAYED = "delayed"
    INSTANT = "instant"

class ApplicationStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    HIRED = "hired"
    WITHDRAWN = "withdrawn"

class JobStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    FILLED = "filled"
    REMOVED = "removed"

class InterviewType(str, Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    LEADERSHIP = "leadership"
    GENERAL = "general"

# =========================================
# USER MANAGEMENT DOCUMENTS
# =========================================

class UserDocument(BaseDocument):
    """Core user authentication and profile"""
    email: str = Field(..., index=True, unique=True)
    password_hash: Optional[str] = None
    provider: str = "local"  # local, google, github, etc.
    provider_id: Optional[str] = None
    email_verified: bool = False
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    login_count: int = 0

    # Profile information (embedded for better performance)
    profile: Optional[Dict[str, Any]] = {
        "full_name": None,
        "first_name": None,
        "last_name": None,
        "phone": None,
        "location": None,
        "city": None,
        "state": None,
        "country": None,
        "timezone": None,
        "linkedin_url": None,
        "github_url": None,
        "portfolio_url": None,
        "bio": None,
        "profile_image_url": None,
        "subscription_status": SubscriptionStatus.FREE,
        "subscription_expires_at": None,
        "credits_remaining": 0,
        "onboarding_completed": False
    }

    # User settings (embedded for better performance)
    settings: Dict[str, Any] = {
        # Job Search Settings
        "job_search_active": True,
        "match_threshold": 55,  # 0-100 percentage
        "approval_mode": ApprovalMode.APPROVAL,
        "auto_apply_delay_hours": 24,
        "max_applications_per_day": 10,

        # AI Features
        "ai_cover_letters_enabled": False,
        "ai_resume_optimization_enabled": False,
        "ai_interview_prep_enabled": True,

        # Notification Preferences
        "email_notifications": True,
        "job_match_notifications": True,
        "application_status_notifications": True,
        "weekly_summary_notifications": True,

        # Privacy Settings
        "profile_visibility": "private",  # private, public, recruiters
        "allow_recruiter_contact": False
    }

    # Job preferences (embedded for matching)
    job_preferences: Dict[str, Any] = {
        "desired_positions": [],
        "preferred_locations": [],
        "remote_preference": "hybrid",  # remote, hybrid, onsite, flexible
        "salary_min": None,
        "salary_max": None,
        "employment_types": ["full_time"],
        "experience_levels": ["mid", "senior"],
        "industries": [],
        "company_sizes": [],
        "skills": [],
        "excluded_companies": [],
        "keywords": []
    }

    class Config:
        collection = "users"
        indexes = [
            [("email", 1)],
            [("provider", 1), ("provider_id", 1)],
            [("profile.subscription_status", 1)],
            [("settings.job_search_active", 1)],
            [("created_at", -1)]
        ]

# =========================================
# RESUME MANAGEMENT DOCUMENTS
# =========================================

class ResumeDocument(BaseDocument):
    """User resumes with AI parsing and optimization"""
    user_id: PyObjectId = Field(..., index=True)

    # File information
    original_filename: str
    stored_filename: str
    file_path: Optional[str] = None
    file_size: int
    file_type: str
    mime_type: Optional[str] = None

    # Resume metadata
    title: Optional[str] = None
    description: Optional[str] = None
    version: int = 1
    is_current: bool = False

    # AI parsing results
    parsed_content: Dict[str, Any] = {
        "raw_text": None,
        "structured_data": {},
        "contact_info": {},
        "work_experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "languages": [],
        "summary": None
    }

    # AI analysis
    ai_analysis: Dict[str, Any] = {
        "skills_extracted": [],
        "experience_years": None,
        "education_level": None,
        "industry_focus": [],
        "role_level": None,
        "ats_score": None,
        "keyword_density": {},
        "improvement_suggestions": []
    }

    # Status and source
    status: str = "active"  # active, deleted, processing
    upload_source: str = "manual"  # manual, imported, generated

    class Config:
        collection = "resumes"
        indexes = [
            [("user_id", 1)],
            [("user_id", 1), ("is_current", 1)],
            [("status", 1)],
            [("ai_analysis.skills_extracted", 1)],
            [("created_at", -1)]
        ]

class EnhancedResumeDocument(BaseDocument):
    """AI-optimized resume versions"""
    user_id: PyObjectId = Field(..., index=True)
    original_resume_id: PyObjectId
    job_id: Optional[PyObjectId] = None  # If enhanced for specific job

    # Generated content
    filename: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None

    # Enhancement details
    enhancement_details: Dict[str, Any] = {
        "ats_score": None,
        "optimization_type": [],  # keywords, format, skills, etc.
        "enhancements_applied": [],
        "keywords_added": [],
        "sections_modified": [],
        "improvement_percentage": None
    }

    # AI metadata
    ai_metadata: Dict[str, Any] = {
        "model_used": None,
        "processing_time_ms": None,
        "confidence_score": None,
        "parameters_used": {},
        "version": "1.0"
    }

    # Performance tracking
    performance: Dict[str, Any] = {
        "download_count": 0,
        "application_success_rate": None,
        "user_rating": None,
        "feedback_text": None
    }

    status: str = "active"

    class Config:
        collection = "enhanced_resumes"
        indexes = [
            [("user_id", 1)],
            [("original_resume_id", 1)],
            [("job_id", 1)],
            [("enhancement_details.ats_score", -1)],
            [("created_at", -1)]
        ]

# =========================================
# JOB DATA DOCUMENTS
# =========================================

class CompanyDocument(BaseDocument):
    """Company information and metrics"""
    name: str = Field(..., index=True)
    domain: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None

    # Company details
    description: Optional[str] = None
    industry: Optional[str] = None
    size_category: Optional[str] = None  # startup, small, medium, large, enterprise
    employee_count_min: Optional[int] = None
    employee_count_max: Optional[int] = None
    founded_year: Optional[int] = None

    # Location information
    headquarters_location: Optional[str] = None
    locations: List[str] = []

    # Company metrics
    metrics: Dict[str, Any] = {
        "glassdoor_rating": None,
        "linkedin_followers": None,
        "company_reviews": [],
        "culture_score": None,
        "diversity_score": None
    }

    # Social and web presence
    social_links: Dict[str, str] = {}

    status: str = "active"

    class Config:
        collection = "companies"
        indexes = [
            [("name", 1)],
            [("domain", 1)],
            [("industry", 1)],
            [("size_category", 1)],
            [("metrics.glassdoor_rating", -1)]
        ]

class JobDocument(BaseDocument):
    """Job postings with AI analysis and matching"""
    external_id: Optional[str] = None  # Original job ID from source
    source: str = Field(..., index=True)  # indeed, linkedin, company_site, etc.
    source_url: Optional[str] = None

    # Basic job information
    title: str = Field(..., index=True)
    company_name: str = Field(..., index=True)
    company_id: Optional[PyObjectId] = None
    location: Optional[str] = None
    remote_type: Optional[str] = None  # remote, hybrid, onsite, flexible

    # Job details
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None

    # Compensation
    salary: Dict[str, Any] = {
        "min": None,
        "max": None,
        "currency": "USD",
        "period": "annual",  # annual, hourly, monthly
        "equity": None,
        "bonus": None,
        "benefits_value": None
    }

    employment_type: Optional[str] = None  # full_time, part_time, contract, intern
    experience_level: Optional[str] = None  # entry, mid, senior, lead, executive

    # Additional metadata
    company_size: Optional[str] = None
    industry: Optional[str] = None

    # AI-extracted skills and requirements
    ai_extracted: Dict[str, Any] = {
        "skills_required": [],
        "skills_preferred": [],
        "education_required": None,
        "experience_years_min": None,
        "experience_years_max": None,
        "certifications": [],
        "languages": [],
        "keywords": [],
        "job_level": None,
        "department": None
    }

    # Job status and discovery
    status: JobStatus = JobStatus.ACTIVE
    posted_date: Optional[datetime] = None
    expires_date: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Matching and AI metadata
    matching_metadata: Dict[str, Any] = {
        "processed_for_matching": False,
        "embedding_vector": None,  # For AI similarity matching
        "match_keywords": [],
        "difficulty_score": None,
        "competition_level": None
    }

    # Application statistics
    application_stats: Dict[str, Any] = {
        "total_applications": 0,
        "response_rate": None,
        "average_response_time": None,
        "success_indicators": []
    }

    class Config:
        collection = "jobs"
        indexes = [
            [("source", 1)],
            [("title", "text"), ("description", "text"), ("company_name", "text")],
            [("company_name", 1)],
            [("location", 1)],
            [("remote_type", 1)],
            [("employment_type", 1)],
            [("experience_level", 1)],
            [("status", 1)],
            [("posted_date", -1)],
            [("ai_extracted.skills_required", 1)],
            [("salary.min", 1), ("salary.max", 1)],
            [("discovered_at", -1)]
        ]

# =========================================
# APPLICATION MANAGEMENT DOCUMENTS
# =========================================

class ApplicationDocument(BaseDocument):
    """Job application tracking with full lifecycle management"""
    user_id: PyObjectId = Field(..., index=True)
    job_id: PyObjectId = Field(..., index=True)
    resume_id: Optional[PyObjectId] = None
    cover_letter_id: Optional[PyObjectId] = None

    # Application details
    status: ApplicationStatus = ApplicationStatus.PENDING
    application_method: Optional[str] = None  # direct, email, platform, etc.
    applied_at: Optional[datetime] = None

    # Matching information
    matching: Dict[str, Any] = {
        "score": None,  # AI-calculated job match score (0-100)
        "reasons": [],
        "strengths": [],
        "weaknesses": [],
        "recommendation_confidence": None
    }

    application_source: str = "auto"  # auto, manual

    # Timeline tracking
    timeline: List[Dict[str, Any]] = []  # Event-based timeline

    # Follow-up and scheduling
    follow_up: Dict[str, Any] = {
        "last_contact_date": None,
        "next_follow_up_date": None,
        "follow_up_count": 0,
        "automated_follow_up": True
    }

    interview: Dict[str, Any] = {
        "scheduled_date": None,
        "interview_type": None,
        "interviewer_info": {},
        "preparation_completed": False,
        "feedback_received": False
    }

    # Company response tracking
    company_response: Dict[str, Any] = {
        "received": False,
        "date": None,
        "type": None,  # rejection, interview, offer, etc.
        "content": None,
        "automated": None
    }

    # User notes and feedback
    notes: Optional[str] = None
    feedback: Optional[str] = None
    user_rating: Optional[int] = None  # 1-5 rating of the application process

    # Performance metrics
    metrics: Dict[str, Any] = {
        "time_to_apply": None,  # seconds from match to application
        "response_time": None,  # time to get company response
        "process_duration": None,  # total application process time
        "success_probability": None
    }

    class Config:
        collection = "applications"
        indexes = [
            [("user_id", 1)],
            [("job_id", 1)],
            [("status", 1)],
            [("applied_at", -1)],
            [("matching.score", -1)],
            [("user_id", 1), ("status", 1)],
            [("created_at", -1)]
        ]

class ApplicationQueueDocument(BaseDocument):
    """Jobs waiting for approval or auto-application"""
    user_id: PyObjectId = Field(..., index=True)
    job_id: PyObjectId = Field(..., index=True)

    # Queue metadata
    status: str = "pending"  # pending, approved, rejected, expired
    priority: int = 5  # 1-10 priority score

    # Matching details
    matching: Dict[str, Any] = {
        "score": None,
        "reasons": [],
        "analysis": {},
        "confidence": None
    }

    # Auto-apply scheduling
    scheduling: Dict[str, Any] = {
        "auto_apply_after": None,
        "expires_at": None,
        "retry_count": 0,
        "max_retries": 3
    }

    # AI preparation status
    ai_preparation: Dict[str, Any] = {
        "cover_letter_generated": False,
        "resume_optimized": False,
        "interview_prep_ready": False,
        "analysis_completed": False
    }

    # User interaction
    user_interaction: Dict[str, Any] = {
        "viewed": False,
        "viewed_at": None,
        "decision_deadline": None,
        "auto_decision": True
    }

    class Config:
        collection = "application_queue"
        indexes = [
            [("user_id", 1)],
            [("status", 1)],
            [("scheduling.auto_apply_after", 1)],
            [("scheduling.expires_at", 1)],
            [("priority", -1), ("matching.score", -1)],
            [("created_at", -1)]
        ]

# =========================================
# AI-POWERED FEATURES DOCUMENTS
# =========================================

class CoverLetterDocument(BaseDocument):
    """AI-generated and custom cover letters"""
    user_id: PyObjectId = Field(..., index=True)
    job_id: Optional[PyObjectId] = None
    application_id: Optional[PyObjectId] = None

    # Content
    title: Optional[str] = None
    content: str
    format: str = "text"  # text, html, pdf

    # Generation metadata
    generation: Dict[str, Any] = {
        "type": "ai",  # ai, template, custom
        "ai_model_used": None,
        "writing_style": "professional",  # professional, casual, executive, etc.
        "tone": "formal",  # formal, friendly, confident, etc.
        "parameters": {},
        "version": "1.0"
    }

    # Performance metrics
    performance: Dict[str, Any] = {
        "generation_time_ms": None,
        "confidence_score": None,
        "word_count": None,
        "readability_score": None,
        "ats_optimization_score": None
    }

    # Usage and feedback
    usage: Dict[str, Any] = {
        "used_in_application": False,
        "download_count": 0,
        "feedback_rating": None,  # 1-5 user rating
        "feedback_text": None,
        "effectiveness_score": None
    }

    # Customization history
    customization_history: List[Dict[str, Any]] = []

    class Config:
        collection = "cover_letters"
        indexes = [
            [("user_id", 1)],
            [("job_id", 1)],
            [("generation.type", 1)],
            [("usage.used_in_application", 1)],
            [("created_at", -1)]
        ]

class InterviewSessionDocument(BaseDocument):
    """Mock interview sessions with AI coaching"""
    user_id: PyObjectId = Field(..., index=True)
    job_id: Optional[PyObjectId] = None

    # Session configuration
    configuration: Dict[str, Any] = {
        "session_type": InterviewType.BEHAVIORAL,
        "difficulty_level": "medium",  # easy, medium, hard, expert
        "ai_personality": "professional",  # professional, friendly, challenging, supportive
        "candidate_name": None,
        "target_duration_minutes": 30,
        "focus_areas": []
    }

    # Session metadata
    session_data: Dict[str, Any] = {
        "total_questions": 0,
        "questions_answered": 0,
        "current_question_index": 0,
        "estimated_duration": None,
        "actual_duration": None
    }

    # Session state
    status: str = "created"  # created, active, paused, completed, abandoned
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Performance results
    results: Dict[str, Any] = {
        "overall_score": None,
        "completion_rate": None,
        "category_scores": {},
        "strengths": [],
        "improvements": [],
        "recommendations": [],
        "performance_summary": None
    }

    # AI coaching insights
    coaching: Dict[str, Any] = {
        "personalized_feedback": None,
        "improvement_plan": [],
        "practice_suggestions": [],
        "follow_up_topics": []
    }

    class Config:
        collection = "interview_sessions"
        indexes = [
            [("user_id", 1)],
            [("status", 1)],
            [("configuration.session_type", 1)],
            [("results.overall_score", -1)],
            [("created_at", -1)]
        ]

class InterviewQuestionDocument(BaseDocument):
    """Individual interview questions and responses"""
    session_id: PyObjectId = Field(..., index=True)

    # Question details
    question_data: Dict[str, Any] = {
        "text": None,
        "type": None,  # behavioral, technical, situational, etc.
        "category": None,
        "difficulty": None,
        "order_index": None,
        "expected_answer_length": None,
        "key_points": []
    }

    # User response
    response: Dict[str, Any] = {
        "answer_text": None,
        "submitted_at": None,
        "time_to_answer_seconds": None,
        "word_count": None,
        "confidence_level": None
    }

    # AI evaluation
    evaluation: Dict[str, Any] = {
        "score": None,  # 0-100
        "feedback": None,
        "strengths": [],
        "improvements": [],
        "specific_suggestions": [],
        "star_method_usage": None,
        "relevance_score": None
    }

    # Follow-up and coaching
    coaching: Dict[str, Any] = {
        "follow_up_questions": [],
        "improvement_exercises": [],
        "resource_links": []
    }

    class Config:
        collection = "interview_questions"
        indexes = [
            [("session_id", 1)],
            [("question_data.order_index", 1)],
            [("evaluation.score", -1)],
            [("created_at", -1)]
        ]

# =========================================
# ANALYTICS AND TRACKING DOCUMENTS
# =========================================

class UserActivityDocument(BaseDocument):
    """User activity tracking for analytics"""
    user_id: PyObjectId = Field(..., index=True)

    # Activity details
    action: str
    entity_type: Optional[str] = None  # job, application, resume, etc.
    entity_id: Optional[PyObjectId] = None

    # Context and metadata
    context: Dict[str, Any] = {}
    session_info: Dict[str, Any] = {
        "ip_address": None,
        "user_agent": None,
        "session_id": None,
        "device_type": None,
        "browser": None
    }

    # Performance metrics
    performance: Dict[str, Any] = {
        "duration_ms": None,
        "success": True,
        "error_message": None,
        "retry_count": 0
    }

    # Geolocation (if available)
    location: Dict[str, Any] = {
        "country": None,
        "city": None,
        "timezone": None
    }

    class Config:
        collection = "user_activity"
        indexes = [
            [("user_id", 1)],
            [("action", 1)],
            [("entity_type", 1), ("entity_id", 1)],
            [("created_at", -1)],
            [("user_id", 1), ("created_at", -1)]
        ]

class SystemMetricsDocument(BaseDocument):
    """System performance and health metrics"""

    # Metric details
    metric_name: str = Field(..., index=True)
    metric_value: float
    metric_unit: Optional[str] = None
    metric_type: str = "gauge"  # counter, gauge, histogram

    # Context and tags
    tags: Dict[str, Any] = {}
    environment: str = "production"
    service: Optional[str] = None

    # Aggregation data
    aggregation: Dict[str, Any] = {
        "period": "1m",  # 1m, 5m, 1h, 1d
        "aggregation_type": "avg",  # avg, sum, min, max, count
        "sample_count": 1
    }

    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        collection = "system_metrics"
        indexes = [
            [("metric_name", 1)],
            [("recorded_at", -1)],
            [("environment", 1), ("service", 1)],
            [("metric_name", 1), ("recorded_at", -1)]
        ]

class AIModelMetricsDocument(BaseDocument):
    """AI model performance and cost tracking"""

    # Model details
    model_info: Dict[str, Any] = {
        "name": None,
        "version": None,
        "provider": None,  # openai, anthropic, custom
        "operation_type": None,  # resume_enhancement, cover_letter, job_matching, etc.
        "model_parameters": {}
    }

    # Performance metrics
    performance: Dict[str, Any] = {
        "processing_time_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "requests_per_second": None,
        "latency_p95": None
    }

    # Cost tracking
    cost: Dict[str, Any] = {
        "cost_usd": None,
        "cost_per_token": None,
        "monthly_budget_used": None,
        "cost_optimization_score": None
    }

    # Quality metrics
    quality: Dict[str, Any] = {
        "confidence_score": None,
        "user_feedback_score": None,  # 1-5
        "accuracy_score": None,
        "hallucination_detected": False
    }

    # Context
    context: Dict[str, Any] = {
        "user_id": None,
        "entity_type": None,
        "entity_id": None,
        "request_id": None,
        "batch_id": None
    }

    class Config:
        collection = "ai_model_metrics"
        indexes = [
            [("model_info.name", 1)],
            [("model_info.operation_type", 1)],
            [("context.user_id", 1)],
            [("performance.processing_time_ms", 1)],
            [("cost.cost_usd", 1)],
            [("created_at", -1)]
        ]

# =========================================
# MONGODB COLLECTION SETUP AND INDEXES
# =========================================

def setup_mongodb_collections(db):
    """
    Setup MongoDB collections with proper indexes and validation
    """

    # Create collections with validation schemas
    collections_config = {
        "users": {
            "validator": {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["email"],
                    "properties": {
                        "email": {"bsonType": "string", "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"},
                        "profile.subscription_status": {"enum": ["free", "premium", "enterprise"]},
                        "settings.approval_mode": {"enum": ["approval", "delayed", "instant"]},
                        "settings.match_threshold": {"bsonType": "number", "minimum": 0, "maximum": 100}
                    }
                }
            }
        },
        "jobs": {
            "validator": {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["title", "company_name", "source"],
                    "properties": {
                        "title": {"bsonType": "string", "minLength": 1},
                        "company_name": {"bsonType": "string", "minLength": 1},
                        "source": {"bsonType": "string", "minLength": 1},
                        "status": {"enum": ["active", "expired", "filled", "removed"]}
                    }
                }
            }
        },
        "applications": {
            "validator": {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["user_id", "job_id"],
                    "properties": {
                        "status": {"enum": ["pending", "submitted", "interview", "rejected", "hired", "withdrawn"]}
                    }
                }
            }
        }
    }

    # Create collections with validation
    for collection_name, config in collections_config.items():
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name, validator=config.get("validator"))

    # Create indexes for better performance
    create_indexes(db)

    print("MongoDB collections and indexes created successfully!")

def create_indexes(db):
    """Create all necessary indexes for optimal performance"""

    # Users collection indexes
    db.users.create_index([("email", 1)], unique=True)
    db.users.create_index([("provider", 1), ("provider_id", 1)])
    db.users.create_index([("profile.subscription_status", 1)])
    db.users.create_index([("settings.job_search_active", 1)])
    db.users.create_index([("created_at", -1)])

    # Jobs collection indexes
    db.jobs.create_index([("source", 1)])
    db.jobs.create_index([("company_name", 1)])
    db.jobs.create_index([("location", 1)])
    db.jobs.create_index([("remote_type", 1)])
    db.jobs.create_index([("employment_type", 1)])
    db.jobs.create_index([("experience_level", 1)])
    db.jobs.create_index([("status", 1)])
    db.jobs.create_index([("posted_date", -1)])
    db.jobs.create_index([("ai_extracted.skills_required", 1)])
    db.jobs.create_index([("salary.min", 1), ("salary.max", 1)])
    db.jobs.create_index([("discovered_at", -1)])

    # Text search indexes
    db.jobs.create_index([
        ("title", "text"),
        ("description", "text"),
        ("company_name", "text")
    ])

    # Applications collection indexes
    db.applications.create_index([("user_id", 1)])
    db.applications.create_index([("job_id", 1)])
    db.applications.create_index([("status", 1)])
    db.applications.create_index([("applied_at", -1)])
    db.applications.create_index([("matching.score", -1)])
    db.applications.create_index([("user_id", 1), ("status", 1)])

    # Application queue indexes
    db.application_queue.create_index([("user_id", 1)])
    db.application_queue.create_index([("status", 1)])
    db.application_queue.create_index([("scheduling.auto_apply_after", 1)])
    db.application_queue.create_index([("scheduling.expires_at", 1)])
    db.application_queue.create_index([("priority", -1), ("matching.score", -1)])

    # Resume collection indexes
    db.resumes.create_index([("user_id", 1)])
    db.resumes.create_index([("user_id", 1), ("is_current", 1)])
    db.resumes.create_index([("status", 1)])
    db.resumes.create_index([("ai_analysis.skills_extracted", 1)])

    # Enhanced resumes indexes
    db.enhanced_resumes.create_index([("user_id", 1)])
    db.enhanced_resumes.create_index([("original_resume_id", 1)])
    db.enhanced_resumes.create_index([("job_id", 1)])
    db.enhanced_resumes.create_index([("enhancement_details.ats_score", -1)])

    # Cover letters indexes
    db.cover_letters.create_index([("user_id", 1)])
    db.cover_letters.create_index([("job_id", 1)])
    db.cover_letters.create_index([("generation.type", 1)])
    db.cover_letters.create_index([("usage.used_in_application", 1)])

    # Interview sessions indexes
    db.interview_sessions.create_index([("user_id", 1)])
    db.interview_sessions.create_index([("status", 1)])
    db.interview_sessions.create_index([("configuration.session_type", 1)])
    db.interview_sessions.create_index([("results.overall_score", -1)])

    # Interview questions indexes
    db.interview_questions.create_index([("session_id", 1)])
    db.interview_questions.create_index([("question_data.order_index", 1)])
    db.interview_questions.create_index([("evaluation.score", -1)])

    # Analytics indexes
    db.user_activity.create_index([("user_id", 1)])
    db.user_activity.create_index([("action", 1)])
    db.user_activity.create_index([("entity_type", 1), ("entity_id", 1)])
    db.user_activity.create_index([("created_at", -1)])
    db.user_activity.create_index([("user_id", 1), ("created_at", -1)])

    # System metrics indexes
    db.system_metrics.create_index([("metric_name", 1)])
    db.system_metrics.create_index([("recorded_at", -1)])
    db.system_metrics.create_index([("environment", 1), ("service", 1)])
    db.system_metrics.create_index([("metric_name", 1), ("recorded_at", -1)])

    # AI model metrics indexes
    db.ai_model_metrics.create_index([("model_info.name", 1)])
    db.ai_model_metrics.create_index([("model_info.operation_type", 1)])
    db.ai_model_metrics.create_index([("context.user_id", 1)])
    db.ai_model_metrics.create_index([("performance.processing_time_ms", 1)])
    db.ai_model_metrics.create_index([("cost.cost_usd", 1)])

    # TTL indexes for automatic data cleanup
    db.user_activity.create_index([("created_at", 1)], expireAfterSeconds=60*60*24*90)  # 90 days
    db.system_metrics.create_index([("recorded_at", 1)], expireAfterSeconds=60*60*24*30)  # 30 days

# =========================================
# SAMPLE DATA FOR TESTING
# =========================================

def insert_sample_data(db):
    """Insert sample data for testing"""

    # Sample user
    sample_user = {
        "email": "demo@applyrush.ai",
        "password_hash": "$2b$12$example_hash",
        "email_verified": True,
        "profile": {
            "full_name": "Demo User",
            "first_name": "Demo",
            "last_name": "User",
            "location": "San Francisco, CA",
            "subscription_status": "free"
        },
        "settings": {
            "job_search_active": True,
            "match_threshold": 55,
            "approval_mode": "approval"
        },
        "job_preferences": {
            "desired_positions": ["Software Engineer", "Full Stack Developer"],
            "preferred_locations": ["San Francisco", "Remote"],
            "remote_preference": "hybrid"
        }
    }

    user_result = db.users.insert_one(sample_user)
    user_id = user_result.inserted_id

    # Sample company
    sample_company = {
        "name": "TechCorp Inc",
        "domain": "techcorp.com",
        "industry": "Technology",
        "size_category": "large",
        "headquarters_location": "San Francisco, CA"
    }

    company_result = db.companies.insert_one(sample_company)

    # Sample job
    sample_job = {
        "title": "Senior Full Stack Developer",
        "company_name": "TechCorp Inc",
        "source": "company_website",
        "location": "San Francisco, CA",
        "remote_type": "hybrid",
        "description": "We are looking for an experienced full stack developer...",
        "employment_type": "full_time",
        "experience_level": "senior",
        "salary": {
            "min": 120000,
            "max": 180000,
            "currency": "USD"
        },
        "ai_extracted": {
            "skills_required": ["React", "Node.js", "Python", "PostgreSQL"],
            "experience_years_min": 5
        },
        "status": "active"
    }

    job_result = db.jobs.insert_one(sample_job)

    print(f"Sample data inserted successfully!")
    print(f"User ID: {user_id}")
    print(f"Job ID: {job_result.inserted_id}")

# =========================================
# MONGODB AGGREGATION PIPELINES
# =========================================

def get_user_dashboard_data(db, user_id):
    """Aggregation pipeline for user dashboard data"""

    pipeline = [
        {"$match": {"user_id": ObjectId(user_id)}},
        {"$facet": {
            "applications": [
                {"$lookup": {
                    "from": "jobs",
                    "localField": "job_id",
                    "foreignField": "_id",
                    "as": "job"
                }},
                {"$unwind": "$job"},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_match_score": {"$avg": "$matching.score"}
                }}
            ],
            "queue": [
                {"$lookup": {
                    "from": "application_queue",
                    "localField": "_id",
                    "foreignField": "user_id",
                    "as": "queue_items"
                }},
                {"$unwind": "$queue_items"},
                {"$count": "pending_applications"}
            ],
            "recent_activity": [
                {"$lookup": {
                    "from": "user_activity",
                    "localField": "_id",
                    "foreignField": "user_id",
                    "as": "activities"
                }},
                {"$unwind": "$activities"},
                {"$sort": {"activities.created_at": -1}},
                {"$limit": 10}
            ]
        }}
    ]

    return list(db.users.aggregate(pipeline))

def get_job_matching_pipeline(db, user_id, match_threshold=55):
    """Aggregation pipeline for job matching"""

    pipeline = [
        {"$match": {"status": "active"}},
        {"$lookup": {
            "from": "users",
            "localField": "_id",
            "foreignField": "_id",
            "as": "user",
            "pipeline": [{"$match": {"_id": ObjectId(user_id)}}]
        }},
        {"$unwind": "$user"},
        {"$addFields": {
            "match_score": {
                "$function": {
                    "body": """
                    function(job, user) {
                        // AI matching logic here
                        // This would be replaced with actual ML model
                        return Math.floor(Math.random() * 100);
                    }
                    """,
                    "args": ["$$ROOT", "$user"],
                    "lang": "js"
                }
            }
        }},
        {"$match": {"match_score": {"$gte": match_threshold}}},
        {"$sort": {"match_score": -1}},
        {"$limit": 50}
    ]

    return list(db.jobs.aggregate(pipeline))

"""
PERFORMANCE OPTIMIZATION RECOMMENDATIONS:

1. Indexing Strategy:
   - Compound indexes for common query patterns
   - Text indexes for search functionality
   - TTL indexes for automatic cleanup
   - Sparse indexes for optional fields

2. Document Design:
   - Embed related data for better read performance
   - Use references for large or frequently changing data
   - Optimize for your most common access patterns

3. Aggregation Optimization:
   - Use $match early in pipelines
   - Create indexes that support aggregation stages
   - Use $lookup sparingly and index foreign keys

4. Monitoring and Maintenance:
   - Monitor slow queries and optimize indexes
   - Regular collection stats analysis
   - Implement sharding for horizontal scaling
   - Use MongoDB Atlas for managed scaling

5. Data Archival:
   - Implement data lifecycle policies
   - Archive old user activity and metrics
   - Compress historical data
"""