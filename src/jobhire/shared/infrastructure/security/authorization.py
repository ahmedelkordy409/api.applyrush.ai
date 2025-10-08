"""
Enterprise authorization service with RBAC and fine-grained permissions.
"""

from typing import Set, List, Optional, Dict, Any
from enum import Enum
import structlog

from jobhire.shared.domain.exceptions import SecurityException
from jobhire.domains.user.domain.value_objects import UserRole


logger = structlog.get_logger(__name__)


class Permission(str, Enum):
    """System permissions enumeration."""

    # User permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"

    # Profile permissions
    PROFILE_READ = "profile:read"
    PROFILE_WRITE = "profile:write"

    # Job permissions
    JOB_READ = "job:read"
    JOB_WRITE = "job:write"
    JOB_DELETE = "job:delete"

    # Application permissions
    APPLICATION_READ = "application:read"
    APPLICATION_WRITE = "application:write"
    APPLICATION_DELETE = "application:delete"

    # AI permissions
    AI_USE = "ai:use"
    AI_PREMIUM = "ai:premium"

    # Admin permissions
    ADMIN_MANAGE = "admin:manage"
    SYSTEM_CONFIGURE = "system:configure"

    # Reports permissions
    REPORTS_VIEW = "reports:view"
    REPORTS_EXPORT = "reports:export"


class Resource(str, Enum):
    """System resources enumeration."""
    USER = "user"
    PROFILE = "profile"
    JOB = "job"
    APPLICATION = "application"
    AI_SERVICE = "ai_service"
    ADMIN_PANEL = "admin_panel"
    REPORTS = "reports"


class Action(str, Enum):
    """Action types enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    EXPORT = "export"


class PermissionChecker:
    """Permission checking service."""

    def __init__(self):
        self.role_permissions = {
            UserRole.ADMIN: {
                Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE,
                Permission.PROFILE_READ, Permission.PROFILE_WRITE,
                Permission.JOB_READ, Permission.JOB_WRITE, Permission.JOB_DELETE,
                Permission.APPLICATION_READ, Permission.APPLICATION_WRITE, Permission.APPLICATION_DELETE,
                Permission.AI_USE, Permission.AI_PREMIUM,
                Permission.ADMIN_MANAGE, Permission.SYSTEM_CONFIGURE,
                Permission.REPORTS_VIEW, Permission.REPORTS_EXPORT
            },
            UserRole.MANAGER: {
                Permission.USER_READ, Permission.USER_WRITE,
                Permission.PROFILE_READ, Permission.PROFILE_WRITE,
                Permission.JOB_READ, Permission.JOB_WRITE,
                Permission.APPLICATION_READ, Permission.APPLICATION_WRITE,
                Permission.AI_USE, Permission.AI_PREMIUM,
                Permission.REPORTS_VIEW
            },
            UserRole.USER: {
                Permission.PROFILE_READ, Permission.PROFILE_WRITE,
                Permission.JOB_READ,
                Permission.APPLICATION_READ, Permission.APPLICATION_WRITE,
                Permission.AI_USE
            },
            UserRole.GUEST: {
                Permission.JOB_READ
            }
        }

    def get_role_permissions(self, role: UserRole) -> Set[Permission]:
        """Get all permissions for a role."""
        return self.role_permissions.get(role, set())

    def has_permission(self, role: UserRole, permission: Permission) -> bool:
        """Check if role has specific permission."""
        role_perms = self.get_role_permissions(role)
        return permission in role_perms

    def has_any_permission(self, role: UserRole, permissions: List[Permission]) -> bool:
        """Check if role has any of the specified permissions."""
        role_perms = self.get_role_permissions(role)
        return any(perm in role_perms for perm in permissions)

    def has_all_permissions(self, role: UserRole, permissions: List[Permission]) -> bool:
        """Check if role has all of the specified permissions."""
        role_perms = self.get_role_permissions(role)
        return all(perm in role_perms for perm in permissions)

    def can_access_resource(
        self,
        role: UserRole,
        resource: Resource,
        action: Action,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if role can perform action on resource."""
        # Map resource+action to permissions
        permission_map = {
            (Resource.USER, Action.READ): Permission.USER_READ,
            (Resource.USER, Action.UPDATE): Permission.USER_WRITE,
            (Resource.USER, Action.DELETE): Permission.USER_DELETE,
            (Resource.PROFILE, Action.READ): Permission.PROFILE_READ,
            (Resource.PROFILE, Action.UPDATE): Permission.PROFILE_WRITE,
            (Resource.JOB, Action.READ): Permission.JOB_READ,
            (Resource.JOB, Action.CREATE): Permission.JOB_WRITE,
            (Resource.JOB, Action.UPDATE): Permission.JOB_WRITE,
            (Resource.JOB, Action.DELETE): Permission.JOB_DELETE,
            (Resource.APPLICATION, Action.READ): Permission.APPLICATION_READ,
            (Resource.APPLICATION, Action.CREATE): Permission.APPLICATION_WRITE,
            (Resource.APPLICATION, Action.UPDATE): Permission.APPLICATION_WRITE,
            (Resource.APPLICATION, Action.DELETE): Permission.APPLICATION_DELETE,
            (Resource.AI_SERVICE, Action.EXECUTE): Permission.AI_USE,
            (Resource.ADMIN_PANEL, Action.READ): Permission.ADMIN_MANAGE,
            (Resource.REPORTS, Action.READ): Permission.REPORTS_VIEW,
            (Resource.REPORTS, Action.EXPORT): Permission.REPORTS_EXPORT,
        }

        required_permission = permission_map.get((resource, action))
        if not required_permission:
            return False

        has_perm = self.has_permission(role, required_permission)

        # Additional context-based checks
        if context and has_perm:
            has_perm = self._check_context_permissions(role, resource, action, context)

        return has_perm

    def _check_context_permissions(
        self,
        role: UserRole,
        resource: Resource,
        action: Action,
        context: Dict[str, Any]
    ) -> bool:
        """Check context-specific permissions."""
        # Owner-based access control
        if "owner_id" in context and "user_id" in context:
            # Users can always access their own resources
            if context["owner_id"] == context["user_id"]:
                return True

        # Subscription-based access control
        if "subscription_tier" in context:
            subscription_tier = context["subscription_tier"]

            # Premium AI features
            if resource == Resource.AI_SERVICE and action == Action.EXECUTE:
                if context.get("ai_feature") == "premium":
                    return subscription_tier in ["premium", "enterprise"]

        return True


