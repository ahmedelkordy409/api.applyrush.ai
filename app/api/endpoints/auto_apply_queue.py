"""
Auto-Apply Queue API endpoints
Manage and monitor the auto-apply queue
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user
from app.services.auto_apply_queue_worker import queue_worker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/queue/status")
async def get_queue_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get queue status and statistics
    """
    try:
        user_id = current_user["id"]

        # Get user's queue items
        user_pending = await db.auto_apply_queue.count_documents({
            "user_id": user_id,
            "status": "pending"
        })

        user_processing = await db.auto_apply_queue.count_documents({
            "user_id": user_id,
            "status": "processing"
        })

        user_completed = await db.auto_apply_queue.count_documents({
            "user_id": user_id,
            "status": "completed"
        })

        user_failed = await db.auto_apply_queue.count_documents({
            "user_id": user_id,
            "status": "failed"
        })

        # Get current processing item for user
        current_item = await db.auto_apply_queue.find_one({
            "user_id": user_id,
            "status": "processing"
        })

        current_application = None
        if current_item:
            app = await db.applications.find_one({
                "_id": ObjectId(current_item["application_id"])
            })
            if app and app.get("job"):
                current_application = {
                    "id": str(app["_id"]),
                    "job_title": app["job"].get("title", "Unknown"),
                    "company": app["job"].get("company", "Unknown"),
                    "started_at": current_item.get("processing_started_at").isoformat() if current_item.get("processing_started_at") else None
                }

        # Get global worker stats
        worker_stats = await queue_worker.get_stats()

        return {
            "success": True,
            "user_stats": {
                "pending": user_pending,
                "processing": user_processing,
                "completed": user_completed,
                "failed": user_failed,
                "total": user_pending + user_processing + user_completed + user_failed
            },
            "current_application": current_application,
            "worker": {
                "is_running": worker_stats.get("is_running", False),
                "total_pending": worker_stats.get("pending", 0),
                "total_processing": worker_stats.get("processing", 0)
            }
        }

    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")


@router.get("/queue/items")
async def get_queue_items(
    status: str = Query(None, description="Filter by status (pending, processing, completed, failed)"),
    limit: int = Query(50, description="Number of items to return"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get user's queue items
    """
    try:
        user_id = current_user["id"]

        # Build query
        query = {"user_id": user_id}
        if status:
            query["status"] = status

        # Get queue items
        items = []
        cursor = db.auto_apply_queue.find(query).sort("created_at", -1).limit(limit)

        async for item in cursor:
            # Get application details
            app = await db.applications.find_one({
                "_id": ObjectId(item["application_id"])
            })

            item_data = {
                "id": str(item["_id"]),
                "status": item.get("status"),
                "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
                "updated_at": item.get("updated_at").isoformat() if item.get("updated_at") else None,
                "retries": item.get("retries", 0),
                "application": None
            }

            if app and app.get("job"):
                item_data["application"] = {
                    "id": str(app["_id"]),
                    "job_title": app["job"].get("title", "Unknown"),
                    "company": app["job"].get("company", "Unknown"),
                    "location": app["job"].get("location", "Unknown")
                }

            items.append(item_data)

        return {
            "success": True,
            "items": items,
            "total": len(items)
        }

    except Exception as e:
        logger.error(f"Error getting queue items: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue items: {str(e)}")


@router.post("/queue/start")
async def start_queue_worker(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Start the queue worker (admin only)
    """
    try:
        # TODO: Add admin check
        if queue_worker.is_running:
            return {
                "success": False,
                "message": "Queue worker is already running"
            }

        # Start worker in background
        import asyncio
        asyncio.create_task(queue_worker.start())

        return {
            "success": True,
            "message": "Queue worker started successfully"
        }

    except Exception as e:
        logger.error(f"Error starting queue worker: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start queue worker: {str(e)}")


@router.post("/queue/stop")
async def stop_queue_worker(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Stop the queue worker (admin only)
    """
    try:
        # TODO: Add admin check
        await queue_worker.stop()

        return {
            "success": True,
            "message": "Queue worker stopped successfully"
        }

    except Exception as e:
        logger.error(f"Error stopping queue worker: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop queue worker: {str(e)}")


@router.delete("/queue/items/{item_id}")
async def remove_queue_item(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Remove an item from the queue
    """
    try:
        user_id = current_user["id"]

        # Only allow removing pending or failed items
        result = await db.auto_apply_queue.delete_one({
            "_id": ObjectId(item_id),
            "user_id": user_id,
            "status": {"$in": ["pending", "failed"]}
        })

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Queue item not found or cannot be removed"
            )

        return {
            "success": True,
            "message": "Queue item removed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing queue item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove queue item: {str(e)}")
