"""
Interview module DTOs.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class CreateInterviewSessionDTO(BaseModel):
    """DTO for creating interview session."""
    job_description: str = Field(..., description="Complete job description")
    interview_type: str = Field(default="general", description="Type of interview")
    difficulty_level: str = Field(default="medium", description="Interview difficulty")
    ai_personality: str = Field(default="professional", description="AI interviewer personality")
    candidate_name: Optional[str] = Field(None, description="Candidate's name for personalization")

    class Config:
        json_schema_extra = {
            "example": {
                "job_description": "Software Engineer position at TechCorp...",
                "interview_type": "general",
                "difficulty_level": "medium",
                "ai_personality": "professional",
                "candidate_name": "John Doe"
            }
        }


class StartInterviewDTO(BaseModel):
    """DTO for starting interview session."""
    session_id: str = Field(..., description="Interview session ID")
    candidate_name: Optional[str] = Field(None, description="Candidate's name")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "candidate_name": "John Doe"
            }
        }


class SubmitAnswerDTO(BaseModel):
    """DTO for submitting interview answer."""
    session_id: str = Field(..., description="Interview session ID")
    answer: str = Field(..., description="Candidate's answer")
    request_feedback: bool = Field(default=True, description="Whether to receive immediate feedback")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "answer": "In my previous role, I led a team of 5 developers...",
                "request_feedback": True
            }
        }


class InterviewMessageDTO(BaseModel):
    """DTO for interview message."""
    id: str
    sender: str  # "ai" or "user"
    content: str
    timestamp: datetime
    message_type: str
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg_1",
                "sender": "ai",
                "content": "Tell me about yourself.",
                "timestamp": "2024-01-15T10:30:00Z",
                "message_type": "question",
                "metadata": {"question_number": 1}
            }
        }


class InterviewFeedbackDTO(BaseModel):
    """DTO for interview feedback."""
    overall_score: float
    strengths: List[str]
    areas_for_improvement: List[str]
    detailed_feedback: str
    question_scores: Dict[str, float]
    recommendations: List[str]
    estimated_performance: str

    class Config:
        json_schema_extra = {
            "example": {
                "overall_score": 85.5,
                "strengths": ["Clear communication", "Specific examples"],
                "areas_for_improvement": ["Use STAR method", "Quantify achievements"],
                "detailed_feedback": "Overall excellent performance...",
                "question_scores": {"question_1": 90.0, "question_2": 80.0},
                "recommendations": ["Practice behavioral questions", "Prepare more examples"],
                "estimated_performance": "good"
            }
        }


class InterviewSessionResponseDTO(BaseModel):
    """DTO for interview session response."""
    id: str
    user_id: str
    status: str
    interview_type: str
    difficulty_level: str
    job_title: Optional[str]
    company_name: Optional[str]
    ai_personality: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_duration_minutes: int
    actual_duration_minutes: Optional[int]
    current_question_index: int
    total_questions_planned: int
    progress_percentage: float
    message_count: Dict[str, int]
    feedback: Optional[InterviewFeedbackDTO]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "session_123",
                "user_id": "user_456",
                "status": "in_progress",
                "interview_type": "general",
                "difficulty_level": "medium",
                "job_title": "Software Engineer",
                "company_name": "TechCorp",
                "ai_personality": "professional",
                "created_at": "2024-01-15T10:00:00Z",
                "started_at": "2024-01-15T10:05:00Z",
                "completed_at": None,
                "estimated_duration_minutes": 30,
                "actual_duration_minutes": None,
                "current_question_index": 3,
                "total_questions_planned": 8,
                "progress_percentage": 37.5,
                "message_count": {"total": 6, "ai_messages": 4, "user_messages": 2},
                "feedback": None
            }
        }


class InterviewProgressDTO(BaseModel):
    """DTO for interview progress."""
    session_id: str
    status: str
    progress_percentage: float
    current_question: int
    total_questions: int
    questions_remaining: int
    estimated_time_remaining: int
    duration_so_far: Optional[int]
    message_count: Dict[str, int]

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "status": "in_progress",
                "progress_percentage": 50.0,
                "current_question": 4,
                "total_questions": 8,
                "questions_remaining": 4,
                "estimated_time_remaining": 16,
                "duration_so_far": 15,
                "message_count": {"total": 8, "ai_messages": 5, "user_messages": 3}
            }
        }


class InterviewChatHistoryDTO(BaseModel):
    """DTO for interview chat history."""
    session_id: str
    messages: List[InterviewMessageDTO]
    total_messages: int

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "messages": [
                    {
                        "id": "msg_1",
                        "sender": "ai",
                        "content": "Hello! Welcome to your mock interview.",
                        "timestamp": "2024-01-15T10:00:00Z",
                        "message_type": "welcome"
                    }
                ],
                "total_messages": 10
            }
        }


class NextQuestionResponseDTO(BaseModel):
    """DTO for next question response."""
    session_id: str
    question: Optional[str]
    question_number: int
    category: Optional[str]
    is_complete: bool
    estimated_time_minutes: Optional[int]

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "question": "Tell me about a challenging project you worked on.",
                "question_number": 4,
                "category": "behavioral",
                "is_complete": False,
                "estimated_time_minutes": 4
            }
        }


class AnswerFeedbackResponseDTO(BaseModel):
    """DTO for answer feedback response."""
    session_id: str
    feedback: Optional[str]
    score: Optional[float]
    strengths: List[str]
    improvements: List[str]
    next_action: str  # "continue", "complete", "follow_up"

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "feedback": "Great example! You clearly explained the situation and outcome.",
                "score": 88.0,
                "strengths": ["Specific example", "Clear structure"],
                "improvements": ["Add more quantified results"],
                "next_action": "continue"
            }
        }


class CompleteInterviewDTO(BaseModel):
    """DTO for completing interview."""
    session_id: str = Field(..., description="Interview session ID")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123"
            }
        }


class InterviewHistoryItemDTO(BaseModel):
    """DTO for interview history item."""
    session_id: str
    job_title: Optional[str]
    company_name: Optional[str]
    interview_type: str
    difficulty_level: str
    status: str
    overall_score: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]
    duration_minutes: Optional[int]

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "job_title": "Software Engineer",
                "company_name": "TechCorp",
                "interview_type": "general",
                "difficulty_level": "medium",
                "status": "completed",
                "overall_score": 85.5,
                "created_at": "2024-01-15T10:00:00Z",
                "completed_at": "2024-01-15T10:30:00Z",
                "duration_minutes": 28
            }
        }


class InterviewHistoryDTO(BaseModel):
    """DTO for interview history."""
    sessions: List[InterviewHistoryItemDTO]
    total_sessions: int
    average_score: Optional[float]
    completed_sessions: int

    class Config:
        json_schema_extra = {
            "example": {
                "sessions": [],
                "total_sessions": 5,
                "average_score": 82.3,
                "completed_sessions": 4
            }
        }


class InterviewAnalyticsDTO(BaseModel):
    """DTO for interview analytics."""
    user_id: str
    total_interviews: int
    completed_interviews: int
    average_score: Optional[float]
    best_score: Optional[float]
    improvement_trend: str  # "improving", "stable", "declining"
    common_strengths: List[str]
    common_improvements: List[str]
    favorite_difficulty: str
    total_time_practiced: int  # minutes

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_456",
                "total_interviews": 12,
                "completed_interviews": 10,
                "average_score": 79.5,
                "best_score": 92.0,
                "improvement_trend": "improving",
                "common_strengths": ["Clear communication", "Specific examples"],
                "common_improvements": ["Use STAR method", "Quantify results"],
                "favorite_difficulty": "medium",
                "total_time_practiced": 360
            }
        }