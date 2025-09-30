"""
Job-related API endpoints
Handles job search, fetching, and management
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json

from app.services.job_fetcher import job_fetcher, JobSource
from app.services.job_matcher import job_matching_engine, MatchingStrategy
from app.workers.job_tasks import fetch_jobs_for_user, match_user_to_existing_jobs
from app.core.database import get_database
import structlog

logger = structlog.get_logger()

router = APIRouter()


# Pydantic models for request/response
class JobSearchRequest(BaseModel):
    query: str = Field(..., description="Job search query")
    location: str = Field("", description="Job location")
    remote_only: bool = Field(False, description="Remote jobs only")
    page: int = Field(1, ge=1, description="Page number")
    num_pages: int = Field(1, ge=1, le=5, description="Number of pages to fetch")
    employment_types: List[str] = Field(["FULLTIME"], description="Employment types")
    salary_min: Optional[int] = Field(None, description="Minimum salary")
    salary_max: Optional[int] = Field(None, description="Maximum salary")
    date_posted: str = Field("all", description="Date posted filter")


class JobResponse(BaseModel):
    id: str
    title: str
    company: Dict[str, Any]
    description: str
    location: Dict[str, Any]
    salary_range: Optional[str]
    employment_type: str
    remote_option: str
    posted_date: Optional[datetime]
    application_url: Optional[str]
    source: str


class JobSearchResponse(BaseModel):
    success: bool
    jobs: List[JobResponse]
    total_count: int
    page: int
    has_more: bool
    search_params: Dict[str, Any]


class JobMatchRequest(BaseModel):
    job_ids: List[str] = Field(..., description="Job IDs to match against")
    user_id: int = Field(..., description="User ID for matching")
    strategy: str = Field("hybrid", description="Matching strategy")


@router.post("/search", response_model=JobSearchResponse)
async def search_jobs(
    search_request: JobSearchRequest,
    background_tasks: BackgroundTasks
) -> JobSearchResponse:
    """
    Search for jobs using JSearch API
    """
    try:
        logger.info("Job search request", query=search_request.query, location=search_request.location)
        
        # Perform job search
        result = await job_fetcher.search_jobs(
            query=search_request.query,
            location=search_request.location,
            remote_only=search_request.remote_only,
            page=search_request.page,
            num_pages=search_request.num_pages,
            employment_types=search_request.employment_types,
            salary_min=search_request.salary_min,
            salary_max=search_request.salary_max,
            date_posted=search_request.date_posted
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail="Job search failed")
        
        # Convert to response format
        job_responses = []
        for job in result["jobs"]:
            job_response = JobResponse(
                id=job.get("external_id", ""),
                title=job.get("title", ""),
                company=job.get("company", {}),
                description=job.get("description", ""),
                location=job.get("location", {}),
                salary_range=_format_salary_range(job.get("salary_min"), job.get("salary_max")),
                employment_type=job.get("employment_type", ""),
                remote_option=job.get("remote_option", "no"),
                posted_date=job.get("posted_date"),
                application_url=job.get("application_url"),
                source=job.get("source", "")
            )
            job_responses.append(job_response)
        
        return JobSearchResponse(
            success=True,
            jobs=job_responses,
            total_count=result["total_count"],
            page=search_request.page,
            has_more=len(job_responses) >= 20,  # Assume more if we got full page
            search_params=result["search_params"]
        )
        
    except Exception as e:
        logger.error("Job search error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job_details(job_id: str):
    """
    Get detailed information about a specific job
    """
    try:
        # First check database
        database = await get_database()
        db_job = await database.fetch_one(
            "SELECT * FROM jobs WHERE external_id = :job_id",
            {"job_id": job_id}
        )
        
        if db_job:
            job_data = dict(db_job)
            # Parse JSON fields
            job_data["location"] = json.loads(job_data.get("location") or "{}")
            job_data["required_skills"] = json.loads(job_data.get("required_skills") or "[]")
            job_data["preferred_skills"] = json.loads(job_data.get("preferred_skills") or "[]")
            job_data["benefits"] = json.loads(job_data.get("benefits") or "[]")
            
            return {"success": True, "job": job_data, "source": "database"}
        
        # If not in database, fetch from API
        result = await job_fetcher.get_job_details(job_id)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=404, detail="Job not found")
            
    except Exception as e:
        logger.error("Job details error", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-for-user/{user_id}")
async def fetch_jobs_for_user_endpoint(
    user_id: int,
    search_request: JobSearchRequest,
    background_tasks: BackgroundTasks
):
    """
    Fetch and match jobs for a specific user in the background
    """
    try:
        # Convert search request to dict
        search_params = search_request.dict()
        
        # Queue background task
        task = fetch_jobs_for_user.delay(user_id, search_params)
        
        logger.info("Job fetch queued for user", user_id=user_id, task_id=task.id)
        
        return {
            "success": True,
            "message": "Job fetch queued successfully",
            "task_id": task.id,
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error("Job fetch queue error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/matches")
async def get_user_job_matches(
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    min_score: int = Query(0, ge=0, le=100),
    recommendation: Optional[str] = Query(None)
):
    """
    Get job matches for a user with filtering and pagination
    """
    try:
        database = await get_database()
        
        # Build query with filters
        where_conditions = ["jm.user_id = :user_id", "jm.overall_score >= :min_score"]
        query_params = {"user_id": user_id, "min_score": min_score}
        
        if recommendation:
            where_conditions.append("jm.recommendation = :recommendation")
            query_params["recommendation"] = recommendation
        
        where_clause = " AND ".join(where_conditions)
        
        # Count total matches
        count_query = f"""
        SELECT COUNT(*) as total
        FROM job_matches jm
        JOIN jobs j ON jm.job_id = j.id
        WHERE {where_clause} AND j.is_active = true
        """
        
        total_result = await database.fetch_one(count_query, query_params)
        total_count = total_result["total"] if total_result else 0
        
        # Get paginated matches
        matches_query = f"""
        SELECT 
            jm.*,
            j.external_id,
            j.title,
            j.description,
            j.company_id,
            j.location,
            j.salary_min,
            j.salary_max,
            j.application_url,
            j.posted_date,
            j.source
        FROM job_matches jm
        JOIN jobs j ON jm.job_id = j.id
        WHERE {where_clause} AND j.is_active = true
        ORDER BY jm.overall_score DESC, jm.created_at DESC
        LIMIT :limit OFFSET :offset
        """
        
        query_params.update({
            "limit": limit,
            "offset": (page - 1) * limit
        })
        
        matches = await database.fetch_all(matches_query, query_params)
        
        # Format response
        formatted_matches = []
        for match in matches:
            match_dict = dict(match)
            
            # Parse JSON fields
            match_dict["matched_skills"] = json.loads(match_dict.get("matched_skills") or "[]")
            match_dict["missing_skills"] = json.loads(match_dict.get("missing_skills") or "[]")
            match_dict["improvement_suggestions"] = json.loads(match_dict.get("improvement_suggestions") or "[]")
            match_dict["red_flags"] = json.loads(match_dict.get("red_flags") or "[]")
            match_dict["location"] = json.loads(match_dict.get("location") or "{}")
            
            formatted_matches.append(match_dict)
        
        has_next = (page * limit) < total_count
        
        return {
            "success": True,
            "matches": formatted_matches,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "has_next": has_next,
                "total_pages": (total_count + limit - 1) // limit
            }
        }
        
    except Exception as e:
        logger.error("User matches error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match")
async def match_jobs_to_user(match_request: JobMatchRequest):
    """
    Match specific jobs against a user profile
    """
    try:
        database = await get_database()
        
        # Get user profile
        user_data = await database.fetch_one(
            "SELECT * FROM users WHERE id = :user_id",
            {"user_id": match_request.user_id}
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_profile = dict(user_data)
        user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
        user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
        
        # Get jobs to match
        job_placeholders = ",".join([f":job_{i}" for i in range(len(match_request.job_ids))])
        job_params = {f"job_{i}": job_id for i, job_id in enumerate(match_request.job_ids)}
        
        jobs_query = f"""
        SELECT * FROM jobs 
        WHERE external_id IN ({job_placeholders})
        AND is_active = true
        """
        
        jobs_data = await database.fetch_all(jobs_query, job_params)
        
        if not jobs_data:
            raise HTTPException(status_code=404, detail="No jobs found")
        
        # Format jobs for matching
        formatted_jobs = []
        for job in jobs_data:
            job_dict = dict(job)
            job_dict["required_skills"] = json.loads(job_dict.get("required_skills") or "[]")
            job_dict["preferred_skills"] = json.loads(job_dict.get("preferred_skills") or "[]")
            job_dict["location"] = json.loads(job_dict.get("location") or "{}")
            formatted_jobs.append(job_dict)
        
        # Perform matching
        strategy_map = {
            "ai_powered": MatchingStrategy.AI_POWERED,
            "algorithmic": MatchingStrategy.ALGORITHMIC,
            "hybrid": MatchingStrategy.HYBRID
        }
        
        strategy = strategy_map.get(match_request.strategy, MatchingStrategy.HYBRID)
        
        # Match each job
        match_results = []
        for job in formatted_jobs:
            match_result = await job_matching_engine.match_job_to_user(
                job_data=job,
                user_profile=user_profile,
                strategy=strategy,
                user_tier=user_profile.get("tier", "free")
            )
            
            match_result["job_id"] = job["external_id"]
            match_result["job_title"] = job["title"]
            match_results.append(match_result)
        
        # Sort by score
        match_results.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
        
        return {
            "success": True,
            "matches": match_results,
            "user_id": match_request.user_id,
            "strategy_used": match_request.strategy
        }
        
    except Exception as e:
        logger.error("Job matching error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/{user_id}/rematch")
async def rematch_user_to_existing_jobs(
    user_id: int,
    background_tasks: BackgroundTasks
):
    """
    Rematch user against existing jobs (useful after profile updates)
    """
    try:
        # Queue background task
        task = match_user_to_existing_jobs.delay(user_id)
        
        logger.info("Job rematch queued for user", user_id=user_id, task_id=task.id)
        
        return {
            "success": True,
            "message": "Job rematch queued successfully",
            "task_id": task.id,
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error("Job rematch queue error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_jobs(
    limit: int = Query(50, ge=1, le=100),
    location: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    """
    Get trending jobs from cache
    """
    try:
        database = await get_database()
        
        # Build query
        where_conditions = ["j.is_active = true", "j.posted_date > NOW() - INTERVAL '7 days'"]
        query_params = {"limit": limit}
        
        if location:
            where_conditions.append("j.location->>'city' ILIKE :location OR j.location->>'state' ILIKE :location")
            query_params["location"] = f"%{location}%"
        
        if category:
            where_conditions.append("LOWER(j.title) LIKE :category")
            query_params["category"] = f"%{category.lower()}%"
        
        where_clause = " AND ".join(where_conditions)
        
        trending_query = f"""
        SELECT 
            j.*,
            COUNT(jm.id) as match_count,
            AVG(jm.overall_score) as avg_match_score
        FROM jobs j
        LEFT JOIN job_matches jm ON j.id = jm.job_id
        WHERE {where_clause}
        GROUP BY j.id
        ORDER BY match_count DESC, avg_match_score DESC, j.posted_date DESC
        LIMIT :limit
        """
        
        trending_jobs = await database.fetch_all(trending_query, query_params)
        
        # Format response
        formatted_jobs = []
        for job in trending_jobs:
            job_dict = dict(job)
            job_dict["location"] = json.loads(job_dict.get("location") or "{}")
            job_dict["required_skills"] = json.loads(job_dict.get("required_skills") or "[]")
            job_dict["benefits"] = json.loads(job_dict.get("benefits") or "[]")
            formatted_jobs.append(job_dict)
        
        return {
            "success": True,
            "trending_jobs": formatted_jobs,
            "total_count": len(formatted_jobs),
            "filters": {
                "location": location,
                "category": category
            }
        }
        
    except Exception as e:
        logger.error("Trending jobs error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _format_salary_range(min_salary: Optional[int], max_salary: Optional[int]) -> Optional[str]:
    """Format salary range for display"""
    if min_salary and max_salary:
        return f"${min_salary:,} - ${max_salary:,}"
    elif min_salary:
        return f"${min_salary:,}+"
    elif max_salary:
        return f"Up to ${max_salary:,}"
    else:
        return None