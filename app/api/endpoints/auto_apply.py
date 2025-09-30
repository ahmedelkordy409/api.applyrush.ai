"""
Auto Apply API endpoints
Handles automated job application features
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker
from app.workers.application_tasks import queue_auto_apply_job

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
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Apply to multiple jobs automatically"""
    try:
        # Check if user has premium access
        if not permission_checker.has_permission(current_user, "auto_apply", "use"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required for auto-apply feature"
            )

        # Check readiness
        readiness = await check_auto_apply_readiness(current_user)
        if not readiness["ready"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not ready for auto-apply: {', '.join(readiness['missing_requirements'])}"
            )

        # Validate job IDs exist and user hasn't already applied
        valid_jobs = []
        for job_id in request.job_ids:
            # Check if job exists and is active
            job_query = """
                SELECT id, title, company_id, external_id
                FROM jobs
                WHERE external_id = :job_id AND is_active = true
            """
            job = await database.fetch_one(query=job_query, values={"job_id": job_id})

            if not job:
                logger.warning(f"Job {job_id} not found or inactive")
                continue

            # Check if user already applied
            app_query = """
                SELECT id FROM applications
                WHERE user_id = :user_id AND job_id = :job_id
            """
            existing = await database.fetch_one(
                query=app_query,
                values={"user_id": current_user["id"], "job_id": job["id"]}
            )

            if existing:
                logger.warning(f"User already applied to job {job_id}")
                continue

            valid_jobs.append(job)

        if not valid_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid jobs found to apply to"
            )

        # Queue auto-apply tasks
        task_ids = []
        for job in valid_jobs:
            if request.apply_immediately:
                # Apply immediately
                task = queue_auto_apply_job.delay(
                    user_id=current_user["id"],
                    job_id=str(job["id"]),
                    use_ai_cover_letter=request.use_ai_cover_letter,
                    custom_message=request.custom_message
                )
                task_ids.append(task.id)
            else:
                # Schedule for later
                task = queue_auto_apply_job.apply_async(
                    args=[
                        current_user["id"],
                        str(job["id"]),
                        request.use_ai_cover_letter,
                        request.custom_message
                    ],
                    eta=datetime.utcnow() + timedelta(minutes=5)  # Schedule 5 minutes later
                )
                task_ids.append(task.id)

        # Log auto-apply session
        await log_auto_apply_session(
            current_user["id"],
            len(valid_jobs),
            request.use_ai_cover_letter,
            task_ids
        )

        return {
            "success": True,
            "jobs_queued": len(valid_jobs),
            "task_ids": task_ids,
            "message": f"Auto-apply queued for {len(valid_jobs)} jobs"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auto-apply: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue auto-apply jobs"
        )


