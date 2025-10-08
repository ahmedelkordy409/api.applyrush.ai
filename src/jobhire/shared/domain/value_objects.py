"""
Base value object classes and common value objects.
"""

from abc import ABC
from typing import Any, Dict
from dataclasses import dataclass


class ValueObject(ABC):
    """Base value object class."""

    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"


@dataclass(frozen=True)
class Email(ValueObject):
    """Email value object."""
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Email cannot be empty")

        if "@" not in self.value:
            raise ValueError("Invalid email format")

        # Basic email validation
        parts = self.value.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid email format")

    def __str__(self) -> str:
        return self.value

    @property
    def domain(self) -> str:
        """Get email domain."""
        return self.value.split("@")[1]

    @property
    def local_part(self) -> str:
        """Get email local part."""
        return self.value.split("@")[0]


@dataclass(frozen=True)
class Money(ValueObject):
    """Money value object."""
    amount: float
    currency: str = "USD"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")

        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be a 3-letter code")

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def add(self, other: "Money") -> "Money":
        """Add two money values."""
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: "Money") -> "Money":
        """Subtract two money values."""
        if self.currency != other.currency:
            raise ValueError("Cannot subtract different currencies")
        return Money(self.amount - other.amount, self.currency)

    def multiply(self, factor: float) -> "Money":
        """Multiply money by a factor."""
        return Money(self.amount * factor, self.currency)

    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == 0.0


@dataclass(frozen=True)
class PhoneNumber(ValueObject):
    """Phone number value object."""
    value: str
    country_code: str = "+1"

    def __post_init__(self):
        if not self.value:
            raise ValueError("Phone number cannot be empty")

        # Remove common formatting characters
        cleaned = self.value.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")

        if not cleaned.isdigit():
            raise ValueError("Phone number must contain only digits")

        if len(cleaned) < 10:
            raise ValueError("Phone number must be at least 10 digits")

        # Store the cleaned value
        object.__setattr__(self, 'value', cleaned)

    def __str__(self) -> str:
        return f"{self.country_code}{self.value}"

    @property
    def formatted(self) -> str:
        """Get formatted phone number."""
        if len(self.value) == 10:
            return f"({self.value[:3]}) {self.value[3:6]}-{self.value[6:]}"
        return self.value


@dataclass(frozen=True)
class Address(ValueObject):
    """Address value object."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "US"

    def __post_init__(self):
        if not self.street:
            raise ValueError("Street cannot be empty")
        if not self.city:
            raise ValueError("City cannot be empty")
        if not self.state:
            raise ValueError("State cannot be empty")
        if not self.postal_code:
            raise ValueError("Postal code cannot be empty")

    def __str__(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.postal_code}, {self.country}"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country
        }


@dataclass(frozen=True)
class Url(ValueObject):
    """URL value object."""
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("URL cannot be empty")

        if not (self.value.startswith("http://") or self.value.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")

    def __str__(self) -> str:
        return self.value

    @property
    def is_secure(self) -> bool:
        """Check if URL uses HTTPS."""
        return self.value.startswith("https://")

    @property
    def domain(self) -> str:
        """Extract domain from URL."""
        # Simple domain extraction
        return self.value.split("://")[1].split("/")[0]