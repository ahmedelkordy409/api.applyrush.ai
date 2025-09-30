"""
Resume Management API endpoints
Handles resume upload, parsing, and management
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import logging
import base64
import uuid

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class ResumeResponse(BaseModel):
    id: str
    original_filename: str
    file_size: int
    file_type: str
    uploaded_at: datetime
    status: str
    is_current: bool


class ResumeUploadResponse(BaseModel):
    success: bool
    resume: ResumeResponse
    message: str


@router.get("/", response_model=List[ResumeResponse])
async def get_resumes(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's resume list"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read resumes"
            )

        # Get user's current resume ID from profile
        profile_query = """
            SELECT current_resume_id
            FROM profiles
            WHERE user_id = :user_id
        """
        profile = await database.fetch_one(
            query=profile_query,
            values={"user_id": current_user["id"]}
        )

        current_resume_id = profile["current_resume_id"] if profile else None

        # Get all resumes
        query = """
            SELECT id, original_filename, file_size, file_type, uploaded_at, status
            FROM resumes
            WHERE user_id = :user_id AND status != 'deleted'
            ORDER BY uploaded_at DESC
        """

        resumes = await database.fetch_all(
            query=query,
            values={"user_id": current_user["id"]}
        )

        return [
            ResumeResponse(
                id=str(resume["id"]),
                original_filename=resume["original_filename"],
                file_size=resume["file_size"],
                file_type=resume["file_type"],
                uploaded_at=resume["uploaded_at"],
                status=resume["status"],
                is_current=str(resume["id"]) == str(current_resume_id)
            )
            for resume in resumes
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching resumes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch resumes"
        )


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    make_current: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload a new resume"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to upload resumes"
            )

        # Validate file type
        allowed_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Please upload PDF or Word document."
            )

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size too large. Maximum 10MB allowed."
            )

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
        }.get(file.content_type, '.pdf')

        stored_filename = f"{file_id}{file_extension}"

        # Encode file content as base64 for storage
        file_content_b64 = base64.b64encode(file_content).decode()

        # Store resume in database
        resume_query = """
            INSERT INTO resumes (
                user_id, original_filename, stored_filename, file_content,
                file_type, file_size, uploaded_at, status
            ) VALUES (
                :user_id, :original_filename, :stored_filename, :file_content,
                :file_type, :file_size, :uploaded_at, :status
            ) RETURNING id
        """

        values = {
            "user_id": current_user["id"],
            "original_filename": file.filename,
            "stored_filename": stored_filename,
            "file_content": file_content_b64,
            "file_type": file.content_type,
            "file_size": len(file_content),
            "uploaded_at": datetime.utcnow(),
            "status": "active"
        }

        result = await database.fetch_one(query=resume_query, values=values)
        resume_id = result["id"]

        # Update profile if this should be the current resume
        if make_current:
            profile_query = """
                UPDATE profiles
                SET resume_uploaded = true, current_resume_id = :resume_id, updated_at = :updated_at
                WHERE user_id = :user_id
            """

            await database.execute(
                query=profile_query,
                values={
                    "resume_id": resume_id,
                    "updated_at": datetime.utcnow(),
                    "user_id": current_user["id"]
                }
            )

        resume_response = ResumeResponse(
            id=str(resume_id),
            original_filename=file.filename,
            file_size=len(file_content),
            file_type=file.content_type,
            uploaded_at=datetime.utcnow(),
            status="active",
            is_current=make_current
        )

        return ResumeUploadResponse(
            success=True,
            resume=resume_response,
            message="Resume uploaded successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload resume"
        )


@router.get("/{resume_id}")
async def get_resume(
    resume_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get resume details"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read resumes"
            )

        query = """
            SELECT id, original_filename, file_size, file_type, uploaded_at, status
            FROM resumes
            WHERE id = :resume_id AND user_id = :user_id AND status != 'deleted'
        """

        resume = await database.fetch_one(
            query=query,
            values={"resume_id": resume_id, "user_id": current_user["id"]}
        )

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Check if this is the current resume
        profile_query = """
            SELECT current_resume_id
            FROM profiles
            WHERE user_id = :user_id
        """
        profile = await database.fetch_one(
            query=profile_query,
            values={"user_id": current_user["id"]}
        )

        is_current = profile and str(profile["current_resume_id"]) == str(resume["id"])

        return ResumeResponse(
            id=str(resume["id"]),
            original_filename=resume["original_filename"],
            file_size=resume["file_size"],
            file_type=resume["file_type"],
            uploaded_at=resume["uploaded_at"],
            status=resume["status"],
            is_current=is_current
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch resume"
        )


@router.post("/{resume_id}/set-current")
async def set_current_resume(
    resume_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Set a resume as the current active resume"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update resumes"
            )

        # Check if resume exists and belongs to user
        check_query = """
            SELECT id FROM resumes
            WHERE id = :resume_id AND user_id = :user_id AND status = 'active'
        """

        resume = await database.fetch_one(
            query=check_query,
            values={"resume_id": resume_id, "user_id": current_user["id"]}
        )

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Update profile to set current resume
        profile_query = """
            UPDATE profiles
            SET current_resume_id = :resume_id, updated_at = :updated_at
            WHERE user_id = :user_id
        """

        await database.execute(
            query=profile_query,
            values={
                "resume_id": resume_id,
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Resume set as current successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting current resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set current resume"
        )


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a resume"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete resumes"
            )

        # Check if resume exists and belongs to user
        check_query = """
            SELECT id FROM resumes
            WHERE id = :resume_id AND user_id = :user_id AND status != 'deleted'
        """

        resume = await database.fetch_one(
            query=check_query,
            values={"resume_id": resume_id, "user_id": current_user["id"]}
        )

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Check if this is the current resume
        profile_query = """
            SELECT current_resume_id
            FROM profiles
            WHERE user_id = :user_id
        """
        profile = await database.fetch_one(
            query=profile_query,
            values={"user_id": current_user["id"]}
        )

        # Soft delete the resume
        delete_query = """
            UPDATE resumes
            SET status = 'deleted', updated_at = :updated_at
            WHERE id = :resume_id
        """

        await database.execute(
            query=delete_query,
            values={"updated_at": datetime.utcnow(), "resume_id": resume_id}
        )

        # If this was the current resume, clear it from profile
        if profile and str(profile["current_resume_id"]) == str(resume_id):
            clear_query = """
                UPDATE profiles
                SET current_resume_id = NULL, resume_uploaded = false, updated_at = :updated_at
                WHERE user_id = :user_id
            """

            await database.execute(
                query=clear_query,
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


@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Download resume file"""
    try:
        if not permission_checker.has_permission(current_user, "resumes", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to download resumes"
            )

        query = """
            SELECT original_filename, file_content, file_type
            FROM resumes
            WHERE id = :resume_id AND user_id = :user_id AND status = 'active'
        """

        resume = await database.fetch_one(
            query=query,
            values={"resume_id": resume_id, "user_id": current_user["id"]}
        )

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Decode base64 content
        file_content = base64.b64decode(resume["file_content"])

        from fastapi.responses import Response

        return Response(
            content=file_content,
            media_type=resume["file_type"],
            headers={
                "Content-Disposition": f"attachment; filename={resume['original_filename']}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download resume"
        )