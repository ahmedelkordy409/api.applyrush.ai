"""
Job matching API endpoints
Handles intelligent job matching and analysis
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import json

from app.services.job_matcher import job_matching_engine, MatchingStrategy
from app.ai.models import generate_job_match_analysis, generate_cover_letter
from app.core.database import get_database
import structlog

logger = structlog.get_logger()

router = APIRouter()


# Pydantic models
class MatchAnalysisRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    job_id: str = Field(..., description="Job external ID")
    strategy: str = Field("hybrid", description="Matching strategy")


class BulkMatchRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    job_ids: List[str] = Field(..., description="List of job external IDs")
    strategy: str = Field("hybrid", description="Matching strategy")
    save_results: bool = Field(True, description="Save results to database")


class CoverLetterRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    job_id: str = Field(..., description="Job external ID")
    include_company_research: bool = Field(False, description="Include company research")


class MatchPreferencesUpdate(BaseModel):
    user_id: int = Field(..., description="User ID")
    preferences: Dict[str, Any] = Field(..., description="Updated matching preferences")


@router.post("/analyze")
async def analyze_job_match(request: MatchAnalysisRequest):
    """
    Perform detailed job matching analysis for a single job
    """
    try:
        logger.info("Job match analysis request", 
                   user_id=request.user_id, 
                   job_id=request.job_id)
        
        database = await get_database()
        
        # Get user profile
        user_data = await database.fetch_one(
            "SELECT * FROM users WHERE id = :user_id",
            {"user_id": request.user_id}
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_profile = dict(user_data)
        user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
        user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
        
        # Get job data
        job_data = await database.fetch_one(
            "SELECT * FROM jobs WHERE external_id = :job_id AND is_active = true",
            {"job_id": request.job_id}
        )
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_details = dict(job_data)
        job_details["required_skills"] = json.loads(job_details.get("required_skills") or "[]")
        job_details["preferred_skills"] = json.loads(job_details.get("preferred_skills") or "[]")
        job_details["location"] = json.loads(job_details.get("location") or "{}")
        job_details["benefits"] = json.loads(job_details.get("benefits") or "[]")
        
        # Perform matching analysis
        strategy_map = {
            "ai_powered": MatchingStrategy.AI_POWERED,
            "algorithmic": MatchingStrategy.ALGORITHMIC,
            "hybrid": MatchingStrategy.HYBRID
        }
        
        strategy = strategy_map.get(request.strategy, MatchingStrategy.HYBRID)
        
        match_result = await job_matching_engine.match_job_to_user(
            job_data=job_details,
            user_profile=user_profile,
            strategy=strategy,
            user_tier=user_profile.get("tier", "free")
        )
        
        if not match_result.get("success", True):
            raise HTTPException(status_code=500, detail="Matching analysis failed")
        
        # Check if we should save results
        existing_match = await database.fetch_one(
            """
            SELECT id FROM job_matches 
            WHERE user_id = :user_id AND job_id = :job_id
            """,
            {"user_id": request.user_id, "job_id": job_data["id"]}
        )
        
        if not existing_match:
            # Save match result to database
            await _save_match_result(match_result, request.user_id, job_data["id"])
        
        # Add job details to response
        match_result["job_details"] = {
            "id": request.job_id,
            "title": job_details.get("title"),
            "company": job_details.get("company_name"),
            "location": job_details.get("location"),
            "posted_date": job_details.get("posted_date")
        }
        
        return {
            "success": True,
            "analysis": match_result,
            "strategy_used": request.strategy
        }
        
    except Exception as e:
        logger.error("Match analysis error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-analyze")
async def bulk_analyze_job_matches(
    request: BulkMatchRequest,
    background_tasks: BackgroundTasks
):
    """
    Perform bulk job matching analysis for multiple jobs
    """
    try:
        logger.info("Bulk match analysis request", 
                   user_id=request.user_id, 
                   job_count=len(request.job_ids))
        
        if len(request.job_ids) > 50:  # Limit bulk operations
            raise HTTPException(status_code=400, detail="Too many jobs requested (max 50)")
        
        database = await get_database()
        
        # Get user profile
        user_data = await database.fetch_one(
            "SELECT * FROM users WHERE id = :user_id",
            {"user_id": request.user_id}
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_profile = dict(user_data)
        user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
        user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
        
        # Get jobs data
        job_placeholders = ",".join([f":job_{i}" for i in range(len(request.job_ids))])
        job_params = {f"job_{i}": job_id for i, job_id in enumerate(request.job_ids)}
        
        jobs_query = f"""
        SELECT * FROM jobs 
        WHERE external_id IN ({job_placeholders})
        AND is_active = true
        """
        
        jobs_data = await database.fetch_all(jobs_query, job_params)
        
        if not jobs_data:
            raise HTTPException(status_code=404, detail="No valid jobs found")
        
        # Format jobs for matching
        formatted_jobs = []
        for job in jobs_data:
            job_dict = dict(job)
            job_dict["required_skills"] = json.loads(job_dict.get("required_skills") or "[]")
            job_dict["preferred_skills"] = json.loads(job_dict.get("preferred_skills") or "[]")
            job_dict["location"] = json.loads(job_dict.get("location") or "{}")
            job_dict["benefits"] = json.loads(job_dict.get("benefits") or "[]")
            formatted_jobs.append(job_dict)
        
        # Perform bulk matching
        strategy_map = {
            "ai_powered": MatchingStrategy.AI_POWERED,
            "algorithmic": MatchingStrategy.ALGORITHMIC,
            "hybrid": MatchingStrategy.HYBRID
        }
        
        strategy = strategy_map.get(request.strategy, MatchingStrategy.HYBRID)
        
        match_results = await job_matching_engine.batch_match_jobs(
            jobs=formatted_jobs,
            user_profile=user_profile,
            strategy=strategy,
            user_tier=user_profile.get("tier", "free")
        )
        
        # Save results if requested
        if request.save_results:
            for i, result in enumerate(match_results):
                if result.get("success", True):
                    job_db_id = next((j["id"] for j in jobs_data 
                                    if j["external_id"] == formatted_jobs[i]["external_id"]), None)
                    if job_db_id:
                        background_tasks.add_task(
                            _save_match_result_background,
                            result, request.user_id, job_db_id
                        )
        
        # Format response
        analysis_results = []
        for i, result in enumerate(match_results):
            job = formatted_jobs[i]
            result["job_details"] = {
                "id": job["external_id"],
                "title": job.get("title"),
                "company": job.get("company_name"),
                "location": job.get("location")
            }
            analysis_results.append(result)
        
        return {
            "success": True,
            "analyses": analysis_results,
            "total_analyzed": len(analysis_results),
            "strategy_used": request.strategy,
            "saved_to_database": request.save_results
        }
        
    except Exception as e:
        logger.error("Bulk match analysis error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cover-letter")
async def generate_cover_letter_endpoint(request: CoverLetterRequest):
    """
    Generate personalized cover letter for a job application
    """
    try:
        logger.info("Cover letter generation request", 
                   user_id=request.user_id, 
                   job_id=request.job_id)
        
        database = await get_database()
        
        # Get user profile
        user_data = await database.fetch_one(
            "SELECT * FROM users WHERE id = :user_id",
            {"user_id": request.user_id}
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_profile = dict(user_data)
        user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
        user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
        
        # Get job data
        job_data = await database.fetch_one(
            "SELECT * FROM jobs WHERE external_id = :job_id",
            {"job_id": request.job_id}
        )
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_details = dict(job_data)
        job_details["required_skills"] = json.loads(job_details.get("required_skills") or "[]")
        job_details["location"] = json.loads(job_details.get("location") or "{}")
        job_details["company"] = {"name": job_details.get("company_name", "")}
        
        # Get company research if requested
        company_research = {}
        if request.include_company_research:
            # In a real implementation, this would:
            # 1. Scrape company website/social media
            # 2. Get recent news about the company
            # 3. Analyze company culture from job descriptions
            # 4. Use AI to summarize company values
            company_research = {
                "culture": "Innovation-focused technology company",
                "recent_news": "Recently raised Series B funding",
                "values": "Customer-centric, collaborative, growth-minded"
            }
        
        # Generate cover letter
        result = await generate_cover_letter(
            job_data=job_details,
            user_profile=user_profile,
            company_research=company_research,
            user_tier=user_profile.get("tier", "free")
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail="Cover letter generation failed")
        
        return {
            "success": True,
            "cover_letter": result["cover_letter"],
            "metadata": result.get("metadata", {}),
            "job_details": {
                "id": request.job_id,
                "title": job_details.get("title"),
                "company": job_details.get("company_name")
            }
        }
        
    except Exception as e:
        logger.error("Cover letter generation error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/preferences")
async def get_matching_preferences(user_id: int):
    """
    Get user's job matching preferences
    """
    try:
        database = await get_database()
        
        user_data = await database.fetch_one(
            "SELECT preferences, auto_apply_rules FROM users WHERE id = :user_id",
            {"user_id": user_id}
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        preferences = json.loads(user_data.get("preferences") or "{}")
        auto_apply_rules = json.loads(user_data.get("auto_apply_rules") or "{}")
        
        return {
            "success": True,
            "user_id": user_id,
            "preferences": preferences,
            "auto_apply_rules": auto_apply_rules
        }
        
    except Exception as e:
        logger.error("Get preferences error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user/{user_id}/preferences")
async def update_matching_preferences(
    user_id: int,
    request: MatchPreferencesUpdate
):
    """
    Update user's job matching preferences
    """
    try:
        database = await get_database()
        
        # Verify user exists
        user_exists = await database.fetch_one(
            "SELECT id FROM users WHERE id = :user_id",
            {"user_id": user_id}
        )
        
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update preferences
        await database.execute(
            """
            UPDATE users 
            SET preferences = :preferences, updated_at = NOW()
            WHERE id = :user_id
            """,
            {
                "user_id": user_id,
                "preferences": json.dumps(request.preferences)
            }
        )
        
        logger.info("User preferences updated", user_id=user_id)
        
        return {
            "success": True,
            "message": "Preferences updated successfully",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error("Update preferences error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/statistics")
async def get_matching_statistics(user_id: int):
    """
    Get user's job matching statistics
    """
    try:
        database = await get_database()
        
        # Get match statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_matches,
            AVG(overall_score) as average_score,
            COUNT(CASE WHEN recommendation = 'strong_match' THEN 1 END) as strong_matches,
            COUNT(CASE WHEN recommendation = 'good_match' THEN 1 END) as good_matches,
            COUNT(CASE WHEN recommendation = 'possible_match' THEN 1 END) as possible_matches,
            COUNT(CASE WHEN recommendation = 'weak_match' THEN 1 END) as weak_matches,
            MAX(overall_score) as best_match_score,
            MIN(overall_score) as worst_match_score
        FROM job_matches 
        WHERE user_id = :user_id
        AND created_at > NOW() - INTERVAL '30 days'
        """
        
        stats_result = await database.fetch_one(stats_query, {"user_id": user_id})
        
        if not stats_result:
            return {
                "success": True,
                "user_id": user_id,
                "statistics": {
                    "total_matches": 0,
                    "average_score": 0,
                    "match_distribution": {},
                    "best_match_score": 0,
                    "worst_match_score": 0
                }
            }
        
        stats = dict(stats_result)
        
        # Format response
        match_distribution = {
            "strong_matches": stats.get("strong_matches", 0),
            "good_matches": stats.get("good_matches", 0),
            "possible_matches": stats.get("possible_matches", 0),
            "weak_matches": stats.get("weak_matches", 0)
        }
        
        return {
            "success": True,
            "user_id": user_id,
            "statistics": {
                "total_matches": stats.get("total_matches", 0),
                "average_score": round(float(stats.get("average_score", 0)), 1),
                "match_distribution": match_distribution,
                "best_match_score": round(float(stats.get("best_match_score", 0)), 1),
                "worst_match_score": round(float(stats.get("worst_match_score", 0)), 1),
                "period": "Last 30 days"
            }
        }
        
    except Exception as e:
        logger.error("Get statistics error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _save_match_result(
    match_result: Dict[str, Any], 
    user_id: int, 
    job_db_id: int
):
    """Save match result to database"""
    database = await get_database()
    
    category_scores = match_result.get("category_scores", {})
    
    match_insert = """
    INSERT INTO job_matches (
        user_id, job_id, overall_score, skill_match_score,
        experience_score, education_score, location_score,
        salary_score, culture_score, recommendation,
        apply_priority, success_probability, matched_skills,
        missing_skills, improvement_suggestions, red_flags,
        competitive_advantage
    ) VALUES (
        :user_id, :job_id, :overall_score, :skill_match_score,
        :experience_score, :education_score, :location_score,
        :salary_score, :culture_score, :recommendation,
        :apply_priority, :success_probability, :matched_skills,
        :missing_skills, :improvement_suggestions, :red_flags,
        :competitive_advantage
    )
    ON CONFLICT (user_id, job_id) DO UPDATE SET
        overall_score = EXCLUDED.overall_score,
        updated_at = NOW()
    """
    
    match_values = {
        "user_id": user_id,
        "job_id": job_db_id,
        "overall_score": match_result.get("overall_score", 0),
        "skill_match_score": category_scores.get("skills", {}).get("score", 0),
        "experience_score": category_scores.get("experience", {}).get("score", 0),
        "education_score": category_scores.get("education", {}).get("score", 0),
        "location_score": category_scores.get("location", {}).get("score", 0),
        "salary_score": category_scores.get("salary", {}).get("score", 0),
        "culture_score": category_scores.get("culture", {}).get("score", 0),
        "recommendation": match_result.get("recommendation", "weak_match"),
        "apply_priority": match_result.get("apply_priority", 5),
        "success_probability": match_result.get("success_probability", 0.5),
        "matched_skills": json.dumps(category_scores.get("skills", {}).get("matched", [])),
        "missing_skills": json.dumps(category_scores.get("skills", {}).get("missing", [])),
        "improvement_suggestions": json.dumps(match_result.get("improvement_suggestions", [])),
        "red_flags": json.dumps(match_result.get("red_flags", [])),
        "competitive_advantage": match_result.get("competitive_advantage", "")
    }
    
    await database.execute(match_insert, match_values)


async def _save_match_result_background(
    match_result: Dict[str, Any], 
    user_id: int, 
    job_db_id: int
):
    """Background task to save match result"""
    try:
        await _save_match_result(match_result, user_id, job_db_id)
    except Exception as e:
        logger.error("Background match save error", error=str(e))