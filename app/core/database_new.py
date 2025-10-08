"""
MongoDB Database Connection and Configuration
Clean, production-ready database layer for ApplyRush.AI
"""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

# Import settings lazily to ensure .env is loaded
def get_mongo_config():
    """Get MongoDB configuration from settings"""
    from app.core.config import settings
    return {
        'url': settings.MONGODB_URL,
        'database': settings.MONGODB_DATABASE,
        'min_pool': 10,
        'max_pool': 100
    }

# Global database instances
_sync_client: Optional[MongoClient] = None
_async_client: Optional[AsyncIOMotorClient] = None
_sync_db: Optional[Database] = None
_async_db: Optional[AsyncIOMotorDatabase] = None


class MongoDB:
    """MongoDB connection manager"""

    @staticmethod
    def get_sync_client() -> MongoClient:
        """Get synchronous MongoDB client"""
        global _sync_client

        if _sync_client is None:
            config = get_mongo_config()
            logger.info(f"Connecting to MongoDB (sync): {config['url'][:50]}...")
            _sync_client = MongoClient(
                config['url'],
                minPoolSize=config['min_pool'],
                maxPoolSize=config['max_pool'],
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
            )

            # Test connection
            try:
                _sync_client.admin.command('ping')
                logger.info("✅ MongoDB sync connection successful")
            except Exception as e:
                logger.error(f"❌ MongoDB sync connection failed: {e}")
                raise

        return _sync_client

    @staticmethod
    def get_async_client() -> AsyncIOMotorClient:
        """Get asynchronous MongoDB client (for async FastAPI endpoints)"""
        global _async_client

        if _async_client is None:
            config = get_mongo_config()
            logger.info(f"Connecting to MongoDB (async): {config['url'][:50]}...")
            _async_client = AsyncIOMotorClient(
                config['url'],
                minPoolSize=config['min_pool'],
                maxPoolSize=config['max_pool'],
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
            )

            logger.info("✅ MongoDB async client created")

        return _async_client

    @staticmethod
    def get_sync_db() -> Database:
        """Get synchronous database instance"""
        global _sync_db

        if _sync_db is None:
            config = get_mongo_config()
            client = MongoDB.get_sync_client()
            _sync_db = client[config['database']]
            logger.info(f"✅ Using database: {config['database']}")

        return _sync_db

    @staticmethod
    def get_async_db() -> AsyncIOMotorDatabase:
        """Get asynchronous database instance"""
        global _async_db

        if _async_db is None:
            config = get_mongo_config()
            client = MongoDB.get_async_client()
            _async_db = client[config['database']]
            logger.info(f"✅ Using async database: {config['database']}")

        return _async_db

    @staticmethod
    def close_connections():
        """Close all database connections"""
        global _sync_client, _async_client, _sync_db, _async_db

        if _sync_client:
            _sync_client.close()
            _sync_client = None
            _sync_db = None
            logger.info("Closed sync MongoDB connection")

        if _async_client:
            _async_client.close()
            _async_client = None
            _async_db = None
            logger.info("Closed async MongoDB connection")

    @staticmethod
    async def ping_async() -> bool:
        """Test async database connection"""
        try:
            db = MongoDB.get_async_db()
            await db.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False

    @staticmethod
    def ping_sync() -> bool:
        """Test sync database connection"""
        try:
            db = MongoDB.get_sync_db()
            db.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False


# Convenience functions
def get_database() -> Database:
    """Get synchronous database instance (for dependencies)"""
    return MongoDB.get_sync_db()


async def get_async_database() -> AsyncIOMotorDatabase:
    """Get async database instance (for async dependencies)"""
    return MongoDB.get_async_db()


# Collection name constants
class Collections:
    """Collection names as constants"""
    USERS = "users"
    RESUMES = "resumes"
    JOBS = "jobs"
    JOB_MATCHES = "job_matches"
    APPLICATIONS = "applications"
    AUTO_APPLY_APPLICATIONS = "auto_apply_applications"
    FORWARDING_EMAILS = "forwarding_emails"
    COVER_LETTERS = "cover_letters"
    INTERVIEW_SESSIONS = "interview_sessions"
    SUBSCRIPTIONS = "subscriptions"
    ACTIVITY_LOGS = "activity_logs"
    GUEST_PROFILES = "guest_profiles"


# Database dependency for FastAPI
def get_db():
    """Dependency for FastAPI routes (sync)"""
    return MongoDB.get_sync_db()


async def get_async_db():
    """Dependency for FastAPI routes (async)"""
    return MongoDB.get_async_db()


# Startup and shutdown events
async def connect_to_mongo():
    """Connect to MongoDB on startup"""
    logger.info("Connecting to MongoDB...")
    MongoDB.get_async_client()
    MongoDB.get_sync_client()

    # Test connections
    if await MongoDB.ping_async() and MongoDB.ping_sync():
        logger.info("✅ MongoDB connected successfully")
    else:
        logger.error("❌ MongoDB connection failed")
        raise Exception("Failed to connect to MongoDB")


async def close_mongo_connection():
    """Close MongoDB connections on shutdown"""
    logger.info("Closing MongoDB connections...")
    MongoDB.close_connections()
    logger.info("✅ MongoDB connections closed")


# Helper function to convert ObjectId to string for JSON serialization
def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None

    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]

    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id':
                result['id'] = str(value)
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            elif isinstance(value, list):
                result[key] = [serialize_doc(item) for item in value]
            else:
                result[key] = value
        return result

    return doc


# Example usage in FastAPI:
"""
from fastapi import Depends
from app.core.database_new import get_db, Collections

@app.get("/users/{user_id}")
async def get_user(user_id: str, db = Depends(get_db)):
    user = db[Collections.USERS].find_one({"_id": ObjectId(user_id)})
    return serialize_doc(user)
"""