class AuthorizationService:
    """Enterprise authorization service."""

    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker

    def authorize_request(
        self,
        user_role: UserRole,
        resource: Resource,
        action: Action,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Authorize a request with full context."""
        try:
            authorized = self.permission_checker.can_access_resource(
                user_role, resource, action, context
            )

            if authorized:
                logger.info(
                    "Authorization granted",
                    role=user_role.value,
                    resource=resource.value,
                    action=action.value
                )
            else:
                logger.warning(
                    "Authorization denied",
                    role=user_role.value,
                    resource=resource.value,
                    action=action.value
                )

            return authorized

        except Exception as e:
            logger.error(
                "Authorization check failed",
                role=user_role.value,
                resource=resource.value,
                action=action.value,
                error=str(e)
            )
            return False

    def require_permission(
        self,
        user_role: UserRole,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Require specific permission or raise exception."""
        if not self.permission_checker.has_permission(user_role, permission):
            logger.warning(
                "Permission denied",
                role=user_role.value,
                permission=permission.value
            )
            raise SecurityException(f"Permission denied: {permission.value}")

    def require_any_permission(
        self,
        user_role: UserRole,
        permissions: List[Permission],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Require any of the specified permissions or raise exception."""
        if not self.permission_checker.has_any_permission(user_role, permissions):
            logger.warning(
                "Permissions denied",
                role=user_role.value,
                permissions=[p.value for p in permissions]
            )
            raise SecurityException("Insufficient permissions")

    def require_all_permissions(
        self,
        user_role: UserRole,
        permissions: List[Permission],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Require all of the specified permissions or raise exception."""
        if not self.permission_checker.has_all_permissions(user_role, permissions):
            logger.warning(
                "Permissions denied",
                role=user_role.value,
                permissions=[p.value for p in permissions]
            )
            raise SecurityException("Insufficient permissions")

    def filter_by_permissions(
        self,
        user_role: UserRole,
        items: List[Dict[str, Any]],
        resource: Resource,
        action: Action = Action.READ
    ) -> List[Dict[str, Any]]:
        """Filter items based on user permissions."""
        filtered_items = []

        for item in items:
            context = {"owner_id": item.get("owner_id")}
            if self.authorize_request(user_role, resource, action, context):
                filtered_items.append(item)

        return filtered_items

    def get_accessible_resources(self, user_role: UserRole) -> Set[Resource]:
        """Get all resources accessible to a role."""
        accessible = set()
        permissions = self.permission_checker.get_role_permissions(user_role)

        resource_permission_map = {
            Resource.USER: [Permission.USER_READ, Permission.USER_WRITE],
            Resource.PROFILE: [Permission.PROFILE_READ, Permission.PROFILE_WRITE],
            Resource.JOB: [Permission.JOB_READ, Permission.JOB_WRITE],
            Resource.APPLICATION: [Permission.APPLICATION_READ, Permission.APPLICATION_WRITE],
            Resource.AI_SERVICE: [Permission.AI_USE],
            Resource.ADMIN_PANEL: [Permission.ADMIN_MANAGE],
            Resource.REPORTS: [Permission.REPORTS_VIEW]
        }

        for resource, required_perms in resource_permission_map.items():
            if any(perm in permissions for perm in required_perms):
                accessible.add(resource)

        return accessible