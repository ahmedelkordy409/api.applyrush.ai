"""
ApplyRush.AI - Main FastAPI Application
Clean, production-ready backend with MongoDB
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import time
from typing import Callable

from app.core.database_new import connect_to_mongo, close_mongo_connection, MongoDB
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting ApplyRush.AI Backend...")
    await connect_to_mongo()

    # Start background job scheduler
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("✅ Background job scheduler started")

    logger.info("✅ Application started successfully")

    yield

    # Shutdown
    logger.info("🛑 Shutting down ApplyRush.AI Backend...")

    # Stop background job scheduler
    from app.core.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("✅ Background job scheduler stopped")

    await close_mongo_connection()
    logger.info("✅ Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="ApplyRush.AI API",
    description="""
## AI-Powered Job Application Automation Platform

### Features:
- 🤖 **Auto-Apply** - Automated job applications with AI
- 📄 **Resume Management** - Upload, parse, and optimize resumes
- 🎯 **Job Matching** - AI-powered job recommendations
- 📧 **Email Integration** - Direct email applications
- 🔍 **Job Scraping** - Indeed + Google Jobs integration
- 💳 **Subscriptions** - Stripe payment integration
- 📊 **Analytics** - Track application success rates

### Authentication:
Most endpoints require JWT authentication via Bearer token:
```
Authorization: Bearer {your_jwt_token}
```

Get your token from `/api/v1/auth/login` endpoint.

### Support:
- Documentation: https://docs.applyrush.ai
- Support: support@applyrush.ai
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "ApplyRush.AI Support",
        "email": "support@applyrush.ai",
    },
    license_info={
        "name": "Proprietary",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.applyrush.ai",
            "description": "Production server"
        }
    ]
)


# Middleware - Request timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Callable):
    """Add processing time to response headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Middleware - CORS
# Allow main app on localhost
allowed_origins = [
    "http://localhost:3000",
    "https://applyrush.ai",
    "https://www.applyrush.ai",
    "https://app.applyrush.ai",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if not settings.APP_DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Middleware - GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation error",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "message": str(exc) if settings.APP_DEBUG else "An error occurred"
        }
    )


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    db_status = await MongoDB.ping_async()

    return {
        "status": "healthy" if db_status else "unhealthy",
        "version": "2.0.0",
        "database": "connected" if db_status else "disconnected",
        "timestamp": time.time()
    }


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint"""
    return {
        "name": "ApplyRush.AI API",
        "version": "2.0.0",
        "description": "AI-Powered Job Application Automation",
        "docs": "/docs",
        "health": "/health"
    }


# Import and include API routers
from app.api.v1.router import api_router

app.include_router(api_router, prefix="/api/v1")


# Development server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main_new:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
