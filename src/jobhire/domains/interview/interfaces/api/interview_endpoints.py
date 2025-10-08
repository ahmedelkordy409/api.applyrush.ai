"""
AI Mock Interview API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.infrastructure.security import get_current_user, require_permission, Permission
from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request

from jobhire.domains.interview.application.services.interview_service import InterviewService
from jobhire.domains.interview.infrastructure.ai.interview_ai_service import InterviewAIService
from jobhire.domains.interview.application.dto.interview_dto import (
    CreateInterviewSessionDTO, StartInterviewDTO, SubmitAnswerDTO,
    InterviewSessionResponseDTO, InterviewProgressDTO, InterviewChatHistoryDTO,
    NextQuestionResponseDTO, AnswerFeedbackResponseDTO, CompleteInterviewDTO,
    InterviewHistoryDTO, InterviewAnalyticsDTO
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/interview", tags=["🎯 AI Mock Interview"])

# In-memory storage for demo (replace with actual repository)
interview_sessions = {}


async def get_interview_service() -> InterviewService:
    """Dependency to get interview service."""
    ai_service = InterviewAIService()
    return InterviewService(ai_service=ai_service)


@router.post("/sessions", response_model=InterviewSessionResponseDTO)
@measure_http_request("/interview/sessions")
async def create_interview_session(
    session_data: CreateInterviewSessionDTO,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Create a new AI mock interview session.

    **Features:**
    - Personalized AI interviewer based on job description
    - Multiple interview types and difficulty levels
    - Custom AI personality selection
    - Job-specific question generation

    **Interview Types:**
    - `general`: Mixed behavioral and technical questions
    - `behavioral`: Focus on past experiences and situations
    - `technical`: Technical skills and problem-solving
    - `leadership`: Management and leadership scenarios

    **Difficulty Levels:**
    - `easy`: Entry-level questions
    - `medium`: Mid-level professional questions
    - `hard`: Senior-level challenging questions
    - `expert`: Executive and expert-level questions

    **AI Personalities:**
    - `professional`: Formal, structured approach
    - `friendly`: Warm, encouraging interviewer
    - `challenging`: Rigorous, pressure-testing style
    - `supportive`: Patient, helps elaborate responses
    """
    try:
        user_id = EntityId.from_string(current_user["user_id"])

        session = await interview_service.create_interview_session(
            user_id=user_id,
            job_description=session_data.job_description,
            interview_type=session_data.interview_type,
            difficulty_level=session_data.difficulty_level,
            ai_personality=session_data.ai_personality
        )

        # Store session in memory (replace with repository)
        interview_sessions[str(session.id)] = session

        logger.info("Interview session created", session_id=str(session.id))

        return InterviewSessionResponseDTO(**session.to_dict())

    except Exception as e:
        logger.error("Failed to create interview session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create interview session")


