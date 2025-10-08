"""
User aggregate root entity.
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum

from jobhire.shared.domain.base import AggregateRoot, DomainEvent
from jobhire.shared.domain.types import EntityId, EmailAddress
from jobhire.shared.domain.exceptions import BusinessRuleException

from ..value_objects import UserRole, SubscriptionTier
from ..events import UserRegistered, UserProfileUpdated, UserSubscriptionChanged


class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class User(AggregateRoot[EntityId]):
    """User aggregate root."""

    def __init__(
        self,
        user_id: EntityId,
        email: EmailAddress,
        password_hash: str,
        role: UserRole = UserRole.USER,
        subscription_tier: SubscriptionTier = SubscriptionTier.FREE,
        created_at: Optional[datetime] = None
    ):
        super().__init__(user_id)
        self._email = email
        self._password_hash = password_hash
        self._role = role
        self._subscription_tier = subscription_tier
        self._status = UserStatus.PENDING_VERIFICATION
        self._created_at = created_at or datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._last_login_at: Optional[datetime] = None
        self._email_verified = False
        self._failed_login_attempts = 0
        self._locked_until: Optional[datetime] = None

        # Add domain event
        self.add_event(UserRegistered(
            event_type="UserRegistered",
            entity_id=str(self.id),
            data={
                "email": str(self.email),
                "role": self.role.value,
                "subscription_tier": self.subscription_tier.value
            }
        ))

    @property
    def email(self) -> EmailAddress:
        return self._email

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def role(self) -> UserRole:
        return self._role

    @property
    def subscription_tier(self) -> SubscriptionTier:
        return self._subscription_tier

    @property
    def status(self) -> UserStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def last_login_at(self) -> Optional[datetime]:
        return self._last_login_at

    @property
    def email_verified(self) -> bool:
        return self._email_verified

    @property
    def failed_login_attempts(self) -> int:
        return self._failed_login_attempts

    @property
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self._locked_until is None:
            return False
        return datetime.utcnow() < self._locked_until

    @property
    def is_active(self) -> bool:
        """Check if user is active and can login."""
        return (
            self._status == UserStatus.ACTIVE and
            self._email_verified and
            not self.is_locked
        )

    def verify_email(self) -> None:
        """Mark email as verified."""
        if self._email_verified:
            raise BusinessRuleException("Email is already verified")

        self._email_verified = True
        self._status = UserStatus.ACTIVE
        self._updated_at = datetime.utcnow()
        self.increment_version()

    def change_password(self, new_password_hash: str) -> None:
        """Change user password."""
        if not new_password_hash:
            raise BusinessRuleException("Password hash cannot be empty")

        self._password_hash = new_password_hash
        self._failed_login_attempts = 0
        self._locked_until = None
        self._updated_at = datetime.utcnow()
        self.increment_version()

    def record_successful_login(self) -> None:
        """Record successful login."""
        if not self.is_active:
            raise BusinessRuleException("User is not active")

        self._last_login_at = datetime.utcnow()
        self._failed_login_attempts = 0
        self._locked_until = None
        self._updated_at = datetime.utcnow()

    def record_failed_login(self) -> None:
        """Record failed login attempt."""
        self._failed_login_attempts += 1
        self._updated_at = datetime.utcnow()

        # Lock account after 5 failed attempts
        if self._failed_login_attempts >= 5:
            self._locked_until = datetime.utcnow().replace(hour=23, minute=59, second=59)

    def change_subscription(self, new_tier: SubscriptionTier) -> None:
        """Change user subscription tier."""
        if self._subscription_tier == new_tier:
            return

        old_tier = self._subscription_tier
        self._subscription_tier = new_tier
        self._updated_at = datetime.utcnow()
        self.increment_version()

        self.add_event(UserSubscriptionChanged(
            event_type="UserSubscriptionChanged",
            entity_id=str(self.id),
            data={
                "old_tier": old_tier.value,
                "new_tier": new_tier.value
            }
        ))

    def suspend(self, reason: str) -> None:
        """Suspend user account."""
        if self._status == UserStatus.SUSPENDED:
            raise BusinessRuleException("User is already suspended")

        self._status = UserStatus.SUSPENDED
        self._updated_at = datetime.utcnow()
        self.increment_version()

    def reactivate(self) -> None:
        """Reactivate suspended user."""
        if self._status != UserStatus.SUSPENDED:
            raise BusinessRuleException("User is not suspended")

        self._status = UserStatus.ACTIVE
        self._updated_at = datetime.utcnow()
        self.increment_version()

    def deactivate(self) -> None:
        """Deactivate user account."""
        self._status = UserStatus.INACTIVE
        self._updated_at = datetime.utcnow()
        self.increment_version()

    def apply_event(self, event: DomainEvent) -> None:
        """Apply domain event to the aggregate."""
        # This method would be used for event sourcing
        # For now, we'll keep it simple
        pass

    def __str__(self) -> str:
        return f"User(id={self.id}, email={self.email})"