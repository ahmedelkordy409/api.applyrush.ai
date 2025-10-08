"""
Auto-application processing tasks
Handles intelligent job application submission and tracking
"""

from celery import shared_task
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
import json

from app.workers.celery_app import celery_app
from app.ai.models import generate_cover_letter, ai_model_manager
from app.ai.prompts import AIPrompts, PromptType
from app.services.job_matcher import job_matching_engine
from app.core.database import get_database
from app.models.database import JobStatus, MatchRecommendation
import structlog

logger = structlog.get_logger()


@shared_task(bind=True)
def process_auto_apply_queue(self) -> Dict[str, Any]:
    """
    Process the auto-apply queue and submit applications for qualified jobs
    """
    try:
        logger.info("Starting auto-apply queue processing")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_process_auto_apply_queue_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Auto-apply queue processing failed", error=str(e))
        return {"success": False, "error": str(e)}


async def _process_auto_apply_queue_async() -> Dict[str, Any]:
    """Async helper for auto-apply queue processing"""
    
    database = await get_database()
    
    # Find users with auto-apply enabled and their qualified matches
    queue_query = """
    SELECT 
        u.id as user_id,
        u.auto_apply_rules,
        u.preferences,
        jm.id as match_id,
        jm.job_id,
        jm.overall_score,
        jm.recommendation,
        j.external_id as job_external_id,
        j.title as job_title,
        j.application_url
    FROM users u
    JOIN job_matches jm ON u.id = jm.user_id
    JOIN jobs j ON jm.job_id = j.id
    WHERE 
        u.auto_apply_enabled = true
        AND jm.overall_score >= 70
        AND jm.recommendation IN ('strong_match', 'good_match')
        AND j.is_active = true
        AND NOT EXISTS (
            SELECT 1 FROM job_applications ja 
            WHERE ja.user_id = u.id AND ja.job_id = j.id
        )
        AND jm.created_at > NOW() - INTERVAL '7 days'
    ORDER BY jm.overall_score DESC
    LIMIT 50  -- Process in batches
    """
    
    candidates = await database.fetch_all(queue_query)
    
    applications_submitted = 0
    applications_skipped = 0
    errors = []
    
    for candidate in candidates:
        try:
            candidate_dict = dict(candidate)
            
            # Parse auto-apply rules
            auto_apply_rules = json.loads(candidate_dict.get("auto_apply_rules") or "{}")
            user_preferences = json.loads(candidate_dict.get("preferences") or "{}")
            
            # Make auto-apply decision
            decision_result = await _make_auto_apply_decision(
                candidate_dict, auto_apply_rules, user_preferences
            )
            
            if decision_result["decision"] == "APPLY":
                # Submit application
                application_result = await _submit_auto_application(candidate_dict)
                
                if application_result["success"]:
                    applications_submitted += 1
                    logger.info("Auto-application submitted",
                               user_id=candidate_dict["user_id"],
                               job_id=candidate_dict["job_external_id"])
                else:
                    applications_skipped += 1
                    errors.append(f"Failed to submit for job {candidate_dict['job_external_id']}: {application_result.get('error')}")
                    
            else:
                applications_skipped += 1
                logger.debug("Auto-application skipped",
                            user_id=candidate_dict["user_id"],
                            job_id=candidate_dict["job_external_id"],
                            reason=decision_result["reasoning"])
                
        except Exception as e:
            applications_skipped += 1
            errors.append(f"Error processing candidate {candidate.get('user_id')}: {str(e)}")
            continue
    
    logger.info("Auto-apply queue processing completed",
               candidates_processed=len(candidates),
               applications_submitted=applications_submitted,
               applications_skipped=applications_skipped,
               errors_count=len(errors))
    
    return {
        "success": True,
        "candidates_processed": len(candidates),
        "applications_submitted": applications_submitted,
        "applications_skipped": applications_skipped,
        "errors": errors[:10]  # Return first 10 errors
    }


