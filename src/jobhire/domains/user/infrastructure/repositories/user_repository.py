"""
User repository implementation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.repositories import BaseMongoRepository
from jobhire.domains.user.domain.entities.user import User


class UserRepository(BaseMongoRepository[User]):
    """Repository for user management."""

    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, "users", User)

    async def create(self, user: User) -> None:
        """Create a new user."""
        document = {
            "_id": str(user.id),
            "email": user.email,
            "username": getattr(user, 'username', None),
            "full_name": getattr(user, 'full_name', None),
            "password_hash": getattr(user, 'password_hash', None),
            "user_tier": getattr(user, 'user_tier', 'free'),
            "is_active": getattr(user, 'is_active', True),
            "job_search_preferences": getattr(user, 'job_search_preferences', None),
            "application_configuration": getattr(user, 'application_configuration', None),
            "created_at": getattr(user, 'created_at', datetime.utcnow()),
            "updated_at": getattr(user, 'updated_at', datetime.utcnow()),
            "last_login": getattr(user, 'last_login', None),
            "version": user.version
        }
        await self.collection.insert_one(document)

    async def update(self, user: User) -> None:
        """Update an existing user."""
        document = {
            "email": user.email,
            "username": getattr(user, 'username', None),
            "full_name": getattr(user, 'full_name', None),
            "password_hash": getattr(user, 'password_hash', None),
            "user_tier": getattr(user, 'user_tier', 'free'),
            "is_active": getattr(user, 'is_active', True),
            "job_search_preferences": getattr(user, 'job_search_preferences', None),
            "application_configuration": getattr(user, 'application_configuration', None),
            "updated_at": datetime.utcnow(),
            "last_login": getattr(user, 'last_login', None),
            "version": user.version
        }

        await self.collection.update_one(
            {"_id": str(user.id)},
            {"$set": document}
        )

    async def find_by_id(self, user_id: EntityId) -> Optional[User]:
        """Find user by ID."""
        document = await self.collection.find_one({"_id": str(user_id)})
        if not document:
            return None
        return self._document_to_entity(document)

    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        document = await self.collection.find_one({"email": email})
        if not document:
            return None
        return self._document_to_entity(document)

    async def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username."""
        document = await self.collection.find_one({"username": username})
        if not document:
            return None
        return self._document_to_entity(document)

    async def find_active_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Find active users with pagination."""
        cursor = self.collection.find({"is_active": True}).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [self._document_to_entity(doc) for doc in documents]

    async def find_by_tier(self, user_tier: str, limit: int = 100) -> List[User]:
        """Find users by tier."""
        cursor = self.collection.find({"user_tier": user_tier}).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [self._document_to_entity(doc) for doc in documents]

    async def count_active_users(self) -> int:
        """Count active users."""
        return await self.collection.count_documents({"is_active": True})

    async def delete_by_id(self, user_id: EntityId) -> bool:
        """Delete a user by ID."""
        result = await self.collection.delete_one({"_id": str(user_id)})
        return result.deleted_count > 0

    def _document_to_entity(self, document: Dict[str, Any]) -> User:
        """Convert MongoDB document to User entity."""
        user_id = EntityId.from_string(document["_id"])

        # Create a minimal user entity - in practice this would be more complete
        user = User.__new__(User)
        user._id = user_id
        user.email = document["email"]
        user.username = document.get("username")
        user.full_name = document.get("full_name")
        user.password_hash = document.get("password_hash")
        user.user_tier = document.get("user_tier", "free")
        user.is_active = document.get("is_active", True)
        user.job_search_preferences = document.get("job_search_preferences")
        user.application_configuration = document.get("application_configuration")
        user.created_at = document.get("created_at")
        user.updated_at = document.get("updated_at")
        user.last_login = document.get("last_login")
        user.version = document.get("version", 1)
        user._domain_events = []

        return user