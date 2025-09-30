"""
Upselling API endpoints
Handles premium features, pricing, and upselling flows
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, validator
import logging

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker
from app.services.ai_client import get_ai_client

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class PricingResponse(BaseModel):
    plans: List[Dict[str, Any]]
    current_plan: Optional[str]
    upgrade_available: bool


class UpgradeRequest(BaseModel):
    plan: str
    billing_cycle: str = "monthly"


class CompaniesToExcludeRequest(BaseModel):
    companies: List[str]


class ResumeUploadRequest(BaseModel):
    file_content: str
    file_name: str
    file_type: str


class PasswordCreateRequest(BaseModel):
    password: str
    confirm_password: str

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get pricing plans and user's current plan"""
    try:
        plans = [
            {
                "id": "free",
                "name": "Free Plan",
                "price": 0,
                "billing_cycle": "monthly",
                "features": [
                    "5 job applications per month",
                    "Basic cover letter generation",
                    "Job search with basic filters",
                    "Email support"
                ],
                "limits": {
                    "applications_per_month": 5,
                    "cover_letters_per_month": 3,
                    "ai_features": False
                }
            },
            {
                "id": "premium",
                "name": "Premium Plan",
                "price": 29.99,
                "billing_cycle": "monthly",
                "features": [
                    "Unlimited job applications",
                    "AI-powered cover letter generation",
                    "Advanced job matching",
                    "Auto-apply to jobs",
                    "Priority support",
                    "Resume optimization",
                    "Interview preparation"
                ],
                "limits": {
                    "applications_per_month": -1,  # unlimited
                    "cover_letters_per_month": -1,
                    "ai_features": True
                }
            },
            {
                "id": "enterprise",
                "name": "Enterprise Plan",
                "price": 99.99,
                "billing_cycle": "monthly",
                "features": [
                    "Everything in Premium",
                    "Custom job scraping",
                    "API access",
                    "Dedicated support",
                    "Team management",
                    "Advanced analytics"
                ],
                "limits": {
                    "applications_per_month": -1,
                    "cover_letters_per_month": -1,
                    "ai_features": True,
                    "api_access": True
                }
            }
        ]

        current_plan = "free"
        upgrade_available = True

        if current_user:
            user_plan = current_user.get("subscription_plan", "free")
            current_plan = user_plan
            upgrade_available = user_plan != "enterprise"

        return PricingResponse(
            plans=plans,
            current_plan=current_plan,
            upgrade_available=upgrade_available
        )

    except Exception as e:
        logger.error(f"Error fetching pricing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch pricing information"
        )


