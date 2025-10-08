"""
Subscription management endpoints with Stripe integration
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import stripe
import os

from app.core.database_new import get_db
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Stripe Price IDs mapping from environment variables
STRIPE_PRICE_IDS = {
    "basic": {
        "monthly": os.getenv("STRIPE_BASIC_MONTHLY", "price_1SCvqGQYDSf5l1Z0fYe0tx37"),
        "annual": os.getenv("STRIPE_BASIC_YEARLY", "price_1SCvqGQYDSf5l1Z03AKC55nc")
    },
    "premium": {
        "monthly": os.getenv("STRIPE_PREMIUM_MONTHLY", "price_1SCvqHQYDSf5l1Z0TGJSvMYX"),
        "annual": os.getenv("STRIPE_PREMIUM_YEARLY", "price_1SCvqHQYDSf5l1Z0ja6i4O9S")
    },
    "enterprise": {
        "monthly": os.getenv("STRIPE_ENTERPRISE_MONTHLY", "price_1SCvqHQYDSf5l1Z0SsQhPMgX"),
        "annual": os.getenv("STRIPE_ENTERPRISE_YEARLY", "price_1SCvqIQYDSf5l1Z0mo9Q9nwp")
    }
}

class CreateCheckoutRequest(BaseModel):
    plan: str  # basic, premium, enterprise
    billing_cycle: str  # monthly, annual
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    url: str
    session_id: str


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Create a Stripe checkout session for subscription
    """
    try:
        # Validate plan and billing cycle
        if request.plan not in STRIPE_PRICE_IDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan: {request.plan}"
            )

        if request.billing_cycle not in ["monthly", "annual"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid billing cycle: {request.billing_cycle}"
            )

        # Get the Stripe Price ID
        price_id = STRIPE_PRICE_IDS[request.plan][request.billing_cycle]

        # Get or create Stripe customer
        user_id = user["_id"] if isinstance(user["_id"], str) else str(user["_id"])
        stripe_customer_id = user.get("stripe_customer_id")

        if not stripe_customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user["email"],
                metadata={
                    "user_id": user_id
                }
            )
            stripe_customer_id = customer.id

            # Update user with Stripe customer ID
            db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"stripe_customer_id": stripe_customer_id}}
            )

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                "user_id": user_id,
                "plan": request.plan,
                "billing_cycle": request.billing_cycle
            }
        )

        return CheckoutSessionResponse(
            url=checkout_session.url,
            session_id=checkout_session.id
        )

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating checkout session: {str(e)}"
        )


@router.post("/webhook")
async def stripe_webhook(request: Request, db = Depends(get_db)):
    """
    Handle Stripe webhook events
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Update user subscription in database
        user_id = session['metadata']['user_id']
        plan = session['metadata']['plan']
        billing_cycle = session['metadata']['billing_cycle']

        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "subscription_tier": plan,
                    "subscription_status": "active",
                    "billing_cycle": billing_cycle,
                    "stripe_subscription_id": session.get('subscription'),
                    "subscription_updated_at": datetime.utcnow()
                }
            }
        )

    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        # Find user by stripe_customer_id
        user = db.users.find_one({"stripe_customer_id": customer_id})
        if user:
            db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "subscription_status": subscription['status'],
                        "subscription_updated_at": datetime.utcnow()
                    }
                }
            )

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        # Find user and downgrade to free
        user = db.users.find_one({"stripe_customer_id": customer_id})
        if user:
            db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "subscription_tier": "free",
                        "subscription_status": "inactive",
                        "subscription_updated_at": datetime.utcnow()
                    }
                }
            )

    return {"status": "success"}


@router.get("/portal")
async def create_portal_session(
    user: dict = Depends(get_current_user)
):
    """
    Create a Stripe customer portal session for managing subscription
    """
    try:
        stripe_customer_id = user.get("stripe_customer_id")

        if not stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription found"
            )

        # Create portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard/manage-subscription"
        )

        return {"url": portal_session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
