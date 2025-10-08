"""
User Settings API endpoints
Manage user preferences, search settings, and configurations
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import logging

from app.core.database_new import get_async_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class UserSettingsUpdate(BaseModel):
    """Settings update request"""
    matchThreshold: Optional[str] = None  # open, good-fit, top
    approvalMode: Optional[str] = None  # approval, delayed, instant
    coverLetters: Optional[bool] = None
    resumeEnhancement: Optional[bool] = None
    searchActive: Optional[bool] = None
    excludedCompanies: Optional[List[str]] = None
    preferredLocations: Optional[List[str]] = None
    jobTypes: Optional[List[str]] = None  # full-time, part-time, contract, etc
    remote: Optional[bool] = None
    salaryMin: Optional[int] = None
    salaryMax: Optional[int] = None


@router.get("/settings")
async def get_user_settings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get user settings
    """
    try:
        user_id = current_user["id"]

        # Get settings from database
        settings = await db.user_settings.find_one({"user_id": user_id})

        if not settings:
            # Return default settings
            default_settings = {
                "matchThreshold": "good-fit",
                "approvalMode": "approval",
                "coverLetters": False,
                "resumeEnhancement": False,
                "searchActive": True,
                "excludedCompanies": [],
                "preferredLocations": [],
                "jobTypes": ["full-time"],
                "remote": None,  # null means no preference
                "salaryMin": None,
                "salaryMax": None
            }
            return {
                "success": True,
                "settings": default_settings
            }

        return {
            "success": True,
            "settings": {
                "matchThreshold": settings.get("matchThreshold", "good-fit"),
                "approvalMode": settings.get("approvalMode", "approval"),
                "coverLetters": settings.get("coverLetters", False),
                "resumeEnhancement": settings.get("resumeEnhancement", False),
                "searchActive": settings.get("searchActive", True),
                "excludedCompanies": settings.get("excludedCompanies", []),
                "preferredLocations": settings.get("preferredLocations", []),
                "jobTypes": settings.get("jobTypes", ["full-time"]),
                "remote": settings.get("remote"),
                "salaryMin": settings.get("salaryMin"),
                "salaryMax": settings.get("salaryMax")
            }
        }

    except Exception as e:
        logger.error(f"Error getting user settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.put("/settings")
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Update user settings
    """
    try:
        user_id = current_user["id"]

        # Build update object (only include fields that were provided)
        update_data = {}
        for field, value in settings_update.dict(exclude_unset=True).items():
            update_data[field] = value

        if not update_data:
            return {
                "success": True,
                "message": "No settings to update"
            }

        # Add timestamp
        update_data["updated_at"] = datetime.utcnow()

        # Update or create settings
        result = await db.user_settings.update_one(
            {"user_id": user_id},
            {
                "$set": update_data,
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        logger.info(f"Updated settings for user {user_id}: {update_data}")

        return {
            "success": True,
            "message": "Settings updated successfully",
            "updated_fields": list(update_data.keys())
        }

    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/settings/pause-search")
async def pause_search(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Pause job search
    """
    try:
        user_id = current_user["id"]

        await db.user_settings.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "searchActive": False,
                    "search_paused_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        logger.info(f"Search paused for user {user_id}")

        return {
            "success": True,
            "message": "Job search paused successfully"
        }

    except Exception as e:
        logger.error(f"Error pausing search: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause search: {str(e)}")


@router.post("/settings/resume-search")
async def resume_search(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Resume job search
    """
    try:
        user_id = current_user["id"]

        await db.user_settings.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "searchActive": True,
                    "search_resumed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "search_paused_at": ""
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        logger.info(f"Search resumed for user {user_id}")

        return {
            "success": True,
            "message": "Job search resumed successfully"
        }

    except Exception as e:
        logger.error(f"Error resuming search: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume search: {str(e)}")


@router.post("/settings/exclude-company")
async def exclude_company(
    company_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Add company to exclusion list (Premium feature)
    """
    try:
        user_id = current_user["id"]

        # Check if user has premium access
        user = await db.users.find_one({"_id": user_id})
        if not user or not user.get("premium", False):
            return {
                "success": False,
                "message": "This is a premium feature. Upgrade to exclude specific companies.",
                "upgrade_required": True
            }

        # Add to excluded companies
        await db.user_settings.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {"excludedCompanies": company_name},
                "$set": {"updated_at": datetime.utcnow()},
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        logger.info(f"Company '{company_name}' excluded for user {user_id}")

        return {
            "success": True,
            "message": f"'{company_name}' added to exclusion list"
        }

    except Exception as e:
        logger.error(f"Error excluding company: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to exclude company: {str(e)}")


@router.delete("/settings/exclude-company/{company_name}")
async def remove_excluded_company(
    company_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Remove company from exclusion list
    """
    try:
        user_id = current_user["id"]

        await db.user_settings.update_one(
            {"user_id": user_id},
            {
                "$pull": {"excludedCompanies": company_name},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        logger.info(f"Company '{company_name}' removed from exclusions for user {user_id}")

        return {
            "success": True,
            "message": f"'{company_name}' removed from exclusion list"
        }

    except Exception as e:
        logger.error(f"Error removing excluded company: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove excluded company: {str(e)}")


@router.get("/settings/search-status")
async def get_search_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    Get current search status
    """
    try:
        user_id = current_user["id"]

        settings = await db.user_settings.find_one({"user_id": user_id})

        is_active = settings.get("searchActive", True) if settings else True
        paused_at = settings.get("search_paused_at") if settings else None

        return {
            "success": True,
            "searchActive": is_active,
            "pausedAt": paused_at.isoformat() if paused_at else None,
            "message": "Your job search is currently active and looking for new opportunities." if is_active
                      else "Your job search is paused. Click 'Resume Search' to continue."
        }

    except Exception as e:
        logger.error(f"Error getting search status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get search status: {str(e)}")
