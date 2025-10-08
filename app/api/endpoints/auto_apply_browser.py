"""
Enhanced Auto-Apply API with Browser Automation
Integrates new auto-apply modules with existing endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import logging

from app.services.auto_apply.greenhouse_applicator import GreenhouseApplicator
from app.services.auto_apply.email_applicator import EmailApplicator
from app.services.email_forwarder.forwarder_service import EmailForwarderService
from app.core.security import get_current_user
from app.core.mongodb import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-apply", tags=["auto-apply-browser"])


class BrowserApplyRequest(BaseModel):
    """Request to apply via browser automation"""
    job_url: str
    job_id: str
    resume_path: Optional[str] = None
    cover_letter: Optional[str] = None
    custom_answers: Optional[Dict[str, str]] = None


class EmailApplyRequest(BaseModel):
    """Request to apply via email"""
    job_url: str
    job_id: str
    recipient_email: str


class ApplyResponse(BaseModel):
    """Response from application submission"""
    success: bool
    application_id: Optional[str] = None
    job_url: str
    ats_type: str
    status: str
    forwarding_email: Optional[str] = None
    confirmation_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    errors: List[str] = []
    screenshot_paths: List[str] = []


@router.post("/submit-browser", response_model=ApplyResponse)
async def submit_via_browser(
    request: BrowserApplyRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """
    Submit job application via browser automation

    Supports:
    - Greenhouse.io
    - Lever.co
    - Generic web forms
    """
    try:
        db = await get_database()
        user_id = current_user.get('id') or current_user.get('_id')

        # Get user profile data
        user_profile = await db.users.find_one({"_id": user_id})
        if not user_profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        # Prepare user data for form filling
        user_data = {
            'user_id': str(user_id),
            'job_id': request.job_id,
            'first_name': user_profile.get('first_name', ''),
            'last_name': user_profile.get('last_name', ''),
            'email': user_profile.get('email', ''),
            'phone': user_profile.get('phone', ''),
            'linkedin_url': user_profile.get('linkedin_url', ''),
            'portfolio_url': user_profile.get('portfolio_url', ''),
            'location': user_profile.get('location', ''),
            'job_title': request.job_id.split('_')[0] if '_' in request.job_id else 'Position',
            'company_name': 'Company',  # Extract from job data
            'cover_letter': request.cover_letter or '',
            'salary_expectation': user_profile.get('salary_expectation', ''),
            'work_authorized': 'Yes',
            'availability': '2 weeks',
            'experience_years': user_profile.get('years_experience', 3),
        }

        # Determine which applicator to use based on URL
        applicator = None
        if 'greenhouse' in request.job_url.lower():
            applicator = GreenhouseApplicator(config={
                'email_forwarding_enabled': True,
                'forwarding_email_domain': 'apply.applyrush.ai',
                'headless': True
            })
        else:
            # Try email applicator first for generic jobs
            applicator = EmailApplicator(config={
                'email_forwarding_enabled': True
            })

        # Get resume path
        resume_path = request.resume_path or user_profile.get('resume_path', '/tmp/resume.pdf')

        # Apply to job
        result = await applicator.apply(
            job_url=request.job_url,
            user_data=user_data,
            resume_path=resume_path
        )

        # Save application to database
        application_doc = {
            'user_id': str(user_id),
            'job_id': request.job_id,
            'job_url': request.job_url,
            'application_method': 'browser_automation',
            'ats_type': result.ats_type.value,
            'status': result.status.value,
            'forwarding_email': result.confirmation_email,
            'confirmation_number': result.confirmation_number,
            'submitted_at': result.submitted_at,
            'screenshot_paths': result.screenshot_paths,
            'steps_completed': result.steps_completed,
            'errors': result.errors,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        insert_result = await db.auto_apply_applications.insert_one(application_doc)
        application_id = str(insert_result.inserted_id)

        # Also save forwarding email configuration
        if result.confirmation_email:
            email_forwarder = EmailForwarderService()
            forwarding_config = email_forwarder.generate_forwarding_email(
                user_id=str(user_id),
                job_id=request.job_id,
                real_email=user_data['email'],
                application_id=application_id
            )

            await db.forwarding_emails.insert_one(forwarding_config.to_dict())

        return ApplyResponse(
            success=result.success,
            application_id=application_id,
            job_url=request.job_url,
            ats_type=result.ats_type.value,
            status=result.status.value,
            forwarding_email=result.confirmation_email,
            confirmation_number=result.confirmation_number,
            submitted_at=result.submitted_at,
            errors=result.errors,
            screenshot_paths=result.screenshot_paths
        )

    except Exception as e:
        logger.error(f"Browser apply error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Application failed: {str(e)}")


@router.post("/submit-email", response_model=ApplyResponse)
async def submit_via_email(
    request: EmailApplyRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Submit job application via email

    For jobs with "Apply via Email" functionality
    """
    try:
        # Implementation similar to submit_via_browser but using EmailApplicator
        pass
    except Exception as e:
        logger.error(f"Email apply error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Email application failed: {str(e)}")


@router.get("/applications")
async def get_auto_applications(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: Dict = Depends(get_current_user)
):
    """Get auto-applied applications for user"""
    try:
        db = await get_database()

        query = {"user_id": user_id or str(current_user.get('id') or current_user.get('_id'))}
        if status:
            query['status'] = status

        applications = await db.auto_apply_applications.find(query).limit(limit).to_list(length=limit)

        return {
            "applications": applications,
            "total": len(applications)
        }

    except Exception as e:
        logger.error(f"Get applications error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_auto_apply_stats(
    current_user: Dict = Depends(get_current_user)
):
    """Get auto-apply statistics for user"""
    try:
        db = await get_database()
        user_id = str(current_user.get('id') or current_user.get('_id'))

        # Count applications by status
        total = await db.auto_apply_applications.count_documents({"user_id": user_id})
        success = await db.auto_apply_applications.count_documents({
            "user_id": user_id,
            "status": "success"
        })
        pending = await db.auto_apply_applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        failed = await db.auto_apply_applications.count_documents({
            "user_id": user_id,
            "status": {"$in": ["failed", "error"]}
        })

        # Get this week's count
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        this_week = await db.auto_apply_applications.count_documents({
            "user_id": user_id,
            "submitted_at": {"$gte": week_ago}
        })

        return {
            "total_applications": total,
            "successful": success,
            "pending": pending,
            "failed": failed,
            "this_week": this_week,
            "success_rate": (success / total * 100) if total > 0 else 0
        }

    except Exception as e:
        logger.error(f"Get stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/email-received")
async def process_incoming_email(email_data: Dict[str, Any]):
    """
    Webhook endpoint for incoming emails

    Called by AWS SES or email server when email is received
    """
    try:
        email_forwarder = EmailForwarderService()

        result = await email_forwarder.process_incoming_email(
            forwarding_address=email_data.get('to'),
            from_address=email_data.get('from'),
            subject=email_data.get('subject'),
            body=email_data.get('body'),
            html_body=email_data.get('html_body')
        )

        return result

    except Exception as e:
        logger.error(f"Email webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
