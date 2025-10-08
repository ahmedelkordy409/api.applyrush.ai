"""
Applications Queue API endpoints
Fast database queries - NO AI processing
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from pydantic import BaseModel
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class QueueActionRequest(BaseModel):
    """Request body for queue actions"""
    action: str
    queueItemId: Optional[str] = None
    limit: Optional[int] = 5


@router.get("/queue/database")
async def get_queue_from_database(
    status: str = Query("pending", description="Queue status filter"),
    limit: int = Query(20, description="Number of items to return"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Read application queue directly from MongoDB - NO AI processing
    Fast database query with no triggers
    """
    try:
        user_id = current_user["id"]

        # Query application queue collection
        queue_items = []
        cursor = db.application_queue.find({
            "user_id": ObjectId(user_id),
            "status": status
        }).sort("created_at", -1).limit(limit)

        async for item in cursor:
            # Get job details
            job_data = await db.jobs.find_one({"_id": item["job_id"]})

            if job_data:
                queue_items.append({
                    "id": str(item["_id"]),
                    "job_id": str(item["job_id"]),
                    "status": item.get("status", "pending"),
                    "match_score": item.get("match_score", 0),
                    "match_reasons": item.get("match_reasons", []),
                    "ai_generated_cover_letter": item.get("ai_generated_cover_letter"),
                    "expires_at": item.get("expires_at").isoformat() if item.get("expires_at") else None,
                    "auto_apply_after": item.get("auto_apply_after").isoformat() if item.get("auto_apply_after") else None,
                    "created_at": item.get("created_at", datetime.utcnow()).isoformat(),
                    "job": {
                        "id": str(job_data["_id"]),
                        "title": job_data.get("title", ""),
                        "company": job_data.get("company", ""),
                        "location": job_data.get("location", ""),
                        "salary_min": job_data.get("salary_min"),
                        "salary_max": job_data.get("salary_max"),
                        "salary_currency": job_data.get("salary_currency", "USD"),
                        "description": job_data.get("description", ""),
                        "requirements": job_data.get("requirements", []),
                        "benefits": job_data.get("benefits", []),
                        "job_type": job_data.get("job_type", "Full-time"),
                        "remote": job_data.get("remote", False),
                        "date_posted": job_data.get("date_posted").isoformat() if job_data.get("date_posted") else None,
                        "apply_url": job_data.get("apply_url", "")
                    }
                })

        return {
            "success": True,
            "queue": queue_items,
            "total": len(queue_items),
            "status": status,
            "limit": limit,
            "source": "database",
            "ai_processing": False
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@router.post("/queue/database")
async def manage_queue_actions(
    request: QueueActionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Handle queue actions: approve, reject, find_matches
    """
    try:
        user_id = current_user["id"]
        action = request.action
        queueItemId = request.queueItemId
        limit = request.limit

        if action == "approve":
            if not queueItemId:
                raise HTTPException(status_code=400, detail="queueItemId required for approve action")

            # Update queue item status to approved
            result = await db.application_queue.update_one(
                {"_id": ObjectId(queueItemId), "user_id": ObjectId(user_id)},
                {"$set": {"status": "approved", "updated_at": datetime.utcnow()}}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Queue item not found")

            return {
                "success": True,
                "message": "Application approved successfully"
            }

        elif action == "reject":
            if not queueItemId:
                raise HTTPException(status_code=400, detail="queueItemId required for reject action")

            # Update queue item status to rejected
            result = await db.application_queue.update_one(
                {"_id": ObjectId(queueItemId), "user_id": ObjectId(user_id)},
                {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Queue item not found")

            return {
                "success": True,
                "message": "Application rejected"
            }

        elif action == "find_matches":
            # Import background job service for matching
            from app.services.job_matcher_service import job_matcher_service

            logger.info(f"🔍 Starting job matching for user {user_id} with limit {limit}")

            # Get user data
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                logger.error(f"❌ User {user_id} not found")
                raise HTTPException(status_code=404, detail="User not found")

            logger.info(f"✅ Found user: {user.get('email', 'unknown')}")

            # Get user settings
            user_settings = await db.user_settings.find_one({"user_id": user_id})

            # Check if search is active
            if user_settings and not user_settings.get("searchActive", True):
                logger.warning(f"⚠️  Search is paused for user {user_id}")
                return {
                    "success": False,
                    "message": "Job search is currently paused. Resume your search to find new matches.",
                    "search_paused": True
                }

            # Get match threshold from settings
            match_threshold = user_settings.get("matchThreshold", "good-fit") if user_settings else "good-fit"

            # Convert match threshold to score
            threshold_map = {
                "open": 30,
                "good-fit": 55,
                "top": 80
            }
            min_score = threshold_map.get(match_threshold, 55)

            # Get excluded companies (premium feature)
            excluded_companies = user_settings.get("excludedCompanies", []) if user_settings else []

            logger.info(f"📊 Match threshold: {match_threshold} (min score: {min_score})")

            # Get active jobs from database
            jobs_cursor = db.jobs.find({
                "is_active": True
            }).sort("created_at", -1)

            jobs = await jobs_cursor.to_list(length=None)
            logger.info(f"📋 Found {len(jobs)} active jobs in database")

            if not jobs:
                logger.warning("⚠️  No active jobs found in database")
                return {
                    "success": True,
                    "message": "No active jobs available to match"
                }

            # Match jobs for user
            matched_count = 0
            skipped_existing = 0
            filtered_out = 0
            low_score_count = 0
            matched_jobs_list = []  # Store matched jobs to return

            for job in jobs:
                try:
                    job_id = str(job["_id"])

                    # Check if job already exists in queue OR in applications
                    existing_queue = await db.application_queue.find_one({
                        "user_id": ObjectId(user_id),
                        "job_id": ObjectId(job_id)
                    })

                    existing_application = await db.applications.find_one({
                        "user_id": user_id,
                        "job_id": job_id
                    })

                    if existing_queue or existing_application:
                        skipped_existing += 1
                        continue

                    # Check if company is excluded (premium feature)
                    company_name = job.get("company", "")
                    if excluded_companies and company_name in excluded_companies:
                        logger.debug(f"🚫 Job {job_id} from excluded company: {company_name}")
                        filtered_out += 1
                        continue

                    # Check hard filters first
                    passes_filters, filter_reason = job_matcher_service.passes_user_filters(user, job)
                    if not passes_filters:
                        logger.debug(f"🚫 Job {job_id} filtered out: {filter_reason}")
                        filtered_out += 1
                        continue

                    # Calculate match score
                    match_result = await job_matcher_service.calculate_match_score(user, job)
                    match_score = match_result["score"]
                    match_reasons = match_result["reasons"]

                    logger.debug(f"🎯 Job '{job.get('title', 'Unknown')}' score: {match_score}")

                    if match_score >= min_score:
                        # Prepare job data for storage
                        job_data = {
                            "id": job_id,
                            "title": job.get("title", ""),
                            "company": job.get("company", ""),
                            "location": job.get("location", ""),
                            "salary_min": job.get("salary_min"),
                            "salary_max": job.get("salary_max"),
                            "salary_currency": job.get("salary_currency", "USD"),
                            "description": job.get("description", ""),
                            "requirements": job.get("requirements", []),
                            "benefits": job.get("benefits", []),
                            "job_type": job.get("job_type", "Full-time"),
                            "remote": job.get("remote", False),
                            "date_posted": job.get("date_posted"),
                            "apply_url": job.get("apply_url", ""),
                            "source": job.get("source", "")
                        }

                        # Create application match entry (for immediate display)
                        application = {
                            "user_id": user_id,
                            "job_id": job_id,
                            "job": job_data,
                            "status": "matched",
                            "match_score": match_score,
                            "match_reasons": match_reasons,
                            "match_breakdown": match_result.get("breakdown", {}),
                            "source": "auto_match",
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }

                        # Insert into applications collection
                        result = await db.applications.insert_one(application)
                        application["_id"] = str(result.inserted_id)

                        # Add to response list
                        matched_jobs_list.append({
                            "id": str(result.inserted_id),
                            "job_id": job_id,
                            "status": "matched",
                            "match_score": match_score,
                            "match_reasons": match_reasons,
                            "match_breakdown": match_result.get("breakdown", {}),
                            "created_at": datetime.utcnow().isoformat(),
                            "job": job_data
                        })

                        matched_count += 1
                        logger.info(f"✅ Added job '{job.get('title', 'Unknown')}' as application match (score: {match_score})")

                        # Stop if we reached the limit
                        if matched_count >= limit:
                            logger.info(f"🎯 Reached match limit of {limit}")
                            break
                    else:
                        low_score_count += 1

                except Exception as e:
                    logger.error(f"❌ Error matching job {job.get('_id')}: {e}")
                    continue

            logger.info(f"""
📊 Matching Summary:
   ✅ Matched: {matched_count}
   🔄 Already exists: {skipped_existing}
   🚫 Filtered out: {filtered_out}
   📉 Low score: {low_score_count}
   📋 Total jobs checked: {len(jobs)}
            """)

            return {
                "success": True,
                "message": f"Found {matched_count} new job matches",
                "matches": matched_jobs_list,  # Return matched jobs immediately
                "stats": {
                    "matched": matched_count,
                    "already_exists": skipped_existing,
                    "filtered_out": filtered_out,
                    "low_score": low_score_count,
                    "total_jobs": len(jobs)
                }
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Action failed: {str(e)}")
