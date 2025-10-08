"""
Cover Letter Generation API endpoints
Handles AI-powered cover letter generation and management
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, validator
import logging
import re

from app.core.database_new import get_async_db
from app.core.security import get_current_user
from app.core.security import PermissionChecker
from app.services.ai_client import get_ai_client

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class CoverLetterRequest(BaseModel):
    fullName: str
    city: Optional[str] = ""
    phoneNumber: Optional[str] = ""
    emailAddress: EmailStr
    desiredPosition: str
    companyName: str
    jobDetails: str
    writingStyle: Optional[str] = "professional"

    @validator('fullName', 'desiredPosition', 'companyName', 'jobDetails')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('This field is required')
        return v.strip()

    @validator('emailAddress')
    def validate_email_format(cls, v):
        email_regex = r'\S+@\S+\.\S+'
        if not re.match(email_regex, v):
            raise ValueError('Please enter a valid email address')
        return v.lower().strip()


class CoverLetterResponse(BaseModel):
    content: str
    ai_generated: bool
    model: str
    id: Optional[str] = None


class CoverLetterListResponse(BaseModel):
    id: str
    title: str
    content: str
    is_ai_generated: bool
    ai_model_version: Optional[str]
    created_at: datetime
    updated_at: datetime


def sanitize(input_str: str) -> str:
    """Remove control characters and trim whitespace"""
    if not input_str:
        return ""
    return re.sub(r'[\u0000-\u001F\u007F]+', '', str(input_str)).strip()


def generate_basic_cover_letter(payload: CoverLetterRequest) -> str:
    """Generate a basic template cover letter as fallback"""
    contact_info = []
    if payload.phoneNumber:
        contact_info.append(payload.phoneNumber)
    if payload.city:
        contact_info.append(payload.city)

    contact_line = '\n' + '\n'.join(contact_info) if contact_info else ''

    return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {payload.desiredPosition} position at {payload.companyName}. With my background and passion for this field, I am confident I would be a valuable addition to your team.

Based on the job description, I believe my skills and experience align well with your requirements. I am particularly excited about the opportunity to contribute to {payload.companyName} and help achieve your goals. My professional approach and dedication to excellence make me an ideal candidate for this role.

I would welcome the opportunity to discuss how my background and enthusiasm can benefit your organization. Thank you for considering my application. I look forward to hearing from you soon.

Sincerely,
{payload.fullName}
{payload.emailAddress}{contact_line}"""


