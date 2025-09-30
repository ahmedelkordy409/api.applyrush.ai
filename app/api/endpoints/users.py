"""
User management API endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import json
from app.core.database import get_database

router = APIRouter()

class UserProfileUpdate(BaseModel):
    skills: Optional[List[str]] = None
    experience_years: Optional[int] = None
    resume_text: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

@router.get("/{user_id}/profile")
async def get_user_profile(user_id: int):
    try:
        database = await get_database()
        user_data = await database.fetch_one(
            "SELECT * FROM users WHERE id = :user_id",
            {"user_id": user_id}
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_profile = dict(user_data)
        user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
        user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
        
        return {"success": True, "profile": user_profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}/profile")
async def update_user_profile(user_id: int, profile_update: UserProfileUpdate):
    try:
        database = await get_database()
        
        update_fields = []
        update_values = {"user_id": user_id}
        
        if profile_update.skills is not None:
            update_fields.append("skills = :skills")
            update_values["skills"] = json.dumps(profile_update.skills)
        
        if profile_update.experience_years is not None:
            update_fields.append("experience_years = :experience_years")
            update_values["experience_years"] = profile_update.experience_years
        
        if profile_update.resume_text is not None:
            update_fields.append("resume_text = :resume_text")
            update_values["resume_text"] = profile_update.resume_text
        
        if profile_update.preferences is not None:
            update_fields.append("preferences = :preferences")
            update_values["preferences"] = json.dumps(profile_update.preferences)
        
        if update_fields:
            update_query = f"""
            UPDATE users SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = :user_id
            """
            await database.execute(update_query, update_values)
        
        return {"success": True, "message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))