"""
Job Matching API - Uses onboarding data to find relevant jobs
Connects user preferences → job filtering → AI matching → auto-apply queue
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.core.database_new import get_db, Collections, serialize_doc
from app.core.security import get_current_user

router = APIRouter()


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class JobMatchResponse(BaseModel):
    """Single job match with score and reasons"""
    job_id: str
    job_title: str
    company_name: str
    location: str
    remote_type: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    match_score: float  # 0-100
    match_reasons: List[str]
    skills_matched: List[str]
    skills_missing: List[str]
    experience_match: bool
    salary_match: bool
    location_match: bool


class JobMatchListResponse(BaseModel):
    """List of matched jobs"""
    total_matches: int
    matches: List[JobMatchResponse]
    filters_applied: dict


# ============================================
# JOB MATCHING ALGORITHM
# ============================================

def calculate_match_score(job: dict, user_preferences: dict, user_onboarding: dict) -> dict:
    """
    Calculate match score based on:
    - Job title match (30%)
    - Skills match (25%)
    - Location match (20%)
    - Salary match (15%)
    - Experience match (10%)
    """

    score = 0.0
    reasons = []
    skills_matched = []
    skills_missing = []

    # 1. JOB TITLE MATCH (30 points)
    job_title = job.get("title", "").lower()
    desired_positions = [p.lower() for p in user_preferences.get("desired_positions", [])]

    title_match = any(pos in job_title or job_title in pos for pos in desired_positions)
    if title_match:
        score += 30
        reasons.append(f"Title matches your desired positions")

    # 2. SKILLS MATCH (25 points)
    job_skills = set([s.lower() for s in job.get("skills_required", [])])
    user_skills = set([s.lower() for s in user_preferences.get("skills", [])])

    if job_skills and user_skills:
        matched_skills = job_skills.intersection(user_skills)
        missing_skills = job_skills.difference(user_skills)

        skills_matched = list(matched_skills)
        skills_missing = list(missing_skills)

        skill_match_percentage = len(matched_skills) / len(job_skills) if job_skills else 0
        skill_score = skill_match_percentage * 25
        score += skill_score

        if skill_match_percentage > 0.7:
            reasons.append(f"Strong skills match ({len(matched_skills)}/{len(job_skills)} skills)")
        elif skill_match_percentage > 0.4:
            reasons.append(f"Good skills match ({len(matched_skills)}/{len(job_skills)} skills)")

    # 3. LOCATION MATCH (20 points)
    job_location = job.get("location", "").lower()
    job_remote_type = job.get("remote_type", "").lower()
    preferred_locations = [l.lower() for l in user_preferences.get("preferred_locations", [])]
    remote_preference = user_preferences.get("remote_preference", "").lower()
    relocation_willing = user_preferences.get("relocation_willing", False)

    location_match = False

    # Check remote match
    if remote_preference == "remote" and job_remote_type in ["remote", "flexible"]:
        score += 20
        reasons.append("Remote work available")
        location_match = True
    # Check hybrid match
    elif remote_preference == "hybrid" and job_remote_type in ["hybrid", "flexible"]:
        score += 20
        reasons.append("Hybrid work available")
        location_match = True
    # Check location match
    elif any(loc in job_location or job_location in loc for loc in preferred_locations):
        score += 20
        reasons.append(f"Location matches your preferences")
        location_match = True
    # Check if willing to relocate
    elif relocation_willing:
        score += 10
        reasons.append("Relocation possible")
        location_match = True

    # 4. SALARY MATCH (15 points)
    salary_match = False
    job_salary_min = job.get("salary_min")
    job_salary_max = job.get("salary_max")
    user_salary_min = user_preferences.get("salary_min")
    user_salary_max = user_preferences.get("salary_max")

    if job_salary_min and user_salary_min:
        if job_salary_min >= user_salary_min:
            score += 15
            reasons.append(f"Salary meets your minimum (${job_salary_min:,}+)")
            salary_match = True
        elif job_salary_max and job_salary_max >= user_salary_min:
            score += 10
            reasons.append(f"Salary range overlaps with your expectations")
            salary_match = True

    # 5. EXPERIENCE MATCH (10 points)
    experience_match = False
    job_experience_required = job.get("experience_years_min", 0)
    user_experience = user_onboarding.get("years_of_experience", 0)

    if user_experience >= job_experience_required:
        score += 10
        reasons.append(f"You meet the experience requirement ({user_experience} years)")
        experience_match = True
    elif user_onboarding.get("experience_exceptional", False):
        score += 10
        reasons.append("Your exceptional experience compensates")
        experience_match = True
    elif user_experience >= job_experience_required - 1:
        score += 5
        reasons.append("Close to experience requirement")

    return {
        "score": round(score, 1),
        "reasons": reasons,
        "skills_matched": skills_matched,
        "skills_missing": skills_missing,
        "experience_match": experience_match,
        "salary_match": salary_match,
        "location_match": location_match,
    }


# ============================================
# ENDPOINTS
# ============================================

@router.get("/jobs", response_model=JobMatchListResponse)
async def get_matched_jobs(
    min_score: int = Query(55, ge=0, le=100, description="Minimum match score"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get matched jobs based on user's onboarding preferences

    This endpoint:
    1. Loads user preferences from onboarding data
    2. Filters jobs based on hard requirements
    3. Calculates match score for each job
    4. Returns sorted list of matches
    """

    user_id = ObjectId(current_user["id"])

    # Get user data
    user = db[Collections.USERS].find_one({"_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_preferences = user.get("job_preferences", {})
    user_onboarding = user.get("onboarding", {})

    if not user_preferences.get("desired_positions"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete onboarding first to set your job preferences"
        )

    # Build MongoDB query with filters from onboarding data
    query = {
        "status": "active",
    }

    # Filter by work authorization if needed
    if user_onboarding.get("visa_sponsorship_needed"):
        # Only show jobs that offer visa sponsorship
        query["visa_sponsorship"] = True

    # Filter by excluded companies
    excluded_companies = user_preferences.get("excluded_companies", [])
    if excluded_companies:
        query["company_name"] = {"$nin": excluded_companies}

    # Filter by employment type
    employment_types = user_preferences.get("employment_types", [])
    if employment_types:
        query["employment_type"] = {"$in": employment_types}

    # Get jobs from database
    jobs = list(db[Collections.JOBS].find(query).limit(limit * 2))  # Get more for filtering

    # Calculate match scores
    matches = []
    for job in jobs:
        match_data = calculate_match_score(job, user_preferences, user_onboarding)

        # Only include if meets minimum score
        if match_data["score"] >= min_score:
            matches.append(JobMatchResponse(
                job_id=str(job["_id"]),
                job_title=job.get("title", ""),
                company_name=job.get("company_name", ""),
                location=job.get("location", ""),
                remote_type=job.get("remote_type", "onsite"),
                salary_min=job.get("salary_min"),
                salary_max=job.get("salary_max"),
                match_score=match_data["score"],
                match_reasons=match_data["reasons"],
                skills_matched=match_data["skills_matched"],
                skills_missing=match_data["skills_missing"],
                experience_match=match_data["experience_match"],
                salary_match=match_data["salary_match"],
                location_match=match_data["location_match"],
            ))

    # Sort by match score (highest first)
    matches.sort(key=lambda x: x.match_score, reverse=True)

    # Limit results
    matches = matches[:limit]

    # Save matches to database for future reference
    for match in matches:
        match_doc = {
            "user_id": user_id,
            "job_id": ObjectId(match.job_id),
            "match_score": match.match_score,
            "match_reasons": match.match_reasons,
            "skills_matched": match.skills_matched,
            "skills_missing": match.skills_missing,
            "status": "pending",  # pending, approved, rejected, applied
            "created_at": datetime.utcnow(),
        }

        # Upsert (update or insert)
        db[Collections.JOB_MATCHES].update_one(
            {
                "user_id": user_id,
                "job_id": ObjectId(match.job_id)
            },
            {"$set": match_doc},
            upsert=True
        )

    return JobMatchListResponse(
        total_matches=len(matches),
        matches=matches,
        filters_applied={
            "min_score": min_score,
            "visa_sponsorship_needed": user_onboarding.get("visa_sponsorship_needed", False),
            "employment_types": employment_types,
            "excluded_companies": excluded_companies,
            "desired_positions": user_preferences.get("desired_positions", []),
            "preferred_locations": user_preferences.get("preferred_locations", []),
        }
    )


@router.post("/approve/{job_id}")
async def approve_job_match(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Approve a job match - adds to auto-apply queue
    """

    user_id = ObjectId(current_user["id"])

    # Update match status
    result = db[Collections.JOB_MATCHES].update_one(
        {
            "user_id": user_id,
            "job_id": ObjectId(job_id)
        },
        {
            "$set": {
                "status": "approved",
                "approved_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job match not found"
        )

    # Add to auto-apply queue (if auto-apply is enabled)
    user = db[Collections.USERS].find_one({"_id": user_id})
    if user.get("settings", {}).get("browser_auto_apply", False):
        # Add to queue for auto-apply
        # This will be processed by Celery worker
        pass

    return {
        "success": True,
        "message": "Job approved for application"
    }


@router.post("/reject/{job_id}")
async def reject_job_match(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Reject a job match"""

    user_id = ObjectId(current_user["id"])

    result = db[Collections.JOB_MATCHES].update_one(
        {
            "user_id": user_id,
            "job_id": ObjectId(job_id)
        },
        {
            "$set": {
                "status": "rejected",
                "rejected_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job match not found"
        )

    return {
        "success": True,
        "message": "Job rejected"
    }
