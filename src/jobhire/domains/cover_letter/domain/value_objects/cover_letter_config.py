"""
Cover Letter value objects and configuration.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


class WritingStyle(Enum):
    """Available writing styles for cover letters."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    CREATIVE = "creative"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    ENTHUSIASTIC = "enthusiastic"
    CONFIDENT = "confident"
    TRADITIONAL = "traditional"


class CoverLetterLength(Enum):
    """Cover letter length options."""
    SHORT = "short"      # 150-250 words
    MEDIUM = "medium"    # 250-400 words
    LONG = "long"        # 400-600 words


class ExportFormat(Enum):
    """Available export formats."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"


@dataclass
class WritingStyleTemplate:
    """Template for writing styles with configuration."""
    style: WritingStyle
    name: str
    description: str
    tone_descriptors: List[str]
    sample_phrases: List[str]
    paragraph_structure: Dict[str, str]
    word_preferences: Dict[str, List[str]]  # formal/informal word choices

    def get_tone_guidance(self) -> str:
        """Get tone guidance for AI generation."""
        return f"Write in a {self.style.value} style that is {', '.join(self.tone_descriptors)}."


# Predefined writing style templates
WRITING_STYLE_TEMPLATES = {
    WritingStyle.PROFESSIONAL: WritingStyleTemplate(
        style=WritingStyle.PROFESSIONAL,
        name="Professional",
        description="Traditional business writing with formal tone and structure",
        tone_descriptors=["formal", "respectful", "business-appropriate", "polished"],
        sample_phrases=[
            "I am writing to express my strong interest in",
            "I would welcome the opportunity to discuss",
            "My experience aligns well with",
            "I look forward to hearing from you"
        ],
        paragraph_structure={
            "opening": "Formal introduction with position and company reference",
            "body": "Professional achievements and qualifications",
            "closing": "Respectful call to action and professional sign-off"
        },
        word_preferences={
            "formal": ["demonstrate", "accomplish", "execute", "facilitate"],
            "avoid": ["awesome", "super", "totally", "grab coffee"]
        }
    ),

    WritingStyle.CASUAL: WritingStyleTemplate(
        style=WritingStyle.CASUAL,
        name="Casual",
        description="Friendly and approachable while maintaining professionalism",
        tone_descriptors=["friendly", "approachable", "conversational", "warm"],
        sample_phrases=[
            "I'm excited about the opportunity to",
            "I'd love to bring my skills to",
            "Your company's mission really resonates with me",
            "I'd be thrilled to chat more about"
        ],
        paragraph_structure={
            "opening": "Warm introduction with genuine enthusiasm",
            "body": "Personal connection to role and relatable achievements",
            "closing": "Friendly invitation for further conversation"
        },
        word_preferences={
            "casual": ["help", "work with", "excited", "passionate"],
            "avoid": ["utilize", "leverage", "synergize", "paradigm"]
        }
    ),

    WritingStyle.CREATIVE: WritingStyleTemplate(
        style=WritingStyle.CREATIVE,
        name="Creative",
        description="Unique and engaging approach that showcases personality",
        tone_descriptors=["innovative", "engaging", "unique", "memorable"],
        sample_phrases=[
            "When I discovered your opening, I knew I had to apply",
            "Your recent project caught my attention because",
            "I've been following your company's journey",
            "Let me tell you a quick story about"
        ],
        paragraph_structure={
            "opening": "Hook with story, question, or unique perspective",
            "body": "Creative presentation of qualifications with storytelling",
            "closing": "Memorable closing that reinforces fit"
        },
        word_preferences={
            "creative": ["craft", "imagine", "create", "transform"],
            "avoid": ["standard", "typical", "normal", "regular"]
        }
    ),

    WritingStyle.EXECUTIVE: WritingStyleTemplate(
        style=WritingStyle.EXECUTIVE,
        name="Executive",
        description="Senior-level leadership tone with strategic focus",
        tone_descriptors=["authoritative", "strategic", "confident", "results-focused"],
        sample_phrases=[
            "Having led successful initiatives in",
            "My track record of driving growth",
            "I have consistently delivered results",
            "I would bring strategic leadership to"
        ],
        paragraph_structure={
            "opening": "Strong value proposition with leadership credentials",
            "body": "Strategic achievements and business impact",
            "closing": "Confident next steps and executive presence"
        },
        word_preferences={
            "executive": ["strategize", "optimize", "drive", "transform"],
            "avoid": ["entry-level", "learning", "basic", "beginner"]
        }
    ),

    WritingStyle.TECHNICAL: WritingStyleTemplate(
        style=WritingStyle.TECHNICAL,
        name="Technical",
        description="Precise and detailed with focus on technical competencies",
        tone_descriptors=["precise", "detailed", "analytical", "competency-focused"],
        sample_phrases=[
            "My technical expertise in",
            "I have successfully implemented",
            "My proficiency includes",
            "I would contribute technical knowledge in"
        ],
        paragraph_structure={
            "opening": "Technical credentials and relevant expertise",
            "body": "Specific technical achievements and project details",
            "closing": "Technical value proposition and next steps"
        },
        word_preferences={
            "technical": ["implement", "develop", "architect", "optimize"],
            "avoid": ["soft skills", "people person", "team player", "communication"]
        }
    ),

    WritingStyle.ENTHUSIASTIC: WritingStyleTemplate(
        style=WritingStyle.ENTHUSIASTIC,
        name="Enthusiastic",
        description="High-energy and passionate tone showing genuine excitement",
        tone_descriptors=["energetic", "passionate", "motivated", "dynamic"],
        sample_phrases=[
            "I'm incredibly excited about",
            "This opportunity perfectly aligns with my passion for",
            "I can't wait to contribute to",
            "I'm energized by the possibility of"
        ],
        paragraph_structure={
            "opening": "High-energy introduction with genuine excitement",
            "body": "Passionate presentation of relevant experience",
            "closing": "Enthusiastic call to action"
        },
        word_preferences={
            "enthusiastic": ["excited", "passionate", "energized", "thrilled"],
            "avoid": ["might", "perhaps", "possibly", "maybe"]
        }
    )
}


@dataclass
class CoverLetterMetadata:
    """Metadata for cover letter tracking and analytics."""
    version: str = "1.0"
    template_used: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    readability_score: Optional[float] = None
    keyword_match_score: Optional[float] = None
    sentiment_score: Optional[float] = None

    # Analytics data
    view_count: int = 0
    download_count: int = 0
    sharing_count: int = 0

    # Performance tracking
    generation_attempts: int = 0
    revision_count: int = 0

    # Quality metrics
    grammar_score: Optional[float] = None
    uniqueness_score: Optional[float] = None

    def increment_view(self) -> None:
        """Increment view count."""
        self.view_count += 1

    def increment_download(self) -> None:
        """Increment download count."""
        self.download_count += 1

    def increment_sharing(self) -> None:
        """Increment sharing count."""
        self.sharing_count += 1

    def add_quality_scores(self, scores: Dict[str, float]) -> None:
        """Add quality assessment scores."""
        self.ai_confidence_score = scores.get("confidence")
        self.readability_score = scores.get("readability")
        self.keyword_match_score = scores.get("keyword_match")
        self.sentiment_score = scores.get("sentiment")
        self.grammar_score = scores.get("grammar")
        self.uniqueness_score = scores.get("uniqueness")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "template_used": self.template_used,
            "ai_confidence_score": self.ai_confidence_score,
            "readability_score": self.readability_score,
            "keyword_match_score": self.keyword_match_score,
            "sentiment_score": self.sentiment_score,
            "view_count": self.view_count,
            "download_count": self.download_count,
            "sharing_count": self.sharing_count,
            "generation_attempts": self.generation_attempts,
            "revision_count": self.revision_count,
            "grammar_score": self.grammar_score,
            "uniqueness_score": self.uniqueness_score
        }


@dataclass
class CoverLetterTemplate:
    """Template for cover letter generation."""
    template_id: str
    name: str
    description: str
    structure: Dict[str, str]
    placeholders: List[str]
    suitable_for: List[str]  # industry types, experience levels
    word_count_range: tuple[int, int]

    def get_structure_guidance(self) -> str:
        """Get structure guidance for AI generation."""
        guidance = []
        for section, description in self.structure.items():
            guidance.append(f"{section.title()}: {description}")
        return "\n".join(guidance)


# Predefined cover letter templates
COVER_LETTER_TEMPLATES = {
    "professional_standard": CoverLetterTemplate(
        template_id="professional_standard",
        name="Professional Standard",
        description="Traditional three-paragraph structure suitable for most roles",
        structure={
            "opening": "Introduction with position and enthusiasm",
            "body": "Relevant experience and achievements with specific examples",
            "closing": "Call to action and professional closing"
        },
        placeholders=["company_name", "position", "key_skills", "achievements"],
        suitable_for=["business", "finance", "consulting", "general"],
        word_count_range=(250, 400)
    ),

    "technical_focused": CoverLetterTemplate(
        template_id="technical_focused",
        name="Technical Professional",
        description="Emphasizes technical skills and project experience",
        structure={
            "opening": "Technical background and position interest",
            "body": "Technical expertise, projects, and measurable results",
            "closing": "Technical contribution potential and next steps"
        },
        placeholders=["technologies", "projects", "metrics", "technical_achievements"],
        suitable_for=["technology", "engineering", "data_science", "development"],
        word_count_range=(300, 450)
    ),

    "creative_industry": CoverLetterTemplate(
        template_id="creative_industry",
        name="Creative Professional",
        description="Showcases creativity and unique perspective",
        structure={
            "opening": "Creative hook and personal brand introduction",
            "body": "Portfolio highlights and creative problem-solving examples",
            "closing": "Creative vision alignment and collaboration invitation"
        },
        placeholders=["creative_hook", "portfolio_items", "creative_achievements"],
        suitable_for=["design", "marketing", "media", "advertising"],
        word_count_range=(200, 350)
    ),

    "executive_level": CoverLetterTemplate(
        template_id="executive_level",
        name="Executive Leadership",
        description="Strategic focus with leadership achievements",
        structure={
            "opening": "Leadership credentials and strategic value proposition",
            "body": "Strategic achievements, team leadership, and business impact",
            "closing": "Strategic vision alignment and leadership commitment"
        },
        placeholders=["leadership_scope", "strategic_achievements", "business_impact"],
        suitable_for=["executive", "management", "leadership", "c-suite"],
        word_count_range=(350, 500)
    )
}


def get_writing_style_options() -> List[Dict[str, str]]:
    """Get available writing style options for API."""
    return [
        {
            "id": style.value,
            "label": template.name,
            "description": template.description
        }
        for style, template in WRITING_STYLE_TEMPLATES.items()
    ]


def get_cover_letter_templates() -> List[Dict[str, Any]]:
    """Get available cover letter templates for API."""
    return [
        {
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "suitable_for": template.suitable_for,
            "word_count_range": template.word_count_range
        }
        for template in COVER_LETTER_TEMPLATES.values()
    ]


def get_length_options() -> List[Dict[str, str]]:
    """Get available length options."""
    return [
        {"id": "short", "label": "Short", "description": "150-250 words, concise and focused"},
        {"id": "medium", "label": "Medium", "description": "250-400 words, balanced detail"},
        {"id": "long", "label": "Long", "description": "400-600 words, comprehensive coverage"}
    ]


def get_tone_options() -> List[Dict[str, str]]:
    """Get available tone options."""
    return [
        {"id": "professional", "label": "Professional", "description": "Formal business tone"},
        {"id": "enthusiastic", "label": "Enthusiastic", "description": "High energy and passion"},
        {"id": "confident", "label": "Confident", "description": "Assertive and self-assured"},
        {"id": "friendly", "label": "Friendly", "description": "Warm and approachable"},
        {"id": "analytical", "label": "Analytical", "description": "Data-driven and logical"}
    ]


def get_focus_area_options() -> List[Dict[str, str]]:
    """Get available focus area options."""
    return [
        {"id": "experience", "label": "Professional Experience", "description": "Highlight work history"},
        {"id": "skills", "label": "Technical Skills", "description": "Emphasize specific competencies"},
        {"id": "achievements", "label": "Key Achievements", "description": "Focus on measurable results"},
        {"id": "passion", "label": "Industry Passion", "description": "Show genuine interest"},
        {"id": "culture_fit", "label": "Cultural Fit", "description": "Alignment with company values"},
        {"id": "leadership", "label": "Leadership", "description": "Management and team experience"},
        {"id": "innovation", "label": "Innovation", "description": "Creative problem-solving"},
        {"id": "growth", "label": "Career Growth", "description": "Development trajectory"}
    ]