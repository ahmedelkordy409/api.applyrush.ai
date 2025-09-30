"""
Skill-related value objects.
"""

from typing import List, Set, Optional
from dataclasses import dataclass
from enum import Enum


class SkillLevel(Enum):
    """Skill proficiency levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillCategory(Enum):
    """Skill categories."""
    TECHNICAL = "technical"
    SOFT = "soft"
    LANGUAGE = "language"
    CERTIFICATION = "certification"
    TOOL = "tool"
    FRAMEWORK = "framework"


@dataclass(frozen=True)
class Skill:
    """Individual skill value object."""
    name: str
    level: SkillLevel
    category: SkillCategory
    verified: bool = False
    years_experience: Optional[int] = None

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Skill name cannot be empty")

        if self.years_experience is not None and self.years_experience < 0:
            raise ValueError("Years of experience cannot be negative")

    @property
    def display_name(self) -> str:
        """Get formatted display name."""
        return f"{self.name} ({self.level.value})"

    def is_technical(self) -> bool:
        """Check if this is a technical skill."""
        return self.category in [
            SkillCategory.TECHNICAL,
            SkillCategory.TOOL,
            SkillCategory.FRAMEWORK
        ]


@dataclass(frozen=True)
class SkillSet:
    """Collection of skills."""
    skills: Set[Skill]

    def __post_init__(self):
        if not isinstance(self.skills, set):
            object.__setattr__(self, 'skills', set(self.skills))

    def add_skill(self, skill: Skill) -> "SkillSet":
        """Add a skill to the set."""
        new_skills = self.skills.copy()
        new_skills.add(skill)
        return SkillSet(new_skills)

    def remove_skill(self, skill_name: str) -> "SkillSet":
        """Remove a skill by name."""
        new_skills = {s for s in self.skills if s.name.lower() != skill_name.lower()}
        return SkillSet(new_skills)

    def get_by_category(self, category: SkillCategory) -> List[Skill]:
        """Get skills by category."""
        return [skill for skill in self.skills if skill.category == category]

    def get_by_level(self, level: SkillLevel) -> List[Skill]:
        """Get skills by level."""
        return [skill for skill in self.skills if skill.level == level]

    def get_technical_skills(self) -> List[Skill]:
        """Get all technical skills."""
        return [skill for skill in self.skills if skill.is_technical()]

    def get_verified_skills(self) -> List[Skill]:
        """Get all verified skills."""
        return [skill for skill in self.skills if skill.verified]

    def has_skill(self, skill_name: str) -> bool:
        """Check if skillset contains a skill."""
        return any(s.name.lower() == skill_name.lower() for s in self.skills)

    def skill_count(self) -> int:
        """Get total number of skills."""
        return len(self.skills)

    def to_list(self) -> List[Skill]:
        """Convert to list of skills."""
        return list(self.skills)