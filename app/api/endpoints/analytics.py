"""
Analytics API endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.core.database import get_database

router = APIRouter()

@router.get("/dashboard/{user_id}")
async def get_user_dashboard(user_id: int):
    try:
        database = await get_database()
        
        # Get basic stats
        stats_query = """
        SELECT 
            COUNT(DISTINCT ja.id) as total_applications,
            COUNT(DISTINCT jm.id) as total_matches,
            AVG(jm.overall_score) as avg_match_score
        FROM users u
        LEFT JOIN job_applications ja ON u.id = ja.user_id
        LEFT JOIN job_matches jm ON u.id = jm.user_id
        WHERE u.id = :user_id
        """
        
        stats = await database.fetch_one(stats_query, {"user_id": user_id})
        
        return {
            "success": True,
            "dashboard": {
                "total_applications": stats["total_applications"] or 0,
                "total_matches": stats["total_matches"] or 0,
                "avg_match_score": round(float(stats["avg_match_score"] or 0), 1)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/health")
async def get_system_health():
    return {
        "success": True,
        "system_status": "healthy",
        "services": {
            "database": "connected",
            "ai_models": "available",
            "job_fetcher": "active"
        }
    }