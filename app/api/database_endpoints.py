"""
Database-first API endpoints that read from database directly
NO AI processing - just fast database queries for dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.applications import Application, ApplicationQueue
from app.models.jobs import Job, JobMatch
from app.models.users import User

router = APIRouter(prefix="/database", tags=["database"])

@router.get("/applications/queue")
async def get_application_queue_from_db(
    user_id: str,
    status: str = Query("pending", description="Queue status filter"),
    limit: int = Query(20, description="Number of items to return"),
    page: int = Query(1, description="Page number"),
    db: AsyncSession = Depends(get_db)
):
    """
    Read application queue directly from database - NO AI processing
    Fast database query with pagination
    """
    try:
        offset = (page - 1) * limit
        
        # Fast database query - no AI calls
        query = select(
            ApplicationQueue.id,
            ApplicationQueue.job_id,
            ApplicationQueue.status,
            ApplicationQueue.match_score,
            ApplicationQueue.match_reasons,
            ApplicationQueue.ai_generated_cover_letter,
            ApplicationQueue.expires_at,
            ApplicationQueue.auto_apply_after,
            ApplicationQueue.created_at,
            Job.id.label("job_db_id"),
            Job.title,
            Job.company,
            Job.location,
            Job.salary_min,
            Job.salary_max,
            Job.salary_currency,
            Job.description,
            Job.requirements,
            Job.benefits,
            Job.job_type,
            Job.remote,
            Job.date_posted,
            Job.apply_url
        ).join(
            Job, ApplicationQueue.job_id == Job.id
        ).where(
            and_(
                ApplicationQueue.user_id == user_id,
                ApplicationQueue.status == status
            )
        ).order_by(
            desc(ApplicationQueue.created_at)
        ).limit(limit).offset(offset)
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        # Format response
        queue_items = []
        for row in rows:
            queue_items.append({
                "id": str(row.id),
                "job_id": str(row.job_id),
                "status": row.status,
                "match_score": row.match_score,
                "match_reasons": row.match_reasons or [],
                "ai_generated_cover_letter": row.ai_generated_cover_letter,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "auto_apply_after": row.auto_apply_after.isoformat() if row.auto_apply_after else None,
                "created_at": row.created_at.isoformat(),
                "job": {
                    "id": str(row.job_db_id),
                    "title": row.title,
                    "company": row.company,
                    "location": row.location,
                    "salary_min": row.salary_min,
                    "salary_max": row.salary_max,
                    "salary_currency": row.salary_currency,
                    "description": row.description,
                    "requirements": row.requirements or [],
                    "benefits": row.benefits or [],
                    "job_type": row.job_type,
                    "remote": row.remote,
                    "date_posted": row.date_posted.isoformat() if row.date_posted else None,
                    "apply_url": row.apply_url
                }
            })
        
        # Get total count for pagination
        count_query = select(func.count(ApplicationQueue.id)).where(
            and_(
                ApplicationQueue.user_id == user_id,
                ApplicationQueue.status == status
            )
        )
        total_result = await db.execute(count_query)
        total_count = total_result.scalar()
        
        return {
            "queue": queue_items,
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit,
            "source": "database",
            "response_time": "fast",
            "ai_processing": False
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/jobs/recent")
async def get_recent_jobs_from_db(
    user_id: str,
    limit: int = Query(50, description="Number of jobs to return"),
    hours: int = Query(24, description="Jobs from last N hours"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent jobs from database - populated by background AI agent
    """
    try:
        # Get jobs from last N hours
        since = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(Job).where(
            Job.created_at >= since
        ).order_by(
            desc(Job.created_at)
        ).limit(limit)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        job_list = []
        for job in jobs:
            job_list.append({
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "description": job.description,
                "job_type": job.job_type,
                "remote": job.remote,
                "date_posted": job.date_posted.isoformat() if job.date_posted else None,
                "apply_url": job.apply_url,
                "created_at": job.created_at.isoformat()
            })
        
        return {
            "jobs": job_list,
            "total": len(job_list),
            "hours": hours,
            "source": "database",
            "ai_populated": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/matches/user/{user_id}")
async def get_user_matches_from_db(
    user_id: str,
    limit: int = Query(20, description="Number of matches to return"),
    min_score: int = Query(70, description="Minimum match score"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user job matches from database - calculated by background AI
    """
    try:
        query = select(
            JobMatch.id,
            JobMatch.job_id,
            JobMatch.match_score,
            JobMatch.match_explanation,
            JobMatch.created_at,
            Job.title,
            Job.company,
            Job.location,
            Job.salary_min,
            Job.salary_max,
            Job.job_type,
            Job.remote,
            Job.apply_url
        ).join(
            Job, JobMatch.job_id == Job.id
        ).where(
            and_(
                JobMatch.user_id == user_id,
                JobMatch.match_score >= min_score
            )
        ).order_by(
            desc(JobMatch.match_score),
            desc(JobMatch.created_at)
        ).limit(limit)
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        matches = []
        for row in rows:
            matches.append({
                "id": str(row.id),
                "job_id": str(row.job_id),
                "match_score": row.match_score,
                "match_explanation": row.match_explanation,
                "created_at": row.created_at.isoformat(),
                "job": {
                    "title": row.title,
                    "company": row.company,
                    "location": row.location,
                    "salary_min": row.salary_min,
                    "salary_max": row.salary_max,
                    "job_type": row.job_type,
                    "remote": row.remote,
                    "apply_url": row.apply_url
                }
            })
        
        return {
            "matches": matches,
            "total": len(matches),
            "min_score": min_score,
            "source": "database",
            "ai_calculated": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/applications/user/{user_id}")
async def get_user_applications_from_db(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Number of applications to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user applications from database
    """
    try:
        conditions = [Application.user_id == user_id]
        if status:
            conditions.append(Application.status == status)
        
        query = select(Application).where(
            and_(*conditions)
        ).order_by(
            desc(Application.created_at)
        ).limit(limit)
        
        result = await db.execute(query)
        applications = result.scalars().all()
        
        app_list = []
        for app in applications:
            app_list.append({
                "id": str(app.id),
                "job_id": str(app.job_id),
                "status": app.status,
                "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                "created_at": app.created_at.isoformat(),
                "updated_at": app.updated_at.isoformat() if app.updated_at else None
            })
        
        return {
            "applications": app_list,
            "total": len(app_list),
            "status_filter": status,
            "source": "database"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/analytics/user/{user_id}")
async def get_user_analytics_from_db(
    user_id: str,
    days: int = Query(30, description="Analytics for last N days"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user analytics from database - calculated by background workers
    """
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # Applications count by status
        app_query = select(
            Application.status,
            func.count(Application.id).label('count')
        ).where(
            and_(
                Application.user_id == user_id,
                Application.created_at >= since
            )
        ).group_by(Application.status)
        
        app_result = await db.execute(app_query)
        status_counts = dict(app_result.fetchall())
        
        # Match scores average
        match_query = select(
            func.avg(JobMatch.match_score).label('avg_score'),
            func.count(JobMatch.id).label('total_matches')
        ).where(
            and_(
                JobMatch.user_id == user_id,
                JobMatch.created_at >= since
            )
        )
        
        match_result = await db.execute(match_query)
        match_stats = match_result.fetchone()
        
        return {
            "user_id": user_id,
            "period_days": days,
            "applications": {
                "total": sum(status_counts.values()),
                "by_status": status_counts,
                "success_rate": (status_counts.get('hired', 0) / max(sum(status_counts.values()), 1)) * 100
            },
            "matches": {
                "total": match_stats.total_matches or 0,
                "average_score": float(match_stats.avg_score or 0)
            },
            "generated_at": datetime.utcnow().isoformat(),
            "source": "database",
            "calculated_by": "background_workers"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")