"""
User profile management API endpoints
Handles user profile CRUD operations and profile completion tracking
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from typing import Optional, Dict, Any, List
from app.core.database import database
from app.core.security import get_current_user
from app.models.user import UserProfileUpdate, UserProfileResponse
from app.core.security import PermissionChecker
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


def calculate_profile_completion(profile: Dict[str, Any]) -> int:
    """Calculate profile completion percentage"""
    completion_fields = [
        profile.get("full_name"),
        profile.get("phone_number"),
        profile.get("job_title"),
        profile.get("years_experience"),
        profile.get("desired_salary"),
        profile.get("work_type") and len(profile.get("work_type", [])),
        profile.get("location_preferences") and len(profile.get("location_preferences", [])),
        profile.get("education_level"),
        profile.get("resume_uploaded"),
        profile.get("work_authorization") is not None
    ]

    completed = sum(1 for field in completion_fields
                   if field is not None and field != "" and field != 0)

    return round((completed / len(completion_fields)) * 100)


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile"""
    try:
        if not permission_checker.has_permission(current_user, "profile", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read profile"
            )

        query = """
            SELECT *
            FROM profiles
            WHERE user_id = :user_id
        """
        profile = await database.fetch_one(query=query, values={"user_id": current_user["id"]})

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        profile_dict = dict(profile)

        # Calculate profile completion percentage
        completion_percentage = calculate_profile_completion(profile_dict)

        # Update completion percentage in database
        update_query = """
            UPDATE profiles
            SET profile_completion_percentage = :completion_percentage,
                updated_at = :updated_at
            WHERE user_id = :user_id
        """
        await database.execute(
            query=update_query,
            values={
                "completion_percentage": completion_percentage,
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        profile_dict["profile_completion_percentage"] = completion_percentage
        profile_dict["id"] = str(profile_dict["id"])
        profile_dict["user_id"] = str(profile_dict["user_id"])

        return UserProfileResponse(**profile_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )


@router.patch("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update current user's profile"""
    try:
        if not permission_checker.has_permission(current_user, "profile", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update profile"
            )

        # Get current profile
        query = "SELECT * FROM profiles WHERE user_id = :user_id"
        current_profile = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        if not current_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        # Prepare update data
        update_data = profile_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Build dynamic update query
        set_clauses = []
        values = {"user_id": current_user["id"], "updated_at": datetime.utcnow()}

        for field, value in update_data.items():
            set_clauses.append(f"{field} = :{field}")
            values[field] = value

        set_clauses.append("updated_at = :updated_at")

        update_query = f"""
            UPDATE profiles
            SET {', '.join(set_clauses)}
            WHERE user_id = :user_id
            RETURNING *
        """

        updated_profile = await database.fetch_one(query=update_query, values=values)
        profile_dict = dict(updated_profile)

        # Calculate and update completion percentage
        completion_percentage = calculate_profile_completion(profile_dict)

        completion_update_query = """
            UPDATE profiles
            SET profile_completion_percentage = :completion_percentage
            WHERE user_id = :user_id
        """
        await database.execute(
            query=completion_update_query,
            values={
                "completion_percentage": completion_percentage,
                "user_id": current_user["id"]
            }
        )

        profile_dict["profile_completion_percentage"] = completion_percentage
        profile_dict["id"] = str(profile_dict["id"])
        profile_dict["user_id"] = str(profile_dict["user_id"])

        return UserProfileResponse(**profile_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.put("/profile", response_model=UserProfileResponse)
async def replace_user_profile(
    profile_update: UserProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Replace entire user profile (PUT operation)"""
    try:
        if not permission_checker.has_permission(current_user, "profile", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update profile"
            )

        # Get current profile
        query = "SELECT * FROM profiles WHERE user_id = :user_id"
        current_profile = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        if not current_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        # Use all provided data, setting None for unspecified fields
        update_data = profile_update.model_dump()
        update_data["updated_at"] = datetime.utcnow()

        # Build update query with all profile fields
        set_clauses = []
        values = {"user_id": current_user["id"]}

        profile_fields = [
            "full_name", "phone_number", "location", "timezone", "job_title",
            "years_experience", "desired_salary", "work_type", "location_preferences",
            "education_level", "skills", "preferred_industries", "preferred_company_sizes",
            "work_authorization", "ai_apply_enabled", "ai_cover_letter_enabled",
            "ai_interview_prep_enabled", "profile_public", "share_analytics", "updated_at"
        ]

        for field in profile_fields:
            set_clauses.append(f"{field} = :{field}")
            values[field] = update_data.get(field)

        update_query = f"""
            UPDATE profiles
            SET {', '.join(set_clauses)}
            WHERE user_id = :user_id
            RETURNING *
        """

        updated_profile = await database.fetch_one(query=update_query, values=values)
        profile_dict = dict(updated_profile)

        # Calculate and update completion percentage
        completion_percentage = calculate_profile_completion(profile_dict)

        completion_update_query = """
            UPDATE profiles
            SET profile_completion_percentage = :completion_percentage
            WHERE user_id = :user_id
        """
        await database.execute(
            query=completion_update_query,
            values={
                "completion_percentage": completion_percentage,
                "user_id": current_user["id"]
            }
        )

        profile_dict["profile_completion_percentage"] = completion_percentage
        profile_dict["id"] = str(profile_dict["id"])
        profile_dict["user_id"] = str(profile_dict["user_id"])

        return UserProfileResponse(**profile_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error replacing user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to replace profile"
        )


@router.post("/profile/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload user resume file"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to upload resume"
            )

        # Validate file type
        allowed_types = ["application/pdf", "application/msword",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only PDF and Word documents are allowed."
            )

        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size too large. Maximum size is 5MB."
            )

        # TODO: Upload to S3 or similar storage service
        # For now, we'll just store the filename and mark as uploaded
        filename = f"resume_{current_user['id']}_{file.filename}"
        file_url = f"/uploads/resumes/{filename}"

        # Update profile with resume info
        update_query = """
            UPDATE profiles
            SET resume_uploaded = true,
                resume_filename = :filename,
                resume_url = :file_url,
                updated_at = :updated_at
            WHERE user_id = :user_id
        """

        await database.execute(
            query=update_query,
            values={
                "filename": file.filename,
                "file_url": file_url,
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Resume uploaded successfully",
            "filename": file.filename,
            "url": file_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload resume"
        )


@router.delete("/profile/resume")
async def delete_resume(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete user's resume"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete resume"
            )

        # Update profile to remove resume info
        update_query = """
            UPDATE profiles
            SET resume_uploaded = false,
                resume_filename = NULL,
                resume_url = NULL,
                updated_at = :updated_at
            WHERE user_id = :user_id
        """

        await database.execute(
            query=update_query,
            values={
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Resume deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resume"
        )


@router.get("/profile/completion")
async def get_profile_completion(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get profile completion status and suggestions"""
    try:
        query = "SELECT * FROM profiles WHERE user_id = :user_id"
        profile = await database.fetch_one(query=query, values={"user_id": current_user["id"]})

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        profile_dict = dict(profile)
        completion_percentage = calculate_profile_completion(profile_dict)

        # Generate completion suggestions
        suggestions = []
        if not profile_dict.get("full_name"):
            suggestions.append("Add your full name")
        if not profile_dict.get("phone_number"):
            suggestions.append("Add your phone number")
        if not profile_dict.get("job_title"):
            suggestions.append("Add your current or desired job title")
        if not profile_dict.get("years_experience"):
            suggestions.append("Add your years of experience")
        if not profile_dict.get("desired_salary"):
            suggestions.append("Add your desired salary")
        if not profile_dict.get("work_type") or not len(profile_dict.get("work_type", [])):
            suggestions.append("Specify your preferred work type (remote, hybrid, on-site)")
        if not profile_dict.get("location_preferences") or not len(profile_dict.get("location_preferences", [])):
            suggestions.append("Add your location preferences")
        if not profile_dict.get("education_level"):
            suggestions.append("Add your education level")
        if not profile_dict.get("resume_uploaded"):
            suggestions.append("Upload your resume")
        if profile_dict.get("work_authorization") is None:
            suggestions.append("Specify your work authorization status")

        return {
            "completion_percentage": completion_percentage,
            "suggestions": suggestions,
            "fields_completed": 10 - len(suggestions),
            "total_fields": 10
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile completion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile completion"
        )