@router.post("/generate", response_model=CoverLetterResponse)
async def generate_cover_letter(
    request: CoverLetterRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate a personalized cover letter using AI"""
    try:
        if not permission_checker.has_permission(current_user, "cover_letters", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to generate cover letters"
            )

        # Clean and sanitize input data
        cleaned_request = CoverLetterRequest(
            fullName=sanitize(request.fullName),
            city=sanitize(request.city),
            phoneNumber=sanitize(request.phoneNumber),
            emailAddress=request.emailAddress,
            desiredPosition=sanitize(request.desiredPosition),
            companyName=sanitize(request.companyName),
            jobDetails=sanitize(request.jobDetails),
            writingStyle=sanitize(request.writingStyle or "professional")
        )

        content = ""
        ai_generated = False
        model_used = "basic-template"

        try:
            # Try to use AI client for cover letter generation
            ai_client = get_ai_client()

            prompt = f"""You are a professional career coach and expert cover letter writer. Write compelling, personalized cover letters that help candidates stand out.

Write a professional cover letter for the following job application:

CANDIDATE INFORMATION:
- Name: {cleaned_request.fullName}
- Location: {cleaned_request.city or 'N/A'}
- Email: {cleaned_request.emailAddress}
- Phone: {cleaned_request.phoneNumber or 'N/A'}
- Desired Position: {cleaned_request.desiredPosition}
- Target Company: {cleaned_request.companyName}
- Writing Style: {cleaned_request.writingStyle}

JOB DETAILS:
{cleaned_request.jobDetails}

REQUIREMENTS:
1. Keep it professional and concise (3-4 paragraphs, 250-400 words)
2. Start with "Dear Hiring Manager,"
3. Highlight relevant experience and skills based on job requirements
4. Show enthusiasm for the role and company
5. Include a strong opening and closing
6. Customize for this specific position and company
7. Do not include placeholders or [brackets]
8. Make it personal and engaging
9. End with "Sincerely," followed by the candidate's name
10. Return ONLY the cover letter text, no extra formatting or explanations"""

            ai_response = await ai_client.generate_text(prompt)
            if ai_response and ai_response.strip():
                content = ai_response.strip()
                ai_generated = True
                model_used = "openai-gpt-4"
            else:
                raise Exception("No content returned from AI")

        except Exception as ai_error:
            logger.warning(f"AI generation failed, using template: {str(ai_error)}")
            # Fallback to basic template
            content = generate_basic_cover_letter(cleaned_request)

        # Save cover letter to database
        cover_letter_id = None
        try:
            insert_query = """
                INSERT INTO cover_letters (
                    user_id, title, content, is_ai_generated, generation_prompt,
                    ai_model_version, generation_time_ms, status, created_at, updated_at
                ) VALUES (
                    :user_id, :title, :content, :is_ai_generated, :generation_prompt,
                    :ai_model_version, :generation_time_ms, :status, :created_at, :updated_at
                ) RETURNING id
            """

            values = {
                "user_id": current_user["id"],
                "title": f"Cover Letter - {cleaned_request.desiredPosition} at {cleaned_request.companyName}",
                "content": content,
                "is_ai_generated": ai_generated,
                "generation_prompt": "Standalone cover letter",
                "ai_model_version": model_used,
                "generation_time_ms": 1000,  # Placeholder
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await database.fetch_one(query=insert_query, values=values)
            if result:
                cover_letter_id = str(result["id"])

        except Exception as db_error:
            logger.error(f"Error saving cover letter to database: {str(db_error)}")
            # Continue even if database save fails

        return CoverLetterResponse(
            content=content,
            ai_generated=ai_generated,
            model=model_used,
            id=cover_letter_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cover letter"
        )


@router.get("/", response_model=List[CoverLetterListResponse])
async def get_cover_letters(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's cover letter history"""
    try:
        if not permission_checker.has_permission(current_user, "cover_letters", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read cover letters"
            )

        query = """
            SELECT id, title, content, is_ai_generated, ai_model_version, created_at, updated_at
            FROM cover_letters
            WHERE user_id = :user_id AND status = 'active'
            ORDER BY created_at DESC
        """

        cover_letters = await database.fetch_all(
            query=query,
            values={"user_id": current_user["id"]}
        )

        return [
            CoverLetterListResponse(
                id=str(cl["id"]),
                title=cl["title"],
                content=cl["content"],
                is_ai_generated=cl["is_ai_generated"],
                ai_model_version=cl["ai_model_version"],
                created_at=cl["created_at"],
                updated_at=cl["updated_at"]
            )
            for cl in cover_letters
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cover letters: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch cover letters"
        )


@router.get("/{cover_letter_id}", response_model=CoverLetterListResponse)
async def get_cover_letter(
    cover_letter_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific cover letter by ID"""
    try:
        if not permission_checker.has_permission(current_user, "cover_letters", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read cover letters"
            )

        query = """
            SELECT id, title, content, is_ai_generated, ai_model_version, created_at, updated_at
            FROM cover_letters
            WHERE id = :cover_letter_id AND user_id = :user_id AND status = 'active'
        """

        cover_letter = await database.fetch_one(
            query=query,
            values={"cover_letter_id": cover_letter_id, "user_id": current_user["id"]}
        )

        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found"
            )

        return CoverLetterListResponse(
            id=str(cover_letter["id"]),
            title=cover_letter["title"],
            content=cover_letter["content"],
            is_ai_generated=cover_letter["is_ai_generated"],
            ai_model_version=cover_letter["ai_model_version"],
            created_at=cover_letter["created_at"],
            updated_at=cover_letter["updated_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cover letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch cover letter"
        )


@router.delete("/{cover_letter_id}")
async def delete_cover_letter(
    cover_letter_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a cover letter"""
    try:
        if not permission_checker.has_permission(current_user, "cover_letters", "delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete cover letters"
            )

        # Check if cover letter exists and belongs to user
        check_query = """
            SELECT id FROM cover_letters
            WHERE id = :cover_letter_id AND user_id = :user_id AND status = 'active'
        """

        cover_letter = await database.fetch_one(
            query=check_query,
            values={"cover_letter_id": cover_letter_id, "user_id": current_user["id"]}
        )

        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found"
            )

        # Soft delete
        delete_query = """
            UPDATE cover_letters
            SET status = 'deleted', updated_at = :updated_at
            WHERE id = :cover_letter_id
        """

        await database.execute(
            query=delete_query,
            values={"cover_letter_id": cover_letter_id, "updated_at": datetime.utcnow()}
        )

        return {"success": True, "message": "Cover letter deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cover letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete cover letter"
        )