@router.post("/queue")
async def queue_auto_apply_batch(
    request: AutoApplyQueueRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Queue auto-apply for jobs matching search criteria"""
    try:
        # Check premium access
        if not permission_checker.has_permission(current_user, "auto_apply", "use"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required for auto-apply feature"
            )

        # Search for matching jobs
        search_query = """
            SELECT id, external_id, title, company_id
            FROM jobs
            WHERE is_active = true
        """

        query_params = {}
        conditions = []

        # Apply search criteria
        criteria = request.search_criteria

        if criteria.get("keywords"):
            conditions.append("(title ILIKE :keywords OR description ILIKE :keywords)")
            query_params["keywords"] = f"%{criteria['keywords']}%"

        if criteria.get("location"):
            conditions.append("location->>'city' ILIKE :location OR location->>'state' ILIKE :location")
            query_params["location"] = f"%{criteria['location']}%"

        if criteria.get("employment_type"):
            conditions.append("employment_type = :employment_type")
            query_params["employment_type"] = criteria["employment_type"]

        if criteria.get("remote_only"):
            conditions.append("remote_option = 'yes'")

        if criteria.get("salary_min"):
            conditions.append("salary_min >= :salary_min")
            query_params["salary_min"] = criteria["salary_min"]

        # Exclude jobs user has already applied to
        conditions.append("""
            id NOT IN (
                SELECT job_id FROM applications WHERE user_id = :user_id
            )
        """)
        query_params["user_id"] = current_user["id"]

        if conditions:
            search_query += " AND " + " AND ".join(conditions)

        search_query += f" ORDER BY posted_date DESC LIMIT {request.max_applications}"

        matching_jobs = await database.fetch_all(query=search_query, values=query_params)

        if not matching_jobs:
            return {
                "success": True,
                "jobs_queued": 0,
                "message": "No matching jobs found"
            }

        # Queue applications based on schedule type
        task_ids = []
        for i, job in enumerate(matching_jobs):
            delay_minutes = 0

            if request.schedule_type == "daily":
                # Spread applications throughout the day
                delay_minutes = i * 60  # 1 hour between each application
            elif request.schedule_type == "weekly":
                # Spread applications throughout the week
                delay_minutes = i * 24 * 60  # 1 day between each application

            if delay_minutes > 0:
                eta = datetime.utcnow() + timedelta(minutes=delay_minutes)
                task = queue_auto_apply_job.apply_async(
                    args=[
                        current_user["id"],
                        str(job["id"]),
                        request.auto_generate_cover_letters,
                        None
                    ],
                    eta=eta
                )
            else:
                task = queue_auto_apply_job.delay(
                    user_id=current_user["id"],
                    job_id=str(job["id"]),
                    use_ai_cover_letter=request.auto_generate_cover_letters,
                    custom_message=None
                )

            task_ids.append(task.id)

        # Save auto-apply queue settings
        await save_auto_apply_queue(
            current_user["id"],
            request.search_criteria,
            request.schedule_type,
            len(matching_jobs),
            task_ids
        )

        return {
            "success": True,
            "jobs_queued": len(matching_jobs),
            "schedule_type": request.schedule_type,
            "task_ids": task_ids,
            "message": f"Auto-apply queued for {len(matching_jobs)} jobs"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing auto-apply batch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue auto-apply batch"
        )


@router.get("/readiness", response_model=ReadinessCheckResponse)
async def check_auto_apply_readiness(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Check if user is ready for auto-apply"""
    try:
        missing_requirements = []
        suggestions = []

        # Check if user has a resume
        resume_query = """
            SELECT id FROM resumes
            WHERE user_id = :user_id AND status = 'active'
        """
        resume = await database.fetch_one(
            query=resume_query,
            values={"user_id": current_user["id"]}
        )

        if not resume:
            missing_requirements.append("Resume upload required")
            suggestions.append("Upload your resume to enable auto-apply")

        # Check profile completion
        profile_query = """
            SELECT full_name, phone_number, job_title, years_experience,
                   work_type, location_preferences, education_level
            FROM profiles
            WHERE user_id = :user_id
        """
        profile = await database.fetch_one(
            query=profile_query,
            values={"user_id": current_user["id"]}
        )

        profile_completion = 0
        if profile:
            completion_fields = [
                profile.get("full_name"),
                profile.get("phone_number"),
                profile.get("job_title"),
                profile.get("years_experience"),
                profile.get("work_type"),
                profile.get("location_preferences"),
                profile.get("education_level")
            ]

            completed = sum(1 for field in completion_fields if field is not None and field != "")
            profile_completion = round((completed / len(completion_fields)) * 100)

            if profile_completion < 70:
                missing_requirements.append("Profile completion below 70%")
                suggestions.append("Complete your profile for better job matching")

        # Check subscription status
        if current_user.get("subscription_plan") == "free":
            missing_requirements.append("Premium subscription required")
            suggestions.append("Upgrade to premium for auto-apply feature")

        # Check for recent failed applications
        failed_query = """
            SELECT COUNT(*) as failed_count
            FROM applications
            WHERE user_id = :user_id AND status = 'failed'
              AND created_at >= :since_date
        """

        since_date = datetime.utcnow() - timedelta(days=7)
        failed_result = await database.fetch_one(
            query=failed_query,
            values={"user_id": current_user["id"], "since_date": since_date}
        )

        failed_count = failed_result["failed_count"] if failed_result else 0
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
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get current auto-apply status and queued applications"""
    try:
        # Get active auto-apply sessions
        session_query = """
            SELECT id, jobs_queued, created_at, status
            FROM auto_apply_sessions
            WHERE user_id = :user_id AND status IN ('active', 'pending')
            ORDER BY created_at DESC
            LIMIT 5
        """

        sessions = await database.fetch_all(
            query=session_query,
            values={"user_id": current_user["id"]}
        )

        # Get recent auto-applied jobs
        recent_query = """
            SELECT a.id, a.status, a.applied_at, j.title, j.company_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.user_id = :user_id AND a.ai_auto_applied = true
            ORDER BY a.applied_at DESC
            LIMIT 10
        """

        recent_applications = await database.fetch_all(
            query=recent_query,
            values={"user_id": current_user["id"]}
        )

        # Get statistics
        stats_query = """
            SELECT
                COUNT(*) as total_auto_applied,
                COUNT(CASE WHEN status = 'applied' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN applied_at >= :since_date THEN 1 END) as recent_7d
            FROM applications
            WHERE user_id = :user_id AND ai_auto_applied = true
        """

        since_date = datetime.utcnow() - timedelta(days=7)
        stats = await database.fetch_one(
            query=stats_query,
            values={"user_id": current_user["id"], "since_date": since_date}
        )

        return {
            "active_sessions": [dict(session) for session in sessions],
            "recent_applications": [dict(app) for app in recent_applications],
            "statistics": dict(stats) if stats else {},
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
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cancel an active auto-apply session"""
    try:
        # Check if session exists and belongs to user
        session_query = """
            SELECT id, status FROM auto_apply_sessions
            WHERE id = :session_id AND user_id = :user_id
        """

        session = await database.fetch_one(
            query=session_query,
            values={"session_id": session_id, "user_id": current_user["id"]}
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auto-apply session not found"
            )

        if session["status"] not in ["active", "pending"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session cannot be canceled"
            )

        # Update session status
        update_query = """
            UPDATE auto_apply_sessions
            SET status = 'canceled', updated_at = :updated_at
            WHERE id = :session_id
        """

        await database.execute(
            query=update_query,
            values={"updated_at": datetime.utcnow(), "session_id": session_id}
        )

        # TODO: Cancel pending Celery tasks
        # This would require storing task IDs and calling task.revoke()

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
    user_id: str,
    jobs_queued: int,
    use_ai_cover_letter: bool,
    task_ids: List[str]
):
    """Log auto-apply session to database"""
    try:
        import json

        insert_query = """
            INSERT INTO auto_apply_sessions (
                user_id, jobs_queued, use_ai_cover_letter, task_ids, status, created_at
            ) VALUES (
                :user_id, :jobs_queued, :use_ai_cover_letter, :task_ids, :status, :created_at
            )
        """

        await database.execute(
            query=insert_query,
            values={
                "user_id": user_id,
                "jobs_queued": jobs_queued,
                "use_ai_cover_letter": use_ai_cover_letter,
                "task_ids": json.dumps(task_ids),
                "status": "active",
                "created_at": datetime.utcnow()
            }
        )

    except Exception as e:
        logger.error(f"Error logging auto-apply session: {str(e)}")


async def save_auto_apply_queue(
    user_id: str,
    search_criteria: Dict[str, Any],
    schedule_type: str,
    jobs_count: int,
    task_ids: List[str]
):
    """Save auto-apply queue configuration"""
    try:
        import json

        insert_query = """
            INSERT INTO auto_apply_queues (
                user_id, search_criteria, schedule_type, jobs_count, task_ids, created_at
            ) VALUES (
                :user_id, :search_criteria, :schedule_type, :jobs_count, :task_ids, :created_at
            )
        """

        await database.execute(
            query=insert_query,
            values={
                "user_id": user_id,
                "search_criteria": json.dumps(search_criteria),
                "schedule_type": schedule_type,
                "jobs_count": jobs_count,
                "task_ids": json.dumps(task_ids),
                "created_at": datetime.utcnow()
            }
        )

    except Exception as e:
        logger.error(f"Error saving auto-apply queue: {str(e)}")