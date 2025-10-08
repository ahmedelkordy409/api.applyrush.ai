"""
Interview configuration value objects.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from jobhire.shared.domain.value_objects import ValueObject


class QuestionCategory(Enum):
    """Interview question categories."""
    BEHAVIORAL = "behavioral"
    TECHNICAL_SKILLS = "technical_skills"
    PROBLEM_SOLVING = "problem_solving"
    COMMUNICATION = "communication"
    LEADERSHIP = "leadership"
    TEAMWORK = "teamwork"
    CONFLICT_RESOLUTION = "conflict_resolution"
    ADAPTABILITY = "adaptability"
    MOTIVATION = "motivation"
    COMPANY_FIT = "company_fit"
    EXPERIENCE = "experience"
    ACHIEVEMENTS = "achievements"
    WEAKNESSES = "weaknesses"
    STRENGTHS = "strengths"
    GOALS = "goals"
    SCENARIO_BASED = "scenario_based"


@dataclass(frozen=True)
class InterviewPersonality(ValueObject):
    """AI interviewer personality configuration."""
    name: str
    description: str
    tone: str  # "professional", "friendly", "encouraging", "challenging"
    questioning_style: str  # "direct", "conversational", "structured", "exploratory"
    feedback_style: str  # "detailed", "concise", "encouraging", "constructive"
    follow_up_frequency: float  # 0.0 to 1.0, how often to ask follow-ups

    def __post_init__(self):
        if not 0.0 <= self.follow_up_frequency <= 1.0:
            raise ValueError("Follow-up frequency must be between 0.0 and 1.0")


@dataclass(frozen=True)
class QuestionTemplate(ValueObject):
    """Template for generating interview questions."""
    id: str
    category: QuestionCategory
    template: str
    variables: List[str]  # Variables that can be replaced in template
    difficulty_level: str
    estimated_time_minutes: int
    follow_up_templates: Optional[List[str]] = None

    def generate_question(self, variables: Dict[str, str]) -> str:
        """Generate question by replacing variables in template."""
        question = self.template
        for var, value in variables.items():
            if var in self.variables:
                question = question.replace(f"{{{var}}}", value)
        return question


@dataclass(frozen=True)
class InterviewConfiguration(ValueObject):
    """Configuration for an interview session."""
    interview_type: str
    difficulty_level: str
    estimated_duration_minutes: int
    total_questions: int
    question_categories: List[QuestionCategory]
    ai_personality: InterviewPersonality
    enable_follow_ups: bool = True
    enable_real_time_feedback: bool = False
    require_audio: bool = False
    custom_instructions: Optional[str] = None

    def __post_init__(self):
        if self.total_questions <= 0:
            raise ValueError("Total questions must be positive")

        if self.estimated_duration_minutes <= 0:
            raise ValueError("Duration must be positive")

        if not self.question_categories:
            raise ValueError("At least one question category is required")


@dataclass(frozen=True)
class FeedbackCriteria(ValueObject):
    """Criteria for evaluating interview performance."""
    criterion_id: str
    name: str
    description: str
    weight: float  # 0.0 to 1.0
    evaluation_points: List[str]  # What to look for
    scoring_guide: Dict[str, str]  # score_range -> description

    def __post_init__(self):
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError("Weight must be between 0.0 and 1.0")


@dataclass(frozen=True)
class InterviewSettings(ValueObject):
    """User's interview preferences and settings."""
    preferred_difficulty: str = "medium"
    preferred_duration_minutes: int = 30
    preferred_question_types: List[QuestionCategory] = None
    preferred_ai_personality: str = "professional"
    enable_notifications: bool = True
    save_recordings: bool = False
    auto_generate_feedback: bool = True
    language: str = "en"

    def __post_init__(self):
        if self.preferred_question_types is None:
            object.__setattr__(self, 'preferred_question_types', [
                QuestionCategory.BEHAVIORAL,
                QuestionCategory.TECHNICAL_SKILLS,
                QuestionCategory.EXPERIENCE
            ])

        if self.preferred_duration_minutes <= 0:
            raise ValueError("Duration must be positive")


# Predefined AI Personalities
INTERVIEW_PERSONALITIES = {
    "professional": InterviewPersonality(
        name="Professional",
        description="Formal, business-like approach with structured questions",
        tone="professional",
        questioning_style="structured",
        feedback_style="detailed",
        follow_up_frequency=0.3
    ),
    "friendly": InterviewPersonality(
        name="Friendly",
        description="Warm, encouraging approach to reduce candidate anxiety",
        tone="friendly",
        questioning_style="conversational",
        feedback_style="encouraging",
        follow_up_frequency=0.5
    ),
    "challenging": InterviewPersonality(
        name="Challenging",
        description="Rigorous questioning to test candidate under pressure",
        tone="challenging",
        questioning_style="direct",
        feedback_style="constructive",
        follow_up_frequency=0.7
    ),
    "supportive": InterviewPersonality(
        name="Supportive",
        description="Patient and understanding, helps candidates elaborate",
        tone="encouraging",
        questioning_style="exploratory",
        feedback_style="encouraging",
        follow_up_frequency=0.4
    )
}

# Standard Question Templates
QUESTION_TEMPLATES = [
    QuestionTemplate(
        id="behavioral_conflict",
        category=QuestionCategory.BEHAVIORAL,
        template="Tell me about a time when you had to deal with a difficult {role_type} at {company_context}. How did you handle the situation?",
        variables=["role_type", "company_context"],
        difficulty_level="medium",
        estimated_time_minutes=4,
        follow_up_templates=[
            "What would you do differently if faced with a similar situation?",
            "How did this experience change your approach to {role_type} relationships?"
        ]
    ),
    QuestionTemplate(
        id="technical_skills",
        category=QuestionCategory.TECHNICAL_SKILLS,
        template="Can you walk me through your experience with {technology} and how you've used it in {project_context}?",
        variables=["technology", "project_context"],
        difficulty_level="medium",
        estimated_time_minutes=5,
        follow_up_templates=[
            "What challenges did you face while working with {technology}?",
            "How do you stay updated with changes in {technology}?"
        ]
    ),
    QuestionTemplate(
        id="problem_solving",
        category=QuestionCategory.PROBLEM_SOLVING,
        template="Describe a complex problem you solved at {company_context}. What was your approach?",
        variables=["company_context"],
        difficulty_level="hard",
        estimated_time_minutes=6,
        follow_up_templates=[
            "What alternative solutions did you consider?",
            "How did you measure the success of your solution?"
        ]
    ),
    QuestionTemplate(
        id="motivation",
        category=QuestionCategory.MOTIVATION,
        template="What attracted you to apply for this {job_title} position at {company_name}?",
        variables=["job_title", "company_name"],
        difficulty_level="easy",
        estimated_time_minutes=3,
        follow_up_templates=[
            "How does this role align with your career goals?",
            "What do you hope to achieve in your first year?"
        ]
    ),
    QuestionTemplate(
        id="leadership",
        category=QuestionCategory.LEADERSHIP,
        template="Tell me about a time when you had to lead a team or project. What was the outcome?",
        variables=[],
        difficulty_level="medium",
        estimated_time_minutes=5,
        follow_up_templates=[
            "What leadership style do you prefer and why?",
            "How do you handle team members who disagree with your decisions?"
        ]
    )
]