"""
Auto Apply API endpoints - MongoDB Version
Handles automated job application features
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from bson import ObjectId
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user
from app.core.security import PermissionChecker

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class AutoApplyRequest(BaseModel):
    job_ids: List[str]
    use_ai_cover_letter: bool = True
    custom_message: Optional[str] = None
    apply_immediately: bool = False


class AutoApplyQueueRequest(BaseModel):
    search_criteria: Dict[str, Any]
    max_applications: int = 10
    schedule_type: str = "immediate"  # immediate, daily, weekly
    auto_generate_cover_letters: bool = True


class ReadinessCheckResponse(BaseModel):
    ready: bool
    missing_requirements: List[str]
    profile_completion: int
    suggestions: List[str]


@router.post("/")
async def auto_apply_to_jobs(
    request: AutoApplyRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Apply to multiple jobs automatically"""
    try:
        user_id = current_user["id"]

        # Check if user has premium access
        if not permission_checker.has_permission(current_user, "auto_apply", "use"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required for auto-apply feature"
            )

        # Check readiness
        readiness = await check_auto_apply_readiness(current_user, db)
        if not readiness["ready"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not ready for auto-apply: {', '.join(readiness['missing_requirements'])}"
            )

        # Validate job IDs exist and user hasn't already applied
        valid_jobs = []
        for job_id in request.job_ids:
            # Check if job exists in applications (matched jobs)
            job = await db.applications.find_one({
                "job.id": job_id,
                "status": "matched"
            })

            if not job:
                logger.warning(f"Job {job_id} not found or not matched")
                continue

            # Check if user already applied
            existing = await db.applications.find_one({
                "user_id": user_id,
                "job.id": job_id,
                "status": {"$in": ["applied", "pending", "completed"]}
            })

            if existing:
                logger.warning(f"User already applied to job {job_id}")
                continue

            valid_jobs.append(job)

        if not valid_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid jobs found to apply to"
            )

        # Update application status to pending (queued for auto-apply)
        applied_jobs = []
        for job in valid_jobs:
            # Update application status
            result = await db.applications.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "status": "pending",
                        "auto_apply_enabled": True,
                        "use_ai_cover_letter": request.use_ai_cover_letter,
                        "custom_message": request.custom_message,
                        "queued_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.modified_count > 0:
                applied_jobs.append({
                    "job_id": job["job"]["id"],
                    "title": job["job"].get("title", "Unknown"),
                    "company": job["job"].get("company", "Unknown")
                })

        # Log auto-apply session
        await log_auto_apply_session(
            db,
            user_id,
            len(applied_jobs),
            request.use_ai_cover_letter
        )

        return {
            "success": True,
            "jobs_queued": len(applied_jobs),
            "jobs": applied_jobs,
            "message": f"Auto-apply queued for {len(applied_jobs)} jobs"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auto-apply: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue auto-apply jobs"
        )




