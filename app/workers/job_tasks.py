"""
Background job processing tasks
Handles job fetching, matching, and processing
"""

from celery import shared_task
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
import json

from app.workers.celery_app import celery_app
from app.services.job_fetcher import job_fetcher
from app.services.job_matcher import job_matching_engine, MatchingStrategy
from app.core.database import get_database
from app.core.monitoring import performance_monitor
import structlog

logger = structlog.get_logger()


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def fetch_jobs_for_user(self, user_id: int, search_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch jobs for a specific user based on their preferences
    """
    try:
        logger.info("Starting job fetch for user", user_id=user_id, params=search_params)
        
        # Run async job fetching in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_fetch_jobs_async(user_id, search_params))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Job fetch failed", user_id=user_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


async def _fetch_jobs_async(user_id: int, search_params: Dict[str, Any]) -> Dict[str, Any]:
    """Async helper for job fetching"""
    
    # Extract search parameters
    query = search_params.get("query", "")
    location = search_params.get("location", "")
    remote_only = search_params.get("remote_only", False)
    num_pages = search_params.get("num_pages", 3)
    employment_types = search_params.get("employment_types", ["FULLTIME"])
    salary_min = search_params.get("salary_min")
    
    # Fetch jobs from API
    job_result = await job_fetcher.search_jobs(
        query=query,
        location=location,
        remote_only=remote_only,
        num_pages=num_pages,
        employment_types=employment_types,
        salary_min=salary_min,
        date_posted="week"  # Focus on recent jobs
    )
    
    if not job_result["success"]:
        return {
            "success": False,
            "error": "Failed to fetch jobs from API",
            "user_id": user_id
        }
    
    jobs = job_result["jobs"]
    
    # Get user profile for matching
    database = await get_database()
    user_query = "SELECT * FROM users WHERE id = :user_id"
    user_result = await database.fetch_one(user_query, {"user_id": user_id})
    
    if not user_result:
        return {
            "success": False,
            "error": "User not found",
            "user_id": user_id
        }
    
    user_profile = dict(user_result)
    
    # Parse JSON fields
    user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
    user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
    
    # Match jobs to user
    matched_jobs = await job_matching_engine.batch_match_jobs(
        jobs=jobs,
        user_profile=user_profile,
        strategy=MatchingStrategy.HYBRID,
        user_tier=user_profile.get("tier", "free")
    )
    
    # Store jobs and matches in database
    stored_count = await _store_jobs_and_matches(matched_jobs, user_id, user_profile)
    
    logger.info("Job fetch completed", 
               user_id=user_id,
               fetched=len(jobs),
               matched=len(matched_jobs),
               stored=stored_count)
    
    return {
        "success": True,
        "user_id": user_id,
        "jobs_fetched": len(jobs),
        "jobs_matched": len(matched_jobs),
        "jobs_stored": stored_count,
        "search_params": search_params
    }


@shared_task(bind=True)
def fetch_trending_jobs(self) -> Dict[str, Any]:
    """
    Fetch trending jobs across popular categories
    """
    try:
        logger.info("Starting trending jobs fetch")
        
        # Run async trending job fetching
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_fetch_trending_jobs_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Trending jobs fetch failed", error=str(e))
        raise self.retry(exc=e, countdown=300, max_retries=2)


async def _fetch_trending_jobs_async() -> Dict[str, Any]:
    """Async helper for trending jobs fetch"""
    
    # Popular job categories and locations
    trending_searches = [
        {"query": "software engineer", "location": "San Francisco, CA"},
        {"query": "data scientist", "location": "New York, NY"},
        {"query": "product manager", "location": "Seattle, WA"},
        {"query": "frontend developer", "location": "Austin, TX"},
        {"query": "backend engineer", "location": "Denver, CO"},
        {"query": "full stack developer", "location": ""},  # Remote
        {"query": "machine learning engineer", "location": "Boston, MA"},
        {"query": "devops engineer", "location": "Chicago, IL"},
    ]
    
    all_jobs = []
    
    for search in trending_searches:
        try:
            result = await job_fetcher.search_jobs(
                query=search["query"],
                location=search["location"],
                remote_only=search["location"] == "",
                num_pages=2,
                date_posted="3days"
            )
            
            if result["success"]:
                all_jobs.extend(result["jobs"])
                
        except Exception as e:
            logger.warning("Failed to fetch trending jobs for category",
                          query=search["query"], error=str(e))
            continue
    
    # Remove duplicates
    unique_jobs = {}
    for job in all_jobs:
        job_id = job.get("external_id")
        if job_id and job_id not in unique_jobs:
            unique_jobs[job_id] = job
    
    # Store trending jobs in cache/database
    stored_count = await _store_trending_jobs(list(unique_jobs.values()))
    
    logger.info("Trending jobs fetch completed", 
               fetched=len(all_jobs),
               unique=len(unique_jobs),
               stored=stored_count)
    
    return {
        "success": True,
        "jobs_fetched": len(all_jobs),
        "unique_jobs": len(unique_jobs),
        "jobs_stored": stored_count
    }


@shared_task(bind=True)
def refresh_job_cache(self) -> Dict[str, Any]:
    """
    Refresh job cache by removing old entries and updating job statuses
    """
    try:
        logger.info("Starting job cache refresh")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_refresh_job_cache_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Job cache refresh failed", error=str(e))
        return {"success": False, "error": str(e)}


async def _refresh_job_cache_async() -> Dict[str, Any]:
    """Async helper for job cache refresh"""
    
    database = await get_database()
    
    # Mark old jobs as inactive (older than 30 days)
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    update_query = """
    UPDATE jobs 
    SET is_active = false, updated_at = NOW()
    WHERE posted_date < :cutoff_date AND is_active = true
    """
    
    result = await database.execute(update_query, {"cutoff_date": cutoff_date})
    deactivated_count = result
    
    # Clean up job matches for inactive jobs
    cleanup_query = """
    DELETE FROM job_matches 
    WHERE job_id IN (
        SELECT id FROM jobs WHERE is_active = false
    ) AND created_at < :cutoff_date
    """
    
    await database.execute(cleanup_query, {"cutoff_date": cutoff_date})
    
    # Update application counts for active jobs (this would require API calls in real implementation)
    # For now, we'll just log the action
    
    logger.info("Job cache refresh completed", deactivated=deactivated_count)
    
    return {
        "success": True,
        "jobs_deactivated": deactivated_count,
        "refresh_timestamp": datetime.utcnow().isoformat()
    }


@shared_task(bind=True)
def match_user_to_existing_jobs(self, user_id: int) -> Dict[str, Any]:
    """
    Match a user against existing jobs in the database
    Useful when a user updates their profile
    """
    try:
        logger.info("Starting job matching for user", user_id=user_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_match_user_to_jobs_async(user_id))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("User job matching failed", user_id=user_id, error=str(e))
        raise self.retry(exc=e, countdown=120, max_retries=2)


async def _match_user_to_jobs_async(user_id: int) -> Dict[str, Any]:
    """Async helper for user-to-jobs matching"""
    
    database = await get_database()
    
    # Get user profile
    user_query = "SELECT * FROM users WHERE id = :user_id"
    user_result = await database.fetch_one(user_query, {"user_id": user_id})
    
    if not user_result:
        return {"success": False, "error": "User not found", "user_id": user_id}
    
    user_profile = dict(user_result)
    user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
    user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
    
    # Get active jobs that haven't been matched to this user
    jobs_query = """
    SELECT j.* FROM jobs j
    WHERE j.is_active = true 
    AND j.posted_date > NOW() - INTERVAL '14 days'
    AND NOT EXISTS (
        SELECT 1 FROM job_matches jm 
        WHERE jm.job_id = j.id AND jm.user_id = :user_id
    )
    LIMIT 100
    """
    
    jobs_result = await database.fetch_all(jobs_query, {"user_id": user_id})
    jobs = [dict(job) for job in jobs_result]
    
    # Convert database format to matching format
    formatted_jobs = []
    for job in jobs:
        formatted_job = {
            "external_id": job["external_id"],
            "title": job["title"],
            "description": job["description"],
            "company": {"name": job.get("company_name", "")},
            "location": job.get("location", {}),
            "remote_option": job.get("remote_option", "no"),
            "required_skills": job.get("required_skills", []),
            "preferred_skills": job.get("preferred_skills", []),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "experience_level": job.get("experience_level"),
            "education_requirements": job.get("education_requirements"),
        }
        
        # Parse JSON fields if they're stored as strings
        if isinstance(formatted_job["location"], str):
            formatted_job["location"] = json.loads(formatted_job["location"] or "{}")
        if isinstance(formatted_job["required_skills"], str):
            formatted_job["required_skills"] = json.loads(formatted_job["required_skills"] or "[]")
        if isinstance(formatted_job["preferred_skills"], str):
            formatted_job["preferred_skills"] = json.loads(formatted_job["preferred_skills"] or "[]")
        
        formatted_jobs.append((formatted_job, job["id"]))  # Keep database ID
    
    # Perform matching
    matches_created = 0
    
    for formatted_job, job_db_id in formatted_jobs:
        try:
            match_result = await job_matching_engine.match_job_to_user(
                formatted_job,
                user_profile,
                strategy=MatchingStrategy.HYBRID,
                user_tier=user_profile.get("tier", "free")
            )
            
            if match_result.get("success"):
                # Store match in database
                await _store_job_match(match_result, user_id, job_db_id)
                matches_created += 1
                
        except Exception as e:
            logger.warning("Failed to match job to user",
                          job_id=formatted_job.get("external_id"),
                          user_id=user_id,
                          error=str(e))
            continue
    
    logger.info("User job matching completed",
               user_id=user_id,
               jobs_processed=len(formatted_jobs),
               matches_created=matches_created)
    
    return {
        "success": True,
        "user_id": user_id,
        "jobs_processed": len(formatted_jobs),
        "matches_created": matches_created
    }


async def _store_jobs_and_matches(
    matched_jobs: List[Dict[str, Any]], 
    user_id: int, 
    user_profile: Dict[str, Any]
) -> int:
    """Store jobs and their matches in database"""
    
    database = await get_database()
    stored_count = 0
    
    for job_data in matched_jobs:
        try:
            # Check if job already exists
            job_check_query = "SELECT id FROM jobs WHERE external_id = :external_id"
            existing_job = await database.fetch_one(
                job_check_query, 
                {"external_id": job_data.get("external_id")}
            )
            
            if existing_job:
                job_db_id = existing_job["id"]
            else:
                # Insert new job
                job_insert_query = """
                INSERT INTO jobs (
                    external_id, title, description, company_id, location,
                    remote_option, employment_type, required_skills,
                    preferred_skills, salary_min, salary_max, currency,
                    source, posted_date, application_url, benefits,
                    experience_level, education_requirements, is_active
                ) VALUES (
                    :external_id, :title, :description, NULL, :location,
                    :remote_option, :employment_type, :required_skills,
                    :preferred_skills, :salary_min, :salary_max, :currency,
                    :source, :posted_date, :application_url, :benefits,
                    :experience_level, :education_requirements, true
                )
                RETURNING id
                """
                
                job_values = {
                    "external_id": job_data.get("external_id"),
                    "title": job_data.get("title"),
                    "description": job_data.get("description"),
                    "location": json.dumps(job_data.get("location", {})),
                    "remote_option": job_data.get("remote_option"),
                    "employment_type": job_data.get("employment_type"),
                    "required_skills": json.dumps(job_data.get("required_skills", [])),
                    "preferred_skills": json.dumps(job_data.get("preferred_skills", [])),
                    "salary_min": job_data.get("salary_min"),
                    "salary_max": job_data.get("salary_max"),
                    "currency": job_data.get("currency", "USD"),
                    "source": job_data.get("source"),
                    "posted_date": job_data.get("posted_date"),
                    "application_url": job_data.get("application_url"),
                    "benefits": json.dumps(job_data.get("benefits", [])),
                    "experience_level": job_data.get("experience_level"),
                    "education_requirements": job_data.get("education_requirements"),
                }
                
                result = await database.fetch_one(job_insert_query, job_values)
                job_db_id = result["id"]
            
            # Store job match
            await _store_job_match(job_data, user_id, job_db_id)
            stored_count += 1
            
        except Exception as e:
            logger.warning("Failed to store job and match",
                          job_id=job_data.get("external_id"),
                          error=str(e))
            continue
    
    return stored_count


async def _store_job_match(match_data: Dict[str, Any], user_id: int, job_db_id: int):
    """Store individual job match in database"""
    
    database = await get_database()
    
    # Check if match already exists
    match_check_query = """
    SELECT id FROM job_matches 
    WHERE user_id = :user_id AND job_id = :job_id
    """
    existing_match = await database.fetch_one(
        match_check_query, 
        {"user_id": user_id, "job_id": job_db_id}
    )
    
    if existing_match:
        return  # Match already exists
    
    # Insert job match
    match_insert_query = """
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
    """
    
    category_scores = match_data.get("category_scores", {})
    
    match_values = {
        "user_id": user_id,
        "job_id": job_db_id,
        "overall_score": match_data.get("overall_score", 0),
        "skill_match_score": category_scores.get("skills", {}).get("score", 0),
        "experience_score": category_scores.get("experience", {}).get("score", 0),
        "education_score": category_scores.get("education", {}).get("score", 0),
        "location_score": category_scores.get("location", {}).get("score", 0),
        "salary_score": category_scores.get("salary", {}).get("score", 0),
        "culture_score": category_scores.get("culture", {}).get("score", 0),
        "recommendation": match_data.get("recommendation", "weak_match"),
        "apply_priority": match_data.get("apply_priority", 5),
        "success_probability": match_data.get("success_probability", 0.5),
        "matched_skills": json.dumps(category_scores.get("skills", {}).get("matched", [])),
        "missing_skills": json.dumps(category_scores.get("skills", {}).get("missing", [])),
        "improvement_suggestions": json.dumps(match_data.get("improvement_suggestions", [])),
        "red_flags": json.dumps(match_data.get("red_flags", [])),
        "competitive_advantage": match_data.get("competitive_advantage", "")
    }
    
    await database.execute(match_insert_query, match_values)


async def _store_trending_jobs(jobs: List[Dict[str, Any]]) -> int:
    """Store trending jobs in database"""
    
    database = await get_database()
    stored_count = 0
    
    for job_data in jobs:
        try:
            # Check if job already exists
            job_check_query = "SELECT id FROM jobs WHERE external_id = :external_id"
            existing_job = await database.fetch_one(
                job_check_query, 
                {"external_id": job_data.get("external_id")}
            )
            
            if not existing_job:
                # Insert new trending job (similar to _store_jobs_and_matches)
                job_insert_query = """
                INSERT INTO jobs (
                    external_id, title, description, location,
                    remote_option, employment_type, required_skills,
                    salary_min, salary_max, source, posted_date,
                    application_url, experience_level, is_active
                ) VALUES (
                    :external_id, :title, :description, :location,
                    :remote_option, :employment_type, :required_skills,
                    :salary_min, :salary_max, :source, :posted_date,
                    :application_url, :experience_level, true
                ) ON CONFLICT (external_id) DO NOTHING
                """
                
                job_values = {
                    "external_id": job_data.get("external_id"),
                    "title": job_data.get("title"),
                    "description": job_data.get("description"),
                    "location": json.dumps(job_data.get("location", {})),
                    "remote_option": job_data.get("remote_option", "no"),
                    "employment_type": job_data.get("employment_type", "full-time"),
                    "required_skills": json.dumps(job_data.get("required_skills", [])),
                    "salary_min": job_data.get("salary_min"),
                    "salary_max": job_data.get("salary_max"),
                    "source": job_data.get("source", "unknown"),
                    "posted_date": job_data.get("posted_date"),
                    "application_url": job_data.get("application_url"),
                    "experience_level": job_data.get("experience_level", "mid-level"),
                }
                
                await database.execute(job_insert_query, job_values)
                stored_count += 1
                
        except Exception as e:
            logger.warning("Failed to store trending job",
                          job_id=job_data.get("external_id"),
                          error=str(e))
            continue
    
    return stored_count