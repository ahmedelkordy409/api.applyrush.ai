"""
Admin API endpoints
Handles administrative functions and user management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import logging

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker, verify_password, hash_password

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    user: Dict[str, Any]
    access_token: str
    token_type: str = "bearer"


class UserListResponse(BaseModel):
    users: List[Dict[str, Any]]
    total: int
    page: int
    limit: int


class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None


async def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Dependency to ensure user has admin role"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """Admin login endpoint"""
    try:
        # Get admin user from database
        query = """
            SELECT id, email, password_hash, full_name, role, active, email_verified
            FROM users
            WHERE email = :email AND role IN ('admin', 'super_admin')
        """
        user = await database.fetch_one(query=query, values={"email": request.email})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )

        if not user["active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is inactive"
            )

        # Verify password
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )

        # Create access token
        from app.core.security import create_access_token
        access_token = create_access_token(
            data={"sub": str(user["id"]), "email": user["email"], "role": user["role"]}
        )

        # Update last login
        update_query = "UPDATE users SET last_login = :last_login WHERE id = :user_id"
        await database.execute(
            query=update_query,
            values={"last_login": datetime.utcnow(), "user_id": user["id"]}
        )

        return AdminLoginResponse(
            success=True,
            user={
                "id": str(user["id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "email_verified": user["email_verified"]
            },
            access_token=access_token
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin login failed"
        )


@router.post("/auth/logout")
async def admin_logout(admin_user: Dict[str, Any] = Depends(require_admin)):
    """Admin logout endpoint"""
    try:
        return {"success": True, "message": "Admin logged out successfully"}
    except Exception as e:
        logger.error(f"Admin logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin logout failed"
        )


@router.get("/users", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    subscription_plan: Optional[str] = Query(None),
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Get list of users with filtering and pagination"""
    try:
        # Build base query
        where_conditions = []
        query_params = {"limit": limit, "offset": (page - 1) * limit}

        if search:
            where_conditions.append("(email ILIKE :search OR full_name ILIKE :search)")
            query_params["search"] = f"%{search}%"

        if role:
            where_conditions.append("role = :role")
            query_params["role"] = role

        if active is not None:
            where_conditions.append("active = :active")
            query_params["active"] = active

        if subscription_plan:
            where_conditions.append("subscription_plan = :subscription_plan")
            query_params["subscription_plan"] = subscription_plan

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM users {where_clause}"
        total_result = await database.fetch_one(count_query, query_params)
        total = total_result["total"] if total_result else 0

        # Get users
        users_query = f"""
            SELECT id, email, full_name, role, active, email_verified,
                   subscription_plan, subscription_status, created_at, last_login
            FROM users
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        users = await database.fetch_all(users_query, query_params)

        # Format users
        formatted_users = []
        for user in users:
            user_dict = dict(user)
            user_dict["id"] = str(user_dict["id"])
            formatted_users.append(user_dict)

        return UserListResponse(
            users=formatted_users,
            total=total,
            page=page,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Get detailed user information"""
    try:
        # Get user details
        user_query = """
            SELECT u.*, p.phone_number, p.job_title, p.years_experience,
                   p.desired_salary, p.work_type, p.location_preferences,
                   p.education_level, p.resume_uploaded, p.work_authorization
            FROM users u
            LEFT JOIN profiles p ON u.id = p.user_id
            WHERE u.id = :user_id
        """

        user = await database.fetch_one(query=user_query, values={"user_id": user_id})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get user's application stats
        app_stats_query = """
            SELECT
                COUNT(*) as total_applications,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'applied' THEN 1 END) as applied,
                COUNT(CASE WHEN status = 'interview' THEN 1 END) as interviews,
                COUNT(CASE WHEN status = 'offer' THEN 1 END) as offers,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected
            FROM applications
            WHERE user_id = :user_id
        """

        app_stats = await database.fetch_one(
            query=app_stats_query,
            values={"user_id": user_id}
        )

        # Get recent applications
        recent_apps_query = """
            SELECT a.id, a.status, a.applied_at, j.title, j.company
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.user_id = :user_id
            ORDER BY a.applied_at DESC
            LIMIT 10
        """

        recent_apps = await database.fetch_all(
            query=recent_apps_query,
            values={"user_id": user_id}
        )

        user_dict = dict(user)
        user_dict["id"] = str(user_dict["id"])

        return {
            "user": user_dict,
            "application_stats": dict(app_stats) if app_stats else {},
            "recent_applications": [dict(app) for app in recent_apps]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user details"
        )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Update user information"""
    try:
        # Check if user exists
        check_query = "SELECT id FROM users WHERE id = :user_id"
        existing_user = await database.fetch_one(
            query=check_query,
            values={"user_id": user_id}
        )

        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prepare update data
        update_data = request.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Build update query
        set_clauses = []
        values = {"user_id": user_id, "updated_at": datetime.utcnow()}

        for field, value in update_data.items():
            set_clauses.append(f"{field} = :{field}")
            values[field] = value

        set_clauses.append("updated_at = :updated_at")

        update_query = f"""
            UPDATE users
            SET {', '.join(set_clauses)}
            WHERE id = :user_id
            RETURNING id, email, full_name, role, active, subscription_plan, subscription_status
        """

        updated_user = await database.fetch_one(query=update_query, values=values)

        user_dict = dict(updated_user)
        user_dict["id"] = str(user_dict["id"])

        return {
            "success": True,
            "user": user_dict,
            "message": "User updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    permanent: bool = Query(False),
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Delete or deactivate user"""
    try:
        # Check if user exists
        check_query = "SELECT id, role FROM users WHERE id = :user_id"
        existing_user = await database.fetch_one(
            query=check_query,
            values={"user_id": user_id}
        )

        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prevent deleting admin users (unless super admin)
        if existing_user["role"] in ["admin", "super_admin"] and admin_user["role"] != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete admin users"
            )

        if permanent:
            # Permanent deletion - cascade delete related data
            await database.execute(
                query="DELETE FROM applications WHERE user_id = :user_id",
                values={"user_id": user_id}
            )
            await database.execute(
                query="DELETE FROM profiles WHERE user_id = :user_id",
                values={"user_id": user_id}
            )
            await database.execute(
                query="DELETE FROM cover_letters WHERE user_id = :user_id",
                values={"user_id": user_id}
            )
            await database.execute(
                query="DELETE FROM users WHERE id = :user_id",
                values={"user_id": user_id}
            )
            message = "User permanently deleted"
        else:
            # Soft delete - deactivate user
            await database.execute(
                query="UPDATE users SET active = false, updated_at = :updated_at WHERE id = :user_id",
                values={"updated_at": datetime.utcnow(), "user_id": user_id}
            )
            message = "User deactivated"

        return {
            "success": True,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.get("/dashboard/stats")
async def get_admin_dashboard_stats(
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Get admin dashboard statistics"""
    try:
        # User stats
        user_stats_query = """
            SELECT
                COUNT(*) as total_users,
                COUNT(CASE WHEN active = true THEN 1 END) as active_users,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as new_users_30d,
                COUNT(CASE WHEN subscription_plan != 'free' THEN 1 END) as premium_users
            FROM users
        """

        user_stats = await database.fetch_one(user_stats_query)

        # Application stats
        app_stats_query = """
            SELECT
                COUNT(*) as total_applications,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as applications_30d,
                COUNT(CASE WHEN status = 'applied' THEN 1 END) as successful_applications,
                COUNT(CASE WHEN status = 'offer' THEN 1 END) as offers_received
            FROM applications
        """

        app_stats = await database.fetch_one(app_stats_query)

        # Job stats
        job_stats_query = """
            SELECT
                COUNT(*) as total_jobs,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_jobs,
                COUNT(CASE WHEN posted_date >= NOW() - INTERVAL '7 days' THEN 1 END) as new_jobs_7d
            FROM jobs
        """

        job_stats = await database.fetch_one(job_stats_query)

        # Revenue stats (mock data for now)
        revenue_stats = {
            "monthly_revenue": 2500.00,
            "total_revenue": 15000.00,
            "revenue_growth": 12.5
        }

        return {
            "user_stats": dict(user_stats) if user_stats else {},
            "application_stats": dict(app_stats) if app_stats else {},
            "job_stats": dict(job_stats) if job_stats else {},
            "revenue_stats": revenue_stats,
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error fetching admin stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch admin dashboard statistics"
        )


@router.get("/jobs/management")
async def get_jobs_management(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Get jobs for management interface"""
    try:
        # Build query conditions
        where_conditions = []
        query_params = {"limit": limit, "offset": (page - 1) * limit}

        if status:
            if status == "active":
                where_conditions.append("is_active = true")
            elif status == "inactive":
                where_conditions.append("is_active = false")

        if source:
            where_conditions.append("source = :source")
            query_params["source"] = source

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM jobs {where_clause}"
        total_result = await database.fetch_one(count_query, query_params)
        total = total_result["total"] if total_result else 0

        # Get jobs
        jobs_query = f"""
            SELECT id, external_id, title, company_id, location, salary_min, salary_max,
                   employment_type, remote_option, posted_date, source, is_active,
                   application_count, created_at
            FROM jobs
            {where_clause}
            ORDER BY posted_date DESC, created_at DESC
            LIMIT :limit OFFSET :offset
        """

        jobs = await database.fetch_all(jobs_query, query_params)

        # Format jobs
        formatted_jobs = []
        for job in jobs:
            job_dict = dict(job)
            job_dict["id"] = str(job_dict["id"])

            # Parse location if it's JSON
            try:
                import json
                if isinstance(job_dict["location"], str):
                    job_dict["location"] = json.loads(job_dict["location"])
            except:
                pass

            formatted_jobs.append(job_dict)

        return {
            "jobs": formatted_jobs,
            "total": total,
            "page": page,
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Error fetching jobs for management: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch jobs"
        )


@router.patch("/jobs/{job_id}/status")
async def update_job_status(
    job_id: str,
    is_active: bool,
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Update job active status"""
    try:
        # Update job status
        update_query = """
            UPDATE jobs
            SET is_active = :is_active, updated_at = :updated_at
            WHERE id = :job_id
            RETURNING id, title, is_active
        """

        result = await database.fetch_one(
            query=update_query,
            values={
                "is_active": is_active,
                "updated_at": datetime.utcnow(),
                "job_id": job_id
            }
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        return {
            "success": True,
            "job": dict(result),
            "message": f"Job {'activated' if is_active else 'deactivated'} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job status"
        )