@router.get("/readiness", response_model=ReadinessCheckResponse)
async def check_auto_apply_readiness(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Check if user is ready for auto-apply"""
    try:
        user_id = current_user["id"]
        missing_requirements = []
        suggestions = []

        # Check if user has a resume
        resume = await db.resumes.find_one({
            "user_id": user_id,
            "is_active": True
        })

        if not resume:
            missing_requirements.append("Resume upload required")
            suggestions.append("Upload your resume to enable auto-apply")

        # Get user data for profile check
        user = await db.users.find_one({"_id": ObjectId(user_id)})

        profile_completion = 0
        if user:
            profile = user.get("profile", {})
            completion_fields = [
                user.get("full_name"),
                user.get("phone_number"),
                profile.get("desired_roles"),
                profile.get("years_experience"),
                profile.get("desired_locations"),
                profile.get("desired_salary_min")
            ]

            completed = sum(1 for field in completion_fields if field is not None and field != "" and field != [])
            profile_completion = round((completed / len(completion_fields)) * 100)

            if profile_completion < 70:
                missing_requirements.append("Profile completion below 70%")
                suggestions.append("Complete your profile for better job matching")

        # Check subscription status
        subscription_plan = user.get("subscription_plan", "free") if user else "free"
        if subscription_plan == "free":
            missing_requirements.append("Premium subscription required")
            suggestions.append("Upgrade to premium for auto-apply feature")

        # Check for recent failed applications
        since_date = datetime.utcnow() - timedelta(days=7)
        failed_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": "failed",
            "created_at": {"$gte": since_date}
        })

        if failed_count > 5:
            suggestions.append("Review recent failed applications before continuing")

        ready = len(missing_requirements) == 0

        return ReadinessCheckResponse(
            ready=ready,
            missing_requirements=missing_requirements,
            profile_completion=profile_completion,
            suggestions=suggestions
        )

    except Exception as e:
        logger.error(f"Error checking auto-apply readiness: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check auto-apply readiness"
        )


@router.get("/status")
async def get_auto_apply_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Get current auto-apply status and queued applications"""
    try:
        user_id = current_user["id"]

        # Get active auto-apply sessions
        sessions = await db.auto_apply_sessions.find({
            "user_id": user_id,
            "status": {"$in": ["active", "pending"]}
        }).sort("created_at", -1).limit(5).to_list(5)

        # Get recent auto-applied jobs
        recent_applications = await db.applications.find({
            "user_id": user_id,
            "auto_apply_enabled": True
        }).sort("updated_at", -1).limit(10).to_list(10)

        # Get statistics
        since_date = datetime.utcnow() - timedelta(days=7)

        total_auto_applied = await db.applications.count_documents({
            "user_id": user_id,
            "auto_apply_enabled": True
        })

        successful = await db.applications.count_documents({
            "user_id": user_id,
            "auto_apply_enabled": True,
            "status": "applied"
        })

        failed = await db.applications.count_documents({
            "user_id": user_id,
            "auto_apply_enabled": True,
            "status": "failed"
        })

        recent_7d = await db.applications.count_documents({
            "user_id": user_id,
            "auto_apply_enabled": True,
            "updated_at": {"$gte": since_date}
        })

        # Format sessions and applications for response
        formatted_sessions = []
        for session in sessions:
            session["_id"] = str(session["_id"])
            formatted_sessions.append(session)

        formatted_applications = []
        for app in recent_applications:
            formatted_applications.append({
                "id": str(app["_id"]),
                "status": app.get("status"),
                "updated_at": app.get("updated_at"),
                "job": app.get("job", {})
            })

        return {
            "success": True,
            "active_sessions": formatted_sessions,
            "recent_applications": formatted_applications,
            "statistics": {
                "total_auto_applied": total_auto_applied,
                "successful": successful,
                "failed": failed,
                "recent_7d": recent_7d
            },
            "last_updated": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error getting auto-apply status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get auto-apply status"
        )


@router.delete("/cancel/{session_id}")
async def cancel_auto_apply_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Cancel an active auto-apply session"""
    try:
        user_id = current_user["id"]

        # Check if session exists and belongs to user
        session = await db.auto_apply_sessions.find_one({
            "_id": ObjectId(session_id),
            "user_id": user_id
        })

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auto-apply session not found"
            )

        if session.get("status") not in ["active", "pending"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session cannot be canceled"
            )

        # Update session status
        await db.auto_apply_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "status": "canceled",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Update all pending applications from this session back to matched
        await db.applications.update_many(
            {
                "user_id": user_id,
                "status": "pending",
                "auto_apply_enabled": True,
                "queued_at": {"$gte": session.get("created_at", datetime.utcnow())}
            },
            {
                "$set": {
                    "status": "matched",
                    "auto_apply_enabled": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "success": True,
            "message": "Auto-apply session canceled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling auto-apply session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel auto-apply session"
        )


async def log_auto_apply_session(
    db,
    user_id: str,
    jobs_queued: int,
    use_ai_cover_letter: bool
):
    """Log auto-apply session to database"""
    try:
        session_data = {
            "user_id": user_id,
            "jobs_queued": jobs_queued,
            "use_ai_cover_letter": use_ai_cover_letter,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await db.auto_apply_sessions.insert_one(session_data)
        logger.info(f"Logged auto-apply session for user {user_id}: {jobs_queued} jobs")

    except Exception as e:
        logger.error(f"Error logging auto-apply session: {str(e)}")


