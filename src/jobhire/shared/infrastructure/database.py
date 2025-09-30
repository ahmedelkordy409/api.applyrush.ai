"""
Database infrastructure components.
"""

import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import structlog

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """MongoDB database manager."""

    def __init__(self, connection_string: str, database_name: str):
        self.connection_string = connection_string
        self.database_name = database_name
        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the database."""
        try:
            self._client = AsyncIOMotorClient(self.connection_string)
            self._database = self._client[self.database_name]

            # Test the connection
            await self._client.admin.command('ping')
            self._connected = True

            logger.info("Database connected successfully", database=self.database_name)
        except Exception as e:
            logger.error("Failed to connect to database", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("Database disconnected")

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Get the database instance."""
        if not self._database:
            raise RuntimeError("Database not connected")
        return self._database

    @property
    def client(self) -> AsyncIOMotorClient:
        """Get the client instance."""
        if not self._client:
            raise RuntimeError("Database not connected")
        return self._client

    async def health_check(self) -> bool:
        """Check database health."""
        try:
            if not self._connected or not self._client:
                return False

            await self._client.admin.command('ping')
            return True
        except Exception:
            return False

    async def create_indexes(self) -> None:
        """Create database indexes."""
        if not self._database:
            return

        try:
            # User indexes
            await self._database.users.create_index("email", unique=True)
            await self._database.users.create_index("created_at")

            # Job indexes
            await self._database.jobs.create_index("title")
            await self._database.jobs.create_index("company")
            await self._database.jobs.create_index("location")
            await self._database.jobs.create_index("created_at")
            await self._database.jobs.create_index([("title", "text"), ("description", "text")])

            # Application indexes
            await self._database.applications.create_index("user_id")
            await self._database.applications.create_index("job_id")
            await self._database.applications.create_index("created_at")
            await self._database.applications.create_index([("user_id", 1), ("job_id", 1)], unique=True)

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error("Failed to create indexes", error=str(e))