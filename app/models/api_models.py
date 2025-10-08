"""
Pydantic models for API request/response schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Enums
class ApplicationStatus(str, Enum):
    pending = "pending"
    submitted = "submitted"
    interview = "interview"
    rejected = "rejected"
    hired = "hired"

class JobType(str, Enum):
    full_time = "Full-time"
    part_time = "Part-time"
    contract = "Contract"
    internship = "Internship"
    freelance = "Freelance"

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class ExperienceLevel(str, Enum):
    entry = "Entry Level"
    junior = "Junior"
    mid = "Mid Level"
    senior = "Senior"
    lead = "Lead"
    executive = "Executive"

# Request Models
class JobSearchRequest(BaseModel):
    """Request model for job search"""
    keywords: str = Field(..., description="Search keywords (e.g., 'Python Developer')", example="Senior Python Developer")
    location: Optional[str] = Field(None, description="Job location or 'Remote'", example="San Francisco, CA")
    salary_min: Optional[int] = Field(None, description="Minimum salary expectation", example=100000)
    salary_max: Optional[int] = Field(None, description="Maximum salary expectation", example=200000)
    experience_level: Optional[ExperienceLevel] = Field(None, description="Required experience level")
    job_type: Optional[JobType] = Field(None, description="Type of employment")
    remote_only: Optional[bool] = Field(False, description="Only show remote positions")
    companies: Optional[List[str]] = Field(None, description="Filter by specific companies", example=["Google", "Microsoft"])
    skills: Optional[List[str]] = Field(None, description="Required skills", example=["Python", "FastAPI", "Docker"])
    page: Optional[int] = Field(1, ge=1, description="Page number for pagination")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Results per page")

class JobMatchAnalysisRequest(BaseModel):
    """Request model for job match analysis"""
    user_profile: Dict[str, Any] = Field(..., description="User profile data", example={
        "user_id": "user_123",
        "name": "John Developer",
        "skills": ["Python", "React", "AWS", "Docker"],
        "experience_years": 5,
        "location": "San Francisco, CA",
        "salary_expectation": 150000,
        "education": "BS Computer Science",
        "preferred_companies": ["Google", "Microsoft"],
        "work_authorization": "US Citizen"
    })
    job_data: Dict[str, Any] = Field(..., description="Job posting data", example={
        "job_id": "job_456",
        "title": "Senior Software Engineer",
        "company": "TechCorp",
        "location": "San Francisco, CA",
        "description": "We are looking for a Senior Software Engineer...",
        "requirements": ["Python", "AWS", "5+ years experience"],
        "salary_min": 140000,
        "salary_max": 180000,
        "remote": True,
        "job_type": "Full-time"
    })
    analysis_depth: Optional[str] = Field("comprehensive", description="Analysis depth level", enum=["quick", "standard", "comprehensive"])

class ApplicationSubmitRequest(BaseModel):
    """Request model for application submission"""
    job_id: str = Field(..., description="Job ID to apply to", example="job_789")
    user_id: str = Field(..., description="User ID of applicant", example="user_123")
    cover_letter: Optional[str] = Field(None, description="Custom cover letter")
    resume_version: Optional[str] = Field("latest", description="Resume version to use")
    answers: Optional[Dict[str, str]] = Field(None, description="Answers to application questions", example={
        "years_experience": "5",
        "work_authorization": "Yes",
        "salary_expectation": "150000"
    })
    auto_apply: Optional[bool] = Field(False, description="Is this an auto-apply submission?")
    referral_code: Optional[str] = Field(None, description="Employee referral code if available")

class UserProfileRequest(BaseModel):
    """Request model for user profile creation/update"""
    name: str = Field(..., description="Full name", example="John Developer")
    email: str = Field(..., description="Email address", example="john@example.com")
    phone: Optional[str] = Field(None, description="Phone number", example="+1-555-0123")
    location: str = Field(..., description="Current location", example="San Francisco, CA")
    skills: List[str] = Field(..., description="Technical skills", example=["Python", "JavaScript", "React", "AWS"])
    experience_years: int = Field(..., ge=0, description="Years of experience", example=5)
    education: str = Field(..., description="Education background", example="BS Computer Science")
    salary_expectation: int = Field(..., ge=0, description="Salary expectation in USD", example=150000)
    job_titles: List[str] = Field(..., description="Target job titles", example=["Senior Software Engineer", "Full Stack Developer"])
    preferred_companies: Optional[List[str]] = Field(None, description="Preferred companies", example=["Google", "Microsoft", "Apple"])
    work_authorization: str = Field(..., description="Work authorization status", example="US Citizen")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL", example="https://linkedin.com/in/johndeveloper")
    github_url: Optional[str] = Field(None, description="GitHub profile URL", example="https://github.com/johndeveloper")
    portfolio_url: Optional[str] = Field(None, description="Portfolio website URL", example="https://johndeveloper.com")

class AIAnalysisRequest(BaseModel):
    """Request model for real-time AI analysis"""
    job_data: Dict[str, Any] = Field(..., description="Job data to analyze", example={
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "location": "San Francisco, CA",
        "description": "We are seeking a Senior Python Developer with experience in FastAPI, machine learning, and cloud technologies.",
        "requirements": ["Python", "FastAPI", "AWS", "Machine Learning"],
        "salary_min": 140000,
        "salary_max": 180000,
        "remote": True
    })
    user_profile: Optional[Dict[str, Any]] = Field(None, description="Optional user profile for personalized analysis")
    analysis_type: Optional[str] = Field("comprehensive", description="Type of analysis", enum=["quick", "standard", "comprehensive"])

# Response Models
class JobSearchResponse(BaseModel):
    """Response model for job search"""
    jobs: List[Dict[str, Any]] = Field(..., description="List of job postings")
    total: int = Field(..., description="Total number of results")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Results per page")
    source: str = Field(..., description="Data source")
    response_time: str = Field(..., description="API response time")

class JobMatchAnalysisResponse(BaseModel):
    """Response model for job match analysis"""
    match_score: int = Field(..., ge=0, le=100, description="Match percentage")
    match_reasons: List[str] = Field(..., description="Reasons for the match score")
    fit_analysis: str = Field(..., description="Detailed fit analysis")
    recommendations: List[str] = Field(..., description="Recommendations for the candidate")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level of analysis")
    processing_time: str = Field(..., description="Processing time")
    ai_model_used: str = Field(..., description="AI model used for analysis")
    timestamp: datetime = Field(..., description="Analysis timestamp")

class ApplicationSubmitResponse(BaseModel):
    """Response model for application submission"""
    application_id: str = Field(..., description="Application ID")
    status: ApplicationStatus = Field(..., description="Application status")
    message: str = Field(..., description="Status message")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    next_steps: Optional[List[str]] = Field(None, description="Next steps in the process")
    estimated_response_time: Optional[str] = Field(None, description="Estimated response time from employer")

class AIAgentStatusResponse(BaseModel):
    """Response model for AI agent status"""
    is_running: bool = Field(..., description="Is the AI agent running?")
    runtime: Optional[str] = Field(None, description="How long the agent has been running")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    statistics: Dict[str, int] = Field(..., description="Processing statistics")
    active_users: int = Field(..., description="Number of active users")
    next_cycles: Dict[str, str] = Field(..., description="Next processing cycle times")

class MonitoringSummaryResponse(BaseModel):
    """Response model for monitoring summary"""
    message: str = Field(..., description="Status message")
    monitoring_features: List[str] = Field(..., description="Available monitoring features")
    current_status: Dict[str, str] = Field(..., description="Current system metrics")

class ApplicationQueueResponse(BaseModel):
    """Response model for application queue"""
    queue: List[Dict[str, Any]] = Field(..., description="Queued applications")
    total: int = Field(..., description="Total applications in queue")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Items per page")
    status: str = Field(..., description="Queue filter status")
    source: str = Field(..., description="Data source")
    ai_processing: bool = Field(..., description="Is AI processing enabled?")
    response_time: str = Field(..., description="API response time")

class DatabaseApplicationsResponse(BaseModel):
    """Response model for database applications"""
    applications: List[Dict[str, Any]] = Field(..., description="List of applications")
    total: int = Field(..., description="Total number of applications")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Items per page")
    sortBy: str = Field(..., description="Sort field")
    sortOrder: SortOrder = Field(..., description="Sort order")
    source: str = Field(..., description="Data source")
    response_time: str = Field(..., description="API response time")

class HealthCheckResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service health status")
    timestamp: datetime = Field(..., description="Current timestamp")
    service: str = Field(..., description="Service name")
    components: Dict[str, str] = Field(..., description="Component health statuses")

class ErrorResponse(BaseModel):
    """Response model for errors"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")