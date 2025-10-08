"""User role value object."""

from enum import Enum
from typing import Set
from jobhire.shared.domain.base import ValueObject


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    GUEST = "guest"

    @property
    def permissions(self) -> Set[str]:
        """Get permissions for this role."""
        permission_map = {
            UserRole.ADMIN: {
                "user:read", "user:write", "user:delete",
                "job:read", "job:write", "job:delete",
                "application:read", "application:write", "application:delete",
                "admin:manage", "system:configure"
            },
            UserRole.MANAGER: {
                "user:read", "user:write",
                "job:read", "job:write",
                "application:read", "application:write",
                "reports:view"
            },
            UserRole.USER: {
                "profile:read", "profile:write",
                "job:read", "application:read", "application:write"
            },
            UserRole.GUEST: {
                "job:read"
            }
        }
        return permission_map.get(self, set())

    def has_permission(self, permission: str) -> bool:
        """Check if role has specific permission."""
        return permission in self.permissions

    def can_access_admin(self) -> bool:
        """Check if role can access admin features."""
        return self in {UserRole.ADMIN, UserRole.MANAGER}

    def can_manage_users(self) -> bool:
        """Check if role can manage other users."""
        return self == UserRole.ADMIN