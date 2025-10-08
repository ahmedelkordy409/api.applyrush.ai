"""
Comprehensive Upselling API Endpoints for ApplyRush.AI
Each endpoint serves the full functionality of its corresponding page
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json

router = APIRouter(prefix="/api/upselling", tags=["Upselling"])


# ==================== PYDANTIC MODELS ====================

class PlanSelection(BaseModel):
    """Pricing page - Plan selection"""
    user_id: str
    plan_type: str = Field(..., description="free, basic, premium, enterprise")
    billing_cycle: str = Field(..., description="monthly or yearly")
    email: EmailStr
    payment_method: Optional[str] = None

class PlanResponse(BaseModel):
    """Response with plan details and features"""
    success: bool
    plan_type: str
    price: float
    features: List[str]
    limits: Dict[str, Any]
    trial_days: Optional[int]
    stripe_session_id: Optional[str] = None


class ResumeCustomizationRequest(BaseModel):
    """Resume customization addon purchase"""
    user_id: str
    email: EmailStr
    enable_customization: bool
    target_keywords: Optional[List[str]] = None

class ResumeCustomizationResponse(BaseModel):
    """Response with customization status and AI capabilities"""
    success: bool
    addon_enabled: bool
    estimated_improvement: str
    sample_keywords: List[str]
    ats_score_boost: int


class CoverLetterAddonRequest(BaseModel):
    """Cover letter addon purchase"""
    user_id: str
    email: EmailStr
    enable_cover_letter: bool
    writing_style: Optional[str] = "professional"

class CoverLetterAddonResponse(BaseModel):
    """Response with cover letter addon status"""
    success: bool
    addon_enabled: bool
    writing_styles: List[str]
    sample_template: Optional[str] = None
    generation_count_limit: int


class PremiumUpgradeRequest(BaseModel):
    """Premium upgrade request"""
    user_id: str
    email: EmailStr
    upgrade_to: str = "premium"
    features_selected: List[str]

class PremiumUpgradeResponse(BaseModel):
    """Response with premium features unlocked"""
    success: bool
    upgraded_to: str
    features_unlocked: List[Dict[str, Any]]
    daily_application_limit: int
    ai_model: str
    priority_support: bool


class PriorityAccessRequest(BaseModel):
    """Priority access addon"""
    user_id: str
    email: EmailStr
    enable_priority: bool

class PriorityAccessResponse(BaseModel):
    """Response with priority access details"""
    success: bool
    priority_enabled: bool
    notification_channels: List[str]
    average_time_advantage: str
    alert_frequency: str


class CreatePasswordRequest(BaseModel):
    """Create password after signup"""
    email: EmailStr
    temp_password: str
    new_password: str
    confirm_password: str

class CreatePasswordResponse(BaseModel):
    """Response after password creation"""
    success: bool
    user_id: str
    token: str
    profile_complete: bool


class UploadResumeRequest(BaseModel):
    """Resume upload metadata"""
    user_id: str
    email: EmailStr
    first_name: str
    last_name: str
    phone_number: str

class UploadResumeResponse(BaseModel):
    """Response after resume upload with AI analysis"""
    success: bool
    resume_id: str
    file_url: str
    analysis: Dict[str, Any]
    ats_score: int
    suggestions: List[str]
    extracted_skills: List[str]


class CompaniesToExcludeRequest(BaseModel):
    """Companies exclusion list"""
    user_id: str
    email: EmailStr
    excluded_companies: List[str]
    excluded_categories: Optional[List[str]] = None

class CompaniesToExcludeResponse(BaseModel):
    """Response with exclusion list saved"""
    success: bool
    total_excluded: int
    company_names: List[str]
    estimated_jobs_filtered: int


# ==================== 1. PRICING PAGE ENDPOINTS ====================

@router.post("/pricing/select-plan", response_model=PlanResponse)
async def select_pricing_plan(request: PlanSelection):
    """
    Handle plan selection from pricing page
    - Create/update user subscription
    - Calculate pricing based on billing cycle
    - Generate Stripe checkout session
    - Record plan selection in database
    """
    try:
        # Plan pricing structure
        pricing = {
            "free": {"monthly": 0, "yearly": 0},
            "basic": {"monthly": 20, "yearly": 200},
            "premium": {"monthly": 50, "yearly": 500},
            "enterprise": {"monthly": 99, "yearly": 990}
        }

        price = pricing.get(request.plan_type, {}).get(request.billing_cycle, 0)

        # Plan features
        features_map = {
            "free": [
                "20 job applications per day",
                "Basic job search",
                "Email notifications",
                "Standard AI model"
            ],
            "basic": [
                "40 job applications per day",
                "Advanced job search",
                "Priority email notifications",
                "GPT-4 Mini AI model",
                "Basic analytics"
            ],
            "premium": [
                "60 job applications per day",
                "AI-powered job matching",
                "Real-time notifications",
                "GPT-4.1 Mini AI model",
                "Advanced analytics",
                "Priority support",
                "Resume customization"
            ],
            "enterprise": [
                "Unlimited job applications",
                "Dedicated AI agent",
                "Multi-channel notifications",
                "Premium AI models",
                "Enterprise analytics",
                "24/7 Priority support",
                "All premium features",
                "API access"
            ]
        }

        # Application limits
        limits = {
            "free": {"daily_applications": 20, "ai_calls": 100},
            "basic": {"daily_applications": 40, "ai_calls": 500},
            "premium": {"daily_applications": 60, "ai_calls": 2000},
            "enterprise": {"daily_applications": -1, "ai_calls": -1}  # unlimited
        }

        # TODO: Save to database
        # db.save_user_subscription(request.user_id, request.plan_type, request.billing_cycle)

        # TODO: Generate Stripe session for payment
        stripe_session_id = None
        if price > 0:
            stripe_session_id = f"stripe_session_{uuid.uuid4().hex[:16]}"

        return PlanResponse(
            success=True,
            plan_type=request.plan_type,
            price=price,
            features=features_map.get(request.plan_type, []),
            limits=limits.get(request.plan_type, {}),
            trial_days=7 if request.plan_type in ["premium", "enterprise"] else None,
            stripe_session_id=stripe_session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process plan selection: {str(e)}")


@router.get("/pricing/plans")
async def get_all_plans():
    """
    Get all available pricing plans with features and pricing
    """
    plans = {
        "free": {
            "name": "Free",
            "price_monthly": 0,
            "price_yearly": 0,
            "features": [
                "20 job applications per day",
                "Basic job search",
                "Email notifications"
            ],
            "limits": {"daily_applications": 20}
        },
        "basic": {
            "name": "Basic",
            "price_monthly": 20,
            "price_yearly": 200,
            "features": [
                "40 job applications per day",
                "Advanced job search",
                "GPT-4 Mini AI"
            ],
            "limits": {"daily_applications": 40},
            "savings_yearly": 40
        },
        "premium": {
            "name": "Premium",
            "price_monthly": 50,
            "price_yearly": 500,
            "features": [
                "60 job applications per day",
                "AI-powered matching",
                "Priority support",
                "Resume customization"
            ],
            "limits": {"daily_applications": 60},
            "savings_yearly": 100,
            "recommended": True
        },
        "enterprise": {
            "name": "Enterprise",
            "price_monthly": 99,
            "price_yearly": 990,
            "features": [
                "Unlimited applications",
                "Dedicated AI agent",
                "24/7 support",
                "API access"
            ],
            "limits": {"daily_applications": -1},
            "savings_yearly": 198
        }
    }

    return {"success": True, "plans": plans}


# ==================== 2. RESUME CUSTOMIZATION ENDPOINTS ====================

@router.post("/resume-customization/enable", response_model=ResumeCustomizationResponse)
async def enable_resume_customization(request: ResumeCustomizationRequest):
    """
    Enable AI-powered resume customization addon
    - Activate ATS keyword optimization
    - Enable auto-tailoring for each job
    - Provide sample keywords and improvements
    """
    try:
        # Sample keywords based on common job requirements
        sample_keywords = [
            "Agile methodology", "REST APIs", "GraphQL",
            "Docker", "AWS", "TypeScript", "Redux",
            "CI/CD", "Microservices", "Scrum"
        ]

        # TODO: Save addon to database
        # db.enable_addon(request.user_id, "resume_customization", True)

        # TODO: Activate AI customization in job processing pipeline
        # ai_service.activate_resume_customization(request.user_id)

        return ResumeCustomizationResponse(
            success=True,
            addon_enabled=request.enable_customization,
            estimated_improvement="+44% more interview invitations",
            sample_keywords=sample_keywords,
            ats_score_boost=35
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable resume customization: {str(e)}")


@router.post("/resume-customization/analyze")
async def analyze_resume_for_job(
    user_id: str = Body(...),
    job_description: str = Body(...),
    current_resume_text: str = Body(...)
):
    """
    Analyze resume against specific job description
    - Extract key requirements from job description
    - Identify missing keywords in resume
    - Suggest improvements for ATS optimization
    """
    try:
        # TODO: Use AI to analyze job description and resume
        # ai_analysis = ai_client.analyze_resume_job_match(job_description, current_resume_text)

        missing_keywords = [
            "React", "Node.js", "MongoDB",
            "Team leadership", "Agile"
        ]

        suggestions = [
            "Add 'React' with specific version (e.g., React 18.2) in skills section",
            "Quantify achievements with metrics (e.g., 'Improved performance by 40%')",
            "Include 'Agile methodology' in project descriptions",
            "Add relevant certifications if available"
        ]

        return {
            "success": True,
            "match_score": 72,
            "missing_keywords": missing_keywords,
            "suggestions": suggestions,
            "optimized_sections": ["skills", "experience", "summary"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume analysis failed: {str(e)}")


# ==================== 3. COVER LETTER ADDON ENDPOINTS ====================

@router.post("/cover-letter/enable", response_model=CoverLetterAddonResponse)
async def enable_cover_letter_addon(request: CoverLetterAddonRequest):
    """
    Enable AI-powered cover letter generation
    - Activate auto-generation for each application
    - Set writing style preference
    - Provide sample template
    """
    try:
        writing_styles = ["professional", "creative", "technical", "executive"]

        sample_template = """Dear Hiring Manager,

