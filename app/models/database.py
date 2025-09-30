"""
Database models for JobHire.AI
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, Dict, Any

Base = declarative_base()


class JobStatus(PyEnum):
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


class MatchRecommendation(PyEnum):
    """Job matching recommendation levels"""
    STRONG_MATCH = "strong_match"
    GOOD_MATCH = "good_match"
    POSSIBLE_MATCH = "possible_match"
    WEAK_MATCH = "weak_match"


class User(Base):
    """User profile model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    supabase_id = Column(String, unique=True, index=True)  # Link to Supabase user
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    
    # Profile information
    resume_text = Column(Text)
    skills = Column(JSON)  # List of skills
    experience_years = Column(Integer)
    education = Column(JSON)  # Education history
    preferences = Column(JSON)  # Job preferences
    
    # Settings
    auto_apply_enabled = Column(Boolean, default=False)
    auto_apply_rules = Column(JSON)  # Auto-apply criteria
    notification_settings = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    job_applications = relationship("JobApplication", back_populates="user")


class Company(Base):
    """Company information model"""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    industry = Column(String)
    size = Column(String)
    description = Column(Text)
    website = Column(String)
    logo_url = Column(String)
    
    # Metadata
    culture_keywords = Column(JSON)
    benefits = Column(JSON)
    remote_policy = Column(String)
    
    # Analytics
    avg_response_time_days = Column(Float)
    hire_rate = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    jobs = relationship("Job", back_populates="company")


class Job(Base):
    """Job listing model"""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True)  # ID from job board
    title = Column(String, index=True)
    description = Column(Text)
    
    # Company
    company_id = Column(Integer, ForeignKey("companies.id"))
    company = relationship("Company", back_populates="jobs")
    
    # Job details
    location = Column(JSON)  # Location data
    remote_option = Column(String)  # full, hybrid, no
    employment_type = Column(String)  # full-time, part-time, contract
    
    # Requirements
    required_skills = Column(JSON)  # List of required skills
    preferred_skills = Column(JSON)  # List of preferred skills
    experience_level = Column(String)
    education_requirements = Column(String)
    
    # Compensation
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    currency = Column(String, default="USD")
    benefits = Column(JSON)
    
    # Metadata
    source = Column(String)  # LinkedIn, Indeed, Glassdoor
    posted_date = Column(DateTime)
    application_deadline = Column(DateTime)
    applicant_count = Column(Integer)
    
    # Flags
    is_active = Column(Boolean, default=True)
    is_vetted = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    job_applications = relationship("JobApplication", back_populates="job")
    job_matches = relationship("JobMatch", back_populates="job")


class JobMatch(Base):
    """Job matching analysis model"""
    __tablename__ = "job_matches"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    
    # Matching scores
    overall_score = Column(Float)  # 0-100
    skill_match_score = Column(Float)
    experience_score = Column(Float)
    education_score = Column(Float)
    location_score = Column(Float)
    salary_score = Column(Float)
    culture_score = Column(Float)
    
    # Analysis results
    recommendation = Column(Enum(MatchRecommendation))
    apply_priority = Column(Integer)  # 1-10
    success_probability = Column(Float)  # 0.0-1.0
    
    # Details
    matched_skills = Column(JSON)
    missing_skills = Column(JSON)
    improvement_suggestions = Column(JSON)
    red_flags = Column(JSON)
    competitive_advantage = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="job_matches")


class JobApplication(Base):
    """Job application tracking model"""
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    job_match_id = Column(Integer, ForeignKey("job_matches.id"))
    
    # Application details
    status = Column(Enum(JobStatus), default=JobStatus.DISCOVERED)
    applied_via = Column(String)  # website, email, platform
    application_url = Column(String)
    
    # Documents
    resume_version = Column(Text)  # Customized resume
    cover_letter = Column(Text)  # Generated cover letter
    
    # Tracking
    submitted_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    last_contact_at = Column(DateTime)
    
    # Analytics
    response_time_hours = Column(Float)
    interview_count = Column(Integer, default=0)
    
    # Metadata
    notes = Column(Text)
    rejection_reason = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="job_applications")
    job = relationship("Job", back_populates="job_applications")
    status_history = relationship("ApplicationStatusHistory", back_populates="application")


class ApplicationStatusHistory(Base):
    """Track status changes in job applications"""
    __tablename__ = "application_status_history"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("job_applications.id"))
    
    from_status = Column(Enum(JobStatus))
    to_status = Column(Enum(JobStatus))
    changed_at = Column(DateTime, default=func.now())
    notes = Column(Text)
    
    # Relationships
    application = relationship("JobApplication", back_populates="status_history")


class AIProcessingLog(Base):
    """Log AI processing activities"""
    __tablename__ = "ai_processing_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Request details
    user_id = Column(Integer, ForeignKey("users.id"))
    operation = Column(String)  # job_matching, cover_letter, resume_optimization
    model_used = Column(String)
    
    # Processing metrics
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    processing_time_ms = Column(Float)
    cost_usd = Column(Float)
    
    # Results
    success = Column(Boolean)
    error_message = Column(Text)
    output_quality_score = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())


class UserAnalytics(Base):
    """User behavior and performance analytics"""
    __tablename__ = "user_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Application metrics
    total_applications = Column(Integer, default=0)
    successful_applications = Column(Integer, default=0)
    interview_rate = Column(Float, default=0.0)
    offer_rate = Column(Float, default=0.0)
    
    # AI performance
    avg_match_score = Column(Float)
    ai_accuracy = Column(Float)
    
    # Usage patterns
    preferred_job_sources = Column(JSON)
    most_successful_times = Column(JSON)  # Days/hours
    avg_response_time = Column(Float)
    
    # Timestamps
    last_calculated = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())