async def _make_auto_apply_decision(
    candidate: Dict[str, Any],
    auto_apply_rules: Dict[str, Any],
    user_preferences: Dict[str, Any]
) -> Dict[str, Any]:
    """Make intelligent auto-apply decision using AI"""
    
    # Check basic rules first
    min_score_threshold = auto_apply_rules.get("min_score_threshold", 70)
    max_daily_applications = auto_apply_rules.get("max_daily_applications", 5)
    
    if candidate["overall_score"] < min_score_threshold:
        return {
            "decision": "SKIP",
            "reasoning": f"Score {candidate['overall_score']} below threshold {min_score_threshold}"
        }
    
    # Check daily application limit
    database = await get_database()
    today_applications_query = """
    SELECT COUNT(*) as count FROM job_applications 
    WHERE user_id = :user_id 
    AND DATE(submitted_at) = CURRENT_DATE
    """
    
    today_count_result = await database.fetch_one(
        today_applications_query, 
        {"user_id": candidate["user_id"]}
    )
    today_count = today_count_result["count"] if today_count_result else 0
    
    if today_count >= max_daily_applications:
        return {
            "decision": "SKIP",
            "reasoning": f"Daily application limit reached ({today_count}/{max_daily_applications})"
        }
    
    # Get additional job data for AI decision
    job_query = """
    SELECT j.*, jm.* FROM jobs j
    JOIN job_matches jm ON j.id = jm.job_id
    WHERE j.id = :job_id AND jm.id = :match_id
    """
    
    job_data = await database.fetch_one(job_query, {
        "job_id": candidate["job_id"],
        "match_id": candidate["match_id"]
    })
    
    if not job_data:
        return {
            "decision": "SKIP",
            "reasoning": "Job data not found"
        }
    
    # Use AI for sophisticated decision making
    try:
        prompt = AIPrompts.format_prompt(
            PromptType.AUTO_APPLY_DECISION,
            overall_match_score=candidate["overall_score"],
            auto_apply_rules=auto_apply_rules,
            past_applications=[],  # Would load from database
            active_applications_count=today_count,
            estimated_applicants=100  # Would estimate based on job data
        )
        
        ai_result = await ai_model_manager.generate_response(
            prompt=prompt,
            user_data={"user_id": candidate["user_id"]},
            model_tier="cheap",  # Fast decision for auto-apply
            provider="replicate"
        )
        
        if ai_result["success"]:
            decision_data = await ai_model_manager.parse_json_response(
                ai_result["response"]["text"]
            )
            return decision_data
        else:
            # Fallback to basic rules
            return {
                "decision": "APPLY",
                "reasoning": "AI decision failed, using basic rules",
                "confidence": 0.7
            }
            
    except Exception as e:
        logger.warning("AI auto-apply decision failed", error=str(e))
        return {
            "decision": "APPLY",
            "reasoning": "AI decision failed, using basic rules",
            "confidence": 0.6
        }


