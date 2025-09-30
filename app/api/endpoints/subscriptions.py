"""
Subscription Management API endpoints
Handles subscription plans, payments, and billing
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging
import stripe

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()

# Initialize Stripe (if API key is available)
stripe_api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
if stripe_api_key:
    stripe.api_key = stripe_api_key


class SubscriptionPlan(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    interval: str  # monthly, yearly
    features: List[str]
    active: bool


class CreateCheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class CreatePortalSessionRequest(BaseModel):
    return_url: str


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_subscription_plans():
    """Get available subscription plans"""
    try:
        # Hardcoded plans for now - could come from database later
        plans = [
            SubscriptionPlan(
                id="free",
                name="Free",
                price=0.0,
                currency="USD",
                interval="monthly",
                features=[
                    "Basic job search",
                    "Up to 5 applications per month",
                    "Basic cover letter templates"
                ],
                active=True
            ),
            SubscriptionPlan(
                id="pro",
                name="Pro",
                price=29.99,
                currency="USD",
                interval="monthly",
                features=[
                    "Unlimited job search",
                    "Unlimited applications",
                    "AI-powered cover letters",
                    "Interview practice",
                    "Priority support"
                ],
                active=True
            ),
            SubscriptionPlan(
                id="enterprise",
                name="Enterprise",
                price=99.99,
                currency="USD",
                interval="monthly",
                features=[
                    "Everything in Pro",
                    "Custom integrations",
                    "Dedicated account manager",
                    "Advanced analytics",
                    "Custom branding"
                ],
                active=True
            )
        ]

        return plans

    except Exception as e:
        logger.error(f"Error fetching subscription plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription plans"
        )


@router.get("/current")
async def get_current_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's current subscription details"""
    try:
        query = """
            SELECT subscription_status, subscription_plan, subscription_expires_at,
                   stripe_customer_id, stripe_subscription_id
            FROM users
            WHERE id = :user_id
        """

        user_subscription = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        if not user_subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User subscription not found"
            )

        return {
            "status": user_subscription["subscription_status"] or "free",
            "plan": user_subscription["subscription_plan"] or "free",
            "expires_at": user_subscription["subscription_expires_at"],
            "is_active": user_subscription["subscription_status"] == "active",
            "stripe_customer_id": user_subscription["stripe_customer_id"],
            "stripe_subscription_id": user_subscription["stripe_subscription_id"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching current subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription details"
        )


@router.post("/checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a Stripe checkout session"""
    try:
        if not stripe_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing not configured"
            )

        # Get or create Stripe customer
        user_query = """
            SELECT stripe_customer_id, email
            FROM users
            WHERE id = :user_id
        """
        user_data = await database.fetch_one(
            query=user_query,
            values={"user_id": current_user["id"]}
        )

        customer_id = user_data["stripe_customer_id"]

        if not customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user_data["email"],
                metadata={"user_id": str(current_user["id"])}
            )
            customer_id = customer.id

            # Update user with customer ID
            update_query = """
                UPDATE users
                SET stripe_customer_id = :customer_id, updated_at = :updated_at
                WHERE id = :user_id
            """
            await database.execute(
                query=update_query,
                values={
                    "customer_id": customer_id,
                    "updated_at": datetime.utcnow(),
                    "user_id": current_user["id"]
                }
            )

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'user_id': str(current_user["id"])
            }
        )

        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment processing error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.post("/portal-session")
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a Stripe customer portal session"""
    try:
        if not stripe_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing not configured"
            )

        # Get Stripe customer ID
        user_query = """
            SELECT stripe_customer_id
            FROM users
            WHERE id = :user_id
        """
        user_data = await database.fetch_one(
            query=user_query,
            values={"user_id": current_user["id"]}
        )

        if not user_data or not user_data["stripe_customer_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No payment account found"
            )

        # Create portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=user_data["stripe_customer_id"],
            return_url=request.return_url,
        )

        return {
            "portal_url": portal_session.url
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment processing error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )


@router.post("/cancel")
async def cancel_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cancel user's subscription"""
    try:
        if not stripe_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing not configured"
            )

        # Get subscription details
        user_query = """
            SELECT stripe_subscription_id, subscription_status
            FROM users
            WHERE id = :user_id
        """
        user_data = await database.fetch_one(
            query=user_query,
            values={"user_id": current_user["id"]}
        )

        if not user_data or not user_data["stripe_subscription_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        if user_data["subscription_status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription is not active"
            )

        # Cancel subscription in Stripe
        stripe.Subscription.delete(user_data["stripe_subscription_id"])

        # Update user subscription status
        update_query = """
            UPDATE users
            SET subscription_status = 'cancelled', updated_at = :updated_at
            WHERE id = :user_id
        """
        await database.execute(
            query=update_query,
            values={
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": True,
            "message": "Subscription cancelled successfully"
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment processing error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.post("/webhook")
async def stripe_webhook(request: dict):
    """Handle Stripe webhooks"""
    try:
        if not stripe_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing not configured"
            )

        # This is a simplified webhook handler
        # In production, you should verify the webhook signature
        event_type = request.get("type")
        data = request.get("data", {}).get("object", {})

        if event_type == "customer.subscription.created":
            # Handle new subscription
            customer_id = data.get("customer")
            subscription_id = data.get("id")
            status = data.get("status")

            # Update user subscription
            update_query = """
                UPDATE users
                SET subscription_status = :status,
                    subscription_plan = 'pro',
                    stripe_subscription_id = :subscription_id,
                    subscription_expires_at = :expires_at,
                    updated_at = :updated_at
                WHERE stripe_customer_id = :customer_id
            """

            # Calculate expiration date (30 days from now for monthly)
            expires_at = datetime.utcnow() + timedelta(days=30)

            await database.execute(
                query=update_query,
                values={
                    "status": status,
                    "subscription_id": subscription_id,
                    "expires_at": expires_at,
                    "updated_at": datetime.utcnow(),
                    "customer_id": customer_id
                }
            )

        elif event_type == "customer.subscription.deleted":
            # Handle subscription cancellation
            customer_id = data.get("customer")

            update_query = """
                UPDATE users
                SET subscription_status = 'cancelled',
                    subscription_plan = 'free',
                    updated_at = :updated_at
                WHERE stripe_customer_id = :customer_id
            """

            await database.execute(
                query=update_query,
                values={
                    "updated_at": datetime.utcnow(),
                    "customer_id": customer_id
                }
            )

        return {"received": True}

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )