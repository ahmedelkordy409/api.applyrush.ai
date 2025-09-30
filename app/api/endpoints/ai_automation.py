"""
AI automation API endpoints
Handles AI-powered features like cover letter generation, resume optimization, and auto-apply
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import logging

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker
from app.services.ai.cover_letter_generator import generate_cover_letter
from app.services.ai.resume_optimizer import optimize_resume
from app.services.auto_apply import AutoApplyService

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()
auto_apply_service = AutoApplyService()


class CoverLetterRequest(BaseModel):
    job_id: str
    job_title: str
    company: str
    job_description: str
    personalization_level: str = "moderate"  # basic, moderate, high


class CoverLetterResponse(BaseModel):
    cover_letter: str
    personalization_level: str
    generated_at: datetime
    ai_model_used: str


class ResumeOptimizationRequest(BaseModel):
    job_description: str
    target_keywords: Optional[List[str]] = None


class ResumeOptimizationResponse(BaseModel):
    optimized_resume_text: str
    ats_score: int
    improvements: List[str]
    matched_keywords: List[str]
    missing_keywords: List[str]


class AutoApplyRuleRequest(BaseModel):
    name: str
    enabled: bool = True
    keywords: List[str] = []
    excluded_keywords: List[str] = []
    job_types: List[str] = ["full-time"]
    locations: List[str] = []
    remote_only: bool = False
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    daily_application_limit: int = 10
    weekly_application_limit: int = 50
    ai_cover_letter: bool = True


class AutoApplyRuleResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    keywords: List[str]
    excluded_keywords: List[str]
    job_types: List[str]
    locations: List[str]
    remote_only: bool
    salary_min: Optional[int]
    salary_max: Optional[int]
    daily_application_limit: int
    weekly_application_limit: int
    ai_cover_letter: bool
    created_at: datetime
    updated_at: datetime


@router.post("/generate-cover-letter", response_model=CoverLetterResponse)
async def generate_ai_cover_letter(
    request: CoverLetterRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate AI-powered cover letter for a specific job"""
    try:
        if not permission_checker.has_permission(current_user, "cover_letters", "generate"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to generate cover letters"
            )

        # Get user profile for personalization
        profile_query = """
            SELECT * FROM profiles WHERE user_id = :user_id
        """
        profile = await database.fetch_one(
            query=profile_query,
            values={"user_id": current_user["id"]}
        )

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Please complete your profile first."
            )

        # Generate cover letter using AI service
        cover_letter_data = await generate_cover_letter(
            user_profile=dict(profile),
            job_title=request.job_title,
            company=request.company,
            job_description=request.job_description,
            personalization_level=request.personalization_level
        )

        # Save generated cover letter
        save_query = """
            INSERT INTO cover_letters (
                user_id, job_id, title, content, ai_generated,
                personalization_level, created_at, updated_at
            ) VALUES (
                :user_id, :job_id, :title, :content, :ai_generated,
                :personalization_level, :created_at, :updated_at
            ) RETURNING id
        """

        await database.execute(
            query=save_query,
            values={
                "user_id": current_user["id"],
                "job_id": request.job_id,
                "title": f"Cover Letter - {request.company} {request.job_title}",
                "content": cover_letter_data["cover_letter"],
                "ai_generated": True,
                "personalization_level": request.personalization_level,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )

        return CoverLetterResponse(
            cover_letter=cover_letter_data["cover_letter"],
            personalization_level=request.personalization_level,
            generated_at=datetime.utcnow(),
            ai_model_used=cover_letter_data.get("model_used", "gpt-4")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cover letter"
        )


@router.post("/optimize-resume", response_model=ResumeOptimizationResponse)
async def optimize_user_resume(
    request: ResumeOptimizationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Optimize user's resume for a specific job description"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to optimize resume"
            )

        # Get user's current resume
        resume_query = """
            SELECT * FROM resumes
            WHERE user_id = :user_id AND is_default = true
            ORDER BY created_at DESC
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

        # Optimize resume using AI service
        optimization_result = await optimize_resume(
            resume_text=resume["extracted_text"],
            job_description=request.job_description,
            target_keywords=request.target_keywords
        )

        # Update resume with optimization results
        update_query = """
            UPDATE resumes
            SET ats_score = :ats_score,
                improvements_suggested = :improvements,
                updated_at = :updated_at
            WHERE id = :resume_id
        """

        await database.execute(
            query=update_query,
            values={
                "ats_score": optimization_result["ats_score"],
                "improvements": optimization_result["improvements"],
                "updated_at": datetime.utcnow(),
                "resume_id": resume["id"]
            }
        )

        return ResumeOptimizationResponse(**optimization_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize resume"
        )


@router.post("/auto-apply/rules", response_model=AutoApplyRuleResponse)
async def create_auto_apply_rule(
    rule: AutoApplyRuleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new auto-apply rule"""
    try:
        if not permission_checker.has_permission(current_user, "auto_apply", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create auto-apply rules"
            )

        # Check subscription status for auto-apply feature
        if current_user.get("subscription_status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Auto-apply feature requires an active subscription"
            )

        # Create auto-apply rule
        insert_query = """
            INSERT INTO auto_apply_rules (
                user_id, name, enabled, keywords, excluded_keywords, job_types,
                locations, remote_only, salary_min, salary_max,
                daily_application_limit, weekly_application_limit,
                ai_cover_letter, created_at, updated_at
            ) VALUES (
                :user_id, :name, :enabled, :keywords, :excluded_keywords, :job_types,
                :locations, :remote_only, :salary_min, :salary_max,
                :daily_application_limit, :weekly_application_limit,
                :ai_cover_letter, :created_at, :updated_at
            ) RETURNING *
        """

        new_rule = await database.fetch_one(
            query=insert_query,
            values={
                "user_id": current_user["id"],
                "name": rule.name,
                "enabled": rule.enabled,
                "keywords": rule.keywords,
                "excluded_keywords": rule.excluded_keywords,
                "job_types": rule.job_types,
                "locations": rule.locations,
                "remote_only": rule.remote_only,
                "salary_min": rule.salary_min,
                "salary_max": rule.salary_max,
                "daily_application_limit": rule.daily_application_limit,
                "weekly_application_limit": rule.weekly_application_limit,
                "ai_cover_letter": rule.ai_cover_letter,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )

        rule_dict = dict(new_rule)
        return AutoApplyRuleResponse(
            id=str(rule_dict["id"]),
            name=rule_dict["name"],
            enabled=rule_dict["enabled"],
            keywords=rule_dict["keywords"],
            excluded_keywords=rule_dict["excluded_keywords"],
            job_types=rule_dict["job_types"],
            locations=rule_dict["locations"],
            remote_only=rule_dict["remote_only"],
            salary_min=rule_dict["salary_min"],
            salary_max=rule_dict["salary_max"],
            daily_application_limit=rule_dict["daily_application_limit"],
            weekly_application_limit=rule_dict["weekly_application_limit"],
            ai_cover_letter=rule_dict["ai_cover_letter"],
            created_at=rule_dict["created_at"],
            updated_at=rule_dict["updated_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating auto-apply rule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create auto-apply rule"
        )


@router.get("/auto-apply/rules", response_model=List[AutoApplyRuleResponse])
async def get_auto_apply_rules(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's auto-apply rules"""
    try:
        query = """
            SELECT * FROM auto_apply_rules
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """
        rules = await database.fetch_all(
            query=query,
            values={"user_id": current_user["id"]}
        )

        return [
            AutoApplyRuleResponse(
                id=str(rule["id"]),
                name=rule["name"],
                enabled=rule["enabled"],
                keywords=rule["keywords"],
                excluded_keywords=rule["excluded_keywords"],
                job_types=rule["job_types"],
                locations=rule["locations"],
                remote_only=rule["remote_only"],
                salary_min=rule["salary_min"],
                salary_max=rule["salary_max"],
                daily_application_limit=rule["daily_application_limit"],
                weekly_application_limit=rule["weekly_application_limit"],
                ai_cover_letter=rule["ai_cover_letter"],
                created_at=rule["created_at"],
                updated_at=rule["updated_at"]
            )
            for rule in rules
        ]

    except Exception as e:
        logger.error(f"Error getting auto-apply rules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get auto-apply rules"
        )


@router.put("/auto-apply/rules/{rule_id}", response_model=AutoApplyRuleResponse)
async def update_auto_apply_rule(
    rule_id: str,
    rule_update: AutoApplyRuleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update an auto-apply rule"""
    try:
        if not permission_checker.has_permission(current_user, "auto_apply", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update auto-apply rules"
            )

        # Check if rule exists and belongs to user
        check_query = """
            SELECT id FROM auto_apply_rules
            WHERE id = :rule_id AND user_id = :user_id
        """
        existing_rule = await database.fetch_one(
            query=check_query,
            values={"rule_id": rule_id, "user_id": current_user["id"]}
        )

        if not existing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auto-apply rule not found"
            )

        # Update rule
        update_query = """
            UPDATE auto_apply_rules
            SET name = :name, enabled = :enabled, keywords = :keywords,
                excluded_keywords = :excluded_keywords, job_types = :job_types,
                locations = :locations, remote_only = :remote_only,
                salary_min = :salary_min, salary_max = :salary_max,
                daily_application_limit = :daily_application_limit,
                weekly_application_limit = :weekly_application_limit,
                ai_cover_letter = :ai_cover_letter, updated_at = :updated_at
            WHERE id = :rule_id
            RETURNING *
        """

        updated_rule = await database.fetch_one(
            query=update_query,
            values={
                "rule_id": rule_id,
                "name": rule_update.name,
                "enabled": rule_update.enabled,
                "keywords": rule_update.keywords,
                "excluded_keywords": rule_update.excluded_keywords,
                "job_types": rule_update.job_types,
                "locations": rule_update.locations,
                "remote_only": rule_update.remote_only,
                "salary_min": rule_update.salary_min,
                "salary_max": rule_update.salary_max,
                "daily_application_limit": rule_update.daily_application_limit,
                "weekly_application_limit": rule_update.weekly_application_limit,
                "ai_cover_letter": rule_update.ai_cover_letter,
                "updated_at": datetime.utcnow()
            }
        )

        rule_dict = dict(updated_rule)
        return AutoApplyRuleResponse(
            id=str(rule_dict["id"]),
            name=rule_dict["name"],
            enabled=rule_dict["enabled"],
            keywords=rule_dict["keywords"],
            excluded_keywords=rule_dict["excluded_keywords"],
            job_types=rule_dict["job_types"],
            locations=rule_dict["locations"],
            remote_only=rule_dict["remote_only"],
            salary_min=rule_dict["salary_min"],
            salary_max=rule_dict["salary_max"],
            daily_application_limit=rule_dict["daily_application_limit"],
            weekly_application_limit=rule_dict["weekly_application_limit"],
            ai_cover_letter=rule_dict["ai_cover_letter"],
            created_at=rule_dict["created_at"],
            updated_at=rule_dict["updated_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating auto-apply rule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update auto-apply rule"
        )


@router.delete("/auto-apply/rules/{rule_id}")
async def delete_auto_apply_rule(
    rule_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete an auto-apply rule"""
    try:
        if not permission_checker.has_permission(current_user, "auto_apply", "delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete auto-apply rules"
            )

        # Check if rule exists and belongs to user
        check_query = """
            SELECT id FROM auto_apply_rules
            WHERE id = :rule_id AND user_id = :user_id
        """
        existing_rule = await database.fetch_one(
            query=check_query,
            values={"rule_id": rule_id, "user_id": current_user["id"]}
        )

        if not existing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auto-apply rule not found"
            )

        # Delete rule
        delete_query = "DELETE FROM auto_apply_rules WHERE id = :rule_id"
        await database.execute(query=delete_query, values={"rule_id": rule_id})

        return {"success": True, "message": "Auto-apply rule deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting auto-apply rule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete auto-apply rule"
        )


@router.post("/auto-apply/trigger")
async def trigger_auto_apply(
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger auto-apply process for user"""
    try:
        if not permission_checker.has_permission(current_user, "auto_apply", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to trigger auto-apply"
            )

        # Check subscription status
        if current_user.get("subscription_status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Auto-apply feature requires an active subscription"
            )

        # Add background task to process auto-apply
        background_tasks.add_task(
            auto_apply_service.process_user_auto_apply,
            current_user["id"]
        )

        return {
            "success": True,
            "message": "Auto-apply process triggered successfully",
            "user_id": current_user["id"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering auto-apply: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger auto-apply"
        )


# Placeholder AI service functions (these would be implemented separately)
async def generate_cover_letter(user_profile: dict, job_title: str, company: str, job_description: str, personalization_level: str) -> dict:
    """Placeholder for AI cover letter generation"""
    return {
        "cover_letter": f"Dear Hiring Manager at {company},\n\nI am writing to express my interest in the {job_title} position...",
        "model_used": "gpt-4"
    }


async def optimize_resume(resume_text: str, job_description: str, target_keywords: List[str] = None) -> dict:
    """Placeholder for AI resume optimization"""
    return {
        "optimized_resume_text": resume_text,
        "ats_score": 85,
        "improvements": ["Add more relevant keywords", "Improve formatting"],
        "matched_keywords": ["Python", "React", "FastAPI"],
        "missing_keywords": ["Docker", "Kubernetes"]
    }


# Placeholder auto-apply service
class AutoApplyService:
    async def process_user_auto_apply(self, user_id: str):
        """Placeholder for auto-apply processing"""
        logger.info(f"Processing auto-apply for user {user_id}")
        # This would implement the actual auto-apply logic