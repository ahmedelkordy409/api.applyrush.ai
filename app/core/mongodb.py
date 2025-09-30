"""
MongoDB connection and configuration management
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB connection manager"""

    client: Optional[AsyncIOMotorClient] = None
    database = None


mongodb = MongoDB()


async def connect_to_mongodb():
    """Create database connection"""
    try:
        mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL)
        mongodb.database = mongodb.client[settings.MONGODB_DATABASE]

        # Test the connection
        await mongodb.client.admin.command('ismaster')
        logger.info(f"Connected to MongoDB: {settings.MONGODB_URL}")

        # Initialize Beanie with document models
        from app.models.mongodb_models import (
            User, Company, Job, JobMatch, JobApplication,
            ApplicationStatusHistory, AIProcessingLog, UserAnalytics
        )

        await init_beanie(
            database=mongodb.database,
            document_models=[
                User, Company, Job, JobMatch, JobApplication,
                ApplicationStatusHistory, AIProcessingLog, UserAnalytics
            ]
        )
        logger.info("Beanie initialized with document models")

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongodb_connection():
    """Close database connection"""
    if mongodb.client:
        mongodb.client.close()
        logger.info("Disconnected from MongoDB")


async def get_mongodb():
    """Get MongoDB database instance"""
    return mongodb.database


async def check_mongodb_health() -> bool:
    """Check if MongoDB is healthy"""
    try:
        if mongodb.client:
            await mongodb.client.admin.command('ismaster')
            return True
        return False
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return False