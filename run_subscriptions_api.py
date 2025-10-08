"""
ApplyRush.AI Production Subscriptions API Server
Handles subscriptions, payments, webhooks, and guest onboarding
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
import uvicorn
import secrets
import string
from datetime import datetime, timedelta

from app.api.endpoints.subscriptions import router as subscriptions_router
from app.api.endpoints.webhook import router as webhook_router
from app.api.endpoints.upselling import router as upselling_router
from app.services.mongodb_service import mongodb_service

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Parse ALLOWED_ORIGINS from environment
if IS_PRODUCTION:
    ALLOWED_ORIGINS = ["https://applyrush.ai", "https://www.applyrush.ai"]
else:
    origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001")
    # Handle both comma-separated string and default
    if origins_str and isinstance(origins_str, str):
        ALLOWED_ORIGINS = [origin.strip() for origin in origins_str.split(",")]
    else:
        ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]

# Pydantic models for request validation
class GuestSessionCreate(BaseModel):
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

class GuestAnswerSave(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    step_id: str = Field(..., min_length=1, max_length=100)
    answer: Dict[str, Any] = Field(default_factory=dict)
    time_spent_seconds: Optional[int] = Field(None, ge=0)

    @validator('session_id', 'step_id')
    def validate_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Must contain only alphanumeric characters, hyphens, and underscores')
        return v

# Create FastAPI app
app = FastAPI(
    title="ApplyRush.AI Subscriptions API",
    description="Subscription management, payment processing, and guest onboarding",
    version="1.0.0",
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None
)

# Validation exception handler
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error on {request.url.path}: {exc.errors()}")
    logger.error(f"Request body: {await request.body()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": str(await request.body())}
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    error_detail = str(exc) if not IS_PRODUCTION else "An internal error occurred"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": error_detail}
    )

# Database connection with retry logic
async def connect_to_mongodb_with_retry(max_retries: int = 3, retry_delay: int = 2):
    """Connect to MongoDB with exponential backoff retry logic"""
    for attempt in range(max_retries):
        try:
            await mongodb_service.connect()
            logger.info("✅ MongoDB connected successfully")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
            else:
                logger.error("❌ MongoDB connection failed after all retries")
                return False
    return False

# Lifespan events
@app.on_event("startup")
async def startup():
    """Connect to MongoDB on startup with retry logic"""
    import asyncio
    connected = await connect_to_mongodb_with_retry()
    if not connected:
        logger.warning("⚠️  Starting API without MongoDB connection")

@app.on_event("shutdown")
async def shutdown():
    """Disconnect from MongoDB on shutdown"""
    try:
        await mongodb_service.disconnect()
        logger.info("✅ MongoDB disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting MongoDB: {str(e)}")

# CORS middleware with environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add global OPTIONS handler for CORS preflight
from fastapi import Response

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight requests"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*" if not IS_PRODUCTION else "https://applyrush.ai",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )

# Include routers
app.include_router(subscriptions_router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(webhook_router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(upselling_router, prefix="/api/upselling", tags=["Upselling"])

# Guest onboarding endpoints with validation and error handling
@app.post("/api/onboarding/guest/create", status_code=status.HTTP_201_CREATED)
async def create_guest_session(data: GuestSessionCreate):
    """
    Create a new guest onboarding session

    Returns a unique session ID that can be used to track the guest's onboarding progress.
    Sessions expire after 24 hours. Data is persisted to MongoDB.
    """
    try:
        # Generate cryptographically secure session ID
        session_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(hours=24)

        session_data = {
            "session_id": session_id,
            "created_at": created_at,
            "expires_at": expires_at,
            "status": "active",
            "current_step": 0,
            "completed_steps": [],
            "answers": {},
            "referrer": data.referrer,
            "utm_source": data.utm_source,
            "utm_medium": data.utm_medium,
            "utm_campaign": data.utm_campaign
        }

        # Save to MongoDB
        try:
            if mongodb_service.db is not None:
                collection = mongodb_service.db["guest_sessions"]
                # Don't include response-only fields in MongoDB document
                db_document = {**session_data}
                await collection.insert_one(db_document)
                logger.info(f"Created guest session in MongoDB: {session_id}")
            else:
                logger.warning(f"MongoDB not available, session created in-memory only: {session_id}")
        except Exception as db_error:
            logger.error(f"MongoDB insert failed: {str(db_error)}", exc_info=True)
            # Continue anyway - session works without persistence

        # Return clean response (without MongoDB _id field)
        response_data = {
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "active",
            "current_step": 0,
            "completed_steps": [],
            "answers": {},
            "referrer": data.referrer,
            "utm_source": data.utm_source,
            "utm_medium": data.utm_medium,
            "utm_campaign": data.utm_campaign
        }

        return response_data

    except Exception as e:
        logger.error(f"Error creating guest session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create guest session"
        )

@app.get("/api/onboarding/guest/session/{session_id}", status_code=status.HTTP_200_OK)
async def get_guest_session(session_id: str):
    """
    Retrieve a guest onboarding session from MongoDB

    Returns the complete session data including all answers, progress, and metadata.
    Used for session recovery and synchronization between client and server.
    """
    try:
        if not session_id or len(session_id) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID"
            )

        if mongodb_service.db is not None:
            collection = mongodb_service.db["guest_sessions"]
            session = await collection.find_one({"session_id": session_id})

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )

            # Remove MongoDB _id from response
            session.pop('_id', None)

            # Convert datetime objects to ISO strings
            if 'created_at' in session:
                session['created_at'] = session['created_at'].isoformat() if hasattr(session['created_at'], 'isoformat') else session['created_at']
            if 'expires_at' in session:
                session['expires_at'] = session['expires_at'].isoformat() if hasattr(session['expires_at'], 'isoformat') else session['expires_at']
            if 'updated_at' in session:
                session['updated_at'] = session['updated_at'].isoformat() if hasattr(session['updated_at'], 'isoformat') else session['updated_at']

            return session
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session"
        )

@app.post("/api/onboarding/guest/answer", status_code=status.HTTP_200_OK)
async def save_guest_answer(data: GuestAnswerSave):
    """
    Save a guest's answer to an onboarding step

    Validates and stores the answer data in MongoDB for later retrieval when the guest converts to a user.
    Updates the guest session with the answer and tracks progress.
    """
    try:
        # Validate answer data doesn't exceed reasonable size (1MB)
        import json
        answer_size = len(json.dumps(data.answer))
        if answer_size > 1_000_000:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Answer data exceeds maximum size of 1MB"
            )

        saved_at = datetime.utcnow()

        # Update MongoDB with the answer
        try:
            if mongodb_service.db is not None:
                collection = mongodb_service.db["guest_sessions"]

                # First check if session exists
                session = await collection.find_one({"session_id": data.session_id})

                if not session:
                    logger.warning(f"Session not found: {data.session_id}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Guest session not found or expired"
                    )

                # Check if session is expired
                if datetime.fromisoformat(session["expires_at"].replace('Z', '+00:00') if isinstance(session["expires_at"], str) else session["expires_at"].isoformat()) < datetime.utcnow():
                    logger.warning(f"Session expired: {data.session_id}")
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Guest session has expired"
                    )

                # Update session with answer
                update_data = {
                    f"answers.{data.step_id}": data.answer,
                    "updated_at": saved_at
                }

                # Add step to completed_steps if not already there
                if data.step_id not in session.get("completed_steps", []):
                    update_data["completed_steps"] = session.get("completed_steps", []) + [data.step_id]

                # Track time spent if provided
                if data.time_spent_seconds:
                    update_data["total_time_spent"] = session.get("total_time_spent", 0) + data.time_spent_seconds

                # Special handling for email collection step
                if data.step_id == "email-collection" and "email" in data.answer:
                    update_data["email"] = data.answer["email"]
                    update_data["status"] = "email_provided"

                result = await collection.update_one(
                    {"session_id": data.session_id},
                    {"$set": update_data}
                )

                if result.modified_count > 0:
                    logger.info(f"✅ SAVED TO DATABASE: session={data.session_id}, step={data.step_id}, answer_keys={list(data.answer.keys())}")
                    logger.info(f"📊 Progress: completed_steps={update_data.get('completed_steps', [])}")
                else:
                    logger.warning(f"⚠️  No documents modified for session {data.session_id}")

            else:
                logger.warning(f"MongoDB not available, answer not persisted: {data.session_id}")

        except HTTPException:
            raise
        except Exception as db_error:
            logger.error(f"MongoDB update failed: {str(db_error)}", exc_info=True)
            # Continue anyway - return success even if persistence fails
            logger.warning(f"Continuing without MongoDB persistence for session {data.session_id}")

        result = {
            "success": True,
            "session_id": data.session_id,
            "step_id": data.step_id,
            "saved_at": saved_at.isoformat(),
            "time_spent_seconds": data.time_spent_seconds
        }

        logger.info(f"Saved answer for session {data.session_id}, step {data.step_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving guest answer: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save answer"
        )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ApplyRush.AI Subscriptions API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "validate_coupon": "POST /api/subscriptions/validate-coupon",
            "create_checkout": "POST /api/subscriptions/create-checkout-session",
            "get_plans": "GET /api/subscriptions/plans"
        }
    }

@app.get("/health")
async def health():
    """
    Comprehensive health check endpoint

    Checks the status of all critical services including database connectivity.
    Returns 200 if all services are healthy, 503 if any service is unhealthy.
    """
    try:
        # Check MongoDB connection
        mongodb_healthy = False
        try:
            if mongodb_service.client:
                # Ping MongoDB to verify connection
                await mongodb_service.client.admin.command('ping')
                mongodb_healthy = True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {str(e)}")

        health_status = {
            "status": "healthy" if mongodb_healthy else "degraded",
            "service": "subscriptions-api",
            "version": "1.0.0",
            "environment": ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "mongodb": "healthy" if mongodb_healthy else "unhealthy",
                "api": "healthy"
            }
        }

        status_code = status.HTTP_200_OK if mongodb_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(content=health_status, status_code=status_code)

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "status": "unhealthy",
                "service": "subscriptions-api",
                "error": str(e)
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

if __name__ == "__main__":
    import asyncio

    print("\n" + "=" * 60)
    print("🚀 Starting ApplyRush.AI Production API Server")
    print("=" * 60)
    print(f"\n🌍 Environment: {ENVIRONMENT}")
    print(f"📍 Server: http://0.0.0.0:8001")
    if not IS_PRODUCTION:
        print(f"📚 API Docs: http://localhost:8001/docs")
    print(f"❤️  Health Check: http://localhost:8001/health")
    print("\n🔗 Available endpoints:")
    print("   Guest Onboarding:")
    print("   - POST /api/onboarding/guest/create")
    print("   - POST /api/onboarding/guest/answer")
    print("   Subscriptions:")
    print("   - GET /api/subscriptions/plans")
    print("   - POST /api/subscriptions/validate-coupon")
    print("   - POST /api/subscriptions/create-checkout-session")
    print("   Webhooks:")
    print("   - POST /api/webhooks/stripe")
    print("   Upselling:")
    print("   - GET /api/upselling/recommendations")
    print("\n" + "=" * 60 + "\n")

    # Production-ready uvicorn configuration
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
