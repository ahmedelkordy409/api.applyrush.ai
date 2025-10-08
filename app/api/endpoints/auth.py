"""
Authentication API endpoints
Handles user authentication, registration, and session management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import string
from app.core.database import database
from app.core.security import verify_password, hash_password, create_access_token, decode_token
from app.core.config import settings
from app.models.user import User
from app.services.email import send_magic_link_email
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


class SignUpRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    from_onboarding: Optional[bool] = False

    @validator('email')
    def email_lowercase(cls, v):
        return v.lower().strip()


class SignUpResponse(BaseModel):
    success: bool
    user: Dict[str, Any]
    temp_password: Optional[str] = None
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @validator('email')
    def email_lowercase(cls, v):
        return v.lower().strip()


class LoginResponse(BaseModel):
    success: bool
    user: Dict[str, Any]
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MagicLinkRequest(BaseModel):
    email: EmailStr
    redirect_url: Optional[str] = None

    @validator('email')
    def email_lowercase(cls, v):
        return v.lower().strip()


class MagicLinkVerifyRequest(BaseModel):
    token: str


class SessionResponse(BaseModel):
    user: Optional[Dict[str, Any]]
    is_authenticated: bool
    subscription_status: Optional[str] = None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user from JWT token or session ID"""
    try:
        token = credentials.credentials
        user_id = None

        # Try to decode as JWT token first
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
        except:
            # If JWT decode fails, treat as session ID and look up in database
            session_query = """
                SELECT user_id FROM sessions
                WHERE session_id = :session_id AND expires_at > :now
            """
            session = await database.fetch_one(
                query=session_query,
                values={"session_id": token, "now": datetime.utcnow()}
            )
            if session:
                user_id = session["user_id"]

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        query = """
            SELECT id, email, full_name, role, created_at, email_verified,
                   subscription_status, subscription_plan
            FROM users
            WHERE id = :user_id AND active = true
        """
        user = await database.fetch_one(query=query, values={"user_id": user_id})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return dict(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest):
    """Create a new user account"""
    try:
        # Check if user already exists
        query = "SELECT id FROM users WHERE email = :email"
        existing_user = await database.fetch_one(
            query=query,
            values={"email": request.email}
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Generate temporary password if not provided
        temp_password = None
        if not request.password:
            temp_password = ''.join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(8)
            ) + 'A1!'
            password = temp_password
        else:
            password = request.password

        # Hash the password
        hashed_password = hash_password(password)

        # Create user in database
        query = """
            INSERT INTO users (
                email, password_hash, created_at, updated_at,
                email_verified, active, role, from_onboarding, onboarding_completed
            ) VALUES (
                :email, :password_hash, :created_at, :updated_at,
                :email_verified, :active, :role, :from_onboarding, :onboarding_completed
            ) RETURNING id, email, created_at, role
        """

        values = {
            "email": request.email,
            "password_hash": hashed_password,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "email_verified": False,
            "active": True,
            "role": "user",
            "from_onboarding": request.from_onboarding,
            "onboarding_completed": request.from_onboarding  # Mark as completed if from onboarding
        }

        user = await database.fetch_one(query=query, values=values)

        # Create profile entry
        profile_query = """
            INSERT INTO profiles (user_id, email, created_at, updated_at)
            VALUES (:user_id, :email, :created_at, :updated_at)
        """
        await database.execute(
            query=profile_query,
            values={
                "user_id": user["id"],
                "email": request.email,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )

        response = SignUpResponse(
            success=True,
            user={
                "id": str(user["id"]),
                "email": user["email"],
                "role": user["role"]
            },
            temp_password=temp_password,
            message="User created successfully"
        )

        if temp_password:
            response.message = "User created with temporary password"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_BAD_REQUEST,
            detail="Failed to create user account"
        )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return access token"""
    try:
        # Get user from database
        query = """
            SELECT id, email, password_hash, full_name, role, active, email_verified,
                   subscription_status, subscription_plan
            FROM users
            WHERE email = :email
        """
        user = await database.fetch_one(query=query, values={"email": request.email})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if not user["active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        # Verify password
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create access token
        access_token = create_access_token(
            data={"sub": str(user["id"]), "email": user["email"], "role": user["role"]}
        )

        # Update last login
        update_query = "UPDATE users SET last_login = :last_login WHERE id = :user_id"
        await database.execute(
            query=update_query,
            values={"last_login": datetime.utcnow(), "user_id": user["id"]}
        )

        return LoginResponse(
            success=True,
            user={
                "id": str(user["id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "email_verified": user["email_verified"],
                "subscription_status": user["subscription_status"],
                "subscription_plan": user["subscription_plan"]
            },
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/magic-link")
async def request_magic_link(request: MagicLinkRequest):
    """Send magic link for passwordless authentication"""
    try:
        # Check if user exists
        query = "SELECT id, email FROM users WHERE email = :email"
        user = await database.fetch_one(query=query, values={"email": request.email})

        if not user:
            # Don't reveal if user exists or not
            return {"success": True, "message": "If an account exists, a magic link has been sent"}

        # Generate magic link token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        # Store token in database
        token_query = """
            INSERT INTO magic_link_tokens (user_id, token, expires_at, used)
            VALUES (:user_id, :token, :expires_at, :used)
        """
        await database.execute(
            query=token_query,
            values={
                "user_id": user["id"],
                "token": token,
                "expires_at": expires_at,
                "used": False
            }
        )

        # Send magic link email
        magic_link_url = f"{request.redirect_url or settings.FRONTEND_URL}/auth/verify?token={token}"
        await send_magic_link_email(user["email"], magic_link_url)

        return {"success": True, "message": "If an account exists, a magic link has been sent"}

    except Exception as e:
        logger.error(f"Magic link request error: {str(e)}")
        # Don't reveal errors to prevent user enumeration
        return {"success": True, "message": "If an account exists, a magic link has been sent"}


@router.post("/magic-link/verify", response_model=LoginResponse)
async def verify_magic_link(request: MagicLinkVerifyRequest):
    """Verify magic link token and authenticate user"""
    try:
        # Get token from database
        query = """
            SELECT mlt.user_id, mlt.expires_at, mlt.used, u.email, u.full_name, u.role,
                   u.email_verified, u.subscription_status, u.subscription_plan
            FROM magic_link_tokens mlt
            JOIN users u ON mlt.user_id = u.id
            WHERE mlt.token = :token
        """
        token_data = await database.fetch_one(query=query, values={"token": request.token})

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )

        if token_data["used"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token has already been used"
            )

        if token_data["expires_at"] < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token has expired"
            )

        # Mark token as used
        update_token_query = """
            UPDATE magic_link_tokens
            SET used = true, used_at = :used_at
            WHERE token = :token
        """
        await database.execute(
            query=update_token_query,
            values={"used_at": datetime.utcnow(), "token": request.token}
        )

        # Update user email verification and last login
        update_user_query = """
            UPDATE users
            SET email_verified = true, last_login = :last_login
            WHERE id = :user_id
        """
        await database.execute(
            query=update_user_query,
            values={"last_login": datetime.utcnow(), "user_id": token_data["user_id"]}
        )

        # Create access token
        access_token = create_access_token(
            data={
                "sub": str(token_data["user_id"]),
                "email": token_data["email"],
                "role": token_data["role"]
            }
        )

        return LoginResponse(
            success=True,
            user={
                "id": str(token_data["user_id"]),
                "email": token_data["email"],
                "full_name": token_data["full_name"],
                "role": token_data["role"],
                "email_verified": True,
                "subscription_status": token_data["subscription_status"],
                "subscription_plan": token_data["subscription_plan"]
            },
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Magic link verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify magic link"
        )


@router.get("/session", response_model=SessionResponse)
async def get_session(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user session"""
    try:
        return SessionResponse(
            user={
                "id": str(current_user["id"]),
                "email": current_user["email"],
                "full_name": current_user["full_name"],
                "role": current_user["role"],
                "email_verified": current_user["email_verified"]
            },
            is_authenticated=True,
            subscription_status=current_user.get("subscription_status")
        )
    except Exception as e:
        logger.error(f"Session retrieval error: {str(e)}")
        return SessionResponse(
            user=None,
            is_authenticated=False
        )


@router.post("/logout")
async def logout(response: Response, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Logout user (client should remove token)"""
    try:
        # In a JWT-based system, logout is typically handled client-side
        # But we can add token to a blacklist if needed

        # Optional: Add token to blacklist in Redis
        # await redis_client.setex(f"blacklist:{token}", settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, "1")

        response.delete_cookie("access_token")
        return {"success": True, "message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/refresh")
async def refresh_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Refresh access token"""
    try:
        # Create new access token
        new_token = create_access_token(
            data={
                "sub": str(current_user["id"]),
                "email": current_user["email"],
                "role": current_user["role"]
            }
        )

        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )