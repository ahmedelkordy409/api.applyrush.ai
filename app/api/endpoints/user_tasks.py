"""
User Tasks API endpoints
Manage user onboarding and progress tasks
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Default tasks for new users
DEFAULT_TASKS = [
    {
        "id": "upload_resume",
        "label": "Upload your resume",
        "description": "Upload your resume to get personalized job matches",
        "gain": 35,
        "category": "profile",
        "order": 1,
        "action_url": "/dashboard/resume-management"
    },
    {
        "id": "complete_profile",
        "label": "Complete your profile (80%+)",
        "description": "Fill out your profile information to improve match quality",
        "gain": 20,
        "category": "profile",
        "order": 2,
        "action_url": "/dashboard/profile"
    },
    {
        "id": "set_preferences",
        "label": "Set job preferences",
        "description": "Configure your job search preferences",
        "gain": 15,
        "category": "settings",
        "order": 3,
        "action_url": "/dashboard/settings"
    },
    {
        "id": "enable_cover_letters",
        "label": "Enable AI cover letters",
        "description": "Let AI generate personalized cover letters for each application",
        "gain": 25,
        "category": "features",
        "order": 4,
        "action_url": "/dashboard/settings"
    },
    {
        "id": "first_application",
        "label": "Approve your first application",
        "description": "Review and approve an application from your preview queue",
        "gain": 20,
        "category": "engagement",
        "order": 5,
        "action_url": "/dashboard/preview"
    },
]


@router.get("/tasks")
async def get_user_tasks(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get user's task list with completion status
    Auto-detects completed tasks based on user data
    """
    try:
        user_id = current_user["id"]

        # Get user's task completions from database
        user_tasks_doc = await db.user_tasks.find_one({"user_id": user_id})

        if not user_tasks_doc:
            # Initialize tasks for new user
            user_tasks_doc = {
                "user_id": user_id,
                "completed_tasks": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db.user_tasks.insert_one(user_tasks_doc)

        completed_task_ids = user_tasks_doc.get("completed_tasks", [])

        # Auto-detect completed tasks based on user data
        auto_completed = await _auto_detect_completed_tasks(user_id, db)

        # Merge manual and auto-detected completions
        all_completed = list(set(completed_task_ids + auto_completed))

        # Build task list
        tasks = []
        for task_template in DEFAULT_TASKS:
            task = task_template.copy()
            task["completed"] = task["id"] in all_completed
            task["completed_at"] = None

            # Add completion timestamp if available
            if task["completed"] and user_tasks_doc.get("completion_timestamps"):
                task["completed_at"] = user_tasks_doc["completion_timestamps"].get(task["id"])

            tasks.append(task)

        # Calculate total progress
        completed_count = sum(1 for t in tasks if t["completed"])
        total_count = len(tasks)
        progress_percentage = int((completed_count / total_count) * 100) if total_count > 0 else 0

        # Calculate potential score increase
        pending_tasks = [t for t in tasks if not t["completed"]]
        potential_gain = sum(t["gain"] for t in pending_tasks)

        return {
            "success": True,
            "tasks": tasks,
            "stats": {
                "total": total_count,
                "completed": completed_count,
                "pending": total_count - completed_count,
                "progress_percentage": progress_percentage,
                "potential_gain": potential_gain
            }
        }

    except Exception as e:
        logger.error(f"Error getting user tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")


@router.post("/tasks/{task_id}/complete")
async def mark_task_complete(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Mark a task as completed
    """
    try:
        user_id = current_user["id"]

        # Validate task exists
        valid_task_ids = [t["id"] for t in DEFAULT_TASKS]
        if task_id not in valid_task_ids:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # Update user tasks
        result = await db.user_tasks.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {"completed_tasks": task_id},
                "$set": {
                    f"completion_timestamps.{task_id}": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        return {
            "success": True,
            "task_id": task_id,
            "completed": True,
            "message": "Task marked as completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete task: {str(e)}")


@router.post("/tasks/{task_id}/uncomplete")
async def mark_task_incomplete(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Mark a task as incomplete (for testing or corrections)
    """
    try:
        user_id = current_user["id"]

        # Update user tasks
        await db.user_tasks.update_one(
            {"user_id": user_id},
            {
                "$pull": {"completed_tasks": task_id},
                "$unset": {f"completion_timestamps.{task_id}": ""},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        return {
            "success": True,
            "task_id": task_id,
            "completed": False,
            "message": "Task marked as incomplete"
        }

    except Exception as e:
        logger.error(f"Error uncompleting task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to uncomplete task: {str(e)}")


async def _auto_detect_completed_tasks(user_id: str, db) -> List[str]:
    """
    Auto-detect completed tasks based on user data
    Returns list of task IDs that should be marked complete
    """
    completed = []

    try:
        # Check if user has uploaded resume
        resume_count = await db.resumes.count_documents({"user_id": user_id})
        if resume_count > 0:
            completed.append("upload_resume")

        # Check if profile is 80%+ complete
        user_profile = await db.users.find_one({"_id": user_id})
        if user_profile:
            profile_completion = user_profile.get("profile_completion_percentage", 0)
            if profile_completion >= 80:
                completed.append("complete_profile")

        # Check if preferences are set
        preferences = await db.user_preferences.find_one({"user_id": user_id})
        if preferences and preferences.get("job_titles"):
            completed.append("set_preferences")

        # Check if cover letters are enabled
        settings = await db.user_settings.find_one({"user_id": user_id})
        if settings and settings.get("enable_cover_letters"):
            completed.append("enable_cover_letters")

        # Check if user has approved at least one application
        applied_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["applied", "reviewing", "interview", "offer"]}
        })
        if applied_count > 0:
            completed.append("first_application")

    except Exception as e:
        logger.error(f"Error auto-detecting tasks: {e}")

    return completed