@router.post("/premium-upgrade")
async def premium_upgrade(
    request: UpgradeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Initiate premium plan upgrade"""
    try:
        # Check current subscription
        user_query = """
            SELECT subscription_status, subscription_plan
            FROM users
            WHERE id = :user_id
        """
        user_data = await database.fetch_one(
            query=user_query,
            values={"user_id": current_user["id"]}
        )

        if user_data and user_data["subscription_plan"] == request.plan:
            return {
                "success": False,
                "message": "You are already on this plan"
            }

        # Create upgrade request record
        upgrade_query = """
            INSERT INTO subscription_requests (
                user_id, requested_plan, billing_cycle, status, created_at
            ) VALUES (
                :user_id, :requested_plan, :billing_cycle, :status, :created_at
            ) RETURNING id
        """

        values = {
            "user_id": current_user["id"],
            "requested_plan": request.plan,
            "billing_cycle": request.billing_cycle,
            "status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await database.fetch_one(query=upgrade_query, values=values)

        return {
            "success": True,
            "message": "Upgrade request created successfully",
            "request_id": str(result["id"]),
            "next_steps": "You will be redirected to payment processing"
        }

    except Exception as e:
        logger.error(f"Error processing upgrade: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upgrade request"
        )


@router.get("/priority-access")
async def check_priority_access(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Check if user has priority access to features"""
    try:
        user_plan = current_user.get("subscription_plan", "free")
        subscription_status = current_user.get("subscription_status", "inactive")

        has_priority = user_plan in ["premium", "enterprise"] and subscription_status == "active"

        features = {
            "auto_apply": has_priority,
            "ai_cover_letters": has_priority,
            "advanced_matching": has_priority,
            "unlimited_applications": has_priority,
            "priority_support": has_priority
        }

        return {
            "has_priority_access": has_priority,
            "current_plan": user_plan,
            "features": features
        }

    except Exception as e:
        logger.error(f"Error checking priority access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check priority access"
        )


@router.post("/companies-to-exclude")
async def update_companies_to_exclude(
    request: CompaniesToExcludeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user's list of companies to exclude from applications"""
    try:
        import json

        # Update user's preferences
        update_query = """
            UPDATE profiles
            SET excluded_companies = :excluded_companies, updated_at = :updated_at
            WHERE user_id = :user_id
        """

        await database.execute(
            query=update_query,
            values={
                "excluded_companies": json.dumps(request.companies),
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Excluded companies updated successfully",
            "excluded_companies": request.companies
        }

    except Exception as e:
        logger.error(f"Error updating excluded companies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update excluded companies"
        )


@router.get("/companies-to-exclude")
async def get_companies_to_exclude(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's list of excluded companies"""
    try:
        import json

        query = """
            SELECT excluded_companies
            FROM profiles
            WHERE user_id = :user_id
        """

        result = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        excluded_companies = []
        if result and result["excluded_companies"]:
            try:
                excluded_companies = json.loads(result["excluded_companies"])
            except json.JSONDecodeError:
                excluded_companies = []

        return {
            "excluded_companies": excluded_companies
        }

    except Exception as e:
        logger.error(f"Error fetching excluded companies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch excluded companies"
        )


@router.post("/upload-resume")
async def upload_resume(
    request: ResumeUploadRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload and process user's resume"""
    try:
        import base64
        import uuid

        # Validate file type
        allowed_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if request.file_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Please upload PDF or Word document."
            )

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
        }.get(request.file_type, '.pdf')

        stored_filename = f"{file_id}{file_extension}"

        # Store resume in database
        resume_query = """
            INSERT INTO resumes (
                user_id, original_filename, stored_filename, file_content,
                file_type, file_size, uploaded_at, status
            ) VALUES (
                :user_id, :original_filename, :stored_filename, :file_content,
                :file_type, :file_size, :uploaded_at, :status
            ) RETURNING id
        """

        # Decode base64 content to get file size
        file_content_bytes = base64.b64decode(request.file_content)
        file_size = len(file_content_bytes)

        values = {
            "user_id": current_user["id"],
            "original_filename": request.file_name,
            "stored_filename": stored_filename,
            "file_content": request.file_content,
            "file_type": request.file_type,
            "file_size": file_size,
            "uploaded_at": datetime.utcnow(),
            "status": "active"
        }

        result = await database.fetch_one(query=resume_query, values=values)

        # Update profile to mark resume as uploaded
        profile_query = """
            UPDATE profiles
            SET resume_uploaded = true, current_resume_id = :resume_id, updated_at = :updated_at
            WHERE user_id = :user_id
        """

        await database.execute(
            query=profile_query,
            values={
                "resume_id": result["id"],
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Resume uploaded successfully",
            "resume_id": str(result["id"]),
            "filename": request.file_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload resume"
        )


@router.post("/create-password")
async def create_password(
    request: PasswordCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create/update user password"""
    try:
        from app.core.security import hash_password

        # Validate password strength
        if len(request.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )

        # Hash the password
        hashed_password = hash_password(request.password)

        # Update user password
        update_query = """
            UPDATE users
            SET password_hash = :password_hash, updated_at = :updated_at
            WHERE id = :user_id
        """

        await database.execute(
            query=update_query,
            values={
                "password_hash": hashed_password,
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Password updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create password"
        )


@router.get("/progress")
async def get_user_progress(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's application and profile progress"""
    try:
        # Get application stats
        app_stats_query = """
            SELECT
                COUNT(*) as total_applications,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_applications,
                COUNT(CASE WHEN status = 'applied' THEN 1 END) as applied_applications,
                COUNT(CASE WHEN status = 'interview' THEN 1 END) as interview_applications,
                COUNT(CASE WHEN status = 'offer' THEN 1 END) as offer_applications,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_applications
            FROM applications
            WHERE user_id = :user_id
        """

        app_stats = await database.fetch_one(
            query=app_stats_query,
            values={"user_id": current_user["id"]}
        )

        # Get profile completion
        profile_query = """
            SELECT *
            FROM profiles
            WHERE user_id = :user_id
        """

        profile = await database.fetch_one(
            query=profile_query,
            values={"user_id": current_user["id"]}
        )

        # Calculate profile completion
        profile_completion = 0
        if profile:
            completion_fields = [
                profile.get("full_name"),
                profile.get("phone_number"),
                profile.get("job_title"),
                profile.get("years_experience"),
                profile.get("desired_salary"),
                profile.get("work_type"),
                profile.get("location_preferences"),
                profile.get("education_level"),
                profile.get("resume_uploaded"),
                profile.get("work_authorization")
            ]

            completed = sum(1 for field in completion_fields if field is not None and field != "")
            profile_completion = round((completed / len(completion_fields)) * 100)

        return {
            "application_stats": dict(app_stats) if app_stats else {},
            "profile_completion": profile_completion,
            "subscription_status": current_user.get("subscription_status", "inactive"),
            "subscription_plan": current_user.get("subscription_plan", "free")
        }

    except Exception as e:
        logger.error(f"Error fetching user progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user progress"
        )


@router.post("/resume-customization")
async def customize_resume(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """AI-powered resume customization suggestions"""
    try:
        if not permission_checker.has_permission(current_user, "ai_features", "use"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required for AI resume customization"
            )

        # Get user's current resume
        resume_query = """
            SELECT file_content, original_filename
            FROM resumes
            WHERE user_id = :user_id AND status = 'active'
            ORDER BY uploaded_at DESC
            LIMIT 1
        """

        resume = await database.fetch_one(
            query=resume_query,
            values={"user_id": current_user["id"]}
        )

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No resume found. Please upload a resume first."
            )

        # Get user's recent job applications to understand target roles
        jobs_query = """
            SELECT j.title, j.description, j.requirements
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.user_id = :user_id
            ORDER BY a.created_at DESC
            LIMIT 5
        """

        recent_jobs = await database.fetch_all(
            query=jobs_query,
            values={"user_id": current_user["id"]}
        )

        # Use AI to generate customization suggestions
        ai_client = get_ai_client()

        job_context = ""
        if recent_jobs:
            job_context = "\n".join([
                f"- {job['title']}: {job['description'][:200]}..."
                for job in recent_jobs
            ])

        prompt = f"""Analyze the uploaded resume and provide customization suggestions based on the user's recent job applications.

Recent target roles:
{job_context}

Please provide:
1. Key skills to highlight
2. Experience sections to emphasize
3. Keywords to include
4. Sections that could be improved
5. Industry-specific recommendations

Focus on making the resume more relevant to the target roles while maintaining accuracy."""

        suggestions = await ai_client.generate_text(prompt)

        return {
            "success": True,
            "suggestions": suggestions,
            "target_roles_analyzed": len(recent_jobs),
            "resume_filename": resume["original_filename"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error customizing resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate resume customization suggestions"
        )