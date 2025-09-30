"""
Application Management API endpoints
Handles job application CRUD operations, tracking, and analytics
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.core.database import database
from app.models.job import ApplicationCreate, ApplicationUpdate, ApplicationResponse
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


@router.get("/", response_model=List[ApplicationResponse])
async def get_applications(
    status: Optional[str] = Query(None, description="Filter by application status"),
    limit: int = Query(50, ge=1, le=100, description="Number of applications to return"),
    offset: int = Query(0, ge=0, description="Number of applications to skip"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's job applications with filtering and pagination"""

    try:
        if not permission_checker.has_permission(current_user, "applications", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read applications"
            )

        # Base query
        query = """
            SELECT a.*, j.title, j.company, j.location, j.salary_min, j.salary_max, j.job_type, j.remote, j.date_posted
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.user_id = :user_id
        """

        values = {"user_id": current_user["id"]}

        # Apply status filter
        if status:
            query += " AND a.status = :status"
            values["status"] = status

        # Order by creation date
        query += " ORDER BY a.created_at DESC LIMIT :limit OFFSET :offset"
        values["limit"] = limit
        values["offset"] = offset

        applications = await database.fetch_all(query=query, values=values)

        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) as total
            FROM applications a
            WHERE a.user_id = :user_id
        """
        count_values = {"user_id": current_user["id"]}

        if status:
            count_query += " AND a.status = :status"
            count_values["status"] = status

        total_result = await database.fetch_one(query=count_query, values=count_values)
        total = total_result["total"] if total_result else 0

        # Format response
        applications_list = []
        for app in applications:
            app_dict = dict(app)
            job_data = {
                "id": str(app_dict["job_id"]),
                "title": app_dict["title"],
                "company": app_dict["company"],
                "location": app_dict["location"],
                "salary_min": app_dict["salary_min"],
                "salary_max": app_dict["salary_max"],
                "job_type": app_dict["job_type"],
                "remote": app_dict["remote"],
                "date_posted": app_dict["date_posted"]
            }

            application_data = {
                "id": str(app_dict["id"]),
                "user_id": str(app_dict["user_id"]),
                "job_id": str(app_dict["job_id"]),
                "status": app_dict["status"],
                "cover_letter": app_dict["cover_letter"],
                "notes": app_dict["notes"],
                "applied_at": app_dict["applied_at"],
                "ai_generated_cover_letter": app_dict.get("ai_generated_cover_letter", False),
                "ai_auto_applied": app_dict.get("ai_auto_applied", False),
                "created_at": app_dict["created_at"],
                "updated_at": app_dict["updated_at"],
                "job": job_data
            }

            applications_list.append(application_data)

        return JSONResponse(content={
            "applications": applications_list,
            "total": total,
            "limit": limit,
            "offset": offset
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching applications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch applications"
        )


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application: ApplicationCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new job application"""

    try:
        if not permission_checker.has_permission(current_user, "applications", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create applications"
            )

        # Check if application already exists
        existing_query = """
            SELECT id FROM applications
            WHERE user_id = :user_id AND job_id = :job_id
        """
        existing = await database.fetch_one(
            query=existing_query,
            values={"user_id": current_user["id"], "job_id": application.job_id}
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application already exists for this job"
            )

        # Verify job exists and is active
        job_query = "SELECT id, title, company FROM jobs WHERE id = :job_id AND active = true"
        job = await database.fetch_one(query=job_query, values={"job_id": application.job_id})

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found or inactive"
            )

        # Create application
        insert_query = """
            INSERT INTO applications (
                user_id, job_id, status, cover_letter, notes, applied_at, created_at, updated_at
            ) VALUES (
                :user_id, :job_id, :status, :cover_letter, :notes, :applied_at, :created_at, :updated_at
            ) RETURNING *
        """

        values = {
            "user_id": current_user["id"],
            "job_id": application.job_id,
            "status": "pending",
            "cover_letter": application.cover_letter,
            "notes": application.notes,
            "applied_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        new_application = await database.fetch_one(query=insert_query, values=values)

        # Update job application count
        await database.execute(
            query="UPDATE jobs SET application_count = application_count + 1 WHERE id = :job_id",
            values={"job_id": application.job_id}
        )

        # Format response
        app_dict = dict(new_application)
        response_data = {
            "id": str(app_dict["id"]),
            "user_id": str(app_dict["user_id"]),
            "job_id": str(app_dict["job_id"]),
            "status": app_dict["status"],
            "cover_letter": app_dict["cover_letter"],
            "notes": app_dict["notes"],
            "applied_at": app_dict["applied_at"],
            "ai_generated_cover_letter": app_dict.get("ai_generated_cover_letter", False),
            "ai_auto_applied": app_dict.get("ai_auto_applied", False),
            "created_at": app_dict["created_at"],
            "updated_at": app_dict["updated_at"],
            "job": {
                "id": str(job["id"]),
                "title": job["title"],
                "company": job["company"]
            }
        }

        return JSONResponse(content=response_data, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create application"
        )


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    update_data: ApplicationUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update a job application"""

    try:
        if not permission_checker.has_permission(current_user, "applications", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update applications"
            )

        # Check if application exists and belongs to user
        check_query = """
            SELECT * FROM applications
            WHERE id = :application_id AND user_id = :user_id
        """
        application = await database.fetch_one(
            query=check_query,
            values={"application_id": application_id, "user_id": current_user["id"]}
        )

        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )

        # Prepare update data
        update_fields = update_data.model_dump(exclude_unset=True)
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Build dynamic update query
        set_clauses = []
        values = {"application_id": application_id, "updated_at": datetime.utcnow()}

        for field, value in update_fields.items():
            set_clauses.append(f"{field} = :{field}")
            values[field] = value

        set_clauses.append("updated_at = :updated_at")

        update_query = f"""
            UPDATE applications
            SET {', '.join(set_clauses)}
            WHERE id = :application_id
            RETURNING *
        """

        updated_application = await database.fetch_one(query=update_query, values=values)

        # Get job details for response
        job_query = """
            SELECT id, title, company, location, salary_min, salary_max, job_type, remote, date_posted
            FROM jobs WHERE id = :job_id
        """
        job = await database.fetch_one(
            query=job_query,
            values={"job_id": updated_application["job_id"]}
        )

        # Format response
        app_dict = dict(updated_application)
        response_data = {
            "id": str(app_dict["id"]),
            "user_id": str(app_dict["user_id"]),
            "job_id": str(app_dict["job_id"]),
            "status": app_dict["status"],
            "cover_letter": app_dict["cover_letter"],
            "notes": app_dict["notes"],
            "applied_at": app_dict["applied_at"],
            "ai_generated_cover_letter": app_dict.get("ai_generated_cover_letter", False),
            "ai_auto_applied": app_dict.get("ai_auto_applied", False),
            "created_at": app_dict["created_at"],
            "updated_at": app_dict["updated_at"],
            "job": {
                "id": str(job["id"]),
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "salary_min": job["salary_min"],
                "salary_max": job["salary_max"],
                "job_type": job["job_type"],
                "remote": job["remote"],
                "date_posted": job["date_posted"]
            }
        }

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application"
        )


@router.delete("/{application_id}")
async def delete_application(
    application_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a job application"""

    try:
        if not permission_checker.has_permission(current_user, "applications", "delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete applications"
            )

        # Check if application exists and belongs to user
        check_query = """
            SELECT job_id FROM applications
            WHERE id = :application_id AND user_id = :user_id
        """
        application = await database.fetch_one(
            query=check_query,
            values={"application_id": application_id, "user_id": current_user["id"]}
        )

        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )

        # Delete application
        delete_query = "DELETE FROM applications WHERE id = :application_id"
        await database.execute(query=delete_query, values={"application_id": application_id})

        # Update job application count
        await database.execute(
            query="UPDATE jobs SET application_count = application_count - 1 WHERE id = :job_id",
            values={"job_id": application["job_id"]}
        )

        return {"success": True, "message": "Application deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete application"
        )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific application by ID"""

    try:
        if not permission_checker.has_permission(current_user, "applications", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read applications"
            )

        query = """
            SELECT a.*, j.title, j.company, j.location, j.salary_min, j.salary_max,
                   j.job_type, j.remote, j.date_posted, j.description, j.apply_url
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.id = :application_id AND a.user_id = :user_id
        """

        application = await database.fetch_one(
            query=query,
            values={"application_id": application_id, "user_id": current_user["id"]}
        )

        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )

        # Format response
        app_dict = dict(application)
        response_data = {
            "id": str(app_dict["id"]),
            "user_id": str(app_dict["user_id"]),
            "job_id": str(app_dict["job_id"]),
            "status": app_dict["status"],
            "cover_letter": app_dict["cover_letter"],
            "notes": app_dict["notes"],
            "applied_at": app_dict["applied_at"],
            "ai_generated_cover_letter": app_dict.get("ai_generated_cover_letter", False),
            "ai_auto_applied": app_dict.get("ai_auto_applied", False),
            "created_at": app_dict["created_at"],
            "updated_at": app_dict["updated_at"],
            "job": {
                "id": str(app_dict["job_id"]),
                "title": app_dict["title"],
                "company": app_dict["company"],
                "location": app_dict["location"],
                "salary_min": app_dict["salary_min"],
                "salary_max": app_dict["salary_max"],
                "job_type": app_dict["job_type"],
                "remote": app_dict["remote"],
                "date_posted": app_dict["date_posted"],
                "description": app_dict["description"],
                "apply_url": app_dict["apply_url"]
            }
        }

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch application"
        )


@router.get("/stats/summary")
async def get_application_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's application statistics"""

    try:
        if not permission_checker.has_permission(current_user, "analytics", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read analytics"
            )

        # Get application counts by status
        stats_query = """
            SELECT
                status,
                COUNT(*) as count
            FROM applications
            WHERE user_id = :user_id
            GROUP BY status
        """

        stats = await database.fetch_all(query=stats_query, values={"user_id": current_user["id"]})

        # Get recent activity (last 30 days)
        recent_query = """
            SELECT COUNT(*) as recent_applications
            FROM applications
            WHERE user_id = :user_id AND created_at >= :since_date
        """

        since_date = datetime.utcnow() - timedelta(days=30)
        recent_result = await database.fetch_one(
            query=recent_query,
            values={"user_id": current_user["id"], "since_date": since_date}
        )

        # Format stats
        status_counts = {stat["status"]: stat["count"] for stat in stats}
        total_applications = sum(status_counts.values())

        response_data = {
            "total_applications": total_applications,
            "by_status": status_counts,
            "recent_applications_30d": recent_result["recent_applications"] if recent_result else 0,
            "success_rate": round(
                (status_counts.get("offer", 0) / total_applications * 100) if total_applications > 0 else 0,
                2
            )
        }

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching application stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch application statistics"
        )