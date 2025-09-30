"""
Onboarding API endpoints for guest sessions and progressive data collection
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import string

from app.models.onboarding_models import (
    GuestProfile,
    OnboardingAnswer,
    OnboardingStatus,
    OnboardingConversion,
    CreateGuestSessionRequest,
    CreateGuestSessionResponse,
    SaveAnswerRequest,
    SaveAnswerResponse,
    ConvertGuestRequest,
    ConvertGuestResponse
)
from app.models.mongodb_models import User
from app.core.config import settings
from app.core.security import hash_password

router = APIRouter()


@router.post("/guest/create", response_model=CreateGuestSessionResponse)
async def create_guest_session(request: CreateGuestSessionRequest):
    """
    Create a new guest session for anonymous onboarding
    """
    try:
        # Generate unique session ID
        session_id = GuestProfile.generate_session_id()

        # Create guest profile
        guest_profile = GuestProfile(
            session_id=session_id,
            answers={
                "referrer": request.referrer,
                "utm_source": request.utm_source,
                "utm_medium": request.utm_medium,
                "utm_campaign": request.utm_campaign
            } if any([request.referrer, request.utm_source]) else {}
        )

        # Save to database
        await guest_profile.save()

        return CreateGuestSessionResponse(
            session_id=session_id,
            created_at=guest_profile.created_at,
            expires_at=guest_profile.expires_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create guest session: {str(e)}"
        )


@router.get("/guest/{session_id}")
async def get_guest_session(session_id: str):
    """
    Get guest session details and progress
    """
    guest_profile = await GuestProfile.find_one(GuestProfile.session_id == session_id)

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    # Check if session expired
    if guest_profile.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Guest session has expired"
        )

    return {
        "session_id": guest_profile.session_id,
        "status": guest_profile.status,
        "current_step": guest_profile.current_step,
        "completed_steps": guest_profile.completed_steps,
        "answers": guest_profile.answers,
        "created_at": guest_profile.created_at,
        "expires_at": guest_profile.expires_at
    }


@router.post("/guest/answer", response_model=SaveAnswerResponse)
async def save_guest_answer(request: SaveAnswerRequest):
    """
    Save an answer for a specific onboarding step
    """
    # Find guest profile
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == request.session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    # Check if session expired
    if guest_profile.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Guest session has expired"
        )

    try:
        # Update guest profile with new answer
        guest_profile.update_answer(request.step_id, request.answer)

        # Update time spent if provided
        if request.time_spent_seconds:
            guest_profile.time_spent_seconds += request.time_spent_seconds

        # Check if this is the email step
        if request.step_id == "email-collection" and "email" in request.answer:
            guest_profile.email = request.answer["email"]
            guest_profile.status = OnboardingStatus.EMAIL_PROVIDED

        # Save updated profile
        await guest_profile.save()

        # Also save as individual answer for analytics
        answer_doc = OnboardingAnswer(
            guest_session_id=request.session_id,
            step_id=request.step_id,
            question_type="onboarding",
            answer=request.answer,
            time_to_answer_seconds=request.time_spent_seconds
        )
        await answer_doc.save()

        return SaveAnswerResponse(
            success=True,
            session_id=request.session_id,
            step_id=request.step_id,
            completed_steps=guest_profile.completed_steps,
            current_step=len(guest_profile.completed_steps)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save answer: {str(e)}"
        )


@router.post("/guest/convert", response_model=ConvertGuestResponse)
async def convert_guest_to_user(request: ConvertGuestRequest):
    """
    Convert a guest session to a registered user account
    """
    # Find guest profile
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == request.session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    # Check if already converted
    if guest_profile.status == OnboardingStatus.CONVERTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guest session already converted"
        )

    try:
        # Check if user already exists
        existing_user = await User.find_one(User.email == request.email)

        if existing_user:
            # Link existing user to guest profile
            user = existing_user
        else:
            # Generate temporary password if requested
            temp_password = None
            if request.generate_temp_password and not request.password:
                temp_password = generate_temp_password()
                password_hash = hash_password(temp_password)
            elif request.password:
                password_hash = hash_password(request.password)
            else:
                password_hash = None

            # Create new user from guest data
            user_data = transform_guest_data_to_user(guest_profile.answers)
            user_data["email"] = request.email

            # Create user
            user = User(**user_data)
            await user.save()

        # Transfer all answers to user
        answers_count = await transfer_answers_to_user(
            guest_profile.session_id,
            user.id
        )

        # Update guest profile
        guest_profile.status = OnboardingStatus.CONVERTED
        guest_profile.converted_user_id = user.id
        guest_profile.converted_at = datetime.utcnow()
        guest_profile.email = request.email
        await guest_profile.save()

        # Create conversion record
        conversion = OnboardingConversion(
            guest_session_id=guest_profile.session_id,
            user_id=user.id,
            email=request.email,
            temporary_password=temp_password,
            session_started_at=guest_profile.created_at,
            email_provided_at=datetime.utcnow(),
            total_duration_seconds=int(
                (datetime.utcnow() - guest_profile.created_at).total_seconds()
            ),
            answers_transferred=answers_count,
            data_migrated=True
        )
        await conversion.save()

        return ConvertGuestResponse(
            success=True,
            user_id=str(user.id),
            email=request.email,
            temporary_password=temp_password,
            answers_transferred=answers_count
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert guest to user: {str(e)}"
        )


@router.post("/guest/{session_id}/complete")
async def complete_guest_onboarding(session_id: str):
    """
    Mark guest onboarding as complete
    """
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    try:
        guest_profile.status = OnboardingStatus.COMPLETED
        guest_profile.updated_at = datetime.utcnow()
        await guest_profile.save()

        return {
            "success": True,
            "session_id": session_id,
            "status": guest_profile.status,
            "completed_steps": guest_profile.completed_steps
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete onboarding: {str(e)}"
        )


@router.delete("/guest/{session_id}")
async def delete_guest_session(session_id: str):
    """
    Delete a guest session and all associated data
    """
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    try:
        # Delete all answers
        await OnboardingAnswer.find(
            OnboardingAnswer.guest_session_id == session_id
        ).delete()

        # Delete guest profile
        await guest_profile.delete()

        return {
            "success": True,
            "message": f"Guest session {session_id} deleted"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.get("/guest/{session_id}/progress")
async def get_guest_progress(session_id: str):
    """
    Get detailed progress for a guest session
    """
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    # Get all answers
    answers = await OnboardingAnswer.find(
        OnboardingAnswer.guest_session_id == session_id
    ).to_list()

    return {
        "session_id": session_id,
        "status": guest_profile.status,
        "current_step": guest_profile.current_step,
        "total_steps_completed": len(guest_profile.completed_steps),
        "completed_steps": guest_profile.completed_steps,
        "time_spent_seconds": guest_profile.time_spent_seconds,
        "last_activity": guest_profile.last_activity,
        "answers_count": len(answers),
        "has_email": guest_profile.email is not None
    }


@router.get("/guest/{session_id}/question/{question_id}")
async def get_question_answer(session_id: str, question_id: str):
    """
    Get the answer for a specific question
    """
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    # Get the answer for this question
    answer = guest_profile.answers.get(question_id)

    return {
        "session_id": session_id,
        "question_id": question_id,
        "answer": answer,
        "is_completed": question_id in guest_profile.completed_steps,
        "answered_at": answer.get('timestamp') if answer else None
    }


@router.post("/guest/{session_id}/question/{question_id}")
async def save_question_answer(
    session_id: str,
    question_id: str,
    request: Dict[str, Any]
):
    """
    Save answer for a specific question
    """
    guest_profile = await GuestProfile.find_one(
        GuestProfile.session_id == session_id
    )

    if not guest_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    # Check if session expired
    if guest_profile.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Guest session has expired"
        )

    try:
        # Extract answer data and time spent
        answer_data = request.get('answer', {})
        time_spent_seconds = request.get('time_spent_seconds', 0)

        # Update guest profile with new answer
        guest_profile.update_answer(question_id, answer_data)

        # Update time spent if provided
        if time_spent_seconds:
            guest_profile.time_spent_seconds += time_spent_seconds

        # Check if this is the email step
        if question_id == "email-collection" and "email" in answer_data:
            guest_profile.email = answer_data["email"]
            guest_profile.status = OnboardingStatus.EMAIL_PROVIDED

        # Save updated profile
        await guest_profile.save()

        # Also save as individual answer for analytics
        answer_doc = OnboardingAnswer(
            guest_session_id=session_id,
            step_id=question_id,
            question_type="onboarding",
            answer=answer_data,
            time_to_answer_seconds=time_spent_seconds
        )
        await answer_doc.save()

        return {
            "success": True,
            "session_id": session_id,
            "question_id": question_id,
            "completed_steps": guest_profile.completed_steps,
            "current_step": len(guest_profile.completed_steps),
            "status": guest_profile.status
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save answer: {str(e)}"
        )


@router.get("/questions")
async def get_onboarding_questions():
    """
    Get the list of onboarding questions with metadata
    """
    questions = [
        {
            "id": "welcome-screen",
            "title": "Welcome",
            "description": "Welcome to ApplyRush.ai",
            "type": "info",
            "required": True,
            "order": 0
        },
        {
            "id": "work-authorization",
            "title": "Work Authorization",
            "description": "Are you authorized to work in the US?",
            "type": "select",
            "required": True,
            "order": 1,
            "options": [
                {"value": "yes", "label": "Yes, I'm authorized to work in the US"},
                {"value": "no", "label": "No, I need sponsorship"},
                {"value": "sponsor", "label": "I have sponsorship"}
            ]
        },
        {
            "id": "salary-selection",
            "title": "Salary Expectations",
            "description": "What is your expected salary range?",
            "type": "select",
            "required": True,
            "order": 2,
            "options": [
                {"value": "0-50k", "label": "$0 - $50,000"},
                {"value": "50k-75k", "label": "$50,000 - $75,000"},
                {"value": "75k-100k", "label": "$75,000 - $100,000"},
                {"value": "100k-150k", "label": "$100,000 - $150,000"},
                {"value": "150k+", "label": "$150,000+"}
            ]
        },
        {
            "id": "work-situation",
            "title": "Work Situation",
            "description": "What is your current work situation?",
            "type": "select",
            "required": True,
            "order": 3
        },
        {
            "id": "job-title-search",
            "title": "Job Title",
            "description": "What job title are you looking for?",
            "type": "text",
            "required": True,
            "order": 4
        },
        {
            "id": "years-of-experience",
            "title": "Years of Experience",
            "description": "How many years of experience do you have?",
            "type": "select",
            "required": True,
            "order": 5
        },
        {
            "id": "education-level",
            "title": "Education Level",
            "description": "What is your highest education level?",
            "type": "select",
            "required": True,
            "order": 6
        },
        {
            "id": "industry-selection",
            "title": "Industry Preferences",
            "description": "Which industries are you interested in?",
            "type": "multiselect",
            "required": True,
            "order": 7
        },
        {
            "id": "work-location",
            "title": "Work Location",
            "description": "Where would you like to work?",
            "type": "select",
            "required": True,
            "order": 8
        },
        {
            "id": "email-collection",
            "title": "Create Account",
            "description": "Enter your email to create your account",
            "type": "email",
            "required": True,
            "order": 9
        }
    ]

    return {
        "questions": questions,
        "total_questions": len(questions)
    }


# Helper functions
def generate_temp_password() -> str:
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(12))


def transform_guest_data_to_user(answers: Dict[str, Any]) -> Dict[str, Any]:
    """Transform guest answers to user profile data"""
    user_data = {
        "full_name": answers.get("name", {}).get("full_name"),
        "skills": answers.get("skills", {}).get("selected_skills", []),
        "experience_years": answers.get("years-of-experience", {}).get("experience"),
        "preferences": {
            "job_title": answers.get("job-title-search", {}).get("jobTitle"),
            "salary_range": answers.get("salary-selection", {}).get("salaryRange"),
            "work_location": answers.get("work-location", {}).get("locationPreference"),
            "industries": answers.get("industry-selection", {}).get("selectedIndustries", []),
            "work_type": answers.get("work-type", {}).get("workTypePreference"),
            "relocation": answers.get("relocation-preference", {}).get("willingToRelocate"),
        },
        "education": {
            "level": answers.get("education-level", {}).get("educationLevel")
        }
    }

    # Remove None values
    return {k: v for k, v in user_data.items() if v is not None}


async def transfer_answers_to_user(session_id: str, user_id: ObjectId) -> int:
    """Transfer all answers from guest session to user"""
    answers = await OnboardingAnswer.find(
        OnboardingAnswer.guest_session_id == session_id
    ).to_list()

    count = 0
    for answer in answers:
        answer.user_id = user_id
        await answer.save()
        count += 1

    return count