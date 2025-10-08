"""
Dashboard API endpoints - Production Ready
Provides dashboard statistics and summary data with caching and error handling
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging
from functools import lru_cache
import asyncio

from app.core.database_new import get_async_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache for frequently accessed data (5 minute TTL)
_cache = {}
_cache_ttl = {}
CACHE_DURATION = 300  # 5 minutes in seconds


def get_from_cache(key: str) -> Optional[Any]:
    """Get data from cache if not expired"""
    if key in _cache and key in _cache_ttl:
        if datetime.now().timestamp() < _cache_ttl[key]:
            return _cache[key]
        else:
            # Clean up expired cache
            del _cache[key]
            del _cache_ttl[key]
    return None


def set_to_cache(key: str, value: Any, ttl: int = CACHE_DURATION):
    """Set data to cache with TTL"""
    _cache[key] = value
    _cache_ttl[key] = datetime.now().timestamp() + ttl


async def clear_user_cache(user_id: str):
    """Clear all cache entries for a specific user"""
    keys_to_remove = [k for k in _cache.keys() if user_id in k]
    for key in keys_to_remove:
        _cache.pop(key, None)
        _cache_ttl.pop(key, None)


@router.get("/summary")
async def get_dashboard_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db),
    force_refresh: bool = Query(False, description="Force cache refresh")
):
    """
    Get dashboard summary with counts for preview, queue, and completed applications

    Returns:
        - preview: Count of matched applications ready for review
        - queue: Count of pending applications waiting for approval
        - completed: Count of applied/completed applications
    """
    try:
        user_id = current_user["id"]
        cache_key = f"dashboard_summary_{user_id}"

        # Check cache first
        if not force_refresh:
            cached_data = get_from_cache(cache_key)
            if cached_data:
                logger.debug(f"Returning cached dashboard summary for user {user_id}")
                return cached_data

        # Run all queries in parallel for better performance
        preview_task = db.applications.count_documents({
            "user_id": user_id,
            "status": "matched"
        })

        queue_task = db.applications.count_documents({
            "user_id": user_id,
            "status": "pending"
        })

        completed_task = db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["applied", "completed"]}
        })

        # Wait for all queries to complete
        preview_count, queue_count, completed_count = await asyncio.gather(
            preview_task,
            queue_task,
            completed_task
        )

        result = {
            "success": True,
            "summary": {
                "preview": preview_count,
                "queue": queue_count,
                "completed": completed_count
            },
            "cached": False,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Cache the result
        set_to_cache(cache_key, result)

        logger.info(f"Dashboard summary for user {user_id}: preview={preview_count}, queue={queue_count}, completed={completed_count}")
        return result

    except Exception as e:
        logger.error(f"Error getting dashboard summary for user {current_user.get('id')}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to load dashboard summary",
                "message": "An error occurred while fetching your dashboard data. Please try again.",
                "code": "DASHBOARD_SUMMARY_ERROR"
            }
        )


@router.get("/increase-items")
async def get_increase_items(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db),
    force_refresh: bool = Query(False, description="Force cache refresh")
):
    """
    Get profile completion items with their completion status

    Returns list of items to increase job matching success rate
    """
    try:
        user_id = current_user["id"]
        cache_key = f"increase_items_{user_id}"

        # Check cache
        if not force_refresh:
            cached_data = get_from_cache(cache_key)
            if cached_data:
                return cached_data

        # Get user data
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Run all checks in parallel
        resume_task = db.resumes.count_documents({"user_id": user_id})
        cover_letter_task = db.applications.count_documents({
            "user_id": user_id,
            "cover_letter": {"$exists": True, "$ne": None}
        })

        has_resume, has_cover_letter = await asyncio.gather(
            resume_task,
            cover_letter_task
        )

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
                "completed": has_resume > 0
            },
            {
                "id": "cover-letter",
                "label": "Generate AI cover letters",
                "gain": 25,
                "completed": has_cover_letter > 0
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

        result = {
            "success": True,
            "items": items,
            "total_gain": sum(item["gain"] for item in items if not item["completed"]),
            "completion_percentage": int(sum(1 for item in items if item["completed"]) / len(items) * 100),
            "cached": False
        }

        # Cache the result
        set_to_cache(cache_key, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting increase items for user {current_user.get('id')}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to load profile completion items",
                "message": "An error occurred while checking your profile completion status.",
                "code": "INCREASE_ITEMS_ERROR"
            }
        )


@router.get("/getting-started")
async def get_getting_started_text(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get personalized getting started message based on user's application status
    """
    try:
        user_id = current_user["id"]

        # Count user's applications
        app_count = await db.applications.count_documents({"user_id": user_id})

        # Get matched count for more context
        matched_count = await db.applications.count_documents({
            "user_id": user_id,
            "status": "matched"
        })

        if app_count == 0:
            text = "It will take a couple of hours to find roles that match your preferences. We'll notify you when new applications are ready for review."
        elif app_count < 5:
            text = f"Great start! You have {app_count} application{'s' if app_count != 1 else ''}. We're continuously searching for more matches based on your preferences."
        elif app_count < 20:
            text = f"You're doing great with {app_count} applications! Keep reviewing new matches to increase your chances."
        else:
            text = f"Excellent progress! You have {app_count} applications. Keep the momentum going!"

        if matched_count > 0:
            text += f" You have {matched_count} new match{'es' if matched_count != 1 else ''} ready for review."

        return {
            "success": True,
            "text": text,
            "stats": {
                "total_applications": app_count,
                "new_matches": matched_count
            }
        }

    except Exception as e:
        logger.error(f"Error getting getting started text for user {current_user.get('id')}: {e}", exc_info=True)
        # Return default message on error
        return {
            "success": True,
            "text": "It will take a couple of hours to find roles that match your preferences. We'll notify you when new applications are ready for review.",
            "stats": {
                "total_applications": 0,
                "new_matches": 0
            }
        }


@router.get("/stats")
async def get_application_stats(
    userId: str = Query(..., description="User ID"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db),
    force_refresh: bool = Query(False, description="Force cache refresh")
):
    """
    Get detailed application statistics with response metrics
    """
    try:
        user_id = current_user["id"]

        # Security check
        if userId != user_id:
            logger.warning(f"Unauthorized stats access attempt: {user_id} tried to access {userId}")
            raise HTTPException(status_code=403, detail="Unauthorized access")

        cache_key = f"app_stats_{user_id}"

        # Check cache
        if not force_refresh:
            cached_data = get_from_cache(cache_key)
            if cached_data:
                return cached_data

        # Calculate date ranges
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Run all queries in parallel
        total_task = db.applications.count_documents({"user_id": user_id})

        week_task = db.applications.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": week_ago}
        })

        month_task = db.applications.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": month_ago}
        })

        applied_task = db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["applied", "completed"]}
        })

        responded_task = db.applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["interview", "offer", "rejected"]}
        })

        # Wait for all queries
        total_applications, this_week, this_month, applied_count, responded_count = await asyncio.gather(
            total_task, week_task, month_task, applied_task, responded_task
        )

        # Calculate response rate
        response_rate = int((responded_count / applied_count * 100)) if applied_count > 0 else 0

        # Calculate average response time
        avg_response_time = 0
        try:
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
            if avg_result:
                avg_response_time = int(avg_result[0]["avg_response_time"])
        except Exception as e:
            logger.warning(f"Error calculating avg response time: {e}")

        result = {
            "success": True,
            "stats": {
                "totalApplications": total_applications,
                "thisWeek": this_week,
                "thisMonth": this_month,
                "responseRate": response_rate,
                "averageResponseTime": avg_response_time
            },
            "cached": False,
            "timestamp": now.isoformat()
        }

        # Cache for 5 minutes
        set_to_cache(cache_key, result)

        logger.info(f"Stats for user {user_id}: total={total_applications}, week={this_week}, month={this_month}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application stats for user {current_user.get('id')}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to load application statistics",
                "message": "An error occurred while fetching your application stats.",
                "code": "APP_STATS_ERROR"
            }
        )


@router.post("/clear-cache")
async def clear_dashboard_cache(
    current_user: Dict[str, Any] = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    Clear dashboard cache for current user (useful after profile updates)
    """
    try:
        user_id = current_user["id"]
        await clear_user_cache(user_id)

        logger.info(f"Cleared dashboard cache for user {user_id}")
        return {
            "success": True,
            "message": "Dashboard cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"Error clearing cache for user {current_user.get('id')}: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/health")
async def dashboard_health_check():
    """Health check endpoint for dashboard service"""
    return {
        "status": "healthy",
        "service": "dashboard",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_entries": len(_cache)
    }
