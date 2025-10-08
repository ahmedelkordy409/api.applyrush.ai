"""
Authentication endpoints - Login, signup, token refresh
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from bson import ObjectId
import bcrypt

from app.core.database_new import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user
)
from app.core.config import settings

router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str | None = None  # Optional for onboarding flow
    first_name: str | None = None
    last_name: str | None = None
    from_onboarding: bool = False  # Flag for passwordless signup


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, db=Depends(get_db)):
    """
    Create a new user account
    Supports both:
    - Full signup with password
    - Passwordless signup from onboarding (generates temp password)
    """
    # Check if user already exists
    existing_user = db.users.find_one({"email": request.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Generate temporary password for onboarding flow
    import secrets
    temp_password = None
    if request.from_onboarding and not request.password:
        temp_password = secrets.token_urlsafe(12)
        password_to_hash = temp_password
    elif request.password:
        password_to_hash = request.password
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required for non-onboarding signup"
        )

    # Hash password using bcrypt directly (avoid passlib compatibility issues)
    password_bytes = password_to_hash.encode('utf-8')
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    # Create new user
    user_doc = {
        "email": request.email,
        "password_hash": password_hash,
        "profile": {
            "first_name": request.first_name,
            "last_name": request.last_name
        },
        "role": "user",
        "subscription_tier": "free",
        "subscription_status": "inactive",
        "from_onboarding": request.from_onboarding,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Create tokens
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    response_data = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id
    )

    # Include temp password in response for onboarding flow
    if temp_password:
        return {
            **response_data.dict(),
            "tempPassword": temp_password,
            "user": {"id": user_id, "email": request.email}
        }

    return response_data


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    """
    Login with email and password
    """
    # Find user
    user = db.users.find_one({"email": request.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password using bcrypt directly (avoid passlib compatibility issues)
    password_hash = user.get("password_hash", "")
    if not password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    password_bytes = request.password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8') if isinstance(password_hash, str) else password_hash

    if not bcrypt.checkpw(password_bytes, hash_bytes):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(user["_id"])

    # Create tokens
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(request: RefreshTokenRequest, db=Depends(get_db)):
    """
    Refresh access token using refresh token
    """
    try:
        payload = decode_token(request.refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        user_id = payload.get("sub")

        # Verify user still exists
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Create new tokens
        access_token = create_access_token({"sub": user_id})
        new_refresh_token = create_refresh_token({"sub": user_id})

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user_id=user_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information
    """
    return {
        "id": current_user["_id"],
        "email": current_user["email"],
        "profile": current_user.get("profile", {}),
        "subscription_tier": current_user.get("subscription_tier", "free"),
        "subscription_status": current_user.get("subscription_status", "inactive")
    }


class UpdatePasswordRequest(BaseModel):
    email: EmailStr
    temp_password: str
    new_password: str


@router.put("/update-password")
async def update_password(request: UpdatePasswordRequest, db=Depends(get_db)):
    """
    Update user password from temporary password (onboarding flow)
    """
    # Find user by email
    user = db.users.find_one({"email": request.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify temporary password using bcrypt directly
    password_hash = user.get("password_hash", "")
    if not password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid temporary password"
        )

    temp_password_bytes = request.temp_password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8') if isinstance(password_hash, str) else password_hash

    if not bcrypt.checkpw(temp_password_bytes, hash_bytes):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid temporary password"
        )

    # Update to new password using bcrypt directly
    new_password_bytes = request.new_password.encode('utf-8')
    salt = bcrypt.gensalt()
    new_password_hash = bcrypt.hashpw(new_password_bytes, salt).decode('utf-8')

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow()
            }
        }
    )

    user_id = str(user["_id"])

    # Create new tokens
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id
    )
