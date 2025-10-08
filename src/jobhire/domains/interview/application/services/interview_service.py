"""
Interview session management service.
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.shared.application.exceptions import NotFoundException, BusinessRuleException
from jobhire.domains.interview.domain.entities.interview_session import (
    InterviewSession, InterviewStatus, InterviewType, DifficultyLevel, InterviewMessage
)
from jobhire.domains.interview.domain.value_objects.interview_config import (
    InterviewConfiguration, InterviewPersonality, INTERVIEW_PERSONALITIES
)
from jobhire.domains.interview.infrastructure.ai.interview_ai_service import InterviewAIService

logger = structlog.get_logger(__name__)


class InterviewService:
    """Service for managing interview sessions."""

    def __init__(self, ai_service: InterviewAIService, interview_repository=None):
        self.ai_service = ai_service
        self.interview_repository = interview_repository

    async def create_interview_session(
        self,
        user_id: EntityId,
        job_description: str,
        interview_type: str = "general",
        difficulty_level: str = "medium",
        ai_personality: str = "professional"
    ) -> InterviewSession:
        """Create a new interview session."""
        try:
            session_id = EntityId.generate()

            # Convert string enums
            interview_type_enum = InterviewType(interview_type)
            difficulty_enum = DifficultyLevel(difficulty_level)

            # Create session
            session = InterviewSession(
                session_id=session_id,
                user_id=user_id,
                job_description=job_description,
                interview_type=interview_type_enum,
                difficulty_level=difficulty_enum
            )

            # Set AI personality
            session.ai_personality = ai_personality

            # Parse job description for additional context
            job_info = await self._extract_job_info(job_description)
            session.job_title = job_info.get("title")
            session.company_name = job_info.get("company")

            logger.info(
                "Interview session created",
                session_id=str(session_id),
                user_id=str(user_id),
                interview_type=interview_type,
                difficulty=difficulty_level
            )

            return session

        except Exception as e:
            logger.error("Failed to create interview session", error=str(e))
            raise BusinessRuleException(
                "interview_creation_failed",
                "Failed to create interview session",
                {"error": str(e)}
            )

    async def start_interview_session(
        self,
        session: InterviewSession,
        candidate_name: Optional[str] = None
    ) -> InterviewSession:
        """Start an interview session with welcome message."""
        try:
            if session.status != InterviewStatus.CREATED:
                raise BusinessRuleException(
                    "invalid_session_status",
                    f"Cannot start interview in status: {session.status}",
                    {"current_status": session.status.value}
                )

            # Generate welcome message
            welcome_message = await self.ai_service.generate_welcome_message(
                job_description=session.job_description,
                ai_personality=session.ai_personality,
                candidate_name=candidate_name
            )

            # Generate questions for the session
            questions = await self.ai_service.generate_questions_for_job(
                job_description=session.job_description,
                interview_type=session.interview_type.value,
                difficulty_level=session.difficulty_level.value,
                total_questions=8
            )

            # Start the session
            session.start_interview(welcome_message, len(questions))

            # Store questions in session metadata for later use
            session.planned_questions = questions

            logger.info(
                "Interview session started",
                session_id=str(session.id),
                questions_count=len(questions)
            )

            return session

        except Exception as e:
            logger.error("Failed to start interview session", error=str(e))
            raise BusinessRuleException(
                "interview_start_failed",
                "Failed to start interview session",
                {"error": str(e)}
            )

    async def ask_next_question(
        self,
        session: InterviewSession
    ) -> Optional[str]:
        """Ask the next question in the interview."""
        try:
            if session.status != InterviewStatus.IN_PROGRESS:
                raise BusinessRuleException(
                    "invalid_session_status",
                    f"Cannot ask question in status: {session.status}",
                    {"current_status": session.status.value}
                )

            # Check if interview should be completed
            if session.is_interview_complete():
                return None

            # Get next question from planned questions
            planned_questions = getattr(session, 'planned_questions', [])

            if session.current_question_index < len(planned_questions):
                next_question_data = planned_questions[session.current_question_index]
                question = next_question_data["question"]
                question_type = next_question_data.get("category", "general")

                session.ask_question(question, question_type)

                logger.info(
                    "Question asked",
                    session_id=str(session.id),
                    question_number=session.current_question_index,
                    category=question_type
                )

                return question

            return None

        except Exception as e:
            logger.error("Failed to ask next question", error=str(e))
            raise BusinessRuleException(
                "question_asking_failed",
                "Failed to ask next question",
                {"error": str(e)}
            )

    async def process_answer(
        self,
        session: InterviewSession,
        answer: str,
        provide_feedback: bool = True
    ) -> Optional[str]:
        """Process user's answer and optionally provide feedback."""
        try:
            if session.status != InterviewStatus.IN_PROGRESS:
                raise BusinessRuleException(
                    "invalid_session_status",
                    f"Cannot process answer in status: {session.status}",
                    {"current_status": session.status.value}
                )

            # Record the answer
            session.answer_question(answer)

            feedback_response = None

            if provide_feedback:
                # Get current question for context
                current_question = self._get_current_question(session)

                if current_question:
                    # Evaluate the answer
                    evaluation = await self.ai_service.evaluate_answer(
                        question=current_question["question"],
                        answer=answer,
                        question_category=current_question.get("category", "general"),
                        job_context={"title": session.job_title, "company": session.company_name}
                    )

                    # Store evaluation for final feedback
                    if not hasattr(session, 'answer_evaluations'):
                        session.answer_evaluations = []
                    session.answer_evaluations.append(evaluation)

                    # Generate feedback response
                    feedback_response = evaluation.get("feedback", "Thank you for your response.")

                    # Add AI feedback to conversation
                    session.add_ai_response(feedback_response, "feedback")

                    logger.info(
                        "Answer processed with feedback",
                        session_id=str(session.id),
                        answer_score=evaluation.get("score", 0)
                    )

            return feedback_response

        except Exception as e:
            logger.error("Failed to process answer", error=str(e))
            raise BusinessRuleException(
                "answer_processing_failed",
                "Failed to process answer",
                {"error": str(e)}
            )

    async def generate_follow_up_question(
        self,
        session: InterviewSession,
        previous_answer: str
    ) -> Optional[str]:
        """Generate a follow-up question based on the answer."""
        try:
            current_question = self._get_current_question(session)

            if not current_question:
                return None

            follow_up_templates = current_question.get("follow_up_templates", [])

            follow_up = await self.ai_service.generate_follow_up_question(
                original_question=current_question["question"],
                answer=previous_answer,
                follow_up_templates=follow_up_templates
            )

            if follow_up:
                session.ask_question(follow_up, "follow_up")

                logger.info(
                    "Follow-up question generated",
                    session_id=str(session.id),
                    question_number=session.current_question_index
                )

            return follow_up

        except Exception as e:
            logger.error("Failed to generate follow-up question", error=str(e))
            return None

    async def complete_interview(
        self,
        session: InterviewSession
    ) -> InterviewSession:
        """Complete the interview session with final feedback."""
        try:
            if session.status != InterviewStatus.IN_PROGRESS:
                raise BusinessRuleException(
                    "invalid_session_status",
                    f"Cannot complete interview in status: {session.status}",
                    {"current_status": session.status.value}
                )

            # Get Q&A pairs and evaluations
            qa_pairs = session.get_questions_and_answers()
            evaluations = getattr(session, 'answer_evaluations', [])

            # Generate comprehensive feedback
            final_feedback = await self.ai_service.generate_final_feedback(
                questions_and_answers=qa_pairs,
                answer_evaluations=evaluations
            )

            # Complete the session
            session.complete_interview(final_feedback)

            logger.info(
                "Interview session completed",
                session_id=str(session.id),
                overall_score=final_feedback.overall_score,
                questions_answered=len(qa_pairs)
            )

            return session

        except Exception as e:
            logger.error("Failed to complete interview session", error=str(e))
            raise BusinessRuleException(
                "interview_completion_failed",
                "Failed to complete interview session",
                {"error": str(e)}
            )

    async def cancel_interview(
        self,
        session: InterviewSession,
        reason: Optional[str] = None
    ) -> InterviewSession:
        """Cancel an interview session."""
        try:
            session.cancel_interview(reason)

            logger.info(
                "Interview session cancelled",
                session_id=str(session.id),
                reason=reason
            )

            return session

        except Exception as e:
            logger.error("Failed to cancel interview session", error=str(e))
            raise BusinessRuleException(
                "interview_cancellation_failed",
                "Failed to cancel interview session",
                {"error": str(e)}
            )

    async def get_session_progress(
        self,
        session: InterviewSession
    ) -> Dict[str, Any]:
        """Get detailed progress information for a session."""
        try:
            return {
                "session_id": str(session.id),
                "status": session.status.value,
                "progress_percentage": session.get_progress_percentage(),
                "current_question": session.current_question_index,
                "total_questions": session.total_questions_planned,
                "questions_remaining": max(0, session.total_questions_planned - session.current_question_index),
                "estimated_time_remaining": self._estimate_time_remaining(session),
                "message_count": session.get_message_count(),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "duration_so_far": self._calculate_duration_so_far(session)
            }

        except Exception as e:
            logger.error("Failed to get session progress", error=str(e))
            return {}

    async def get_chat_history(
        self,
        session: InterviewSession,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chat history for a session."""
        try:
            messages = session.get_conversation_history()

            if limit:
                messages = messages[-limit:]

            return [
                {
                    "id": msg.id,
                    "sender": msg.sender,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "message_type": msg.message_type,
                    "metadata": msg.metadata
                }
                for msg in messages
            ]

        except Exception as e:
            logger.error("Failed to get chat history", error=str(e))
            return []

    def _get_current_question(self, session: InterviewSession) -> Optional[Dict[str, Any]]:
        """Get the current question being asked."""
        planned_questions = getattr(session, 'planned_questions', [])

        if session.current_question_index > 0 and session.current_question_index <= len(planned_questions):
            return planned_questions[session.current_question_index - 1]

        return None

    def _estimate_time_remaining(self, session: InterviewSession) -> int:
        """Estimate remaining time in minutes."""
        questions_remaining = max(0, session.total_questions_planned - session.current_question_index)
        avg_time_per_question = 4  # minutes
        return questions_remaining * avg_time_per_question

    def _calculate_duration_so_far(self, session: InterviewSession) -> Optional[int]:
        """Calculate duration so far in minutes."""
        if not session.started_at:
            return None

        duration = (datetime.utcnow() - session.started_at).total_seconds() / 60
        return int(duration)

    async def _extract_job_info(self, job_description: str) -> Dict[str, Any]:
        """Extract key information from job description."""
        # Use AI service to parse job description
        ai_service = InterviewAIService()
        return ai_service._parse_job_description(job_description)