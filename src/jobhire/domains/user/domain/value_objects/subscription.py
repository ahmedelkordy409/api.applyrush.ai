"""Subscription tier value object."""

from enum import Enum
from typing import Dict, Any
from jobhire.shared.domain.types import Money


class SubscriptionTier(str, Enum):
    """Subscription tier enumeration."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

    @property
    def limits(self) -> Dict[str, Any]:
        """Get limits for this subscription tier."""
        limits_map = {
            SubscriptionTier.FREE: {
                "job_applications_per_month": 10,
                "ai_cover_letters_per_month": 5,
                "job_alerts": 1,
                "resume_templates": 1,
                "priority_support": False,
                "api_calls_per_day": 100
            },
            SubscriptionTier.BASIC: {
                "job_applications_per_month": 50,
                "ai_cover_letters_per_month": 25,
                "job_alerts": 5,
                "resume_templates": 5,
                "priority_support": False,
                "api_calls_per_day": 500
            },
            SubscriptionTier.PREMIUM: {
                "job_applications_per_month": 200,
                "ai_cover_letters_per_month": 100,
                "job_alerts": 20,
                "resume_templates": -1,  # Unlimited
                "priority_support": True,
                "api_calls_per_day": 2000
            },
            SubscriptionTier.ENTERPRISE: {
                "job_applications_per_month": -1,  # Unlimited
                "ai_cover_letters_per_month": -1,  # Unlimited
                "job_alerts": -1,  # Unlimited
                "resume_templates": -1,  # Unlimited
                "priority_support": True,
                "api_calls_per_day": 10000
            }
        }
        return limits_map.get(self, {})

    @property
    def monthly_price(self) -> Money:
        """Get monthly price for this tier."""
        price_map = {
            SubscriptionTier.FREE: Money(amount=0.0, currency="USD"),
            SubscriptionTier.BASIC: Money(amount=9.99, currency="USD"),
            SubscriptionTier.PREMIUM: Money(amount=29.99, currency="USD"),
            SubscriptionTier.ENTERPRISE: Money(amount=99.99, currency="USD")
        }
        return price_map[self]

    @property
    def features(self) -> list[str]:
        """Get features included in this tier."""
        features_map = {
            SubscriptionTier.FREE: [
                "Basic job search",
                "Limited AI assistance",
                "Standard resume templates"
            ],
            SubscriptionTier.BASIC: [
                "Enhanced job search",
                "AI cover letter generation",
                "Multiple resume templates",
                "Job application tracking"
            ],
            SubscriptionTier.PREMIUM: [
                "Advanced AI matching",
                "Unlimited cover letters",
                "Premium resume templates",
                "Priority job alerts",
                "Interview preparation",
                "Priority support"
            ],
            SubscriptionTier.ENTERPRISE: [
                "Full AI automation",
                "Custom integrations",
                "Advanced analytics",
                "Team management",
                "Dedicated support",
                "Custom training"
            ]
        }
        return features_map.get(self, [])

    def can_use_feature(self, feature: str) -> bool:
        """Check if tier includes specific feature."""
        return feature in self.features

    def get_limit(self, resource: str) -> int:
        """Get limit for specific resource."""
        return self.limits.get(resource, 0)

    def is_unlimited(self, resource: str) -> bool:
        """Check if resource is unlimited for this tier."""
        return self.get_limit(resource) == -1

    def upgrade_available(self) -> list["SubscriptionTier"]:
        """Get available upgrade options."""
        tier_order = [
            SubscriptionTier.FREE,
            SubscriptionTier.BASIC,
            SubscriptionTier.PREMIUM,
            SubscriptionTier.ENTERPRISE
        ]
        current_index = tier_order.index(self)
        return tier_order[current_index + 1:]