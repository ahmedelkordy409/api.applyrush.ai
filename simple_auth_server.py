"""
Simple standalone authentication server for onboarding flow.
Loads environment variables and connects to MongoDB Atlas.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
import os
import secrets
import string
from datetime import datetime
import uvicorn
import logging
import stripe

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get MongoDB connection details from environment
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "jobhire")

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = STRIPE_SECRET_KEY

# Initialize FastAPI app with enhanced Swagger documentation
app = FastAPI(
    title="ApplyRush API",
    version="1.0.0",
    description="""
    ## ApplyRush Full-Stack Application API

    Complete API for job application platform with authentication, subscriptions, and onboarding.

    ### Features:
    * **Authentication** - User signup, login, and magic link authentication
    * **Subscriptions** - Stripe-powered subscription management with checkout and add-ons
    * **Guest Onboarding** - Session-based onboarding flow for guest users
    * **Upselling** - Multi-step upselling workflow with profile management
    * **Webhooks** - Stripe webhook handling for subscription events

    ### Backend: FastAPI + MongoDB + Stripe
    ### Frontend: Next.js
    """,
    contact={
        "name": "ApplyRush Support",
        "email": "support@applyrush.ai"
    },
    license_info={
        "name": "Proprietary"
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3004", "http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB client (will be initialized on startup)
mongodb_client = None
db = None


# Request/Response models
class SignupRequest(BaseModel):
    email: EmailStr
    from_onboarding: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str


class SignupResponse(BaseModel):
    success: bool
    user: UserResponse
    tempPassword: str
    message: str


class LoginResponse(BaseModel):
    success: bool
    user: UserResponse
    access_token: str
    message: str


# Upselling models
class UpdateProfileRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class OnboardingStepRequest(BaseModel):
    email: EmailStr
    step: str
    data: Dict[str, Any]


class UploadResumeRequest(BaseModel):
    email: EmailStr
    resume_url: str
    resume_filename: Optional[str] = None


class CompanyPreferencesRequest(BaseModel):
    email: EmailStr
    excluded_companies: List[str] = Field(default_factory=list)
    preferred_companies: List[str] = Field(default_factory=list)
    target_job_titles: List[str] = Field(default_factory=list)


class CreatePasswordRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str


# Utility functions
def generate_temp_password(length: int = 16) -> str:
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# Startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    """Connect to MongoDB on startup."""
    global mongodb_client, db
    try:
        print(f"Connecting to MongoDB at: {MONGODB_URL[:20]}...")
        mongodb_client = AsyncIOMotorClient(MONGODB_URL)
        db = mongodb_client[MONGODB_DATABASE]

        # Test connection
        await db.command('ping')
        print(f"✓ Successfully connected to MongoDB database: {MONGODB_DATABASE}")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_db_client():
    """Close MongoDB connection on shutdown."""
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        print("✓ MongoDB connection closed")


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint - Verify API is running."""
    return {
        "status": "healthy",
        "database": "connected" if mongodb_client else "disconnected",
        "database_name": MONGODB_DATABASE
    }