async def _submit_auto_application(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Submit automatic job application"""
    
    try:
        database = await get_database()
        
        # Get full user profile
        user_query = "SELECT * FROM users WHERE id = :user_id"
        user_data = await database.fetch_one(user_query, {"user_id": candidate["user_id"]})
        
        if not user_data:
            return {"success": False, "error": "User not found"}
        
        user_profile = dict(user_data)
        user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
        user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
        
        # Get job details
        job_query = "SELECT * FROM jobs WHERE id = :job_id"
        job_data = await database.fetch_one(job_query, {"job_id": candidate["job_id"]})
        
        if not job_data:
            return {"success": False, "error": "Job not found"}
        
        job_details = dict(job_data)
        job_details["required_skills"] = json.loads(job_details.get("required_skills") or "[]")
        job_details["location"] = json.loads(job_details.get("location") or "{}")
        
        # Generate customized cover letter
        cover_letter_result = await generate_cover_letter(
            job_data=job_details,
            user_profile=user_profile,
            user_tier=user_profile.get("tier", "free")
        )
        
        cover_letter_text = ""
        if cover_letter_result["success"]:
            cover_letter_text = cover_letter_result["cover_letter"].get("cover_letter", "")
        
        # Create application record
        application_insert = """
        INSERT INTO job_applications (
            user_id, job_id, job_match_id, status, applied_via,
            application_url, cover_letter, submitted_at
        ) VALUES (
            :user_id, :job_id, :job_match_id, :status, :applied_via,
            :application_url, :cover_letter, :submitted_at
        )
        RETURNING id
        """
        
        application_data = {
            "user_id": candidate["user_id"],
            "job_id": candidate["job_id"],
            "job_match_id": candidate["match_id"],
            "status": JobStatus.SUBMITTED.value,
            "applied_via": "auto_apply",
            "application_url": candidate["application_url"],
            "cover_letter": cover_letter_text,
            "submitted_at": datetime.utcnow()
        }
        
        application_result = await database.fetch_one(application_insert, application_data)
        application_id = application_result["id"]
        
        # Record status history
        status_history_insert = """
        INSERT INTO application_status_history (
            application_id, from_status, to_status, changed_at
        ) VALUES (
            :application_id, NULL, :status, :changed_at
        )
        """
        
        await database.execute(status_history_insert, {
            "application_id": application_id,
            "status": JobStatus.SUBMITTED.value,
            "changed_at": datetime.utcnow()
        })
        
        # In a real implementation, this would:
        # 1. Submit actual application via job board APIs
        # 2. Handle different application methods (email, website forms, etc.)
        # 3. Track submission confirmations
        # 4. Set up follow-up reminders
        
        logger.info("Auto-application submitted successfully",
                   application_id=application_id,
                   user_id=candidate["user_id"],
                   job_id=candidate["job_external_id"])
        
        return {
            "success": True,
            "application_id": application_id,
            "cover_letter_generated": bool(cover_letter_text)
        }
        
    except Exception as e:
        logger.error("Auto-application submission failed",
                    user_id=candidate["user_id"],
                    job_id=candidate.get("job_external_id"),
                    error=str(e))
        return {"success": False, "error": str(e)}


@shared_task(bind=True)
def update_application_statuses(self) -> Dict[str, Any]:
    """
    Update application statuses by checking with job boards
    """
    try:
        logger.info("Starting application status updates")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_update_application_statuses_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Application status update failed", error=str(e))
        return {"success": False, "error": str(e)}


async def _update_application_statuses_async() -> Dict[str, Any]:
    """Async helper for application status updates"""
    
    database = await get_database()
    
    # Get applications that need status updates
    pending_applications_query = """
    SELECT ja.*, j.external_id as job_external_id, j.source
    FROM job_applications ja
    JOIN jobs j ON ja.job_id = j.id
    WHERE ja.status IN ('submitted', 'acknowledged', 'screening')
    AND ja.submitted_at > NOW() - INTERVAL '30 days'
    AND (ja.last_status_check IS NULL OR ja.last_status_check < NOW() - INTERVAL '24 hours')
    ORDER BY ja.submitted_at DESC
    LIMIT 100
    """
    
    applications = await database.fetch_all(pending_applications_query)
    
    updates_made = 0
    errors = []
    
    for app in applications:
        try:
            app_dict = dict(app)
            
            # In a real implementation, this would:
            # 1. Check status via job board APIs
            # 2. Parse email confirmations
            # 3. Check application portals
            # 4. Use web scraping for status updates
            
            # For now, we'll simulate status progression based on time elapsed
            new_status = await _simulate_status_progression(app_dict)
            
            if new_status and new_status != app_dict["status"]:
                await _update_application_status(app_dict["id"], new_status)
                updates_made += 1
                
            # Update last status check timestamp
            await database.execute(
                "UPDATE job_applications SET last_status_check = NOW() WHERE id = :id",
                {"id": app_dict["id"]}
            )
            
        except Exception as e:
            errors.append(f"Error updating application {app.get('id')}: {str(e)}")
            continue
    
    logger.info("Application status updates completed",
               applications_checked=len(applications),
               updates_made=updates_made,
               errors_count=len(errors))
    
    return {
        "success": True,
        "applications_checked": len(applications),
        "updates_made": updates_made,
        "errors": errors[:5]  # Return first 5 errors
    }


async def _simulate_status_progression(application: Dict[str, Any]) -> Optional[str]:
    """Simulate realistic application status progression"""
    
    current_status = application["status"]
    submitted_at = application["submitted_at"]
    days_since_submission = (datetime.utcnow() - submitted_at).days
    
    # Simulate status progression based on time and randomization
    if current_status == "submitted":
        if days_since_submission >= 1:
            # 70% chance of acknowledgment after 1 day
            import random
            if random.random() < 0.7:
                return "acknowledged"
    
    elif current_status == "acknowledged":
        if days_since_submission >= 5:
            # 60% chance of screening after 5 days
            import random
            if random.random() < 0.6:
                return "screening"
            elif random.random() < 0.2:
                return "rejected"  # 20% rejection rate
    
    elif current_status == "screening":
        if days_since_submission >= 10:
            # 30% chance of interview after 10 days
            import random
            rand = random.random()
            if rand < 0.3:
                return "interview_scheduled"
            elif rand < 0.6:
                return "rejected"  # 30% rejection rate at screening
    
    return None  # No status change


async def _update_application_status(application_id: int, new_status: str):
    """Update application status and record history"""
    
    database = await get_database()
    
    # Get current status
    current_app = await database.fetch_one(
        "SELECT status FROM job_applications WHERE id = :id",
        {"id": application_id}
    )
    
    if not current_app:
        return
    
    old_status = current_app["status"]
    
    # Update application status
    await database.execute(
        "UPDATE job_applications SET status = :status, updated_at = NOW() WHERE id = :id",
        {"id": application_id, "status": new_status}
    )
    
    # Record status history
    await database.execute(
        """
        INSERT INTO application_status_history (
            application_id, from_status, to_status, changed_at
        ) VALUES (
            :application_id, :from_status, :to_status, :changed_at
        )
        """,
        {
            "application_id": application_id,
            "from_status": old_status,
            "to_status": new_status,
            "changed_at": datetime.utcnow()
        }
    )
    
    logger.info("Application status updated",
               application_id=application_id,
               old_status=old_status,
               new_status=new_status)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 300})
def generate_application_documents(self, user_id: int, job_id: int) -> Dict[str, Any]:
    """
    Generate customized resume and cover letter for a specific application
    """
    try:
        logger.info("Generating application documents", user_id=user_id, job_id=job_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _generate_application_documents_async(user_id, job_id)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Application document generation failed",
                    user_id=user_id, job_id=job_id, error=str(e))
        raise self.retry(exc=e, countdown=300, max_retries=2)


async def _generate_application_documents_async(user_id: int, job_id: int) -> Dict[str, Any]:
    """Async helper for application document generation"""
    
    database = await get_database()
    
    # Get user profile
    user_data = await database.fetch_one(
        "SELECT * FROM users WHERE id = :user_id",
        {"user_id": user_id}
    )
    
    if not user_data:
        return {"success": False, "error": "User not found"}
    
    user_profile = dict(user_data)
    user_profile["skills"] = json.loads(user_profile.get("skills") or "[]")
    user_profile["preferences"] = json.loads(user_profile.get("preferences") or "{}")
    
    # Get job details
    job_data = await database.fetch_one(
        "SELECT * FROM jobs WHERE id = :job_id",
        {"job_id": job_id}
    )
    
    if not job_data:
        return {"success": False, "error": "Job not found"}
    
    job_details = dict(job_data)
    job_details["required_skills"] = json.loads(job_details.get("required_skills") or "[]")
    job_details["location"] = json.loads(job_details.get("location") or "{}")
    
    documents = {}
    
    # Generate cover letter
    try:
        cover_letter_result = await generate_cover_letter(
            job_data=job_details,
            user_profile=user_profile,
            user_tier=user_profile.get("tier", "free")
        )
        
        if cover_letter_result["success"]:
            documents["cover_letter"] = cover_letter_result["cover_letter"]
        else:
            documents["cover_letter_error"] = cover_letter_result.get("error")
            
    except Exception as e:
        documents["cover_letter_error"] = str(e)
    
    # Generate optimized resume (would use resume optimization AI)
    try:
        resume_prompt = AIPrompts.format_prompt(
            PromptType.RESUME_OPTIMIZATION,
            current_resume=user_profile.get("resume_text", ""),
            job_description=job_details.get("description", ""),
            extracted_keywords=job_details.get("required_skills", []),
            industry_resume_patterns={}  # Would load from database
        )
        
        resume_result = await ai_model_manager.generate_response(
            prompt=resume_prompt,
            user_data=user_profile,
            model_tier="balanced",
            provider="replicate"
        )
        
        if resume_result["success"]:
            resume_data = await ai_model_manager.parse_json_response(
                resume_result["response"]["text"]
            )
            documents["optimized_resume"] = resume_data
        else:
            documents["resume_error"] = resume_result.get("error")
            
    except Exception as e:
        documents["resume_error"] = str(e)
    
    logger.info("Application documents generated",
               user_id=user_id,
               job_id=job_id,
               documents_generated=list(documents.keys()))
    
    return {
        "success": True,
        "user_id": user_id,
        "job_id": job_id,
        "documents": documents
    }


# Export task functions for Celery discovery
__all__ = [
    "process_auto_apply_queue",
    "update_application_statuses",
    "generate_application_documents"
]