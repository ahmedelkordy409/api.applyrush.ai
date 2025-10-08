#!/usr/bin/env python3
"""
Server startup script with comprehensive configuration.
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from jobhire.config.settings import get_settings
import structlog


def setup_environment():
    """Setup environment variables if not already set."""
    # Default environment variables for development
    defaults = {
        "APP_ENVIRONMENT": "development",
        "APP_HOST": "0.0.0.0",
        "APP_PORT": "8000",
        "LOG_LEVEL": "INFO",
        "SECRET_KEY": "dev-secret-key-change-in-production",
        "MONGODB_URL": "mongodb://localhost:27017",
        "MONGODB_DATABASE": "jobhire_ai_dev",
        "REDIS_URL": "redis://localhost:6379/0",
        "OPENAI_API_KEY": "your-openai-api-key",
        "REPLICATE_API_TOKEN": "your-replicate-token",
        "JSEARCH_API_KEY": "your-jsearch-api-key",
        "RAPID_API_KEY": "your-rapid-api-key",
        "ENABLE_METRICS": "true",
        "ENABLE_TRACING": "false"
    }

    for key, value in defaults.items():
        if key not in os.environ:
            os.environ[key] = value


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="JobHire.AI Backend Server")
    parser.add_argument(
        "--env",
        choices=["development", "staging", "production", "testing"],
        default="development",
        help="Environment to run in"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level"
    )

    args = parser.parse_args()

    # Setup environment
    setup_environment()
    os.environ["APP_ENVIRONMENT"] = args.env
    os.environ["APP_HOST"] = args.host
    os.environ["APP_PORT"] = str(args.port)
    os.environ["LOG_LEVEL"] = args.log_level

    # Get settings
    settings = get_settings()

    # Configure logging
    logger = structlog.get_logger(__name__)
    logger.info(
        "Starting JobHire.AI Backend Server",
        environment=settings.app_environment,
        host=args.host,
        port=args.port,
        version=settings.app_version
    )

    # Uvicorn configuration
    uvicorn_config = {
        "app": "src.jobhire.main:app",
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level.lower(),
        "access_log": True,
        "loop": "uvloop" if sys.platform != "win32" else "asyncio",
        "http": "httptools" if sys.platform != "win32" else "h11",
    }

    # Development specific settings
    if args.env == "development" or args.reload:
        uvicorn_config.update({
            "reload": True,
            "reload_dirs": [str(src_path)],
            "reload_excludes": ["*.pyc", "__pycache__", ".git", ".pytest_cache"]
        })
    else:
        # Production settings
        uvicorn_config.update({
            "workers": args.workers if args.workers > 1 else 1,
        })

    # Print startup information
    print("\n" + "="*60)
    print("🚀 JobHire.AI Backend Server")
    print("="*60)
    print(f"Environment: {args.env}")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Workers: {args.workers}")
    print(f"Reload: {args.reload or args.env == 'development'}")
    print(f"Log Level: {args.log_level}")
    print("\n📋 API Documentation:")
    print(f"  • Swagger UI: http://{args.host}:{args.port}/docs")
    print(f"  • ReDoc: http://{args.host}:{args.port}/redoc")
    print(f"  • OpenAPI JSON: http://{args.host}:{args.port}/openapi.json")
    print("\n🔗 Health Endpoints:")
    print(f"  • Health: http://{args.host}:{args.port}/api/v1/health")
    print(f"  • Status: http://{args.host}:{args.port}/api/v1/status")
    if settings.monitoring.enable_metrics:
        print(f"  • Metrics: http://{args.host}:{args.port}/metrics")
    print("\n💡 Press Ctrl+C to stop the server")
    print("="*60 + "\n")

    try:
        # Start the server
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Server startup failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()