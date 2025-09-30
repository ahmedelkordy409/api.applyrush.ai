"""User domain events."""

from jobhire.shared.domain.base import DomainEvent


class UserRegistered(DomainEvent):
    """Event raised when a user registers."""
    pass


class UserProfileUpdated(DomainEvent):
    """Event raised when user profile is updated."""
    pass


class UserSubscriptionChanged(DomainEvent):
    """Event raised when user subscription changes."""
    pass


class UserEmailVerified(DomainEvent):
    """Event raised when user email is verified."""
    pass


class UserPasswordChanged(DomainEvent):
    """Event raised when user password is changed."""
    pass


class UserSuspended(DomainEvent):
    """Event raised when user is suspended."""
    pass


class UserReactivated(DomainEvent):
    """Event raised when user is reactivated."""
    pass