I am excited to apply for the [POSITION] role at [COMPANY]. With my [YEARS] years of experience in [FIELD], I am confident I can contribute to your team's success.

Your recent work on [COMPANY_PROJECT] aligns perfectly with my background in [RELEVANT_SKILL]. At my previous role, I [ACHIEVEMENT].

I am particularly drawn to [COMPANY]'s commitment to [COMPANY_VALUE] and would love to discuss how my expertise can help achieve your goals.

Best regards,
[YOUR_NAME]"""

        # TODO: Save addon preference
        # db.enable_addon(request.user_id, "cover_letter", True)
        # db.set_user_preference(request.user_id, "writing_style", request.writing_style)

        return CoverLetterAddonResponse(
            success=True,
            addon_enabled=request.enable_cover_letter,
            writing_styles=writing_styles,
            sample_template=sample_template if request.enable_cover_letter else None,
            generation_count_limit=100  # per month
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable cover letter addon: {str(e)}")


@router.post("/cover-letter/generate")
async def generate_cover_letter(
    user_id: str = Body(...),
    job_title: str = Body(...),
    company_name: str = Body(...),
    job_description: str = Body(...),
    user_experience: Optional[str] = Body(None)
):
    """
    Generate AI-powered cover letter for specific job
    - Analyze job requirements
    - Match user's experience
    - Generate personalized cover letter
    """
    try:
        # TODO: Use AI to generate cover letter
        # cover_letter = ai_client.generate_cover_letter(
        #     job_title, company_name, job_description, user_experience
        # )

        cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company_name}. With my proven track record in the field, I am confident that I would be a valuable addition to your team.

Based on the job description, I understand you're looking for someone with expertise in the key technologies and methodologies your team uses. My experience aligns well with these requirements, and I'm particularly excited about the opportunity to contribute to {company_name}'s innovative projects.

I would welcome the opportunity to discuss how my skills and experience can contribute to your team's success. Thank you for considering my application.

Best regards,
[Your Name]"""

        return {
            "success": True,
            "cover_letter": cover_letter,
            "word_count": len(cover_letter.split()),
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {str(e)}")


# ==================== 4. PREMIUM UPGRADE ENDPOINTS ====================

@router.post("/premium/upgrade", response_model=PremiumUpgradeResponse)
async def upgrade_to_premium(request: PremiumUpgradeRequest):
    """
    Upgrade user to premium plan
    - Unlock all premium features
    - Increase application limits
    - Enable advanced AI models
    - Activate priority support
    """
    try:
        features_unlocked = [
            {
                "feature": "GPT-4.1 Mini Integration",
                "description": "Advanced AI for better job matching",
                "icon": "zap"
            },
            {
                "feature": "60 Jobs Per Day",
                "description": "Triple your daily application limit",
                "icon": "briefcase"
            },
            {
                "feature": "Priority Support",
                "description": "Get help faster with dedicated support",
                "icon": "headphones"
            },
            {
                "feature": "Advanced Analytics",
                "description": "Detailed insights into your applications",
                "icon": "trending-up"
            }
        ]

        # TODO: Upgrade user in database
        # db.upgrade_user_subscription(request.user_id, "premium")
        # db.update_user_limits(request.user_id, daily_applications=60)

        # TODO: Enable premium features in AI agent
        # ai_agent.upgrade_user_model(request.user_id, "gpt-4.1-mini")

        return PremiumUpgradeResponse(
            success=True,
            upgraded_to=request.upgrade_to,
            features_unlocked=features_unlocked,
            daily_application_limit=60,
            ai_model="gpt-4.1-mini",
            priority_support=True
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Premium upgrade failed: {str(e)}")


@router.get("/premium/features")
async def get_premium_features():
    """
    Get detailed list of premium features and benefits
    """
    features = {
        "ai_model": {
            "name": "GPT-4.1 Mini",
            "benefits": [
                "Better job matching accuracy",
                "More natural cover letters",
                "Smarter resume optimization"
            ]
        },
        "application_limit": {
            "free": 20,
            "premium": 60,
            "increase": "3x"
        },
        "support": {
            "free": "Email support (48h response)",
            "premium": "Priority support (4h response)"
        },
        "analytics": {
            "features": [
                "Application success rate tracking",
                "Interview conversion rates",
                "Response time analytics",
                "Industry insights"
            ]
        }
    }

    return {"success": True, "features": features}


# ==================== 5. PRIORITY ACCESS ENDPOINTS ====================

@router.post("/priority-access/enable", response_model=PriorityAccessResponse)
async def enable_priority_access(request: PriorityAccessRequest):
    """
    Enable priority access to new job postings
    - Set up instant notifications
    - Configure alert channels (email, SMS, push)
    - Get first access to new jobs
    """
    try:
        notification_channels = ["email", "push", "sms"]

        # TODO: Enable priority queue for user
        # job_queue.enable_priority_access(request.user_id)
        # notification_service.configure_channels(request.user_id, channels)

        return PriorityAccessResponse(
            success=True,
            priority_enabled=request.enable_priority,
            notification_channels=notification_channels,
            average_time_advantage="Within first hour of posting",
            alert_frequency="Real-time (instant)"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable priority access: {str(e)}")


@router.post("/priority-access/configure-notifications")
async def configure_priority_notifications(
    user_id: str = Body(...),
    channels: List[str] = Body(...),
    job_criteria: Optional[Dict[str, Any]] = Body(None)
):
    """
    Configure notification preferences for priority access
    - Set preferred notification channels
    - Define job criteria for alerts
    - Set notification frequency
    """
    try:
        # TODO: Save notification preferences
        # db.save_notification_preferences(user_id, channels, job_criteria)

        return {
            "success": True,
            "channels_enabled": channels,
            "criteria_set": bool(job_criteria),
            "estimated_alerts_per_day": 15
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure notifications: {str(e)}")


# ==================== 6. CREATE PASSWORD ENDPOINTS ====================

@router.post("/password/create", response_model=CreatePasswordResponse)
async def create_user_password(request: CreatePasswordRequest):
    """
    Create permanent password after signup
    - Verify temp password
    - Validate new password strength
    - Update user authentication
    - Generate auth token
    """
    try:
        # Validate password match
        if request.new_password != request.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")

        # Password strength validation
        if len(request.new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        # TODO: Verify temp password from database
        # user = db.verify_temp_password(request.email, request.temp_password)
        # if not user:
        #     raise HTTPException(status_code=401, detail="Invalid temporary password")

        # TODO: Update user password
        # db.update_user_password(user.id, request.new_password)

        # TODO: Generate auth token
        token = f"jwt_token_{uuid.uuid4().hex}"
        user_id = f"user_{uuid.uuid4().hex[:12]}"

        return CreatePasswordResponse(
            success=True,
            user_id=user_id,
            token=token,
            profile_complete=True
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password creation failed: {str(e)}")


@router.post("/password/validate")
async def validate_password_strength(password: str = Body(..., embed=True)):
    """
    Validate password strength and return requirements met
    """
    requirements = {
        "length": len(password) >= 8,
        "uppercase": any(c.isupper() for c in password),
        "lowercase": any(c.islower() for c in password),
        "number": any(c.isdigit() for c in password),
        "special": any(c in "!@#$%^&*(),.?\":{}|<>" for c in password)
    }

    strength_score = sum(requirements.values())
    strength = "weak"
    if strength_score >= 4:
        strength = "medium"
    if strength_score == 5:
        strength = "strong"

    return {
        "success": True,
        "strength": strength,
        "requirements_met": requirements,
        "score": strength_score
    }


# ==================== 7. UPLOAD RESUME ENDPOINTS ====================

@router.post("/resume/upload", response_model=UploadResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    email: EmailStr = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone_number: str = Form(...)
):
    """
    Upload and process user resume
    - Save resume file
    - Extract text content
    - Parse skills and experience
    - Calculate ATS score
    - Provide optimization suggestions
    """
    try:
        # Validate file type
        allowed_extensions = [".pdf", ".doc", ".docx", ".txt"]
        file_ext = file.filename.split(".")[-1].lower()
        if f".{file_ext}" not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Validate file size (10MB max)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")

        # TODO: Save file to storage
        resume_id = f"resume_{uuid.uuid4().hex[:16]}"
        # file_url = storage.save_file(content, file.filename, user_id)
        file_url = f"https://storage.applyrush.ai/resumes/{resume_id}.pdf"

        # TODO: Parse resume with AI
        # resume_data = ai_client.parse_resume(content)

        # Mock AI analysis
        analysis = {
            "total_experience_years": 5,
            "job_titles": ["Senior Software Engineer", "Software Developer"],
            "companies": ["Tech Corp", "StartupXYZ"],
            "education": ["B.S. Computer Science"],
            "certifications": ["AWS Certified Developer"]
        }

        extracted_skills = [
            "Python", "JavaScript", "React", "Node.js",
            "AWS", "Docker", "PostgreSQL", "Git"
        ]

        suggestions = [
            "Add more quantifiable achievements (e.g., 'Increased performance by 40%')",
            "Include keywords from target job descriptions",
            "Add a professional summary at the top",
            "List technical skills in a dedicated section"
        ]

        # TODO: Save resume data to database
        # db.save_resume(user_id, resume_id, file_url, analysis)
        # db.update_user_profile(user_id, first_name, last_name, phone_number)

        return UploadResumeResponse(
            success=True,
            resume_id=resume_id,
            file_url=file_url,
            analysis=analysis,
            ats_score=78,
            suggestions=suggestions,
            extracted_skills=extracted_skills
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume upload failed: {str(e)}")


@router.get("/resume/{resume_id}")
async def get_resume_details(resume_id: str):
    """
    Get resume details and analysis
    """
    # TODO: Fetch from database
    # resume = db.get_resume(resume_id)

    return {
        "success": True,
        "resume_id": resume_id,
        "file_url": f"https://storage.applyrush.ai/resumes/{resume_id}.pdf",
        "uploaded_at": datetime.utcnow().isoformat(),
        "ats_score": 78,
        "status": "processed"
    }


@router.post("/resume/reanalyze/{resume_id}")
async def reanalyze_resume(resume_id: str):
    """
    Re-run AI analysis on existing resume
    - Useful after resume updates
    - Recalculate ATS score
    - Update suggestions
    """
    try:
        # TODO: Fetch resume and reanalyze
        # resume = db.get_resume(resume_id)
        # analysis = ai_client.analyze_resume(resume.content)

        return {
            "success": True,
            "resume_id": resume_id,
            "ats_score": 82,
            "improvements": [
                "ATS score improved by 4 points",
                "Added 3 new relevant keywords",
                "Better formatting detected"
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume reanalysis failed: {str(e)}")


# ==================== 8. COMPANIES TO EXCLUDE ENDPOINTS ====================

@router.post("/exclusions/save", response_model=CompaniesToExcludeResponse)
async def save_company_exclusions(request: CompaniesToExcludeRequest):
    """
    Save user's company exclusion list
    - Save excluded companies
    - Process exclusion categories
    - Update job filtering rules
    - Estimate jobs filtered
    """
    try:
        # Category to companies mapping
        category_companies = {
            "consulting": ["Accenture", "Deloitte", "McKinsey", "BCG"],
            "bigtech": ["Google", "Meta", "Amazon", "Apple", "Microsoft"],
            "banks": ["JPMorgan", "Goldman Sachs", "Morgan Stanley", "Citi"],
            "startups": [],  # Dynamic based on company size
            "government": [],  # Gov agencies
            "nonprofits": []
        }

        # Expand categories to company names
        all_excluded = list(request.excluded_companies)
        if request.excluded_categories:
            for category in request.excluded_categories:
                all_excluded.extend(category_companies.get(category, []))

        # Remove duplicates
        all_excluded = list(set(all_excluded))

        # TODO: Save exclusions to database
        # db.save_user_exclusions(request.user_id, all_excluded)
        # job_filter.update_exclusion_rules(request.user_id, all_excluded)

        # Estimate filtered jobs (rough calculation)
        avg_jobs_per_company = 5
        estimated_filtered = len(all_excluded) * avg_jobs_per_company

        return CompaniesToExcludeResponse(
            success=True,
            total_excluded=len(all_excluded),
            company_names=all_excluded[:10],  # Return first 10
            estimated_jobs_filtered=estimated_filtered
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save exclusions: {str(e)}")


@router.get("/exclusions/{user_id}")
async def get_user_exclusions(user_id: str):
    """
    Get user's current exclusion list
    """
    # TODO: Fetch from database
    # exclusions = db.get_user_exclusions(user_id)

    return {
        "success": True,
        "excluded_companies": [
            "Meta", "Amazon", "Uber", "Tesla", "Salesforce"
        ],
        "excluded_categories": ["bigtech"],
        "total_excluded": 5
    }


@router.delete("/exclusions/{user_id}/company/{company_name}")
async def remove_company_exclusion(user_id: str, company_name: str):
    """
    Remove a specific company from exclusion list
    """
    try:
        # TODO: Remove from database
        # db.remove_exclusion(user_id, company_name)

        return {
            "success": True,
            "message": f"Removed {company_name} from exclusion list",
            "remaining_exclusions": 4
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove exclusion: {str(e)}")


@router.get("/exclusions/categories")
async def get_exclusion_categories():
    """
    Get available exclusion categories with descriptions
    """
    categories = [
        {
            "id": "consulting",
            "label": "Consulting firms",
            "description": "Management and technology consulting companies",
            "example_companies": ["Accenture", "Deloitte", "McKinsey"]
        },
        {
            "id": "bigtech",
            "label": "Big Tech",
            "description": "Large technology companies",
            "example_companies": ["Google", "Meta", "Amazon"]
        },
        {
            "id": "banks",
            "label": "Banks",
            "description": "Financial institutions and investment banks",
            "example_companies": ["JPMorgan", "Goldman Sachs"]
        },
        {
            "id": "startups",
            "label": "Startups",
            "description": "Early-stage companies (< 50 employees)",
            "example_companies": ["Various startups"]
        },
        {
            "id": "government",
            "label": "Government",
            "description": "Government agencies and public sector",
            "example_companies": ["Federal agencies"]
        },
        {
            "id": "nonprofits",
            "label": "Non-profits",
            "description": "Non-profit organizations",
            "example_companies": ["Various NGOs"]
        }
    ]

    return {"success": True, "categories": categories}


# ==================== UTILITY ENDPOINTS ====================

@router.get("/user/{user_id}/upselling-progress")
async def get_upselling_progress(user_id: str):
    """
    Get user's progress through upselling flow
    """
    # TODO: Fetch from database
    # progress = db.get_upselling_progress(user_id)

    return {
        "success": True,
        "user_id": user_id,
        "steps_completed": [
            "pricing",
            "resume-customization",
            "cover-letter"
        ],
        "current_step": "premium-upgrade",
        "total_steps": 8,
        "completion_percentage": 37.5,
        "addons_purchased": ["resume_customization", "cover_letter"],
        "plan_selected": "premium"
    }


@router.post("/user/{user_id}/complete-upselling")
async def complete_upselling_flow(user_id: str):
    """
    Mark upselling flow as complete and redirect to dashboard
    """
    try:
        # TODO: Update database
        # db.mark_upselling_complete(user_id)
        # db.activate_all_features(user_id)

        return {
            "success": True,
            "message": "Upselling completed successfully",
            "redirect_to": "/dashboard",
            "features_enabled": [
                "job_search",
                "auto_apply",
                "resume_customization",
                "cover_letter_generation"
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete upselling: {str(e)}")