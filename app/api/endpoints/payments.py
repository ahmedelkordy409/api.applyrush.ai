"""
Payment and subscription management API endpoints
Handles Stripe integration, checkout sessions, and subscription management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import stripe
import logging

from app.core.database import database
from app.core.security import get_current_user
from app.core.security import PermissionChecker
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()

# Configure Stripe
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

# Product configuration
STRIPE_PRODUCTS = {
    "premium_monthly": {
        "name": "Premium Monthly",
        "price_id": getattr(settings, 'STRIPE_PREMIUM_MONTHLY_PRICE_ID', ''),
        "type": "subscription",
        "interval": "month",
        "amount": 2900,  # $29.00
        "features": [
            "Unlimited job applications",
            "AI-generated cover letters",
            "Premium job matching",
            "Interview preparation",
            "Auto-apply functionality",
            "Priority support"
        ]
    },
    "premium_yearly": {
        "name": "Premium Yearly",
        "price_id": getattr(settings, 'STRIPE_PREMIUM_YEARLY_PRICE_ID', ''),
        "type": "subscription",
        "interval": "year",
        "amount": 29000,  # $290.00 (save $58)
        "features": [
            "Unlimited job applications",
            "AI-generated cover letters",
            "Premium job matching",
            "Interview preparation",
            "Auto-apply functionality",
            "Priority support",
            "2 months free"
        ]
    },
    "credits_50": {
        "name": "50 Application Credits",
        "price_id": getattr(settings, 'STRIPE_CREDITS_50_PRICE_ID', ''),
        "type": "one_time",
        "amount": 999,  # $9.99
        "credits": 50
    },
    "credits_100": {
        "name": "100 Application Credits",
        "price_id": getattr(settings, 'STRIPE_CREDITS_100_PRICE_ID', ''),
        "type": "one_time",
        "amount": 1899,  # $18.99
        "credits": 100
    }
}


class CheckoutSessionRequest(BaseModel):
    product_key: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    metadata: Optional[Dict[str, str]] = {}


class CheckoutSessionResponse(BaseModel):
    session_id: str
    url: str


class SubscriptionResponse(BaseModel):
    id: str
    status: str
    plan: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    amount: int
    currency: str
    interval: str


class PaymentHistoryResponse(BaseModel):
    id: str
    amount: int
    currency: str
    status: str
    description: str
    created_at: datetime
    invoice_url: Optional[str] = None


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription or one-time payment"""
    try:
        # Validate product key
        if request.product_key not in STRIPE_PRODUCTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid product key"
            )

        product = STRIPE_PRODUCTS[request.product_key]

        # Validate that product has a valid price ID
        if not product["price_id"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Price ID not configured for product: {request.product_key}"
            )

        # Check if user already has an active subscription for subscription products
        if product["type"] == "subscription":
            existing_sub_query = """
                SELECT stripe_subscription_id FROM users
                WHERE id = :user_id AND subscription_status = 'active'
            """
            existing_sub = await database.fetch_one(
                query=existing_sub_query,
                values={"user_id": current_user["id"]}
            )

            if existing_sub:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already has an active subscription"
                )

        # Get or create Stripe customer
        customer_id = await get_or_create_stripe_customer(
            user_id=current_user["id"],
            email=current_user["email"],
            name=current_user.get("full_name")
        )

        # Create checkout session configuration
        session_config = {
            "customer": customer_id,
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price": product["price_id"],
                    "quantity": 1,
                }
            ],
            "mode": "subscription" if product["type"] == "subscription" else "payment",
            "success_url": request.success_url or f"{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": request.cancel_url or f"{settings.FRONTEND_URL}/pricing",
            "metadata": {
                "product_key": request.product_key,
                "user_id": str(current_user["id"]),
                **request.metadata
            }
        }

        # Add subscription-specific configuration
        if product["type"] == "subscription":
            session_config["subscription_data"] = {
                "metadata": {
                    "product_key": request.product_key,
                    "user_id": str(current_user["id"]),
                }
            }
        else:
            # One-time payment configuration
            session_config["payment_intent_data"] = {
                "metadata": {
                    "product_key": request.product_key,
                    "user_id": str(current_user["id"]),
                    "credits": str(product.get("credits", 0))
                }
            }

        # Create the checkout session
        session = stripe.checkout.sessions.create(**session_config)

        return CheckoutSessionResponse(
            session_id=session.id,
            url=session.url
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get current user's subscription details"""
    try:
        # Get user's subscription info from database
        query = """
            SELECT stripe_subscription_id, subscription_status, subscription_plan
            FROM users
            WHERE id = :user_id
        """
        user_data = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        if not user_data or not user_data["stripe_subscription_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        # Get subscription details from Stripe
        subscription = stripe.Subscription.retrieve(user_data["stripe_subscription_id"])

        return SubscriptionResponse(
            id=subscription.id,
            status=subscription.status,
            plan=user_data["subscription_plan"] or "unknown",
            current_period_start=datetime.fromtimestamp(subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            cancel_at_period_end=subscription.cancel_at_period_end,
            amount=subscription.items.data[0].price.unit_amount,
            currency=subscription.items.data[0].price.currency,
            interval=subscription.items.data[0].price.recurring.interval
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription details"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription"
        )


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cancel user's subscription (at period end)"""
    try:
        # Get user's subscription ID
        query = """
            SELECT stripe_subscription_id FROM users
            WHERE id = :user_id AND subscription_status = 'active'
        """
        user_data = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        if not user_data or not user_data["stripe_subscription_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        # Cancel subscription at period end
        subscription = stripe.Subscription.modify(
            user_data["stripe_subscription_id"],
            cancel_at_period_end=True
        )

        # Log the cancellation
        await database.execute(
            query="""
                INSERT INTO subscription_history (
                    user_id, plan, status, started_at, change_reason,
                    stripe_subscription_id, created_at
                ) VALUES (
                    :user_id, :plan, :status, :started_at, :change_reason,
                    :stripe_subscription_id, :created_at
                )
            """,
            values={
                "user_id": current_user["id"],
                "plan": "premium",
                "status": "cancelled",
                "started_at": datetime.fromtimestamp(subscription.current_period_start),
                "change_reason": "user_cancelled",
                "stripe_subscription_id": subscription.id,
                "created_at": datetime.utcnow()
            }
        )

        return {
            "success": True,
            "message": "Subscription will be cancelled at the end of the current billing period",
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.post("/reactivate-subscription")
async def reactivate_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reactivate a cancelled subscription"""
    try:
        # Get user's subscription ID
        query = """
            SELECT stripe_subscription_id FROM users
            WHERE id = :user_id AND subscription_status IN ('active', 'cancelled')
        """
        user_data = await database.fetch_one(
            query=query,
            values={"user_id": current_user["id"]}
        )

        if not user_data or not user_data["stripe_subscription_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )

        # Reactivate subscription
        subscription = stripe.Subscription.modify(
            user_data["stripe_subscription_id"],
            cancel_at_period_end=False
        )

        return {
            "success": True,
            "message": "Subscription reactivated successfully",
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error reactivating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reactivating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription"
        )


@router.get("/payment-history", response_model=List[PaymentHistoryResponse])
async def get_payment_history(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's payment history"""
    try:
        # Get payment history from database
        query = """
            SELECT * FROM payment_transactions
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 50
        """
        transactions = await database.fetch_all(
            query=query,
            values={"user_id": current_user["id"]}
        )

        payment_history = []
        for transaction in transactions:
            payment_history.append(PaymentHistoryResponse(
                id=str(transaction["id"]),
                amount=transaction["amount"],
                currency=transaction["currency"],
                status=transaction["status"],
                description=transaction["description"] or "Payment",
                created_at=transaction["created_at"],
                invoice_url=None  # Could be populated from Stripe if needed
            ))

        return payment_history

    except Exception as e:
        logger.error(f"Error retrieving payment history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment history"
        )


@router.get("/products")
async def get_available_products():
    """Get available subscription and credit products"""
    try:
        return {
            "products": STRIPE_PRODUCTS,
            "currency": "usd"
        }
    except Exception as e:
        logger.error(f"Error retrieving products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve products"
        )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')

        # Verify webhook signature
        endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )

        # Handle different event types
        if event['type'] == 'checkout.session.completed':
            await handle_checkout_completed(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            await handle_subscription_updated(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            await handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'payment_intent.succeeded':
            await handle_payment_succeeded(event['data']['object'])

        return {"status": "success"}

    except ValueError as e:
        logger.error(f"Invalid payload in webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature in webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def get_or_create_stripe_customer(user_id: str, email: str, name: str = None) -> str:
    """Get existing Stripe customer or create a new one"""
    try:
        # Check if user already has a Stripe customer ID
        query = "SELECT stripe_customer_id FROM users WHERE id = :user_id"
        result = await database.fetch_one(query=query, values={"user_id": user_id})

        if result and result["stripe_customer_id"]:
            return result["stripe_customer_id"]

        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"user_id": user_id}
        )

        # Update user with Stripe customer ID
        update_query = """
            UPDATE users SET stripe_customer_id = :customer_id, updated_at = :updated_at
            WHERE id = :user_id
        """
        await database.execute(
            query=update_query,
            values={
                "customer_id": customer.id,
                "updated_at": datetime.utcnow(),
                "user_id": user_id
            }
        )

        return customer.id

    except Exception as e:
        logger.error(f"Error creating Stripe customer: {str(e)}")
        raise


async def handle_checkout_completed(session):
    """Handle successful checkout completion"""
    try:
        user_id = session['metadata'].get('user_id')
        product_key = session['metadata'].get('product_key')

        if not user_id:
            logger.error("No user_id in checkout session metadata")
            return

        if session['mode'] == 'subscription':
            # Handle subscription creation
            subscription = stripe.Subscription.retrieve(session['subscription'])
            await update_user_subscription(user_id, subscription, product_key)
        else:
            # Handle one-time payment (credits)
            payment_intent = stripe.PaymentIntent.retrieve(session['payment_intent'])
            await handle_credits_purchase(user_id, payment_intent)

    except Exception as e:
        logger.error(f"Error handling checkout completion: {str(e)}")


async def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        user_id = subscription['metadata'].get('user_id')
        if not user_id:
            return

        await update_user_subscription(user_id, subscription)

    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")


async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        user_id = subscription['metadata'].get('user_id')
        if not user_id:
            return

        # Update user subscription status
        await database.execute(
            query="""
                UPDATE users
                SET subscription_status = 'cancelled',
                    subscription_expires_at = :expires_at,
                    updated_at = :updated_at
                WHERE id = :user_id
            """,
            values={
                "expires_at": datetime.fromtimestamp(subscription['current_period_end']),
                "updated_at": datetime.utcnow(),
                "user_id": user_id
            }
        )

    except Exception as e:
        logger.error(f"Error handling subscription deletion: {str(e)}")


async def handle_payment_succeeded(payment_intent):
    """Handle successful one-time payment"""
    try:
        user_id = payment_intent['metadata'].get('user_id')
        if not user_id:
            return

        # Record payment transaction
        await database.execute(
            query="""
                INSERT INTO payment_transactions (
                    user_id, stripe_payment_intent_id, amount, currency,
                    status, transaction_type, description, created_at, updated_at
                ) VALUES (
                    :user_id, :payment_intent_id, :amount, :currency,
                    :status, :transaction_type, :description, :created_at, :updated_at
                )
            """,
            values={
                "user_id": user_id,
                "payment_intent_id": payment_intent['id'],
                "amount": payment_intent['amount'],
                "currency": payment_intent['currency'],
                "status": payment_intent['status'],
                "transaction_type": "one_time",
                "description": payment_intent.get('description', 'One-time payment'),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )

    except Exception as e:
        logger.error(f"Error handling payment success: {str(e)}")


async def update_user_subscription(user_id: str, subscription, product_key: str = None):
    """Update user's subscription status in database"""
    try:
        plan = "premium"  # Default plan name
        if product_key and "monthly" in product_key:
            plan = "premium_monthly"
        elif product_key and "yearly" in product_key:
            plan = "premium_yearly"

        await database.execute(
            query="""
                UPDATE users
                SET subscription_status = :status,
                    subscription_plan = :plan,
                    subscription_expires_at = :expires_at,
                    stripe_subscription_id = :subscription_id,
                    updated_at = :updated_at
                WHERE id = :user_id
            """,
            values={
                "status": subscription['status'],
                "plan": plan,
                "expires_at": datetime.fromtimestamp(subscription['current_period_end']),
                "subscription_id": subscription['id'],
                "updated_at": datetime.utcnow(),
                "user_id": user_id
            }
        )

    except Exception as e:
        logger.error(f"Error updating user subscription: {str(e)}")


async def handle_credits_purchase(user_id: str, payment_intent):
    """Handle credits purchase from one-time payment"""
    try:
        credits = int(payment_intent['metadata'].get('credits', 0))
        if credits > 0:
            # Add credits to user account (you might have a separate credits table)
            # For now, we'll just log it
            logger.info(f"User {user_id} purchased {credits} credits")

    except Exception as e:
        logger.error(f"Error handling credits purchase: {str(e)}")