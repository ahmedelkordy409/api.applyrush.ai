"""
Applications Database API endpoints
Fast database queries for applications - NO AI processing
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/database")
async def get_applications_from_database(
    status: Optional[str] = Query(None, description="Filter by status (matched, applied, rejected, etc.)"),
    limit: int = Query(100, description="Number of applications to return"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Read applications directly from MongoDB - NO AI processing
    Fast database query with no triggers
    """
    try:
        user_id = current_user["id"]

        # Build query
        query = {"user_id": user_id}

        if status:
            query["status"] = status

        # Query applications collection
        applications_list = []
        cursor = db.applications.find(query).sort("created_at", -1).limit(limit)

        async for app in cursor:
            # Convert job data to ensure all ObjectIds are strings
            job_data = app.get("job", {})
            if job_data:
                # Convert any ObjectId fields to strings
                if "_id" in job_data and isinstance(job_data["_id"], ObjectId):
                    job_data["_id"] = str(job_data["_id"])
                if "id" in job_data and isinstance(job_data["id"], ObjectId):
                    job_data["id"] = str(job_data["id"])

            application_data = {
                "id": str(app["_id"]),
                "user_id": str(app.get("user_id", "")),
                "job_id": str(app.get("job_id", "")),
                "status": app.get("status", "unknown"),
                "match_score": app.get("match_score"),
                "match_reasons": app.get("match_reasons", []),
                "match_breakdown": app.get("match_breakdown", {}),
                "source": app.get("source", ""),
                "cover_letter": app.get("cover_letter"),
                "applied_at": app.get("applied_at").isoformat() if app.get("applied_at") else None,
                "created_at": app.get("created_at", datetime.utcnow()).isoformat(),
                "updated_at": app.get("updated_at", datetime.utcnow()).isoformat(),
                "job": job_data
            }

            applications_list.append(application_data)

        return {
            "success": True,
            "applications": applications_list,
            "total": len(applications_list),
            "status_filter": status,
            "limit": limit,
            "source": "database"
        }

    except Exception as e:
        logger.error(f"Error getting applications: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@router.put("/{application_id}/approve")
async def approve_application(
    application_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Approve an application - changes status from 'matched' to 'approved' and adds to auto-apply queue
    """
    try:
        user_id = current_user["id"]

        # Get the application first
        application = await db.applications.find_one({
            "_id": ObjectId(application_id),
            "user_id": user_id
        })

        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Update application status to approved
        await db.applications.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "status": "approved",
                    "approved_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Add to auto-apply queue for processing
        queue_item = {
            "user_id": user_id,
            "application_id": application_id,
            "job_id": application.get("job_id"),
            "status": "pending",  # pending, processing, completed, failed
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "retries": 0,
            "max_retries": 3,
            "priority": 1  # Lower number = higher priority
        }

        await db.auto_apply_queue.insert_one(queue_item)

        logger.info(f"Application {application_id} approved and added to auto-apply queue")

        return {
            "success": True,
            "message": "Application approved and queued for auto-apply"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving application: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve application: {str(e)}")


@router.put("/{application_id}/reject")
async def reject_application(
    application_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Reject an application - changes status from 'matched' to 'rejected'
    """
    try:
        user_id = current_user["id"]

        # Update application status
        result = await db.applications.update_one(
            {
                "_id": ObjectId(application_id),
                "user_id": user_id
            },
            {
                "$set": {
                    "status": "rejected",
                    "rejected_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Application not found")

        return {
            "success": True,
            "message": "Application rejected"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting application: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reject application: {str(e)}")


@router.get("/database/stats")
async def get_application_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get application counts by status - optimized for dashboard
    Returns counts for matched, pending, and completed applications
    """
    try:
        user_id = current_user["id"]

        # Use aggregation pipeline for efficient counting
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]

        # Execute aggregation
        status_counts = {}
        async for result in db.applications.aggregate(pipeline):
            status_counts[result["_id"]] = result["count"]

        # Calculate dashboard metrics
        matched_count = status_counts.get("matched", 0)
        pending_count = status_counts.get("pending", 0)

        # Completed = all statuses except matched and pending
        completed_statuses = ["applied", "reviewing", "interview", "offer", "accepted", "rejected", "withdrawn"]
        completed_count = sum(status_counts.get(status, 0) for status in completed_statuses)

        return {
            "success": True,
            "stats": {
                "preview": matched_count,      # Matched applications waiting for review
                "queue": pending_count,         # Pending applications in queue
                "completed": completed_count,   # All other applications (applied, reviewing, etc.)
                "by_status": status_counts,     # Detailed breakdown by status
                "total": sum(status_counts.values())
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting application stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
