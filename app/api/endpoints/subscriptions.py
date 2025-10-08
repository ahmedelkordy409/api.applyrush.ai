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

from app.core.config import settings
from app.services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Initialize Stripe (if API key is available)
stripe_api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
if stripe_api_key:
    stripe.api_key = stripe_api_key

# Coupon database (in-memory for now - move to database in production)
COUPONS = {
    "SAVE30": {"valid": True, "discountPercent": 30, "expiry": "2025-12-31"},
    "EARLYBIRD": {"valid": True, "discountPercent": 20, "expiry": "2025-11-30"},
    "WELCOME10": {"valid": True, "discountPercent": 10, "expiry": "2025-12-31"},
}


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


class ValidateCouponRequest(BaseModel):
    code: str


class CreateCheckoutSessionRequestV2(BaseModel):
    planId: str
    billingCycle: str  # "monthly" or "yearly"
    coupon: Optional[str] = None
    userEmail: Optional[str] = None  # User email from session
    userId: Optional[str] = None  # User ID from session


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


# @router.get("/current")
# async def get_current_subscription(
#     current_user: Dict[str, Any] = Depends(get_current_user)
# ):
#     """Get user's current subscription details"""
#     # Disabled - requires authentication
#     pass


@router.post("/checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest
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


# @router.post("/portal-session")
# async def create_portal_session(
#     request: CreatePortalSessionRequest,
#     current_user: Dict[str, Any] = Depends(get_current_user)
# ):
#     """Create a Stripe customer portal session"""
#     # Disabled - requires authentication
#     pass


# @router.post("/cancel")
# async def cancel_subscription(
#     current_user: Dict[str, Any] = Depends(get_current_user)
# ):
#     """Cancel user's subscription"""
#     # Disabled - requires authentication
#     pass


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


@router.post("/validate-coupon")
async def validate_coupon(request: ValidateCouponRequest):
    """
    Validate a coupon code
    Returns coupon details if valid, error if invalid
    """
    try:
        code = request.code.upper().strip()

        if code not in COUPONS:
            return {
                "valid": False,
                "error": "Invalid coupon code"
            }

        coupon = COUPONS[code]

        # Check if coupon is expired
        expiry_date = datetime.strptime(coupon["expiry"], "%Y-%m-%d")
        if datetime.utcnow() > expiry_date:
            return {
                "valid": False,
                "error": "Coupon has expired"
            }

        return {
            "valid": True,
            "discountPercent": coupon["discountPercent"],
            "expiry": coupon["expiry"]
        }

    except Exception as e:
        logger.error(f"Error validating coupon: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate coupon"
        )


@router.post("/create-checkout-session")
async def create_checkout_session_v2(
    request: CreateCheckoutSessionRequestV2
):
    """
    Create a Stripe checkout session with optional coupon
    All pricing logic is handled on the frontend
    User information provided in request body
    """
    try:
        if not stripe_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing not configured"
            )

        # Validate coupon if provided
        discount_percent = 0
        if request.coupon:
            coupon_code = request.coupon.upper().strip()
            if coupon_code in COUPONS:
                coupon = COUPONS[coupon_code]
                expiry_date = datetime.strptime(coupon["expiry"], "%Y-%m-%d")
                if datetime.utcnow() <= expiry_date:
                    discount_percent = coupon["discountPercent"]

        # Get user information from request
        user_email = request.userEmail or "user@applyrush.ai"
        user_id = request.userId or "unknown"

        # Create Stripe customer (simplified - no database lookup)
        customer = stripe.Customer.create(
            email=user_email,
            metadata={"user_id": str(user_id)}
        )
        customer_id = customer.id

        # Map planId and billingCycle to Stripe price IDs
        # These are the actual Stripe price IDs from setup script
        price_mapping = {
            "starter_monthly": "price_1SDKIKQYDSf5l1Z0hXbunNSJ",
            "starter_yearly": "price_1SDKIKQYDSf5l1Z0tPciS0Dl",
            "pro_monthly": "price_1SDKILQYDSf5l1Z0JE97c6I5",
            "pro_yearly": "price_1SDKILQYDSf5l1Z0Klb7WwL8",
            "pro-plus_monthly": "price_1SDKIMQYDSf5l1Z0G5tWnwRa",
            "pro-plus_yearly": "price_1SDKIMQYDSf5l1Z0B5ldXuUa",
        }

        price_key = f"{request.planId}_{request.billingCycle}"
        price_id = price_mapping.get(price_key)

        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan or billing cycle"
            )

        # Build checkout session params
        checkout_params = {
            "customer": customer_id,
            "payment_method_types": ['card'],
            "line_items": [{
                'price': price_id,
                'quantity': 1,
            }],
            "mode": 'subscription',
            "success_url": f"{settings.FRONTEND_URL}/upselling/resume-customization?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL}/upselling/pricing",
            "metadata": {
                'user_id': str(user_id),
                'plan_id': request.planId,
                'billing_cycle': request.billingCycle,
                'coupon': request.coupon or ""
            }
        }

        # Apply discount if coupon is valid
        if discount_percent > 0:
            checkout_params["discounts"] = [{
                "coupon": request.coupon.upper()
            }]

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(**checkout_params)

        # Create/update user in MongoDB
        await mongodb_service.create_or_update_user(
            email=user_email,
            user_id=user_id,
            stripe_customer_id=customer_id,
            onboarding_data={
                "selected_plan": request.planId,
                "billing_cycle": request.billingCycle,
                "from_pricing_page": True
            },
            metadata={
                "checkout_session_id": checkout_session.id,
                "coupon": request.coupon or ""
            }
        )

        # Save subscription to MongoDB
        await mongodb_service.create_or_update_subscription(
            user_id=user_id,
            user_email=user_email,
            stripe_customer_id=customer_id,
            stripe_subscription_id=None,  # Will be updated by webhook
            subscription_status="pending",
            subscription_plan=request.planId,
            billing_cycle=request.billingCycle,
            metadata={
                "checkout_session_id": checkout_session.id,
                "coupon": request.coupon or "",
                "source": "pricing_page"
            }
        )

        return {
            "checkoutUrl": checkout_session.url,
            "sessionId": checkout_session.id
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


class DirectPaymentRequest(BaseModel):
    productKey: str
    customerEmail: str
    paymentMethodId: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None


@router.post("/direct-payment")
async def process_direct_payment(request: DirectPaymentRequest):
    """
    Process direct payment for add-ons
    Creates a payment intent for one-time purchases (not subscriptions)
    """
    try:
        if not stripe_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing not configured"
            )

        # Find or create customer
        customers = stripe.Customer.list(
            email=request.customerEmail,
            limit=1
        )

        if len(customers.data) > 0:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=request.customerEmail,
                metadata=request.metadata or {}
            )

        # Map product key to amount
        addon_amounts = {
            "coverLetterAddon": 1200,  # $12.00
            "resumeCustomizationAddon": 1200,  # $12.00
            "priorityAccessAddon": 1200,  # $12.00
        }

        amount = addon_amounts.get(request.productKey, 1200)

        # Create payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
            customer=customer.id,
            payment_method=request.paymentMethodId or "pm_card_visa",  # Default test card
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"} if not request.paymentMethodId else None,
            metadata={
                "productKey": request.productKey,
                "addonType": request.productKey.replace("Addon", ""),
                **(request.metadata or {})
            },
            description=f"Add-on: {request.productKey}"
        )

        if payment_intent.status == "succeeded":
            # Log payment to MongoDB
            await mongodb_service.log_payment(
                user_id=request.metadata.get("userId", "unknown") if request.metadata else "unknown",
                user_email=request.customerEmail,
                stripe_customer_id=customer.id,
                amount=amount / 100,  # Convert cents to dollars
                status="succeeded",
                payment_type="addon",
                stripe_payment_intent_id=payment_intent.id,
                product_key=request.productKey,
                description=f"Add-on: {request.productKey}",
                metadata=request.metadata
            )

            # Add addon to subscription
            await mongodb_service.add_addon_to_subscription(
                user_email=request.customerEmail,
                addon_key=request.productKey
            )

            return {
                "success": True,
                "paymentIntentId": payment_intent.id,
                "status": payment_intent.status,
                "message": "Payment processed successfully"
            }
        elif payment_intent.status == "requires_payment_method":
            return {
                "success": False,
                "status": payment_intent.status,
                "message": "Payment requires payment method",
                "clientSecret": payment_intent.client_secret
            }
        else:
            return {
                "success": False,
                "status": payment_intent.status,
                "message": f"Payment status: {payment_intent.status}"
            }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in direct payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing direct payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process payment"
        )

