"""
Enterprise Production-Ready Onboarding Server
MongoDB integration with proper validation, security, and monitoring
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field, validator
import uvicorn
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import secrets
import string

# Import MongoDB models
from app.models.onboarding_models import (
    GuestProfile,
    OnboardingAnswer,
    OnboardingStatus,
    CreateGuestSessionRequest,
    CreateGuestSessionResponse,
    SaveAnswerRequest,
    SaveAnswerResponse
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)

# Rate limiting tracking (in production use Redis)
request_counts = {}

class RateLimitConfig:
    REQUESTS_PER_MINUTE = 60
    REQUESTS_PER_HOUR = 1000

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MongoDB connection and cleanup on shutdown"""
    try:
        # MongoDB connection
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        database_name = os.getenv("DATABASE_NAME", "jobhire_ai")

        client = AsyncIOMotorClient(mongodb_url)
        database = client[database_name]

        # Initialize Beanie with document models
        await init_beanie(
            database=database,
            document_models=[
                GuestProfile,
                OnboardingAnswer,
            ]
        )

        logger.info(f"✅ Connected to MongoDB: {mongodb_url}/{database_name}")
        yield

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    finally:
        # Cleanup
        if 'client' in locals():
            client.close()
            logger.info("🔌 MongoDB connection closed")

# Create FastAPI app with enterprise features
app = FastAPI(
    title="JobHire.AI Onboarding API",
    description="Enterprise-grade guest onboarding with progressive data collection",
    version="2.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None,
    lifespan=lifespan
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.applyrush.ai"]
)

# CORS with strict production settings
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://app.applyrush.ai",
    "https://www.applyrush.ai"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=86400,  # 24 hours
)

async def rate_limit_check(request: Request) -> bool:
    """Simple rate limiting (use Redis in production)"""
    client_ip = request.client.host
    current_time = datetime.utcnow()

    if client_ip not in request_counts:
        request_counts[client_ip] = []

    # Remove old requests (older than 1 hour)
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if (current_time - req_time).total_seconds() < 3600
    ]

    # Check rate limits
    recent_requests = [
        req_time for req_time in request_counts[client_ip]
        if (current_time - req_time).total_seconds() < 60
    ]

    if len(recent_requests) >= RateLimitConfig.REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if len(request_counts[client_ip]) >= RateLimitConfig.REQUESTS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Hourly rate limit exceeded")

    request_counts[client_ip].append(current_time)
    return True

def generate_secure_session_id() -> str:
    """Generate cryptographically secure session ID"""
    return secrets.token_urlsafe(32)

async def log_user_activity(
    session_id: str,
    action: str,
    metadata: Optional[Dict[str, Any]] = None,
    background_tasks: Optional[BackgroundTasks] = None
):
    """Log user activity for analytics (async)"""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "action": action,
        "metadata": metadata or {}
    }

    # In production, send to analytics service
    logger.info(f"📊 User Activity: {log_data}")

