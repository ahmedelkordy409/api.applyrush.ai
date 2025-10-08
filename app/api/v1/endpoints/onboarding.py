"""
Onboarding API - Collect user preferences and save to profile
This data is used for job matching and auto-apply filtering
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.core.database_new import get_db, Collections, serialize_doc
from app.core.security import get_current_user, hash_password

router = APIRouter()


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class OnboardingData(BaseModel):
    """Complete onboarding data from frontend"""
    # Step 1: Welcome
    started: bool = True

    # Step 2: Work Authorization
    work_authorization: str  # "us_citizen", "green_card", "work_visa", "need_sponsorship"

    # Step 3: Salary
    salary_min: int
    salary_max: int
    salary_currency: str = "USD"

    # Step 4: Work Situation
    work_situation: str  # "employed", "unemployed", "student", "freelance"

    # Step 5: Job Titles
    job_titles: List[str]  # ["Software Engineer", "Full Stack Developer"]

    # Step 6-8: Experience
    years_of_experience: int
    education_level: str  # "high_school", "bachelors", "masters", "phd"
    experience_exceptional: Optional[bool] = False

    # Step 9: Industry
    industries: List[str]  # ["Technology", "Finance", "Healthcare"]

    # Step 10: Timezone
    timezone: str

    # Step 11: Relocation
    relocation_willing: bool
    preferred_locations: List[str]

    # Step 12: Work Location
    work_location_preference: str  # "remote", "hybrid", "onsite", "flexible"

    # Step 13: Work Type
    work_types: List[str]  # ["full_time", "part_time", "contract"]

    # Step 14: Security Clearance (optional)
    security_clearance: Optional[str] = None

    # Step 15: Visa Sponsorship
    visa_sponsorship_needed: bool

    # Demographics (optional)
    veteran_status: Optional[str] = None
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    disability_status: Optional[str] = None

    # Step 16: Email (if guest)
    email: Optional[EmailStr] = None

    # Additional preferences
    skills: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    excluded_companies: Optional[List[str]] = []
    company_size_preferences: Optional[List[str]] = []


class GuestOnboardingRequest(BaseModel):
    """Guest onboarding without authentication"""
    data: OnboardingData
    create_account: bool = False
    password: Optional[str] = None


class OnboardingResponse(BaseModel):
    """Response after onboarding"""
    success: bool
    message: str
    user_id: Optional[str] = None
    profile_id: Optional[str] = None
    redirect_to: str  # Next step: "/upselling" or "/dashboard"


# ============================================
# ENDPOINTS
# ============================================

@router.post("/guest", response_model=OnboardingResponse)
async def guest_onboarding(
    request: GuestOnboardingRequest,
    db = Depends(get_db)
):
    """
    Handle guest onboarding - save preferences for job matching

    Data Flow:
    1. Save onboarding data to guest_profiles (if no account)
    2. Create user account (if requested)
    3. Save preferences to user profile
    4. Use preferences for job matching filters
    """

    data = request.data

    # Validate required fields
    if not data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required for onboarding"
        )

    # Check if user already exists
    existing_user = db[Collections.USERS].find_one({"email": data.email})

    if request.create_account:
        # Create new user account
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        if not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required to create account"
            )

        # Create user with onboarding data embedded
        user_doc = {
            "email": data.email,
            "password_hash": hash_password(request.password),
            "email_verified": False,
            "is_active": True,

            # Subscription defaults
            "subscription_status": "free",
            "subscription_plan_id": None,
            "stripe_customer_id": None,

            # Embed onboarding data into user profile
            "profile": {
                "full_name": None,  # Will be collected later
                "location": data.preferred_locations[0] if data.preferred_locations else None,
                "timezone": data.timezone,
                "onboarding_completed": True,
            },

            # Job preferences from onboarding - THIS IS KEY FOR MATCHING
            "job_preferences": {
                "desired_positions": data.job_titles,
                "preferred_locations": data.preferred_locations,
                "remote_preference": data.work_location_preference,
                "salary_min": data.salary_min,
                "salary_max": data.salary_max,
                "salary_currency": data.salary_currency,
                "employment_types": data.work_types,
                "industries": data.industries,
                "skills": data.skills or [],
                "keywords": data.keywords or [],
                "excluded_companies": data.excluded_companies or [],
                "company_size_preferences": data.company_size_preferences or [],
                "relocation_willing": data.relocation_willing,
            },

            # Onboarding details for future reference
            "onboarding": {
                "completed": True,
                "work_authorization": data.work_authorization,
                "visa_sponsorship_needed": data.visa_sponsorship_needed,
                "work_situation": data.work_situation,
                "years_of_experience": data.years_of_experience,
                "education_level": data.education_level,
                "experience_exceptional": data.experience_exceptional,
                "security_clearance": data.security_clearance,
                # Demographics (optional)
                "veteran_status": data.veteran_status,
                "gender": data.gender,
                "ethnicity": data.ethnicity,
                "disability_status": data.disability_status,
            },

            # Default settings
            "settings": {
                "job_search_active": True,
                "match_threshold": 55,  # 55% match minimum
                "approval_mode": "approval",  # Require user approval before applying
                "auto_apply_delay_hours": 24,
                "max_applications_per_day": 10,
                "browser_auto_apply": False,  # Disabled by default, enable in upselling
                "ai_cover_letters_enabled": False,
                "ai_resume_optimization_enabled": False,
                "email_notifications": True,
                "job_match_notifications": True,
            },

            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = db[Collections.USERS].insert_one(user_doc)
        user_id = str(result.inserted_id)

        return OnboardingResponse(
            success=True,
            message="Account created successfully",
            user_id=user_id,
            redirect_to="/upselling"  # Next: upselling flow
        )

    else:
        # Save as guest profile (no account yet)
        guest_profile = {
            "email": data.email,
            "onboarding_data": data.dict(),
            "account_created": False,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow(),  # Guest profiles expire after 7 days
        }

        result = db["guest_profiles"].insert_one(guest_profile)

        return OnboardingResponse(
            success=True,
            message="Onboarding data saved. Create an account to continue.",
            profile_id=str(result.inserted_id),
            redirect_to="/auth/sign-up"  # Redirect to sign up
        )


@router.post("/authenticated", response_model=OnboardingResponse)
async def authenticated_onboarding(
    data: OnboardingData,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Update onboarding data for authenticated user
    """

    user_id = ObjectId(current_user["id"])

    # Update user with onboarding data
    update_data = {
        "$set": {
            "profile.timezone": data.timezone,
            "profile.location": data.preferred_locations[0] if data.preferred_locations else None,
            "profile.onboarding_completed": True,

            "job_preferences": {
                "desired_positions": data.job_titles,
                "preferred_locations": data.preferred_locations,
                "remote_preference": data.work_location_preference,
                "salary_min": data.salary_min,
                "salary_max": data.salary_max,
                "salary_currency": data.salary_currency,
                "employment_types": data.work_types,
                "industries": data.industries,
                "skills": data.skills or [],
                "keywords": data.keywords or [],
                "excluded_companies": data.excluded_companies or [],
                "company_size_preferences": data.company_size_preferences or [],
                "relocation_willing": data.relocation_willing,
            },

            "onboarding": {
                "completed": True,
                "work_authorization": data.work_authorization,
                "visa_sponsorship_needed": data.visa_sponsorship_needed,
                "work_situation": data.work_situation,
                "years_of_experience": data.years_of_experience,
                "education_level": data.education_level,
                "experience_exceptional": data.experience_exceptional,
                "security_clearance": data.security_clearance,
                "veteran_status": data.veteran_status,
                "gender": data.gender,
                "ethnicity": data.ethnicity,
                "disability_status": data.disability_status,
            },

            "updated_at": datetime.utcnow(),
        }
    }

    db[Collections.USERS].update_one(
        {"_id": user_id},
        update_data
    )

    return OnboardingResponse(
        success=True,
        message="Onboarding completed successfully",
        user_id=str(user_id),
        redirect_to="/upselling"
    )


@router.get("/status")
async def get_onboarding_status(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Check if user has completed onboarding"""

    user_id = ObjectId(current_user["id"])
    user = db[Collections.USERS].find_one({"_id": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    onboarding_completed = user.get("profile", {}).get("onboarding_completed", False)

    return {
        "completed": onboarding_completed,
        "preferences": serialize_doc(user.get("job_preferences", {})),
        "redirect_to": "/dashboard" if onboarding_completed else "/onboarding"
    }


# ============================================
# STEP-BY-STEP ONBOARDING (for frontend compatibility)
# ============================================

class GuestSessionRequest(BaseModel):
    """Create guest session for step-by-step onboarding"""
    referrer: Optional[str] = ""
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class GuestSessionResponse(BaseModel):
    """Response when creating a guest session"""
    session_id: str
    created_at: str
    expires_at: str
    status: str


class StepAnswerRequest(BaseModel):
    """Save answer for a single step"""
    session_id: str
    step_id: str
    answer: dict
    time_spent_seconds: Optional[int] = 0


@router.post("/guest/create", response_model=GuestSessionResponse)
async def create_guest_session(request: GuestSessionRequest = None):
    """
    Create a new guest onboarding session (step-by-step flow)
    Returns a session ID that can be used to save answers step by step
    """
    import uuid
    from datetime import timedelta

    # Generate session ID
    session_id = str(uuid.uuid4())
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(hours=24)

    # Store session metadata (in production, use Redis or MongoDB)
    # For now, just return the session info
    return GuestSessionResponse(
        session_id=session_id,
        created_at=created_at.isoformat(),
        expires_at=expires_at.isoformat(),
        status="in_progress"
    )


@router.post("/guest/answer")
async def save_step_answer(request: StepAnswerRequest):
    """
    Save answer for a single onboarding step (step-by-step flow)
    This is stored temporarily until all steps are completed
    """
    # For now, just store in memory/cache (you can add Redis later)
    # The frontend will eventually call POST /guest with all data
    return {
        "success": True,
        "message": "Answer saved",
        "session_id": request.session_id,
        "step_id": request.step_id
    }
