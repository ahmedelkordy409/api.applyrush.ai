"""
Admin API endpoints - MongoDB Version
Handles administrative functions and user management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from bson import ObjectId
import logging
import bcrypt

from app.core.database_new import MongoDB
from app.core.security import get_current_user, create_access_token, verify_password, hash_password

logger = logging.getLogger(__name__)

router = APIRouter()


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
    is_active: Optional[bool] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None


async def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Dependency to ensure user has admin role"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None

    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """Admin login endpoint"""
    try:
        # Get admin user from database
        db = MongoDB.get_async_db()
        users_collection = db["users"]
        user = await users_collection.find_one({
            "email": request.email,
            "role": {"$in": ["admin", "super_admin"]}
        })

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )

        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is inactive"
            )

        # Verify password using bcrypt directly (avoid passlib compatibility issues)
        password_hash = user.get("password_hash") or user.get("hashed_password")
        if not password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )

        # Use bcrypt directly for verification
        password_bytes = request.password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8') if isinstance(password_hash, str) else password_hash

        if not bcrypt.checkpw(password_bytes, hash_bytes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )

        # Create access token
        access_token = create_access_token(
            data={
                "sub": str(user["_id"]),
                "email": user["email"],
                "role": user.get("role", "user")
            }
        )

        # Update last login
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )

        return AdminLoginResponse(
            success=True,
            user={
                "id": str(user["_id"]),
                "email": user["email"],
                "full_name": user.get("full_name", ""),
                "role": user.get("role", "user"),
                "email_verified": user.get("email_verified", False)
            },
            access_token=access_token
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin login failed"
        )


@router.post("/auth/logout")
async def admin_logout(admin_user: Dict[str, Any] = Depends(require_admin)):
    """Admin logout endpoint"""
    return {"success": True, "message": "Admin logged out successfully"}


@router.get("/users", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    subscription_tier: Optional[str] = Query(None),
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Get list of users with filtering and pagination"""
    try:
        db = MongoDB.get_async_db()
        users_collection = db["users"]

        # Build query filter
        query_filter = {}

        if search:
            query_filter["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"full_name": {"$regex": search, "$options": "i"}}
            ]

        if role:
            query_filter["role"] = role

        if is_active is not None:
            query_filter["is_active"] = is_active

        if subscription_tier:
            query_filter["subscription_tier"] = subscription_tier

        # Get total count
        total = await users_collection.count_documents(query_filter)

        # Get users with pagination
        skip = (page - 1) * limit
        cursor = users_collection.find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
        users = await cursor.to_list(length=limit)

        # Format users
        formatted_users = [serialize_doc(user) for user in users]

        return UserListResponse(
            users=formatted_users,
            total=total,
            page=page,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}", exc_info=True)
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
        db = MongoDB.get_async_db()
        users_collection = db["users"]
        applications_collection = db["applications"]

        # Get user
        try:
            user_object_id = ObjectId(user_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )

        user = await users_collection.find_one({"_id": user_object_id})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get application stats
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_applications": {"$sum": 1},
                "pending": {"$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}},
                "applied": {"$sum": {"$cond": [{"$eq": ["$status", "applied"]}, 1, 0]}},
                "interviews": {"$sum": {"$cond": [{"$eq": ["$status", "interview"]}, 1, 0]}},
                "offers": {"$sum": {"$cond": [{"$eq": ["$status", "offer"]}, 1, 0]}},
                "rejected": {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}}
            }}
        ]

        stats_cursor = applications_collection.aggregate(pipeline)
        stats_list = await stats_cursor.to_list(length=1)
        app_stats = stats_list[0] if stats_list else {
            "total_applications": 0,
            "pending": 0,
            "applied": 0,
            "interviews": 0,
            "offers": 0,
            "rejected": 0
        }

        # Get recent applications
        recent_apps_cursor = applications_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(10)
        recent_apps = await recent_apps_cursor.to_list(length=10)

        return {
            "user": serialize_doc(user),
            "application_stats": app_stats,
            "recent_applications": [serialize_doc(app) for app in recent_apps]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details: {str(e)}", exc_info=True)
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
        db = MongoDB.get_async_db()
        users_collection = db["users"]

        # Validate user ID
        try:
            user_object_id = ObjectId(user_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )

        # Check if user exists
        existing_user = await users_collection.find_one({"_id": user_object_id})

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

        update_data["updated_at"] = datetime.utcnow()

        # Update user
        result = await users_collection.update_one(
            {"_id": user_object_id},
            {"$set": update_data}
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get updated user
        updated_user = await users_collection.find_one({"_id": user_object_id})

        return {
            "success": True,
            "user": serialize_doc(updated_user),
            "message": "User updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}", exc_info=True)
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
        db = MongoDB.get_async_db()
        users_collection = db["users"]
        applications_collection = db["applications"]

        # Validate user ID
        try:
            user_object_id = ObjectId(user_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )

        # Check if user exists
        existing_user = await users_collection.find_one({"_id": user_object_id})

        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prevent deleting admin users (unless super admin)
        if existing_user.get("role") in ["admin", "super_admin"] and admin_user.get("role") != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete admin users"
            )

        if permanent:
            # Permanent deletion
            await applications_collection.delete_many({"user_id": user_id})
            await users_collection.delete_one({"_id": user_object_id})
            message = "User permanently deleted"
        else:
            # Soft delete - deactivate user
            await users_collection.update_one(
                {"_id": user_object_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            message = "User deactivated"

        return {
            "success": True,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}", exc_info=True)
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
        db = MongoDB.get_async_db()
        users_collection = db["users"]
        applications_collection = db["applications"]
        jobs_collection = db["jobs"]

        # User stats
        total_users = await users_collection.count_documents({})
        active_users = await users_collection.count_documents({"is_active": True})

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        new_users_30d = await users_collection.count_documents({
            "created_at": {"$gte": thirty_days_ago}
        })

        premium_users = await users_collection.count_documents({
            "subscription_tier": {"$ne": "free"}
        })

        # Application stats
        total_applications = await applications_collection.count_documents({})
        applications_30d = await applications_collection.count_documents({
            "created_at": {"$gte": thirty_days_ago}
        })
        successful_applications = await applications_collection.count_documents({
            "status": "applied"
        })
        offers_received = await applications_collection.count_documents({
            "status": "offer"
        })

        # Job stats
        total_jobs = await jobs_collection.count_documents({})
        active_jobs = await jobs_collection.count_documents({"is_active": True})

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        new_jobs_7d = await jobs_collection.count_documents({
            "scraped_at": {"$gte": seven_days_ago}
        })

        return {
            "user_stats": {
                "total_users": total_users,
                "active_users": active_users,
                "new_users_30d": new_users_30d,
                "premium_users": premium_users
            },
            "application_stats": {
                "total_applications": total_applications,
                "applications_30d": applications_30d,
                "successful_applications": successful_applications,
                "offers_received": offers_received
            },
            "job_stats": {
                "total_jobs": total_jobs,
                "active_jobs": active_jobs,
                "new_jobs_7d": new_jobs_7d
            },
            "revenue_stats": {
                "monthly_revenue": 0.00,
                "total_revenue": 0.00,
                "revenue_growth": 0.0
            },
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching admin stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch admin dashboard statistics"
        )


@router.get("/jobs/management")
async def get_jobs_management(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    source: Optional[str] = Query(None),
    admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Get jobs for management interface"""
    try:
        db = MongoDB.get_async_db()
        jobs_collection = db["jobs"]

        # Build query filter
        query_filter = {}

        if status_filter:
            if status_filter == "active":
                query_filter["is_active"] = True
            elif status_filter == "inactive":
                query_filter["is_active"] = False

        if source:
            query_filter["source"] = source

        # Get total count
        total = await jobs_collection.count_documents(query_filter)

        # Get jobs with pagination
        skip = (page - 1) * limit
        cursor = jobs_collection.find(query_filter).sort("scraped_at", -1).skip(skip).limit(limit)
        jobs = await cursor.to_list(length=limit)

        # Format jobs
        formatted_jobs = [serialize_doc(job) for job in jobs]

        return {
            "jobs": formatted_jobs,
            "total": total,
            "page": page,
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Error fetching jobs for management: {str(e)}", exc_info=True)
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
        db = MongoDB.get_async_db()
        jobs_collection = db["jobs"]

        # Validate job ID
        try:
            job_object_id = ObjectId(job_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job ID"
            )

        # Update job status
        result = await jobs_collection.update_one(
            {"_id": job_object_id},
            {"$set": {"is_active": is_active, "updated_at": datetime.utcnow()}}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        # Get updated job
        job = await jobs_collection.find_one({"_id": job_object_id})

        return {
            "success": True,
            "job": serialize_doc(job),
            "message": f"Job {'activated' if is_active else 'deactivated'} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job status"
        )