def validate_step_data(step_id: str, answer: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize step data based on step type"""

    # Define validation rules for each step
    validation_rules = {
        "work-authorization": {
            "required_fields": ["authorized"],
            "allowed_values": {"authorized": [True, False, "sponsor"]}
        },
        "salary-selection": {
            "required_fields": ["salaryRange"],
            "pattern_validation": {"salaryRange": r"^\d+-\d+$"}
        },
        "email-collection": {
            "required_fields": ["email"],
            "email_validation": ["email"]
        }
    }

    rules = validation_rules.get(step_id, {})

    # Validate required fields
    for field in rules.get("required_fields", []):
        if field not in answer:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field}"
            )

    # Validate email fields
    for field in rules.get("email_validation", []):
        if field in answer:
            try:
                EmailStr.validate(answer[field])
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid email format: {field}"
                )

    # Sanitize data (remove any potential XSS)
    sanitized = {}
    for key, value in answer.items():
        if isinstance(value, str):
            # Basic XSS prevention
            sanitized[key] = value.replace("<", "&lt;").replace(">", "&gt;")[:1000]
        elif isinstance(value, (bool, int, float)):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = value[:50]  # Limit array size
        else:
            sanitized[key] = str(value)[:1000]

    return sanitized

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"

    return response

# === API ENDPOINTS ===

@app.post("/api/onboarding/guest/create", response_model=CreateGuestSessionResponse)
async def create_guest_session(
    request: CreateGuestSessionRequest,
    background_tasks: BackgroundTasks,
    client_request: Request,
    _rate_limit: bool = Depends(rate_limit_check)
):
    """Create a new guest onboarding session with enterprise validation"""

    try:
        # Generate secure session ID
        session_id = generate_secure_session_id()

        # Create guest profile in MongoDB
        guest_profile = GuestProfile(
            session_id=session_id,
            status=OnboardingStatus.IN_PROGRESS,
            current_step=0,
            completed_steps=[],
            answers={},
            time_spent_seconds=0
        )

        # Add tracking metadata
        client_ip = client_request.client.host
        user_agent = client_request.headers.get("user-agent", "")

        # Save to MongoDB
        await guest_profile.save()

        # Log activity asynchronously
        await log_user_activity(
            session_id=session_id,
            action="session_created",
            metadata={
                "ip": client_ip,
                "user_agent": user_agent,
                "referrer": request.referrer,
                "utm_source": request.utm_source
            },
            background_tasks=background_tasks
        )

        logger.info(f"✅ Created guest session: {session_id}")

        return CreateGuestSessionResponse(
            session_id=session_id,
            created_at=guest_profile.created_at.isoformat(),
            expires_at=guest_profile.expires_at.isoformat(),
            status="success"
        )

    except Exception as e:
        logger.error(f"❌ Failed to create guest session: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create session. Please try again."
        )

@app.post("/api/onboarding/guest/answer", response_model=SaveAnswerResponse)
async def save_guest_answer(
    request: SaveAnswerRequest,
    background_tasks: BackgroundTasks,
    _rate_limit: bool = Depends(rate_limit_check)
):
    """Save guest answer with enterprise validation and monitoring"""

    try:
        # Find guest profile
        guest_profile = await GuestProfile.find_one(
            GuestProfile.session_id == request.session_id
        )

        if not guest_profile:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check session expiry
        if datetime.utcnow() > guest_profile.expires_at:
            raise HTTPException(status_code=410, detail="Session expired")

        # Validate and sanitize answer data
        sanitized_answer = validate_step_data(request.step_id, request.answer)

        # Update guest profile
        guest_profile.answers[request.step_id] = sanitized_answer

        # Update completion tracking
        if request.step_id not in guest_profile.completed_steps:
            guest_profile.completed_steps.append(request.step_id)

        guest_profile.current_step = len(guest_profile.completed_steps)
        guest_profile.last_activity = datetime.utcnow()

        # Update time spent
        if request.time_spent_seconds:
            guest_profile.time_spent_seconds += request.time_spent_seconds

        # Handle email collection step
        if request.step_id == "email-collection" and "email" in sanitized_answer:
            guest_profile.email = sanitized_answer["email"]
            guest_profile.status = OnboardingStatus.EMAIL_PROVIDED

        # Save to MongoDB
        await guest_profile.save()

        # Create OnboardingAnswer document for detailed tracking
        answer_doc = OnboardingAnswer(
            guest_session_id=request.session_id,
            step_id=request.step_id,
            question_type="onboarding",
            answer=sanitized_answer,
            time_to_answer_seconds=request.time_spent_seconds
        )
        await answer_doc.save()

        # Log activity
        await log_user_activity(
            session_id=request.session_id,
            action="answer_saved",
            metadata={
                "step_id": request.step_id,
                "time_spent": request.time_spent_seconds
            },
            background_tasks=background_tasks
        )

        logger.info(f"💾 Saved answer: {request.session_id} - {request.step_id}")

        return SaveAnswerResponse(
            success=True,
            step_id=request.step_id,
            current_step=guest_profile.current_step,
            completed_steps=guest_profile.completed_steps,
            status=guest_profile.status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save answer: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to save answer. Please try again."
        )

@app.get("/api/onboarding/guest/{session_id}")
async def get_guest_session(
    session_id: str,
    _rate_limit: bool = Depends(rate_limit_check)
):
    """Get guest session data with security validation"""

    try:
        guest_profile = await GuestProfile.find_one(
            GuestProfile.session_id == session_id
        )

        if not guest_profile:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check expiry
        if datetime.utcnow() > guest_profile.expires_at:
            raise HTTPException(status_code=410, detail="Session expired")

        return {
            "session_id": guest_profile.session_id,
            "created_at": guest_profile.created_at.isoformat(),
            "expires_at": guest_profile.expires_at.isoformat(),
            "status": guest_profile.status,
            "current_step": guest_profile.current_step,
            "completed_steps": guest_profile.completed_steps,
            "answers": guest_profile.answers,
            "email": guest_profile.email,
            "time_spent_seconds": guest_profile.time_spent_seconds
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get session: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

@app.get("/health")
async def health_check():
    """Enterprise health check endpoint"""
    try:
        # Test MongoDB connection
        test_count = await GuestProfile.count()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "total_sessions": test_count,
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.get("/metrics")
async def get_metrics():
    """Basic metrics endpoint (use Prometheus in production)"""
    try:
        total_sessions = await GuestProfile.count()
        active_sessions = await GuestProfile.find(
            GuestProfile.status.in_([OnboardingStatus.IN_PROGRESS, OnboardingStatus.EMAIL_PROVIDED])
        ).count()

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "conversion_rate": (active_sessions / max(total_sessions, 1)) * 100
        }
    except Exception as e:
        logger.error(f"❌ Metrics failed: {e}")
        return {"error": "Metrics unavailable"}

if __name__ == "__main__":
    # Production configuration
    config = {
        "host": "0.0.0.0",
        "port": int(os.getenv("PORT", 8000)),
        "log_level": "info",
        "access_log": True,
        "workers": int(os.getenv("WORKERS", 1)),
    }

    # Add SSL in production
    if os.getenv("SSL_KEYFILE") and os.getenv("SSL_CERTFILE"):
        config.update({
            "ssl_keyfile": os.getenv("SSL_KEYFILE"),
            "ssl_certfile": os.getenv("SSL_CERTFILE")
        })

    print("🚀 Starting Enterprise Onboarding Server...")
    print(f"📍 Server: http://0.0.0.0:{config['port']}")
    print(f"📚 API Docs: http://0.0.0.0:{config['port']}/docs")
    print(f"🔍 Health: http://0.0.0.0:{config['port']}/health")

    uvicorn.run("production_onboarding_server:app", **config)