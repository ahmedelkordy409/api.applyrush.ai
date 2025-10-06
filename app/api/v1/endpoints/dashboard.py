"""
Dashboard API endpoints
Provides dashboard statistics and summary data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get dashboard summary with counts for preview, queue, and completed applications
    """
    try:
        user_id = current_user["id"]

        # Count applications by status
        # "matched" = new matches ready for preview
        # "pending" = in queue waiting for approval
        # "applied"/"completed" = already applied
        preview_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": "matched"
        })

        queue_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": "pending"
        })

        completed_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["applied", "completed"]}
        })

        return {
            "success": True,
            "summary": {
                "preview": preview_count,
                "queue": queue_count,
                "completed": completed_count
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/increase-items")
async def get_increase_items(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get boost success items with completion status
    """
    try:
        user_id = current_user["id"]

        # Check user profile completion
        user = await db.users.find_one({"_id": ObjectId(user_id)})

        # Check if user has uploaded resume
        has_resume = await db.resumes.count_documents({"user_id": user_id}) > 0

        # Check if user has generated cover letter
        has_cover_letter = await db.applications.count_documents({
            "user_id": user_id,
            "cover_letter": {"$exists": True, "$ne": None}
        }) > 0

        # Check profile completion
        profile = user.get("profile", {})
        has_profile = bool(
            profile.get("desired_roles") and
            profile.get("desired_locations") and
            profile.get("desired_salary_min")
        )

        # Check preferences
        preferences = user.get("preferences", {})
        has_preferences = bool(
            preferences.get("work_type") and
            preferences.get("job_type")
        )

        items = [
            {
                "id": "resume",
                "label": "Upload optimized resume",
                "gain": 35,
                "completed": has_resume
            },
            {
                "id": "cover-letter",
                "label": "Generate AI cover letters",
                "gain": 25,
                "completed": has_cover_letter
            },
            {
                "id": "profile",
                "label": "Complete profile (80%+)",
                "gain": 20,
                "completed": has_profile
            },
            {
                "id": "preferences",
                "label": "Set job preferences",
                "gain": 15,
                "completed": has_preferences
            }
        ]

        return {
            "success": True,
            "items": items
        }
    except Exception as e:
        logger.error(f"Error getting increase items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/getting-started")
async def get_getting_started_text(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get personalized getting started text based on user's application status
    """
    try:
        user_id = current_user["id"]

        # Count user's applications
        app_count = await db.applications.count_documents({"user_id": user_id})

        if app_count == 0:
            text = "It will take a couple of hours to find roles that match your preferences. We'll notify you when new applications are ready for review."
        elif app_count < 5:
            text = f"Great start! You have {app_count} applications. We're continuously searching for more matches based on your preferences."
        else:
            text = f"You're doing great with {app_count} applications! Keep reviewing new matches to increase your chances."

        return {
            "success": True,
            "text": text
        }
    except Exception as e:
        logger.error(f"Error getting getting started text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_application_stats(
    userId: str = Query(..., description="User ID"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get detailed application statistics
    """
    try:
        user_id = current_user["id"]

        # Ensure userId matches current user
        if userId != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        # Get total applications
        total_applications = await db.applications.count_documents({"user_id": user_id})

        # Get applications from this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        this_week = await db.applications.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": week_ago}
        })

        # Get applications from this month
        month_ago = datetime.utcnow() - timedelta(days=30)
        this_month = await db.applications.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": month_ago}
        })

        # Calculate response rate
        applied_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["applied", "completed"]}
        })

        # Count applications with responses
        responded_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["interview", "offer", "rejected"]}
        })

        response_rate = int((responded_count / applied_count * 100)) if applied_count > 0 else 0

        # Calculate average response time
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "status": {"$in": ["interview", "offer", "rejected"]},
                    "applied_at": {"$exists": True},
                    "updated_at": {"$exists": True}
                }
            },
            {
                "$project": {
                    "response_time": {
                        "$divide": [
                            {"$subtract": ["$updated_at", "$applied_at"]},
                            1000 * 60 * 60 * 24  # Convert to days
                        ]
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_response_time": {"$avg": "$response_time"}
                }
            }
        ]

        avg_result = await db.applications.aggregate(pipeline).to_list(1)
        average_response_time = int(avg_result[0]["avg_response_time"]) if avg_result else 0

        return {
            "success": True,
            "stats": {
                "totalApplications": total_applications,
                "thisWeek": this_week,
                "thisMonth": this_month,
                "responseRate": response_rate,
                "averageResponseTime": average_response_time
            }
        }
    except Exception as e:
        logger.error(f"Error getting application stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
