"""
Upselling Flow API endpoints
Handles all upselling pages and user onboarding
REQUIRES AUTHENTICATION - All endpoints protected
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr
import logging
import stripe

from app.services.mongodb_service import mongodb_service
from app.core.security import get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Stripe
stripe_api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
if stripe_api_key:
    stripe.api_key = stripe_api_key

# Stripe Price IDs for subscriptions
STRIPE_PRICE_IDS = {
    "starter_monthly": "price_1SDKIKQYDSf5l1Z0hXbunNSJ",
    "starter_yearly": "price_1SDKIKQYDSf5l1Z0tPciS0Dl",
    "pro_monthly": "price_1SDKILQYDSf5l1Z0JE97c6I5",
    "pro_yearly": "price_1SDKILQYDSf5l1Z0Klb7WwL8",
    "pro-plus_monthly": "price_1SDKIMQYDSf5l1Z0G5tWnwRa",
    "pro-plus_yearly": "price_1SDKIMQYDSf5l1Z0B5ldXuUa",
    "basic_monthly": "price_1SDKIKQYDSf5l1Z0hXbunNSJ",
    "basic_yearly": "price_1SDKIKQYDSf5l1Z0tPciS0Dl",
    "premium_monthly": "price_1SDKILQYDSf5l1Z0JE97c6I5",
    "premium_yearly": "price_1SDKILQYDSf5l1Z0Klb7WwL8",
    "enterprise_monthly": "price_1SDKIMQYDSf5l1Z0G5tWnwRa",
    "enterprise_yearly": "price_1SDKIMQYDSf5l1Z0B5ldXuUa",
}

# Add-on prices (in cents)
ADDON_PRICES = {
    "resume-customization": 1200,  # $12.00
    "cover-letter": 1200,  # $12.00
    "priority-access": 1200,  # $12.00
    "premium-upgrade": 2900,  # $29.00
}


# Request/Response Models (All require authentication)
class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    data: Dict[str, Any]


class OnboardingStepRequest(BaseModel):
    step: str
    data: Dict[str, Any]


class UploadResumeRequest(BaseModel):
    resume_url: str


class CompanyPreferencesRequest(BaseModel):
    excluded_companies: List[str] = []
    preferred_companies: List[str] = []
    target_job_titles: List[str] = []


class CreatePasswordRequest(BaseModel):
    password: str
    confirm_password: str


class PricingRequest(BaseModel):
    selectedPlan: str  # 'free', 'basic', 'premium', 'enterprise'
    billingCycle: str  # 'monthly', 'yearly'
    agreedToTerms: bool
    stripeSessionId: Optional[str] = None
    subscriptionId: Optional[str] = None


class ResumeCustomizationRequest(BaseModel):
    enabled: bool
    targetKeywords: Optional[List[str]] = []
    purchaseDate: Optional[str] = None
    stripeSessionId: Optional[str] = None


class CoverLetterRequest(BaseModel):
    enabled: bool
    writingStyle: Optional[str] = None  # 'professional', 'creative', 'technical', 'executive'
    purchaseDate: Optional[str] = None
    stripeSessionId: Optional[str] = None


class PremiumUpgradeRequest(BaseModel):
    upgraded: bool
    selectedFeatures: Optional[List[str]] = []
    upgradeDate: Optional[str] = None


class PriorityAccessRequest(BaseModel):
    enabled: bool
    notificationChannels: Optional[List[str]] = []  # 'email', 'push', 'sms'
    jobCriteria: Optional[Dict[str, Any]] = {}
    purchaseDate: Optional[str] = None


class UploadResumeDataRequest(BaseModel):
    resumeId: Optional[str] = None
    fileName: Optional[str] = None
    fileUrl: Optional[str] = None
    atsScore: Optional[int] = None
    uploadedAt: Optional[str] = None
    firstName: str
    lastName: str
    phoneNumber: str


class CompaniesToExcludeRequest(BaseModel):
    excludedCompanies: List[str] = []
    excludedCategories: Optional[List[str]] = []
    completedAt: Optional[str] = None


# Endpoints

@router.post("/update-profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Update user profile data
    Works for both authenticated users (via token) and guests (via email)
    """
    try:
        # Get email from auth token or request body
        if current_user:
            email = current_user.get("email")
        elif request.email:
            email = request.email
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email required for guest users"
            )

        success = await mongodb_service.update_user_profile(
            email=email,
            profile_data=request.data
        )

        if not success:
            await mongodb_service.create_or_update_user(
                email=email,
                full_name=request.full_name,
                onboarding_data=request.data
            )

        return {
            "success": True,
            "message": "Profile updated successfully",
            "user_email": email,
            "authenticated": current_user is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/save-step")
async def save_onboarding_step(
    request: OnboardingStepRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Save onboarding step progress
    Works for both authenticated users (via token) and guests (via email)
    """
    try:
        # Get email from auth token or request body
        if current_user:
            email = current_user.get("email")
        elif request.email:
            email = request.email
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email required for guest users"
            )

        success = await mongodb_service.save_onboarding_progress(
            email=email,
            step=request.step,
            data=request.data
        )

        return {
            "success": success,
            "message": f"Step {request.step} saved successfully",
            "user_email": email,
            "authenticated": current_user is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving onboarding step: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save progress"
        )


@router.get("/user-profile")
async def get_user_profile(
    email: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Get user profile data
    Works for both authenticated users (via token) and guests (via email parameter)
    """
    try:
        # Get email from auth token or query parameter
        if current_user:
            user_email = current_user.get("email")
        elif email:
            user_email = email
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email required for guest users"
            )

        user = await mongodb_service.get_user(user_email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        subscription = await mongodb_service.get_subscription(user_email)

        return {
            "user": {
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "stripe_customer_id": user.get("stripe_customer_id"),
                "resume_uploaded": user.get("resume_uploaded", False),
                "resume_url": user.get("resume_url"),
                "password_created": user.get("password_created", False),
                "preferences": user.get("preferences", {}),
                "metadata": user.get("metadata", {})
            },
            "subscription": subscription or {},
            "onboarding": {
                "current_step": user.get("onboarding_current_step"),
                "data": user.get("onboarding_data", {})
            },
            "authenticated": current_user is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


@router.post("/complete-onboarding")
async def complete_onboarding(
    request: OnboardingStepRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Mark onboarding as completed
    Works for both authenticated users (via token) and guests (via email)
    """
    try:
        # Get email from auth token or request body
        if current_user:
            email = current_user.get("email")
        elif request.email:
            email = request.email
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email required for guest users"
            )

        success = await mongodb_service.update_user_profile(
            email=email,
            profile_data={
                "onboarding_completed": True,
                "onboarding_completed_at": datetime.utcnow(),
                **request.data
            }
        )

        return {
            "success": success,
            "message": "Onboarding completed successfully",
            "user_email": email,
            "authenticated": current_user is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding"
        )


# Specific Upselling Page Endpoints

@router.post("/pricing")
async def save_pricing(
    request: PricingRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save pricing/plan selection and create Stripe checkout if needed"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Save onboarding progress
        await mongodb_service.save_onboarding_progress(
            email=email,
            step="pricing",
            data=request.dict(exclude={'email'})
        )

        response = {
            "success": True,
            "message": "Pricing selection saved",
            "email": email,
            "authenticated": current_user is not None
        }

        # Create Stripe checkout if plan requires payment and Stripe is configured
        if request.selectedPlan != "free" and stripe_api_key:
            try:
                # Find or create Stripe customer
                user = await mongodb_service.get_user(email)
                customer_id = user.get("stripe_customer_id") if user else None

                if not customer_id:
                    customer = stripe.Customer.create(
                        email=email,
                        metadata={"user_email": email}
                    )
                    customer_id = customer.id

                    # Update user with customer ID
                    await mongodb_service.update_user_profile(
                        email=email,
                        profile_data={"stripe_customer_id": customer_id}
                    )

                # Get Stripe price ID
                price_key = f"{request.selectedPlan}_{request.billingCycle}"
                price_id = STRIPE_PRICE_IDS.get(price_key)

                if not price_id:
                    logger.warning(f"No Stripe price ID found for {price_key}")
                else:
                    # Create checkout session
                    checkout_session = stripe.checkout.Session.create(
                        customer=customer_id,
                        payment_method_types=['card'],
                        line_items=[{
                            'price': price_id,
                            'quantity': 1,
                        }],
                        mode='subscription',
                        success_url=f"{settings.FRONTEND_URL}/upselling/resume-customization?session_id={{CHECKOUT_SESSION_ID}}",
                        cancel_url=f"{settings.FRONTEND_URL}/upselling/pricing",
                        metadata={
                            'user_email': email,
                            'plan': request.selectedPlan,
                            'billing_cycle': request.billingCycle
                        }
                    )

                    # Add checkout info to response
                    response["checkoutUrl"] = checkout_session.url
                    response["sessionId"] = checkout_session.id

                    # Update user with session ID
                    await mongodb_service.save_onboarding_progress(
                        email=email,
                        step="pricing",
                        data={
                            **request.dict(exclude={'email'}),
                            "stripeSessionId": checkout_session.id
                        }
                    )

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {e}")
                response["stripeError"] = str(e)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to save pricing")


@router.post("/resume-customization")
async def save_resume_customization(
    request: ResumeCustomizationRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save resume customization preferences with optional Stripe payment"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Save onboarding progress
        await mongodb_service.save_onboarding_progress(
            email=email,
            step="resume-customization",
            data=request.dict(exclude={'email'})
        )

        response = {
            "success": True,
            "message": "Resume customization saved",
            "email": email,
            "authenticated": current_user is not None
        }

        # Create Stripe payment if enabled and Stripe is configured
        if request.enabled and stripe_api_key:
            try:
                # Get or create Stripe customer
                user = await mongodb_service.get_user(email)
                customer_id = user.get("stripe_customer_id") if user else None

                if not customer_id:
                    customer = stripe.Customer.create(email=email, metadata={"user_email": email})
                    customer_id = customer.id
                    await mongodb_service.update_user_profile(email=email, profile_data={"stripe_customer_id": customer_id})

                # Create payment intent
                amount = ADDON_PRICES.get("resume-customization", 1200)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    customer=customer_id,
                    automatic_payment_methods={"enabled": True},
                    metadata={"user_email": email, "addon": "resume-customization"},
                    description="Resume Customization Add-on"
                )

                response["paymentIntent"] = {
                    "clientSecret": payment_intent.client_secret,
                    "paymentIntentId": payment_intent.id,
                    "amount": amount / 100
                }

                # Save payment intent ID
                await mongodb_service.save_onboarding_progress(
                    email=email,
                    step="resume-customization",
                    data={**request.dict(exclude={'email'}), "stripePaymentIntentId": payment_intent.id}
                )

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {e}")
                response["stripeError"] = str(e)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving resume customization: {e}")
        raise HTTPException(status_code=500, detail="Failed to save resume customization")


@router.post("/cover-letter")
async def save_cover_letter(
    request: CoverLetterRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save cover letter generation preferences with optional Stripe payment"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Save onboarding progress
        await mongodb_service.save_onboarding_progress(
            email=email,
            step="cover-letter",
            data=request.dict(exclude={'email'})
        )

        response = {
            "success": True,
            "message": "Cover letter preferences saved",
            "email": email,
            "authenticated": current_user is not None
        }

        # Create Stripe payment if enabled and Stripe is configured
        if request.enabled and stripe_api_key:
            try:
                # Get or create Stripe customer
                user = await mongodb_service.get_user(email)
                customer_id = user.get("stripe_customer_id") if user else None

                if not customer_id:
                    customer = stripe.Customer.create(email=email, metadata={"user_email": email})
                    customer_id = customer.id
                    await mongodb_service.update_user_profile(email=email, profile_data={"stripe_customer_id": customer_id})

                # Create payment intent
                amount = ADDON_PRICES.get("cover-letter", 1200)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    customer=customer_id,
                    automatic_payment_methods={"enabled": True},
                    metadata={"user_email": email, "addon": "cover-letter"},
                    description="Cover Letter Generation Add-on"
                )

                response["paymentIntent"] = {
                    "clientSecret": payment_intent.client_secret,
                    "paymentIntentId": payment_intent.id,
                    "amount": amount / 100
                }

                # Save payment intent ID
                await mongodb_service.save_onboarding_progress(
                    email=email,
                    step="cover-letter",
                    data={**request.dict(exclude={'email'}), "stripePaymentIntentId": payment_intent.id}
                )

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {e}")
                response["stripeError"] = str(e)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving cover letter: {e}")
        raise HTTPException(status_code=500, detail="Failed to save cover letter preferences")


@router.post("/premium-upgrade")
async def save_premium_upgrade(
    request: PremiumUpgradeRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save premium upgrade selection with optional Stripe payment"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Save onboarding progress
        await mongodb_service.save_onboarding_progress(
            email=email,
            step="premium-upgrade",
            data=request.dict(exclude={'email'})
        )

        response = {
            "success": True,
            "message": "Premium upgrade saved",
            "email": email,
            "authenticated": current_user is not None
        }

        # Create Stripe payment if upgraded and Stripe is configured
        if request.upgraded and stripe_api_key:
            try:
                # Get or create Stripe customer
                user = await mongodb_service.get_user(email)
                customer_id = user.get("stripe_customer_id") if user else None

                if not customer_id:
                    customer = stripe.Customer.create(email=email, metadata={"user_email": email})
                    customer_id = customer.id
                    await mongodb_service.update_user_profile(email=email, profile_data={"stripe_customer_id": customer_id})

                # Create payment intent
                amount = ADDON_PRICES.get("premium-upgrade", 2900)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    customer=customer_id,
                    automatic_payment_methods={"enabled": True},
                    metadata={"user_email": email, "addon": "premium-upgrade"},
                    description="Premium Upgrade"
                )

                response["paymentIntent"] = {
                    "clientSecret": payment_intent.client_secret,
                    "paymentIntentId": payment_intent.id,
                    "amount": amount / 100
                }

                # Save payment intent ID
                await mongodb_service.save_onboarding_progress(
                    email=email,
                    step="premium-upgrade",
                    data={**request.dict(exclude={'email'}), "stripePaymentIntentId": payment_intent.id}
                )

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {e}")
                response["stripeError"] = str(e)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving premium upgrade: {e}")
        raise HTTPException(status_code=500, detail="Failed to save premium upgrade")


@router.post("/priority-access")
async def save_priority_access(
    request: PriorityAccessRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save priority access preferences with optional Stripe payment"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Save onboarding progress
        await mongodb_service.save_onboarding_progress(
            email=email,
            step="priority-access",
            data=request.dict(exclude={'email'})
        )

        response = {
            "success": True,
            "message": "Priority access preferences saved",
            "email": email,
            "authenticated": current_user is not None
        }

        # Create Stripe payment if enabled and Stripe is configured
        if request.enabled and stripe_api_key:
            try:
                # Get or create Stripe customer
                user = await mongodb_service.get_user(email)
                customer_id = user.get("stripe_customer_id") if user else None

                if not customer_id:
                    customer = stripe.Customer.create(email=email, metadata={"user_email": email})
                    customer_id = customer.id
                    await mongodb_service.update_user_profile(email=email, profile_data={"stripe_customer_id": customer_id})

                # Create payment intent
                amount = ADDON_PRICES.get("priority-access", 1200)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    customer=customer_id,
                    automatic_payment_methods={"enabled": True},
                    metadata={"user_email": email, "addon": "priority-access"},
                    description="Priority Job Access Add-on"
                )

                response["paymentIntent"] = {
                    "clientSecret": payment_intent.client_secret,
                    "paymentIntentId": payment_intent.id,
                    "amount": amount / 100
                }

                # Save payment intent ID
                await mongodb_service.save_onboarding_progress(
                    email=email,
                    step="priority-access",
                    data={**request.dict(exclude={'email'}), "stripePaymentIntentId": payment_intent.id}
                )

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {e}")
                response["stripeError"] = str(e)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving priority access: {e}")
        raise HTTPException(status_code=500, detail="Failed to save priority access")


@router.post("/create-password")
async def create_password(
    request: CreatePasswordRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Create user password"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Validate passwords match
        if request.password != request.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")

        # Hash password
        from app.core.security import get_password_hash
        password_hash = get_password_hash(request.password)

        # Update user with password
        success = await mongodb_service.update_user_profile(
            email=email,
            profile_data={
                "password_hash": password_hash,
                "password_created": True,
                "password_created_at": datetime.utcnow()
            }
        )

        # Save step progress
        await mongodb_service.save_onboarding_progress(
            email=email,
            step="create-password",
            data={
                "passwordCreated": True,
                "createdAt": datetime.utcnow().isoformat()
            }
        )

        return {
            "success": success,
            "message": "Password created successfully",
            "email": email,
            "authenticated": current_user is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating password: {e}")
        raise HTTPException(status_code=500, detail="Failed to create password")


@router.post("/upload-resume-data")
async def save_upload_resume_data(
    request: UploadResumeDataRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save resume upload data"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Update user profile with resume info
        await mongodb_service.update_user_profile(
            email=email,
            profile_data={
                "resume_uploaded": True,
                "resume_url": request.fileUrl,
                "resume_id": request.resumeId,
                "first_name": request.firstName,
                "last_name": request.lastName,
                "phone_number": request.phoneNumber,
                "ats_score": request.atsScore
            }
        )

        # Save step progress
        success = await mongodb_service.save_onboarding_progress(
            email=email,
            step="upload-resume",
            data=request.dict(exclude={'email'})
        )

        return {
            "success": success,
            "message": "Resume data saved",
            "email": email,
            "authenticated": current_user is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving resume data: {e}")
        raise HTTPException(status_code=500, detail="Failed to save resume data")


@router.post("/companies-to-exclude")
async def save_companies_to_exclude(
    request: CompaniesToExcludeRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Save companies to exclude"""
    try:
        email = current_user.get("email") if current_user else request.email
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        success = await mongodb_service.save_onboarding_progress(
            email=email,
            step="companies-to-exclude",
            data=request.dict(exclude={'email'})
        )

        return {
            "success": success,
            "message": "Excluded companies saved",
            "email": email,
            "authenticated": current_user is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving excluded companies: {e}")
        raise HTTPException(status_code=500, detail="Failed to save excluded companies")


@router.get("/progress")
async def get_upselling_progress(
    email: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get upselling progress"""
    try:
        user_email = current_user.get("email") if current_user else email
        if not user_email:
            raise HTTPException(status_code=400, detail="Email required")

        user = await mongodb_service.get_user(user_email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        onboarding_data = user.get("onboarding_data", {})
        completed_steps = [step for step in onboarding_data.keys() if onboarding_data.get(step)]

        total_steps = 8  # Total upselling steps
        current_step = len(completed_steps)
        percent_complete = (current_step / total_steps) * 100

        return {
            "currentStep": current_step,
            "totalSteps": total_steps,
            "completedSteps": completed_steps,
            "percentComplete": round(percent_complete, 2),
            "data": onboarding_data,
            "email": user_email,
            "authenticated": current_user is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to get progress")
