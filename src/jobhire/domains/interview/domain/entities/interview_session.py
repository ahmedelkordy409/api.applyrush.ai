"""
Interview session entity and related domain objects.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

from jobhire.shared.domain.entities import AggregateRoot
from jobhire.shared.domain.types import EntityId
from jobhire.shared.domain.events import DomainEvent


class InterviewStatus(Enum):
    """Interview session status."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class InterviewType(Enum):
    """Interview type enumeration."""
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    SYSTEM_DESIGN = "system_design"
    CODING = "coding"
    CASE_STUDY = "case_study"
    GENERAL = "general"
    CUSTOM = "custom"


class DifficultyLevel(Enum):
    """Interview difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass(frozen=True)
class InterviewMessage:
    """Single message in the interview conversation."""
    id: str
    sender: str  # "ai" or "user"
    content: str
    timestamp: datetime
    message_type: str = "text"  # text, question, answer, feedback
    metadata: Optional[Dict[str, Any]] = None

    def is_from_ai(self) -> bool:
        return self.sender == "ai"

    def is_question(self) -> bool:
        return self.message_type == "question"


@dataclass(frozen=True)
class InterviewFeedback:
    """Interview feedback and scoring."""
    overall_score: float  # 0-100
    strengths: List[str]
    areas_for_improvement: List[str]
    detailed_feedback: str
    question_scores: Dict[str, float]  # question_id -> score
    recommendations: List[str]
    estimated_performance: str  # "excellent", "good", "average", "needs_improvement"


class InterviewSessionCreatedEvent(DomainEvent):
    """Event raised when interview session is created."""
    pass


class InterviewSessionStartedEvent(DomainEvent):
    """Event raised when interview session starts."""
    pass


class InterviewSessionCompletedEvent(DomainEvent):
    """Event raised when interview session completes."""
    pass


class InterviewQuestionAskedEvent(DomainEvent):
    """Event raised when AI asks a question."""
    pass


class InterviewAnswerReceivedEvent(DomainEvent):
    """Event raised when user provides an answer."""
    pass


class InterviewSession(AggregateRoot[EntityId]):
    """Interview session aggregate root."""

    def __init__(
        self,
        session_id: EntityId,
        user_id: EntityId,
        job_description: str,
        interview_type: InterviewType = InterviewType.GENERAL,
        difficulty_level: DifficultyLevel = DifficultyLevel.MEDIUM
    ):
        super().__init__(session_id)
        self.user_id = user_id
        self.job_description = job_description
        self.interview_type = interview_type
        self.difficulty_level = difficulty_level
        self.status = InterviewStatus.CREATED
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.messages: List[InterviewMessage] = []
        self.current_question_index = 0
        self.total_questions_planned = 0
        self.feedback: Optional[InterviewFeedback] = None
        self.ai_personality = "professional"  # professional, friendly, strict
        self.estimated_duration_minutes = 30
        self.actual_duration_minutes: Optional[int] = None
        self.job_title: Optional[str] = None
        self.company_name: Optional[str] = None

        # Raise domain event
        self.add_domain_event(InterviewSessionCreatedEvent({
            "session_id": str(session_id),
            "user_id": str(user_id),
            "interview_type": interview_type.value,
            "difficulty_level": difficulty_level.value
        }))

    def start_interview(self, welcome_message: str, total_questions: int = 8) -> None:
        """Start the interview session."""
        if self.status != InterviewStatus.CREATED:
            raise ValueError(f"Cannot start interview in status: {self.status}")

        self.status = InterviewStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.total_questions_planned = total_questions
        self.increment_version()

        # Add welcome message
        welcome_msg = InterviewMessage(
            id=f"msg_{len(self.messages) + 1}",
            sender="ai",
            content=welcome_message,
            timestamp=datetime.utcnow(),
            message_type="welcome"
        )
        self.messages.append(welcome_msg)

        self.add_domain_event(InterviewSessionStartedEvent({
            "session_id": str(self.id),
            "user_id": str(self.user_id),
            "total_questions": total_questions
        }))

    def ask_question(self, question: str, question_type: str = "question") -> None:
        """AI asks a question."""
        if self.status != InterviewStatus.IN_PROGRESS:
            raise ValueError(f"Cannot ask question in status: {self.status}")

        self.current_question_index += 1
        question_msg = InterviewMessage(
            id=f"msg_{len(self.messages) + 1}",
            sender="ai",
            content=question,
            timestamp=datetime.utcnow(),
            message_type=question_type,
            metadata={"question_number": self.current_question_index}
        )
        self.messages.append(question_msg)
        self.increment_version()

        self.add_domain_event(InterviewQuestionAskedEvent({
            "session_id": str(self.id),
            "question_number": self.current_question_index,
            "question": question,
            "question_type": question_type
        }))

    def answer_question(self, answer: str) -> None:
        """User provides an answer."""
        if self.status != InterviewStatus.IN_PROGRESS:
            raise ValueError(f"Cannot answer question in status: {self.status}")

        answer_msg = InterviewMessage(
            id=f"msg_{len(self.messages) + 1}",
            sender="user",
            content=answer,
            timestamp=datetime.utcnow(),
            message_type="answer",
            metadata={"question_number": self.current_question_index}
        )
        self.messages.append(answer_msg)
        self.increment_version()

        self.add_domain_event(InterviewAnswerReceivedEvent({
            "session_id": str(self.id),
            "question_number": self.current_question_index,
            "answer_length": len(answer)
        }))

    def add_ai_response(self, response: str, response_type: str = "feedback") -> None:
        """AI provides feedback or follow-up."""
        if self.status != InterviewStatus.IN_PROGRESS:
            raise ValueError(f"Cannot add AI response in status: {self.status}")

        response_msg = InterviewMessage(
            id=f"msg_{len(self.messages) + 1}",
            sender="ai",
            content=response,
            timestamp=datetime.utcnow(),
            message_type=response_type
        )
        self.messages.append(response_msg)
        self.increment_version()

    def complete_interview(self, feedback: InterviewFeedback) -> None:
        """Complete the interview session with feedback."""
        if self.status != InterviewStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete interview in status: {self.status}")

        self.status = InterviewStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.feedback = feedback

        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds() / 60
            self.actual_duration_minutes = int(duration)

        self.increment_version()

        self.add_domain_event(InterviewSessionCompletedEvent({
            "session_id": str(self.id),
            "user_id": str(self.user_id),
            "duration_minutes": self.actual_duration_minutes,
            "overall_score": feedback.overall_score,
            "questions_answered": self.current_question_index
        }))

    def cancel_interview(self, reason: Optional[str] = None) -> None:
        """Cancel the interview session."""
        if self.status in [InterviewStatus.COMPLETED, InterviewStatus.CANCELLED]:
            raise ValueError(f"Cannot cancel interview in status: {self.status}")

        self.status = InterviewStatus.CANCELLED
        self.completed_at = datetime.utcnow()

        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds() / 60
            self.actual_duration_minutes = int(duration)

        self.increment_version()

    def get_conversation_history(self) -> List[InterviewMessage]:
        """Get the full conversation history."""
        return self.messages.copy()

    def get_questions_and_answers(self) -> List[Dict[str, Any]]:
        """Get structured Q&A pairs."""
        qa_pairs = []
        current_question = None

        for message in self.messages:
            if message.is_question():
                current_question = message
            elif message.message_type == "answer" and current_question:
                qa_pairs.append({
                    "question": current_question.content,
                    "answer": message.content,
                    "question_number": message.metadata.get("question_number") if message.metadata else None,
                    "timestamp": message.timestamp
                })
                current_question = None

        return qa_pairs

    def get_progress_percentage(self) -> float:
        """Get interview progress as percentage."""
        if self.total_questions_planned == 0:
            return 0.0
        return min(100.0, (self.current_question_index / self.total_questions_planned) * 100)

    def is_interview_complete(self) -> bool:
        """Check if interview should be completed."""
        return (
            self.current_question_index >= self.total_questions_planned and
            self.total_questions_planned > 0
        )

    def get_message_count(self) -> Dict[str, int]:
        """Get message statistics."""
        ai_messages = sum(1 for msg in self.messages if msg.sender == "ai")
        user_messages = sum(1 for msg in self.messages if msg.sender == "user")
        questions = sum(1 for msg in self.messages if msg.is_question())

        return {
            "total": len(self.messages),
            "ai_messages": ai_messages,
            "user_messages": user_messages,
            "questions_asked": questions
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "interview_type": self.interview_type.value,
            "difficulty_level": self.difficulty_level.value,
            "job_title": self.job_title,
            "company_name": self.company_name,
            "job_description": self.job_description,
            "ai_personality": self.ai_personality,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "actual_duration_minutes": self.actual_duration_minutes,
            "current_question_index": self.current_question_index,
            "total_questions_planned": self.total_questions_planned,
            "progress_percentage": self.get_progress_percentage(),
            "message_count": self.get_message_count(),
            "messages": [
                {
                    "id": msg.id,
                    "sender": msg.sender,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "message_type": msg.message_type,
                    "metadata": msg.metadata
                } for msg in self.messages
            ],
            "feedback": {
                "overall_score": self.feedback.overall_score,
                "strengths": self.feedback.strengths,
                "areas_for_improvement": self.feedback.areas_for_improvement,
                "detailed_feedback": self.feedback.detailed_feedback,
                "question_scores": self.feedback.question_scores,
                "recommendations": self.feedback.recommendations,
                "estimated_performance": self.feedback.estimated_performance
            } if self.feedback else None
        }