@router.post("/sessions/{session_id}/start", response_model=NextQuestionResponseDTO)
@measure_http_request("/interview/sessions/start")
async def start_interview_session(
    session_id: str,
    start_data: StartInterviewDTO,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Start an interview session with AI welcome message and first question.

    **Process:**
    1. AI generates personalized welcome message
    2. Questions are prepared based on job description
    3. Session status changes to 'in_progress'
    4. First question is ready to be asked

    **Response includes:**
    - Welcome message from AI interviewer
    - Session progress information
    - Readiness for first question
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        session = await interview_service.start_interview_session(
            session=session,
            candidate_name=start_data.candidate_name
        )

        # Get first question
        first_question = await interview_service.ask_next_question(session)

        logger.info("Interview session started", session_id=session_id)

        return NextQuestionResponseDTO(
            session_id=session_id,
            question=first_question,
            question_number=session.current_question_index,
            category="welcome",
            is_complete=False,
            estimated_time_minutes=session.estimated_duration_minutes
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start interview session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to start interview session")


@router.post("/sessions/{session_id}/answer", response_model=AnswerFeedbackResponseDTO)
@measure_http_request("/interview/sessions/answer")
async def submit_answer(
    session_id: str,
    answer_data: SubmitAnswerDTO,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Submit an answer to the current interview question.

    **AI Analysis:**
    - Real-time answer evaluation and scoring
    - Identification of strengths in response
    - Specific improvement suggestions
    - STAR method compliance checking
    - Communication effectiveness assessment

    **Feedback Features:**
    - Immediate constructive feedback
    - Scoring based on multiple criteria
    - Personalized improvement tips
    - Follow-up question suggestions

    **Next Steps:**
    - Automatic progression to next question
    - Option for follow-up questions
    - Session completion when appropriate
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Process the answer
        feedback = await interview_service.process_answer(
            session=session,
            answer=answer_data.answer,
            provide_feedback=answer_data.request_feedback
        )

        # Determine next action
        next_action = "continue"
        if session.is_interview_complete():
            next_action = "complete"

        # Get evaluation if available
        evaluations = getattr(session, 'answer_evaluations', [])
        latest_evaluation = evaluations[-1] if evaluations else {}

        logger.info("Answer submitted", session_id=session_id, answer_length=len(answer_data.answer))

        return AnswerFeedbackResponseDTO(
            session_id=session_id,
            feedback=feedback,
            score=latest_evaluation.get("score"),
            strengths=latest_evaluation.get("strengths", []),
            improvements=latest_evaluation.get("improvements", []),
            next_action=next_action
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit answer", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to submit answer")


@router.get("/sessions/{session_id}/next-question", response_model=NextQuestionResponseDTO)
@measure_http_request("/interview/sessions/next-question")
async def get_next_question(
    session_id: str,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Get the next interview question.

    **Smart Question Selection:**
    - Questions tailored to job description
    - Progressive difficulty based on performance
    - Mix of behavioral and technical questions
    - Context-aware follow-up questions

    **Question Categories:**
    - Behavioral (STAR method scenarios)
    - Technical skills assessment
    - Problem-solving challenges
    - Leadership and teamwork
    - Communication and interpersonal
    - Company fit and motivation
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        next_question = await interview_service.ask_next_question(session)

        is_complete = next_question is None or session.is_interview_complete()

        return NextQuestionResponseDTO(
            session_id=session_id,
            question=next_question,
            question_number=session.current_question_index,
            category="behavioral",  # Could be dynamic based on question
            is_complete=is_complete,
            estimated_time_minutes=4
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get next question", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get next question")


@router.post("/sessions/{session_id}/complete", response_model=InterviewSessionResponseDTO)
@measure_http_request("/interview/sessions/complete")
async def complete_interview(
    session_id: str,
    complete_data: CompleteInterviewDTO,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Complete the interview session and generate comprehensive feedback.

    **Comprehensive Analysis:**
    - Overall performance scoring (0-100)
    - Detailed strengths identification
    - Specific improvement areas
    - Question-by-question breakdown
    - Professional development recommendations

    **Feedback Report:**
    - Executive summary of performance
    - Behavioral competency analysis
    - Technical skill assessment
    - Communication effectiveness
    - Interview readiness score
    - Actionable improvement plan

    **Performance Metrics:**
    - Response quality and depth
    - STAR method usage
    - Specific examples provided
    - Professional presentation
    - Confidence and clarity
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        completed_session = await interview_service.complete_interview(session)

        logger.info("Interview session completed", session_id=session_id,
                   overall_score=completed_session.feedback.overall_score if completed_session.feedback else None)

        return InterviewSessionResponseDTO(**completed_session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to complete interview session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to complete interview session")


@router.get("/sessions/{session_id}/progress", response_model=InterviewProgressDTO)
@measure_http_request("/interview/sessions/progress")
async def get_interview_progress(
    session_id: str,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Get real-time interview session progress.

    **Progress Tracking:**
    - Completion percentage
    - Questions answered vs remaining
    - Time elapsed and estimated remaining
    - Session status and phase
    - Performance indicators
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        progress = await interview_service.get_session_progress(session)

        return InterviewProgressDTO(**progress)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get interview progress", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get interview progress")


@router.get("/sessions/{session_id}/chat", response_model=InterviewChatHistoryDTO)
@measure_http_request("/interview/sessions/chat")
async def get_chat_history(
    session_id: str,
    limit: Optional[int] = Query(None, description="Limit number of messages"),
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Get the complete conversation history for an interview session.

    **Chat Features:**
    - Complete AI-candidate conversation log
    - Message timestamps and types
    - Question and answer pairs
    - Feedback and follow-ups
    - Session progression tracking

    **Message Types:**
    - `welcome`: AI introduction and setup
    - `question`: Interview questions
    - `answer`: Candidate responses
    - `feedback`: AI feedback and evaluation
    - `follow_up`: Additional probing questions
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        messages = await interview_service.get_chat_history(session, limit)

        return InterviewChatHistoryDTO(
            session_id=session_id,
            messages=messages,
            total_messages=len(session.messages)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get chat history", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get chat history")


@router.get("/sessions/{session_id}", response_model=InterviewSessionResponseDTO)
@measure_http_request("/interview/sessions/get")
async def get_interview_session(
    session_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get detailed information about a specific interview session.

    **Session Details:**
    - Current status and progress
    - Job and company information
    - AI configuration settings
    - Performance metrics
    - Time tracking
    - Completion status
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        return InterviewSessionResponseDTO(**session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get interview session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get interview session")


@router.delete("/sessions/{session_id}")
@measure_http_request("/interview/sessions/cancel")
async def cancel_interview_session(
    session_id: str,
    current_user=Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service)
):
    """
    Cancel an active interview session.

    **Cancellation:**
    - Immediately stops the interview
    - Saves progress made so far
    - Provides partial feedback if requested
    - Updates session status to cancelled
    """
    try:
        session = interview_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Verify user ownership
        if str(session.user_id) != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        await interview_service.cancel_interview(session, "User requested cancellation")

        logger.info("Interview session cancelled", session_id=session_id)

        return {"success": True, "message": "Interview session cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel interview session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cancel interview session")


@router.get("/history", response_model=InterviewHistoryDTO)
@measure_http_request("/interview/history")
async def get_interview_history(
    limit: int = Query(10, description="Number of sessions to return"),
    current_user=Depends(get_current_user)
):
    """
    Get user's interview session history and statistics.

    **History Features:**
    - Chronological list of all sessions
    - Performance trends over time
    - Average scores and improvement
    - Completion rates
    - Practice time analytics

    **Statistics:**
    - Total interviews conducted
    - Average performance score
    - Best and worst performances
    - Improvement trajectory
    - Most practiced interview types
    """
    try:
        user_id = current_user["user_id"]

        # Filter sessions for current user
        user_sessions = [
            session for session in interview_sessions.values()
            if str(session.user_id) == user_id
        ]

        # Sort by creation date (newest first)
        user_sessions.sort(key=lambda x: x.created_at, reverse=True)

        # Limit results
        limited_sessions = user_sessions[:limit]

        # Calculate statistics
        completed_sessions = [s for s in user_sessions if s.status.value == "completed"]
        scores = [s.feedback.overall_score for s in completed_sessions if s.feedback]

        avg_score = sum(scores) / len(scores) if scores else None

        # Convert to DTO format
        history_items = []
        for session in limited_sessions:
            history_items.append({
                "session_id": str(session.id),
                "job_title": session.job_title,
                "company_name": session.company_name,
                "interview_type": session.interview_type.value,
                "difficulty_level": session.difficulty_level.value,
                "status": session.status.value,
                "overall_score": session.feedback.overall_score if session.feedback else None,
                "created_at": session.created_at,
                "completed_at": session.completed_at,
                "duration_minutes": session.actual_duration_minutes
            })

        return InterviewHistoryDTO(
            sessions=history_items,
            total_sessions=len(user_sessions),
            average_score=avg_score,
            completed_sessions=len(completed_sessions)
        )

    except Exception as e:
        logger.error("Failed to get interview history", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get interview history")


@router.get("/analytics", response_model=InterviewAnalyticsDTO)
@measure_http_request("/interview/analytics")
async def get_interview_analytics(
    current_user=Depends(get_current_user)
):
    """
    Get comprehensive interview practice analytics and insights.

    **Analytics Dashboard:**
    - Performance trend analysis
    - Skill development tracking
    - Weakness identification patterns
    - Practice consistency metrics
    - Improvement recommendations

    **Insights:**
    - Most challenging question categories
    - Strongest and weakest competencies
    - Progress over time
    - Benchmarking against standards
    - Personalized coaching suggestions
    """
    try:
        user_id = current_user["user_id"]

        # Get user sessions
        user_sessions = [
            session for session in interview_sessions.values()
            if str(session.user_id) == user_id
        ]

        completed = [s for s in user_sessions if s.status.value == "completed"]
        scores = [s.feedback.overall_score for s in completed if s.feedback]

        # Calculate analytics
        total_time = sum(s.actual_duration_minutes or 0 for s in completed)

        # Aggregate feedback patterns
        all_strengths = []
        all_improvements = []
        for session in completed:
            if session.feedback:
                all_strengths.extend(session.feedback.strengths)
                all_improvements.extend(session.feedback.areas_for_improvement)

        # Get most common items
        from collections import Counter
        strength_counter = Counter(all_strengths)
        improvement_counter = Counter(all_improvements)

        common_strengths = [item for item, count in strength_counter.most_common(5)]
        common_improvements = [item for item, count in improvement_counter.most_common(5)]

        # Determine improvement trend (simplified)
        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / 3
            earlier_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else scores[0]

            if recent_avg > earlier_avg + 5:
                trend = "improving"
            elif recent_avg < earlier_avg - 5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Most common difficulty
        difficulty_counter = Counter(s.difficulty_level.value for s in user_sessions)
        favorite_difficulty = difficulty_counter.most_common(1)[0][0] if difficulty_counter else "medium"

        return InterviewAnalyticsDTO(
            user_id=user_id,
            total_interviews=len(user_sessions),
            completed_interviews=len(completed),
            average_score=sum(scores) / len(scores) if scores else None,
            best_score=max(scores) if scores else None,
            improvement_trend=trend,
            common_strengths=common_strengths,
            common_improvements=common_improvements,
            favorite_difficulty=favorite_difficulty,
            total_time_practiced=total_time
        )

    except Exception as e:
        logger.error("Failed to get interview analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get interview analytics")