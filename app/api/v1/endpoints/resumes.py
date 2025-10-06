"""
Resume Management - Upload, parse, optimize for ATS
"""

import os
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime

from app.core.database_new import get_db
from app.services.cv_parser_service import CVParserService
from app.core.security import get_current_user
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter()


def process_resume_background(resume_id: str, user_id: str, file_url: str, filename: str, db):
    """
    Background task to process resume with retry logic
    Downloads from S3, parses, and updates database
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info(f"Processing resume {resume_id} (attempt {retry_count + 1}/{max_retries})")

            # Download resume from S3
            file_content = storage_service.download_resume(file_url)

            # Save temporarily for parsing
            temp_path = f"/tmp/resume_processing_{resume_id}.pdf"
            with open(temp_path, 'wb') as f:
                f.write(file_content)

            # Parse resume
            cv_parser = CVParserService(db)

            # Extract text
            resume_text = cv_parser.extract_text_from_pdf(temp_path)

            # Parse with AI
            parsed_data = cv_parser.parse_resume_with_ai(resume_text)

            # Calculate ATS score
            ats_analysis = cv_parser.calculate_ats_score(resume_text)

            # Update resume document with parsed data
            db.resumes.update_one(
                {"_id": ObjectId(resume_id)},
                {
                    "$set": {
                        "raw_text": resume_text,
                        "parsed_data": parsed_data,
                        "ats_score": ats_analysis["score"],
                        "ats_grade": ats_analysis["grade"],
                        "ats_analysis": ats_analysis,
                        "status": "completed",
                        "retry_count": retry_count,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

            logger.info(f"Successfully processed resume {resume_id} with ATS score: {ats_analysis['score']}")
            return  # Success, exit the retry loop

        except Exception as e:
            retry_count += 1
            logger.error(f"Error processing resume {resume_id} (attempt {retry_count}/{max_retries}): {str(e)}")

            if retry_count >= max_retries:
                # Final failure after all retries
                db.resumes.update_one(
                    {"_id": ObjectId(resume_id)},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "retry_count": retry_count,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.error(f"Failed to process resume {resume_id} after {max_retries} attempts")
            else:
                # Wait before retry (exponential backoff)
                import time
                time.sleep(2 ** retry_count)  # 2, 4, 8 seconds


class ResumeResponse(BaseModel):
    """Resume with parsed data and ATS score"""
    id: str
    filename: str
    status: str  # "processing", "completed", "failed"
    ats_score: float | None = None
    ats_grade: str | None = None
    parsed_data: dict | None = None
    ats_analysis: dict | None = None
    is_primary: bool
    created_at: str
    error: str | None = None

    class Config:
        from_attributes = True


class TailoredResumeRequest(BaseModel):
    """Request to generate job-specific resume"""
    job_id: str


class TailoredResumeResponse(BaseModel):
    """Tailored resume with improvement stats"""
    id: str
    job_id: str
    optimized_text: str
    original_ats_score: float
    optimized_ats_score: float
    improvement: float
    created_at: str


@router.post("/upload-guest")
async def upload_resume_guest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = None,
    db = Depends(get_db)
):
    """
    Upload resume for guest users during upselling flow
    Does not require authentication - uses session_id from guest onboarding
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # For guest users, use session_id as temporary user_id
    user_id = session_id or "guest_temp"

    try:
        # Read file content
        file_content = await file.read()

        # Upload to storage (using session_id as user identifier)
        file_url = storage_service.upload_resume(
            file_content=file_content,
            user_id=user_id,
            filename=file.filename,
            content_type='application/pdf'
        )

        logger.info(f"Uploaded guest resume to storage: {file_url}")

        # Create resume document with "processing" status
        # We'll link this to the actual user later when they complete signup
        resume_doc = {
            "session_id": session_id,  # Store session_id to link later
            "user_id": None,  # Will be set when user completes signup
            "filename": file.filename,
            "file_url": file_url,
            "status": "processing",
            "is_primary": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = db.resumes.insert_one(resume_doc)
        resume_id = str(result.inserted_id)

        # Trigger background processing
        background_tasks.add_task(
            process_resume_background,
            resume_id=resume_id,
            user_id=user_id,
            file_url=file_url,
            filename=file.filename,
            db=db
        )

        logger.info(f"Guest resume uploaded, processing in background")

        return ResumeResponse(
            id=resume_id,
            filename=file.filename,
            status="processing",
            is_primary=True,
            created_at=resume_doc["created_at"].isoformat()
        )

    except Exception as e:
        logger.error(f"Error uploading guest resume: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not upload resume: {str(e)}")


@router.post("/upload", response_model=ResumeResponse)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Upload resume to S3 and process in background with retry logic
    Returns immediately with processing status
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Read file content
        file_content = await file.read()

        # Upload to S3/R2 storage
        file_url = storage_service.upload_resume(
            file_content=file_content,
            user_id=current_user["id"],
            filename=file.filename,
            content_type='application/pdf'
        )

        logger.info(f"Uploaded resume to storage: {file_url}")

        # Set all other resumes as non-primary
        db.resumes.update_many(
            {"user_id": ObjectId(current_user["id"])},
            {"$set": {"is_primary": False}}
        )

        # Create resume document with "processing" status
        resume_doc = {
            "user_id": ObjectId(current_user["id"]),
            "filename": file.filename,
            "file_url": file_url,  # S3 URL instead of local path
            "status": "processing",
            "is_primary": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = db.resumes.insert_one(resume_doc)
        resume_id = str(result.inserted_id)

        # Trigger background processing with retry logic
        background_tasks.add_task(
            process_resume_background,
            resume_id=resume_id,
            user_id=current_user["id"],
            file_url=file_url,
            filename=file.filename,
            db=db
        )

        logger.info(f"Resume uploaded for user {current_user['id']}, processing in background with retries")

        return ResumeResponse(
            id=resume_id,
            filename=file.filename,
            status="processing",
            is_primary=True,
            created_at=resume_doc["created_at"].isoformat()
        )

    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not upload resume: {str(e)}")


@router.get("/", response_model=List[ResumeResponse])
async def get_resumes(
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get all resumes for current user
    """
    resumes = list(
        db.resumes.find({"user_id": ObjectId(current_user["id"])})
        .sort("created_at", -1)
    )

    return [
        ResumeResponse(
            id=str(resume["_id"]),
            filename=resume["filename"],
            status=resume.get("status", "completed"),
            ats_score=resume.get("ats_score"),
            ats_grade=resume.get("ats_grade"),
            parsed_data=resume.get("parsed_data"),
            ats_analysis=resume.get("ats_analysis"),
            is_primary=resume.get("is_primary", False),
            created_at=resume["created_at"].isoformat(),
            error=resume.get("error")
        )
        for resume in resumes
    ]


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get specific resume by ID (check status for processing completion)
    """
    resume = db.resumes.find_one({
        "_id": ObjectId(resume_id),
        "user_id": ObjectId(current_user["id"])
    })

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    return ResumeResponse(
        id=str(resume["_id"]),
        filename=resume["filename"],
        status=resume.get("status", "completed"),
        ats_score=resume.get("ats_score"),
        ats_grade=resume.get("ats_grade"),
        parsed_data=resume.get("parsed_data"),
        ats_analysis=resume.get("ats_analysis"),
        is_primary=resume.get("is_primary", False),
        created_at=resume["created_at"].isoformat(),
        error=resume.get("error")
    )


@router.post("/{resume_id}/set-primary")
async def set_primary_resume(
    resume_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Set resume as primary (used for auto-apply)
    """
    # Verify resume belongs to user
    resume = db.resumes.find_one({
        "_id": ObjectId(resume_id),
        "user_id": ObjectId(current_user["id"])
    })

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Set all resumes as non-primary
    db.resumes.update_many(
        {"user_id": ObjectId(current_user["id"])},
        {"$set": {"is_primary": False}}
    )

    # Set this resume as primary
    db.resumes.update_one(
        {"_id": ObjectId(resume_id)},
        {"$set": {"is_primary": True}}
    )

    return {"message": "Primary resume updated"}


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Delete resume
    """
    resume = db.resumes.find_one({
        "_id": ObjectId(resume_id),
        "user_id": ObjectId(current_user["id"])
    })

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Delete file
    if os.path.exists(resume["file_path"]):
        os.remove(resume["file_path"])

    # Delete from database
    db.resumes.delete_one({"_id": ObjectId(resume_id)})

    return {"message": "Resume deleted"}


@router.post("/tailor", response_model=TailoredResumeResponse)
async def generate_tailored_resume(
    request: TailoredResumeRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Generate job-specific optimized resume
    Uses AI to tailor resume for specific job posting
    """
    try:
        cv_parser = CVParserService(db)
        tailored_resume = cv_parser.generate_tailored_resume(
            user_id=current_user["id"],
            job_id=request.job_id
        )

        return TailoredResumeResponse(
            id=str(tailored_resume["_id"]),
            job_id=str(tailored_resume["job_id"]),
            optimized_text=tailored_resume["optimized_text"],
            original_ats_score=tailored_resume["original_ats_score"],
            optimized_ats_score=tailored_resume["optimized_ats_score"],
            improvement=tailored_resume["improvement"],
            created_at=tailored_resume["created_at"].isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating tailored resume: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{resume_id}/analyze")
async def analyze_resume_for_job(
    resume_id: str,
    job_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Analyze how well resume matches a specific job
    Returns ATS score for this job
    """
    # Get resume
    resume = db.resumes.find_one({
        "_id": ObjectId(resume_id),
        "user_id": ObjectId(current_user["id"])
    })

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Get job
    job = db.jobs.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Build job description
    job_description = f"""
{job.get('title', '')}
{job.get('description', '')}

Required Skills: {', '.join(job.get('skills_required', []))}
Experience Required: {job.get('experience_years_min', 0)}+ years
"""

    # Calculate ATS score for this job
    cv_parser = CVParserService(db)
    ats_analysis = cv_parser.calculate_ats_score(
        resume["raw_text"],
        job_description
    )

    return {
        "resume_id": resume_id,
        "job_id": job_id,
        "ats_score": ats_analysis["score"],
        "grade": ats_analysis["grade"],
        "issues": ats_analysis["issues"],
        "recommendations": ats_analysis["recommendations"]
    }
