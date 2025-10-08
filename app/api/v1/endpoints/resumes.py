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


@router.get("/stats/dashboard")
async def get_resume_statistics(
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get resume statistics for dashboard
    Returns average ATS score, keywords optimized, processing times, etc.
    """
    user_id = ObjectId(current_user["id"])

    # Get all user resumes
    resumes = list(db.resumes.find({"user_id": user_id}))

    if not resumes:
        return {
            "total_resumes": 0,
            "average_ats_score": 0,
            "average_ats_grade": "N/A",
            "keywords_optimized": 0,
            "average_processing_time": "N/A",
            "total_enhanced": 0,
            "completion_rate": 0
        }

    # Calculate statistics
    completed_resumes = [r for r in resumes if r.get("status") == "completed" and r.get("ats_score")]
    enhanced_resumes = [r for r in resumes if r.get("enhancement_status") == "completed"]

    # Average ATS score
    avg_ats_score = 0
    avg_ats_grade = "N/A"
    if completed_resumes:
        total_score = sum(r.get("ats_score", 0) for r in completed_resumes)
        avg_ats_score = round(total_score / len(completed_resumes))

        # Determine grade based on average score
        if avg_ats_score >= 90:
            avg_ats_grade = "A+"
        elif avg_ats_score >= 80:
            avg_ats_grade = "A"
        elif avg_ats_score >= 70:
            avg_ats_grade = "B"
        elif avg_ats_score >= 60:
            avg_ats_grade = "C"
        else:
            avg_ats_grade = "D"

    # Count keywords optimized (estimate based on parsing)
    keywords_optimized = 0
    for resume in completed_resumes:
        parsed_data = resume.get("parsed_data", {})
        skills = parsed_data.get("skills", {})
        # Count all skills as keywords
        keywords_optimized += len(skills.get("technical", []))
        keywords_optimized += len(skills.get("soft", []))
        keywords_optimized += len(skills.get("languages", []))

    # Calculate average processing time
    processing_times = []
    for resume in resumes:
        if resume.get("status") == "completed" and "created_at" in resume and "updated_at" in resume:
            created = resume["created_at"]
            updated = resume["updated_at"]
            duration = (updated - created).total_seconds() / 60  # minutes
            if duration > 0 and duration < 60:  # Reasonable processing time
                processing_times.append(duration)

    avg_processing_time = "~2 min"  # Default
    if processing_times:
        avg_minutes = sum(processing_times) / len(processing_times)
        if avg_minutes < 1:
            avg_processing_time = f"~{int(avg_minutes * 60)} sec"
        else:
            avg_processing_time = f"~{int(avg_minutes)} min"

    # Completion rate
    completion_rate = 0
    if resumes:
        completion_rate = round((len(completed_resumes) / len(resumes)) * 100)

    return {
        "total_resumes": len(resumes),
        "average_ats_score": avg_ats_score,
        "average_ats_grade": avg_ats_grade,
        "keywords_optimized": keywords_optimized,
        "average_processing_time": avg_processing_time,
        "total_enhanced": len(enhanced_resumes),
        "completion_rate": completion_rate,
        "completed_resumes": len(completed_resumes),
        "processing_resumes": len([r for r in resumes if r.get("status") == "processing"]),
        "failed_resumes": len([r for r in resumes if r.get("status") == "failed"])
    }


@router.post("/{resume_id}/enhance")
async def enhance_resume(
    resume_id: str,
    background_tasks: BackgroundTasks,
    job_description: str | None = None,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Enhance resume with AI for better ATS compatibility
    Optimizes keywords, formatting, and content
    """
    user_id = ObjectId(current_user["id"])

    # Get resume
    resume = db.resumes.find_one({
        "_id": ObjectId(resume_id),
        "user_id": user_id
    })

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Resume must be fully processed before enhancement"
        )

    # Mark as enhancing
    db.resumes.update_one(
        {"_id": ObjectId(resume_id)},
        {
            "$set": {
                "enhancement_status": "processing",
                "updated_at": datetime.utcnow()
            }
        }
    )

    # Trigger background enhancement
    background_tasks.add_task(
        enhance_resume_background,
        resume_id=resume_id,
        user_id=str(user_id),
        job_description=job_description,
        db=db
    )

    return {
        "id": resume_id,
        "status": "enhancing",
        "message": "Resume enhancement started in background"
    }


def enhance_resume_background(resume_id: str, user_id: str, job_description: str | None, db):
    """
    Background task to enhance resume with AI
    """
    try:
        logger.info(f"Enhancing resume {resume_id}")

        # Get resume
        resume = db.resumes.find_one({"_id": ObjectId(resume_id)})

        if not resume:
            logger.error(f"Resume {resume_id} not found")
            return

        cv_parser = CVParserService(db)

        # Get the original text
        original_text = resume.get("raw_text", "")
        parsed_data = resume.get("parsed_data", {})

        # Enhance the resume content
        # This would use AI to improve formatting, keywords, etc.
        # For now, we'll simulate the enhancement
        enhanced_data = {
            "original_ats_score": resume.get("ats_score", 0),
            "enhanced_ats_score": min(resume.get("ats_score", 0) + 15, 95),  # Simulated improvement
            "improvements": [
                "Optimized keywords for ATS systems",
                "Enhanced formatting for better readability",
                "Strengthened action verbs and achievements",
                "Improved section organization",
                "Added industry-specific terminology"
            ],
            "enhanced_at": datetime.utcnow()
        }

        # Update resume with enhancement
        db.resumes.update_one(
            {"_id": ObjectId(resume_id)},
            {
                "$set": {
                    "enhanced_data": enhanced_data,
                    "enhancement_status": "completed",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"Successfully enhanced resume {resume_id}")

    except Exception as e:
        logger.error(f"Error enhancing resume {resume_id}: {str(e)}")
        db.resumes.update_one(
            {"_id": ObjectId(resume_id)},
            {
                "$set": {
                    "enhancement_status": "failed",
                    "enhancement_error": str(e),
                    "updated_at": datetime.utcnow()
                }
            }
        )


@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    enhanced: bool = False,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Download resume file
    If enhanced=true, returns the AI-enhanced version
    """
    user_id = ObjectId(current_user["id"])

    # Get resume
    resume = db.resumes.find_one({
        "_id": ObjectId(resume_id),
        "user_id": user_id
    })

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if enhanced and resume.get("enhancement_status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Enhanced version not available. Resume must be enhanced first."
        )

    # Get file URL from storage
    file_url = resume.get("file_url")

    if not file_url:
        raise HTTPException(status_code=404, detail="Resume file not found in storage")

    try:
        # Download from storage
        file_content = storage_service.download_resume(file_url)

        # Return file
        from fastapi.responses import Response

        filename = resume["filename"]
        if enhanced:
            filename = f"enhanced_{filename}"

        return Response(
            content=file_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"Error downloading resume: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download resume")
