"""
User management API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId

from app.core.database_new import get_async_db
from app.core.security import get_current_user

router = APIRouter()


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[int] = None
    resume_text: Optional[str] = None


class UserPreferencesUpdate(BaseModel):
    excluded_companies: Optional[List[str]] = None
    cover_letter_enabled: Optional[bool] = None
    resume_customization_enabled: Optional[bool] = None
    job_preferences: Optional[Dict[str, Any]] = None
    match_threshold: Optional[str] = None
    approval_mode: Optional[str] = None
    search_active: Optional[bool] = None


# Current user endpoints (auth required)
@router.get("/profile")
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Get current authenticated user's profile"""
    try:
        user_data = await db.users.find_one({"_id": ObjectId(current_user["id"])})

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        user_profile = dict(user_data)
        user_profile["id"] = str(user_profile.pop("_id"))

        return {"success": True, "profile": user_profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile")
async def update_current_user_profile(
    profile_update: UserProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Update current authenticated user's profile"""
    try:
        update_data = {}

        if profile_update.first_name is not None:
            update_data["first_name"] = profile_update.first_name

        if profile_update.last_name is not None:
            update_data["last_name"] = profile_update.last_name

        if profile_update.phone is not None:
            update_data["phone"] = profile_update.phone

        if profile_update.linkedin_url is not None:
            update_data["linkedin_url"] = profile_update.linkedin_url

        if profile_update.portfolio_url is not None:
            update_data["portfolio_url"] = profile_update.portfolio_url

        if profile_update.skills is not None:
            update_data["skills"] = profile_update.skills

        if profile_update.experience_years is not None:
            update_data["experience_years"] = profile_update.experience_years

        if profile_update.resume_text is not None:
            update_data["resume_text"] = profile_update.resume_text

        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            await db.users.update_one(
                {"_id": ObjectId(current_user["id"])},
                {"$set": update_data}
            )

        return {"success": True, "message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preferences")
async def get_user_preferences(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Get current user's preferences"""
    try:
        # Get current user
        user_data = await db.users.find_one({"_id": ObjectId(current_user["id"])})

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Get preferences with defaults
        preferences = user_data.get("preferences", {})

        return {
            "success": True,
            "preferences": preferences
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/preferences")
async def update_user_preferences(
    preferences_update: UserPreferencesUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Update current user's preferences"""
    try:
        # Get current user
        user_data = await db.users.find_one({"_id": ObjectId(current_user["id"])})

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Get current preferences
        current_prefs = user_data.get("preferences", {})

        # Update preferences
        if preferences_update.excluded_companies is not None:
            current_prefs["excluded_companies"] = preferences_update.excluded_companies

        if preferences_update.cover_letter_enabled is not None:
            current_prefs["cover_letter_enabled"] = preferences_update.cover_letter_enabled

        if preferences_update.resume_customization_enabled is not None:
            current_prefs["resume_customization_enabled"] = preferences_update.resume_customization_enabled

        if preferences_update.job_preferences is not None:
            current_prefs["job_preferences"] = preferences_update.job_preferences

        if preferences_update.match_threshold is not None:
            current_prefs["match_threshold"] = preferences_update.match_threshold

        if preferences_update.approval_mode is not None:
            current_prefs["approval_mode"] = preferences_update.approval_mode

        if preferences_update.search_active is not None:
            current_prefs["search_active"] = preferences_update.search_active

        # Save updated preferences
        await db.users.update_one(
            {"_id": ObjectId(current_user["id"])},
            {
                "$set": {
                    "preferences": current_prefs,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "success": True,
            "message": "Preferences updated successfully",
            "preferences": current_prefs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
