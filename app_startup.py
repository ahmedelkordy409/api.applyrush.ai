"""
Application startup script with MongoDB initialization
"""
import asyncio
import logging
from app.services.mongodb_service import mongodb_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_mongodb():
    """Initialize MongoDB connection"""
    try:
        await mongodb_service.connect()
        logger.info("MongoDB initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {str(e)}")
        # Don't fail - app can run without MongoDB


# Run initialization
if __name__ == "__main__":
    asyncio.run(init_mongodb())