# Authentication endpoints
@app.post("/api/auth/signup", response_model=SignupResponse, tags=["Authentication"])
async def signup(request: SignupRequest):
    """
    Create a new user account.
    Returns temporary password for auto-login.
    """
    try:
        users_collection = db.users

        # Check if user already exists
        existing_user = await users_collection.find_one({"email": request.email})
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User already exists with this email address"
            )

        # Generate temporary password
        temp_password = generate_temp_password()

        # Create user document
        user_doc = {
            "email": request.email,
            "password": temp_password,  # In production, this should be hashed
            "from_onboarding": request.from_onboarding,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "email_verified": False
        }

        # Insert user into database
        result = await users_collection.insert_one(user_doc)
        user_id = str(result.inserted_id)

        print(f"✓ Created user account: {request.email} (ID: {user_id})")

        return SignupResponse(
            success=True,
            user=UserResponse(
                id=user_id,
                email=request.email
            ),
            tempPassword=temp_password,
            message="Account created successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Signup error: {e}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@app.post("/api/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(request: LoginRequest):
    """
    Login with email and password.
    Returns access token for session management.
    """
    try:
        users_collection = db.users

        # Find user by email
        user = await users_collection.find_one({"email": request.email})
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Verify password (in production, use proper password hashing)
        if user.get("password") != request.password:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Generate access token (simple token for now)
        access_token = secrets.token_urlsafe(32)

        # Update user's last login
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )

        user_id = str(user["_id"])
        print(f"✓ User logged in: {request.email} (ID: {user_id})")

        return LoginResponse(
            success=True,
            user=UserResponse(
                id=user_id,
                email=user["email"]
            ),
            access_token=access_token,
            message="Login successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@app.post("/api/auth/magic-link", tags=["Authentication"])
async def send_magic_link(request: dict):
    """
    Send magic link for existing users.
    For now, returns success to allow email collection flow.
    """
    email = request.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    print(f"✓ Magic link requested for: {email}")

    return {
        "success": True,
        "message": "Magic link sent to email"
    }


# ==================== UPSELLING ENDPOINTS ====================

@app.post("/api/upselling/update-profile", tags=["Upselling"])
async def update_profile(request: UpdateProfileRequest):
    """Update user profile data during upselling flow"""
    try:
        users_collection = db.users

        # Find user by email
        user = await users_collection.find_one({"email": request.email})

        if not user:
            # Create user if doesn't exist
            user_doc = {
                "email": request.email,
                "full_name": request.full_name,
                "profile_data": request.data,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_active": True
            }
            await users_collection.insert_one(user_doc)
            logger.info(f"✓ Created new user profile: {request.email}")
        else:
            # Update existing user
            update_data = {
                "updated_at": datetime.utcnow()
            }
            if request.full_name:
                update_data["full_name"] = request.full_name
            if request.data:
                update_data["profile_data"] = request.data

            await users_collection.update_one(
                {"email": request.email},
                {"$set": update_data}
            )
            logger.info(f"✓ Updated user profile: {request.email}")

        return {
            "success": True,
            "message": "Profile updated successfully"
        }

    except Exception as e:
        logger.error(f"✗ Error updating profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


@app.post("/api/upselling/save-step", tags=["Upselling"])
async def save_onboarding_step(request: OnboardingStepRequest):
    """Save onboarding step progress"""
    try:
        users_collection = db.users

        # Find or create user
        user = await users_collection.find_one({"email": request.email})

        if not user:
            # Create user with onboarding data
            user_doc = {
                "email": request.email,
                "onboarding_data": {request.step: request.data},
                "onboarding_current_step": request.step,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await users_collection.insert_one(user_doc)
        else:
            # Update onboarding data
            await users_collection.update_one(
                {"email": request.email},
                {
                    "$set": {
                        f"onboarding_data.{request.step}": request.data,
                        "onboarding_current_step": request.step,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

        logger.info(f"✓ Saved onboarding step '{request.step}' for: {request.email}")

        return {
            "success": True,
            "message": f"Step {request.step} saved successfully"
        }

    except Exception as e:
        logger.error(f"✗ Error saving onboarding step: {e}")
        raise HTTPException(status_code=500, detail="Failed to save progress")


@app.get("/api/upselling/user-profile", tags=["Upselling"])
async def get_user_profile(email: str):
    """Get user profile data"""
    try:
        users_collection = db.users

        user = await users_collection.find_one({"email": email})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Remove MongoDB _id
        user.pop('_id', None)

        return {
            "user": {
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "stripe_customer_id": user.get("stripe_customer_id"),
                "resume_uploaded": user.get("resume_uploaded", False),
                "resume_url": user.get("resume_url"),
                "resume_filename": user.get("resume_filename"),
                "password_created": user.get("password_created", False),
                "preferences": user.get("preferences", {}),
                "metadata": user.get("metadata", {}),
                "profile_data": user.get("profile_data", {})
            },
            "onboarding": {
                "current_step": user.get("onboarding_current_step"),
                "completed": user.get("onboarding_completed", False),
                "data": user.get("onboarding_data", {})
            },
            "upselling": {
                "completed": user.get("upselling_completed", False),
                "completed_at": user.get("upselling_completed_at")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user profile")


@app.post("/api/upselling/upload-resume", tags=["Upselling"])
async def upload_resume(request: UploadResumeRequest):
    """Mark resume as uploaded for user"""
    try:
        users_collection = db.users

        update_data = {
            "resume_uploaded": True,
            "resume_url": request.resume_url,
            "resume_uploaded_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        if request.resume_filename:
            update_data["resume_filename"] = request.resume_filename

        result = await users_collection.update_one(
            {"email": request.email},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"✓ Resume uploaded for: {request.email}")

        return {
            "success": True,
            "message": "Resume uploaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error uploading resume: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload resume")


@app.post("/api/upselling/company-preferences", tags=["Upselling"])
async def save_company_preferences(request: CompanyPreferencesRequest):
    """Save user's company preferences"""
    try:
        users_collection = db.users

        preferences = {
            "excluded_companies": request.excluded_companies,
            "preferred_companies": request.preferred_companies,
            "target_job_titles": request.target_job_titles,
            "updated_at": datetime.utcnow()
        }

        result = await users_collection.update_one(
            {"email": request.email},
            {
                "$set": {
                    "preferences": preferences,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"✓ Company preferences saved for: {request.email}")

        return {
            "success": True,
            "message": "Preferences saved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error saving preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to save preferences")


@app.post("/api/upselling/create-password", tags=["Upselling"])
async def create_password(request: CreatePasswordRequest):
    """Allow user to create a permanent password"""
    try:
        # Validate passwords match
        if request.password != request.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")

        # Validate password strength
        if len(request.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

        users_collection = db.users

        # Update password (in production, hash this!)
        result = await users_collection.update_one(
            {"email": request.email},
            {
                "$set": {
                    "password": request.password,  # In production: hash this!
                    "password_created": True,
                    "password_created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"✓ Password created for: {request.email}")

        return {
            "success": True,
            "message": "Password created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error creating password: {e}")
        raise HTTPException(status_code=500, detail="Failed to create password")


@app.post("/api/upselling/complete-onboarding", tags=["Upselling"])
async def complete_onboarding(request: OnboardingStepRequest):
    """Mark onboarding/upselling as completed"""
    try:
        users_collection = db.users

        result = await users_collection.update_one(
            {"email": request.email},
            {
                "$set": {
                    "onboarding_completed": True,
                    "upselling_completed": True,
                    "onboarding_completed_at": datetime.utcnow(),
                    "upselling_completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"✓ Upselling/Onboarding completed for: {request.email}")

        return {
            "success": True,
            "message": "Onboarding completed successfully",
            "redirect_to": "/dashboard"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error completing onboarding: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete onboarding")


# ==================== SUBSCRIPTION ENDPOINTS ====================

class CreateCheckoutSessionRequest(BaseModel):
    userEmail: str
    planId: str
    billingCycle: str
    coupon: Optional[str] = None
    userId: Optional[str] = None

@app.post("/api/subscriptions/create-checkout-session", tags=["Subscriptions"])
async def create_checkout_session(request: CreateCheckoutSessionRequest):
    """Create a Stripe checkout session for subscription purchase"""
    try:
        users_collection = db.users

        # Verify user exists
        user = await users_collection.find_one({"email": request.userEmail})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Map planId to Stripe price IDs (you'll need to create these in Stripe Dashboard)
        # For now using placeholders - replace with your actual Stripe price IDs
        price_map = {
            "starter": {
                "monthly": os.getenv("STRIPE_STARTER_MONTHLY_PRICE_ID", "price_starter_monthly"),
                "yearly": os.getenv("STRIPE_STARTER_YEARLY_PRICE_ID", "price_starter_yearly")
            },
            "pro": {
                "monthly": os.getenv("STRIPE_PRO_MONTHLY_PRICE_ID", "price_pro_monthly"),
                "yearly": os.getenv("STRIPE_PRO_YEARLY_PRICE_ID", "price_pro_yearly")
            },
            "pro-plus": {
                "monthly": os.getenv("STRIPE_PRO_PLUS_MONTHLY_PRICE_ID", "price_pro_plus_monthly"),
                "yearly": os.getenv("STRIPE_PRO_PLUS_YEARLY_PRICE_ID", "price_pro_plus_yearly")
            }
        }

        price_id = price_map.get(request.planId, {}).get(request.billingCycle)
        if not price_id:
            raise HTTPException(status_code=400, detail=f"Invalid plan or billing cycle")

        # Create or retrieve Stripe customer
        stripe_customer_id = user.get("stripe_customer_id")

        if not stripe_customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=request.userEmail,
                metadata={
                    "user_id": str(user["_id"]),
                }
            )
            stripe_customer_id = customer.id

            # Save customer ID to database
            await users_collection.update_one(
                {"email": request.userEmail},
                {"$set": {"stripe_customer_id": stripe_customer_id}}
            )

        # Prepare checkout session params
        checkout_params = {
            "customer": stripe_customer_id,
            "payment_method_types": ['card'],
            "line_items": [{
                'price': price_id,
                'quantity': 1,
            }],
            "mode": 'subscription',
            "success_url": "http://localhost:3000/upselling/resume-customization?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "http://localhost:3000/upselling/pricing",
            "metadata": {
                'user_email': request.userEmail,
                'user_id': str(user["_id"]),
                'plan': request.planId,
                'billing_cycle': request.billingCycle,
            },
            "subscription_data": {
                'metadata': {
                    'user_email': request.userEmail,
                    'user_id': str(user["_id"]),
                    'plan': request.planId,
                    'billing_cycle': request.billingCycle,
                }
            }
        }

        # Note: In subscription mode, Stripe automatically saves the payment method
        # to the customer for future recurring charges and can be used for add-ons

        # Add coupon if provided
        if request.coupon:
            checkout_params["discounts"] = [{"coupon": request.coupon}]

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(**checkout_params)

        logger.info(f"✓ Created checkout session for {request.userEmail}: {checkout_session.id}")

        return {
            "success": True,
            "sessionId": checkout_session.id,
            "sessionUrl": checkout_session.url,
            "url": checkout_session.url  # Add this for frontend compatibility
        }

    except stripe.error.StripeError as e:
        logger.error(f"✗ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


# ==================== ADDON PURCHASE ====================

class PurchaseAddonRequest(BaseModel):
    userEmail: str
    userId: str
    addonType: str  # 'resume_customization', 'cover_letter', etc.
    amount: float

@app.post("/api/subscriptions/purchase-addon", tags=["Subscriptions"])
async def purchase_addon(request: PurchaseAddonRequest):
    """Purchase an addon using existing Stripe customer - No checkout required"""
    try:
        users_collection = db.users
        subscriptions_collection = db.subscriptions
        transactions_collection = db.transactions

        # Verify user exists
        user = await users_collection.find_one({"email": request.userEmail})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get Stripe customer ID
        stripe_customer_id = user.get("stripe_customer_id")
        if not stripe_customer_id:
            raise HTTPException(status_code=400, detail="User must have an active subscription first")

        # Get customer's default payment method
        customer = stripe.Customer.retrieve(stripe_customer_id)
        default_payment_method = customer.get('invoice_settings', {}).get('default_payment_method')

        if not default_payment_method:
            # Try to get from subscription
            subscription_doc = await subscriptions_collection.find_one({"user_id": request.userId})
            if subscription_doc and subscription_doc.get('stripe_subscription_id'):
                subscription = stripe.Subscription.retrieve(subscription_doc['stripe_subscription_id'])
                default_payment_method = subscription.get('default_payment_method')

        if not default_payment_method:
            raise HTTPException(
                status_code=400,
                detail="No payment method found. Please complete your subscription purchase first to add a payment method."
            )

        # Create a one-time payment
        amount_cents = int(request.amount * 100)

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            customer=stripe_customer_id,
            payment_method=default_payment_method,
            off_session=True,
            confirm=True,
            description=f"{request.addonType.replace('_', ' ').title()} Add-on",
            metadata={
                'user_id': request.userId,
                'user_email': request.userEmail,
                'addon_type': request.addonType,
                'type': 'addon_purchase'
            }
        )

        if payment_intent.status == 'succeeded':
            # Add addon to subscription document
            addon_doc = {
                "id": payment_intent.id,
                "type": request.addonType,
                "name": request.addonType.replace('_', ' ').title(),
                "amount": request.amount,
                "currency": "usd",
                "purchased_at": datetime.utcnow(),
                "status": "active",
                "payment_intent_id": payment_intent.id
            }

            await subscriptions_collection.update_one(
                {"user_id": request.userId},
                {
                    "$push": {"addons": addon_doc},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            # Create transaction record
            transaction_doc = {
                "user_id": request.userId,
                "user_email": request.userEmail,
                "type": "addon_purchase",
                "stripe_payment_intent_id": payment_intent.id,
                "amount": request.amount,
                "currency": "usd",
                "status": "succeeded",
                "description": f"{request.addonType.replace('_', ' ').title()} add-on purchase",
                "created_at": datetime.utcnow(),
                "metadata": {
                    "addon_type": request.addonType
                }
            }
            await transactions_collection.insert_one(transaction_doc)

            logger.info(f"✓ Addon purchased for {request.userEmail}: {request.addonType} (${request.amount})")

            return {
                "success": True,
                "paymentIntentId": payment_intent.id,
                "addonType": request.addonType,
                "amount": request.amount,
                "message": "Add-on purchased successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Payment failed: {payment_intent.status}")

    except stripe.error.CardError as e:
        logger.error(f"✗ Card error: {e}")
        raise HTTPException(status_code=400, detail=f"Card error: {str(e)}")
    except stripe.error.StripeError as e:
        logger.error(f"✗ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error purchasing addon: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to purchase add-on")


@app.get("/api/subscriptions/user", tags=["Subscriptions"])
async def get_user_subscription(email: str):
    """Get user's subscription details with usage limits and features"""
    try:
        users_collection = db.users

        user = await users_collection.find_one({"email": email})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Define plan limits (all paid plans - no free tier)
        plan_limits = {
            "starter": {
                "applications_per_month": 50,
                "cover_letters": 25,
                "ai_suggestions": 100,
                "resume_scans": 5
            },
            "pro": {
                "applications_per_month": -1,  # unlimited
                "cover_letters": -1,
                "ai_suggestions": -1,
                "resume_scans": -1
            },
            "pro-plus": {
                "applications_per_month": -1,
                "cover_letters": -1,
                "ai_suggestions": -1,
                "resume_scans": -1,
                "priority_support": True,
                "dedicated_account_manager": True
            }
        }

        current_plan = user.get("subscription_plan")
        usage = user.get("usage", {})
        addons = user.get("addons", [])

        # Check if user has an active subscription
        if not current_plan or current_plan not in plan_limits:
            return {
                "subscription": None,
                "requires_subscription": True,
                "redirect_url": "http://localhost:3004/upselling/pricing",
                "message": "No active subscription. Please subscribe to a plan to continue."
            }

        logger.info(f"✓ Retrieved subscription for: {email} (Plan: {current_plan})")

        return {
            "subscription": {
                "plan": current_plan,
                "status": user.get("subscription_status", "active"),
                "billing_cycle": user.get("billing_cycle", "monthly"),
                "next_billing_date": user.get("next_billing_date"),
                "stripe_subscription_id": user.get("stripe_subscription_id"),
                "stripe_customer_id": user.get("stripe_customer_id")
            },
            "limits": plan_limits.get(current_plan),
            "usage": {
                "applications_this_month": usage.get("applications", 0),
                "cover_letters_generated": usage.get("cover_letters", 0),
                "ai_suggestions_used": usage.get("ai_suggestions", 0),
                "resume_scans_used": usage.get("resume_scans", 0)
            },
            "addons": addons,
            "features": {
                "ai_cover_letters": current_plan in ["pro", "pro-plus", "starter"],
                "auto_apply": current_plan in ["pro", "pro-plus"],
                "priority_support": current_plan == "pro-plus",
                "custom_branding": current_plan == "pro-plus",
                "api_access": current_plan in ["pro", "pro-plus"],
                "resume_builder": True,  # Available to all paid plans
                "job_tracking": True  # Available to all paid plans
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscription")


class UsageIncrementRequest(BaseModel):
    email: EmailStr
    feature: str  # e.g., "applications", "cover_letters", "ai_suggestions", "resume_scans"
    amount: int = 1


@app.post("/api/subscriptions/usage/increment", tags=["Subscriptions"])
async def increment_usage(request: UsageIncrementRequest):
    """Track feature usage and enforce limits"""
    try:
        users_collection = db.users

        # Find user
        user = await users_collection.find_one({"email": request.email})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get current plan and usage
        current_plan = user.get("subscription_plan")
        usage = user.get("usage", {})

        # Check if user has an active subscription
        if not current_plan:
            raise HTTPException(
                status_code=403,
                detail="No active subscription. Please subscribe to a plan to continue."
            )

        # Plan limits (all paid plans - no free tier)
        plan_limits = {
            "starter": {
                "applications": 50,
                "cover_letters": 25,
                "ai_suggestions": 100,
                "resume_scans": 5
            },
            "pro": {
                "applications": -1,
                "cover_letters": -1,
                "ai_suggestions": -1,
                "resume_scans": -1
            },
            "pro-plus": {
                "applications": -1,
                "cover_letters": -1,
                "ai_suggestions": -1,
                "resume_scans": -1
            }
        }

        # Validate plan exists
        if current_plan not in plan_limits:
            raise HTTPException(
                status_code=403,
                detail="Invalid subscription plan. Please subscribe to a valid plan."
            )

        # Get limit for this feature
        limits = plan_limits.get(current_plan)
        feature_limit = limits.get(request.feature, 0)

        # Check if feature is unlimited (-1) or within limit
        current_usage = usage.get(request.feature, 0)

        if feature_limit != -1 and current_usage >= feature_limit:
            raise HTTPException(
                status_code=403,
                detail=f"Usage limit reached for {request.feature}. Please upgrade your plan."
            )

        # Increment usage
        new_usage = current_usage + request.amount

        await users_collection.update_one(
            {"email": request.email},
            {
                "$set": {
                    f"usage.{request.feature}": new_usage,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✓ Incremented {request.feature} usage for {request.email}: {current_usage} → {new_usage}")

        return {
            "success": True,
            "feature": request.feature,
            "usage": new_usage,
            "limit": feature_limit,
            "remaining": feature_limit - new_usage if feature_limit != -1 else -1
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error incrementing usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to track usage")


class PurchaseAddonRequest(BaseModel):
    email: EmailStr
    addon_id: str
    addon_name: str
    addon_price: float
    addon_credits: Optional[int] = None


@app.post("/api/subscriptions/addon/purchase", tags=["Subscriptions"])
async def purchase_addon(request: PurchaseAddonRequest):
    """Add purchased addon to user account"""
    try:
        users_collection = db.users

        # Find user
        user = await users_collection.find_one({"email": request.email})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create addon record
        addon = {
            "id": request.addon_id,
            "name": request.addon_name,
            "price": request.addon_price,
            "credits": request.addon_credits,
            "purchased_at": datetime.utcnow(),
            "status": "active"
        }

        # Add addon to user's addons list
        await users_collection.update_one(
            {"email": request.email},
            {
                "$push": {"addons": addon},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        logger.info(f"✓ Addon '{request.addon_name}' purchased for {request.email}")

        return {
            "success": True,
            "message": f"Addon '{request.addon_name}' purchased successfully",
            "addon": addon
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Error purchasing addon: {e}")
        raise HTTPException(status_code=500, detail="Failed to purchase addon")


# ==================== STRIPE WEBHOOK ====================

@app.post("/api/webhooks/stripe", tags=["Webhooks"])
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events - Enterprise-grade subscription management"""
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')

        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"✗ Invalid payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"✗ Invalid signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        users_collection = db.users
        subscriptions_collection = db.subscriptions
        transactions_collection = db.transactions

        event_type = event['type']
        logger.info(f"📥 Received Stripe webhook: {event_type}")

        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            user_email = session['metadata'].get('user_email')
            user_id = session['metadata'].get('user_id')
            plan = session['metadata'].get('plan')
            billing_cycle = session['metadata'].get('billing_cycle')

            if user_email and user_id:
                # Get price amount from Stripe
                amount_total = session.get('amount_total', 0) / 100  # Convert from cents

                # Create subscription document
                subscription_doc = {
                    "user_id": user_id,
                    "user_email": user_email,
                    "stripe_subscription_id": session.get('subscription'),
                    "stripe_customer_id": session.get('customer'),
                    "stripe_checkout_session_id": session.get('id'),

                    # Plan details
                    "plan_id": plan,
                    "plan_name": plan.replace('-', ' ').title(),
                    "billing_cycle": billing_cycle,
                    "status": "active",

                    # Pricing
                    "amount": amount_total,
                    "currency": session.get('currency', 'usd'),
                    "discount_applied": session.get('discount') is not None,
                    "coupon_code": session.get('discount', {}).get('coupon', {}).get('id') if session.get('discount') else None,

                    # Dates
                    "current_period_start": datetime.utcnow(),
                    "current_period_end": None,  # Will be set when we get subscription details
                    "trial_end": None,
                    "cancel_at": None,
                    "canceled_at": None,
                    "ended_at": None,

                    # Add-ons (initially empty, will be added later)
                    "addons": [],

                    # Payment history
                    "total_paid": amount_total,
                    "payment_count": 1,
                    "last_payment_date": datetime.utcnow(),
                    "next_payment_date": None,

                    # Metadata
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "metadata": session.get('metadata', {})
                }

                # Insert or update subscription
                await subscriptions_collection.update_one(
                    {"user_id": user_id},
                    {"$set": subscription_doc},
                    upsert=True
                )

                # Create transaction record
                transaction_doc = {
                    "user_id": user_id,
                    "user_email": user_email,
                    "type": "subscription_payment",
                    "stripe_payment_intent_id": session.get('payment_intent'),
                    "stripe_checkout_session_id": session.get('id'),
                    "amount": amount_total,
                    "currency": session.get('currency', 'usd'),
                    "status": "succeeded",
                    "description": f"{plan} subscription - {billing_cycle}",
                    "created_at": datetime.utcnow(),
                    "metadata": {
                        "plan": plan,
                        "billing_cycle": billing_cycle
                    }
                }
                await transactions_collection.insert_one(transaction_doc)

                # Update user document with reference
                await users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$set": {
                            "subscription_id": str(subscription_doc.get('_id')),
                            "subscription_status": "active",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                logger.info(f"✓ Created subscription for {user_email}: {plan} ({billing_cycle})")

        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            user_email = subscription['metadata'].get('user_email')
            user_id = subscription['metadata'].get('user_id')

            if user_id:
                update_data = {
                    "status": subscription['status'],
                    "current_period_start": datetime.fromtimestamp(subscription['current_period_start']),
                    "current_period_end": datetime.fromtimestamp(subscription['current_period_end']),
                    "cancel_at_period_end": subscription.get('cancel_at_period_end', False),
                    "updated_at": datetime.utcnow()
                }

                if subscription.get('canceled_at'):
                    update_data['canceled_at'] = datetime.fromtimestamp(subscription['canceled_at'])
                if subscription.get('cancel_at'):
                    update_data['cancel_at'] = datetime.fromtimestamp(subscription['cancel_at'])

                await subscriptions_collection.update_one(
                    {"user_id": user_id},
                    {"$set": update_data}
                )

                await users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"subscription_status": subscription['status'], "updated_at": datetime.utcnow()}}
                )

                logger.info(f"✓ Updated subscription for {user_email}: {subscription['status']}")

        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            user_id = subscription['metadata'].get('user_id')

            if user_id:
                await subscriptions_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "status": "cancelled",
                            "ended_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                await users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"subscription_status": "cancelled", "updated_at": datetime.utcnow()}}
                )

                logger.info(f"✓ Cancelled subscription for user {user_id}")

        elif event_type == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription['metadata'].get('user_id')
                user_email = subscription['metadata'].get('user_email')
                amount = invoice.get('amount_paid', 0) / 100

                if user_id:
                    # Update subscription payment history
                    await subscriptions_collection.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {
                                "status": "active",
                                "last_payment_date": datetime.utcnow(),
                                "updated_at": datetime.utcnow()
                            },
                            "$inc": {
                                "total_paid": amount,
                                "payment_count": 1
                            }
                        }
                    )

                    # Create transaction record
                    transaction_doc = {
                        "user_id": user_id,
                        "user_email": user_email,
                        "type": "subscription_renewal",
                        "stripe_invoice_id": invoice.get('id'),
                        "stripe_payment_intent_id": invoice.get('payment_intent'),
                        "amount": amount,
                        "currency": invoice.get('currency', 'usd'),
                        "status": "succeeded",
                        "description": f"Subscription renewal payment",
                        "created_at": datetime.utcnow()
                    }
                    await transactions_collection.insert_one(transaction_doc)

                    await users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": {"subscription_status": "active", "updated_at": datetime.utcnow()}}
                    )

                    logger.info(f"✓ Payment succeeded for {user_email}: ${amount}")

        elif event_type == 'invoice.payment_failed':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription['metadata'].get('user_id')
                user_email = subscription['metadata'].get('user_email')

                if user_id:
                    await subscriptions_collection.update_one(
                        {"user_id": user_id},
                        {"$set": {"status": "past_due", "updated_at": datetime.utcnow()}}
                    )

                    await users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": {"subscription_status": "past_due", "updated_at": datetime.utcnow()}}
                    )

                    # Create failed transaction record
                    transaction_doc = {
                        "user_id": user_id,
                        "user_email": user_email,
                        "type": "subscription_payment_failed",
                        "stripe_invoice_id": invoice.get('id'),
                        "amount": invoice.get('amount_due', 0) / 100,
                        "currency": invoice.get('currency', 'usd'),
                        "status": "failed",
                        "description": f"Subscription payment failed",
                        "created_at": datetime.utcnow()
                    }
                    await transactions_collection.insert_one(transaction_doc)

                    logger.warning(f"⚠️ Payment failed for {user_email}")

        return {"success": True, "event_type": event_type}

    except Exception as e:
        logger.error(f"✗ Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# ============================================================
# GUEST ONBOARDING ENDPOINTS
# ============================================================

class CreateGuestSessionRequest(BaseModel):
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

class CreateGuestSessionResponse(BaseModel):
    session_id: str
    created_at: str
    expires_at: str
    status: str

class SaveAnswerRequest(BaseModel):
    session_id: str
    step: Optional[int] = None
    step_id: Optional[str] = None
    answer: Dict[str, Any]
    time_spent_seconds: Optional[int] = None

class SaveAnswerResponse(BaseModel):
    success: bool
    session_id: str
    current_step: int

@app.post("/api/onboarding/guest/create", tags=["Guest Onboarding"])
async def create_guest_session(request: CreateGuestSessionRequest):
    """Create a new guest onboarding session"""
    try:
        # Generate secure session ID
        session_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

        # Calculate expiration (24 hours from now)
        created_at = datetime.utcnow()
        expires_at = created_at.replace(hour=23, minute=59, second=59)

        # Create guest profile document
        guest_profile = {
            "session_id": session_id,
            "status": "in_progress",
            "current_step": 0,
            "completed_steps": [],
            "answers": {},
            "created_at": created_at,
            "expires_at": expires_at,
            "referrer": request.referrer,
            "utm_source": request.utm_source,
            "utm_medium": request.utm_medium,
            "utm_campaign": request.utm_campaign
        }

        # Save to MongoDB
        guest_collection = db.guest_profiles
        await guest_collection.insert_one(guest_profile)

        logger.info(f"✓ Created guest session: {session_id}")

        return {
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "success"
        }

    except Exception as e:
        logger.error(f"✗ Failed to create guest session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create session")

@app.post("/api/onboarding/guest/answer", tags=["Guest Onboarding"])
async def save_guest_answer(request: SaveAnswerRequest):
    """Save guest answer to a specific onboarding step"""
    try:
        guest_collection = db.guest_profiles

        # Find guest profile
        guest_profile = await guest_collection.find_one({"session_id": request.session_id})

        if not guest_profile:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if session expired
        if datetime.utcnow() > guest_profile["expires_at"]:
            raise HTTPException(status_code=410, detail="Session expired")

        # Use step_id or step (support both formats)
        step_key = request.step_id if request.step_id else str(request.step) if request.step is not None else "0"

        # Update answers and progress
        update_data = {
            f"answers.{step_key}": request.answer,
            "updated_at": datetime.utcnow()
        }

        # Track current step number if provided
        if request.step is not None:
            current_step = guest_profile.get("current_step", 0)
            update_data["current_step"] = max(current_step, request.step + 1)

        await guest_collection.update_one(
            {"session_id": request.session_id},
            {"$set": update_data}
        )

        logger.info(f"✓ Saved answer for session {request.session_id}, step {step_key}")

        return {
            "success": True,
            "session_id": request.session_id,
            "current_step": update_data.get("current_step", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Failed to save answer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save answer")

@app.get("/api/onboarding/guest/{session_id}", tags=["Guest Onboarding"])
async def get_guest_session(session_id: str):
    """Get guest session data"""
    try:
        guest_collection = db.guest_profiles

        guest_profile = await guest_collection.find_one({"session_id": session_id})

        if not guest_profile:
            raise HTTPException(status_code=404, detail="Session not found")

        # Convert ObjectId to string for JSON serialization
        guest_profile["_id"] = str(guest_profile["_id"])
        guest_profile["created_at"] = guest_profile["created_at"].isoformat()
        guest_profile["expires_at"] = guest_profile["expires_at"].isoformat()
        if "updated_at" in guest_profile:
            guest_profile["updated_at"] = guest_profile["updated_at"].isoformat()

        return guest_profile

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Failed to get session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve session")


if __name__ == "__main__":
    print("=" * 60)
    print("Starting ApplyRush Auth Service")
    print("=" * 60)
    print(f"MongoDB URL: {MONGODB_URL[:30]}...")
    print(f"MongoDB Database: {MONGODB_DATABASE}")
    print(f"Server will run on: http://localhost:8000")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
