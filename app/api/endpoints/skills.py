"""
Skills Management API endpoints
Handles skill extraction, management, and matching
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import logging

from app.core.database import database
from app.core.security import get_current_user
from app.core.security import PermissionChecker
from app.services.ai_client import get_ai_client

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class SkillRequest(BaseModel):
    name: str
    level: str = "intermediate"  # beginner, intermediate, advanced, expert
    years_experience: Optional[int] = None
    is_featured: bool = False


class SkillResponse(BaseModel):
    id: str
    name: str
    level: str
    years_experience: Optional[int]
    is_featured: bool
    created_at: datetime


class SkillsListResponse(BaseModel):
    skills: List[SkillResponse]
    featured_skills: List[SkillResponse]
    total_count: int


class SkillExtractionRequest(BaseModel):
    text: str  # Resume content or job description
    extraction_type: str = "resume"  # resume, job_description, profile


@router.get("/", response_model=SkillsListResponse)
async def get_user_skills(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's skills"""
    try:
        if not permission_checker.has_permission(current_user, "skills", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read skills"
            )

        query = """
            SELECT id, name, level, years_experience, is_featured, created_at
            FROM user_skills
            WHERE user_id = :user_id AND status = 'active'
            ORDER BY is_featured DESC, name ASC
        """

        skills = await database.fetch_all(
            query=query,
            values={"user_id": current_user["id"]}
        )

        skill_responses = [
            SkillResponse(
                id=str(skill["id"]),
                name=skill["name"],
                level=skill["level"],
                years_experience=skill["years_experience"],
                is_featured=skill["is_featured"],
                created_at=skill["created_at"]
            )
            for skill in skills
        ]

        featured_skills = [skill for skill in skill_responses if skill.is_featured]

        return SkillsListResponse(
            skills=skill_responses,
            featured_skills=featured_skills,
            total_count=len(skill_responses)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user skills: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user skills"
        )


@router.post("/", response_model=SkillResponse)
async def add_skill(
    skill: SkillRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add a new skill to user's profile"""
    try:
        if not permission_checker.has_permission(current_user, "skills", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to add skills"
            )

        # Check if skill already exists
        existing_query = """
            SELECT id FROM user_skills
            WHERE user_id = :user_id AND LOWER(name) = LOWER(:name) AND status = 'active'
        """

        existing = await database.fetch_one(
            query=existing_query,
            values={"user_id": current_user["id"], "name": skill.name}
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Skill already exists in your profile"
            )

        # Validate skill level
        valid_levels = ["beginner", "intermediate", "advanced", "expert"]
        if skill.level not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid skill level. Must be one of: {', '.join(valid_levels)}"
            )

        # Add skill
        insert_query = """
            INSERT INTO user_skills (
                user_id, name, level, years_experience, is_featured, status, created_at, updated_at
            ) VALUES (
                :user_id, :name, :level, :years_experience, :is_featured, :status, :created_at, :updated_at
            ) RETURNING id, name, level, years_experience, is_featured, created_at
        """

        values = {
            "user_id": current_user["id"],
            "name": skill.name.strip(),
            "level": skill.level,
            "years_experience": skill.years_experience,
            "is_featured": skill.is_featured,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await database.fetch_one(query=insert_query, values=values)

        return SkillResponse(
            id=str(result["id"]),
            name=result["name"],
            level=result["level"],
            years_experience=result["years_experience"],
            is_featured=result["is_featured"],
            created_at=result["created_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding skill: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add skill"
        )


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    skill: SkillRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update an existing skill"""
    try:
        if not permission_checker.has_permission(current_user, "skills", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update skills"
            )

        # Check if skill exists and belongs to user
        check_query = """
            SELECT id FROM user_skills
            WHERE id = :skill_id AND user_id = :user_id AND status = 'active'
        """

        existing = await database.fetch_one(
            query=check_query,
            values={"skill_id": skill_id, "user_id": current_user["id"]}
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Skill not found"
            )

        # Validate skill level
        valid_levels = ["beginner", "intermediate", "advanced", "expert"]
        if skill.level not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid skill level. Must be one of: {', '.join(valid_levels)}"
            )

        # Update skill
        update_query = """
            UPDATE user_skills
            SET name = :name, level = :level, years_experience = :years_experience,
                is_featured = :is_featured, updated_at = :updated_at
            WHERE id = :skill_id
            RETURNING id, name, level, years_experience, is_featured, created_at
        """

        values = {
            "skill_id": skill_id,
            "name": skill.name.strip(),
            "level": skill.level,
            "years_experience": skill.years_experience,
            "is_featured": skill.is_featured,
            "updated_at": datetime.utcnow()
        }

        result = await database.fetch_one(query=update_query, values=values)

        return SkillResponse(
            id=str(result["id"]),
            name=result["name"],
            level=result["level"],
            years_experience=result["years_experience"],
            is_featured=result["is_featured"],
            created_at=result["created_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating skill: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update skill"
        )


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a skill"""
    try:
        if not permission_checker.has_permission(current_user, "skills", "delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete skills"
            )

        # Check if skill exists and belongs to user
        check_query = """
            SELECT id FROM user_skills
            WHERE id = :skill_id AND user_id = :user_id AND status = 'active'
        """

        existing = await database.fetch_one(
            query=check_query,
            values={"skill_id": skill_id, "user_id": current_user["id"]}
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Skill not found"
            )

        # Soft delete the skill
        delete_query = """
            UPDATE user_skills
            SET status = 'deleted', updated_at = :updated_at
            WHERE id = :skill_id
        """

        await database.execute(
            query=delete_query,
            values={"skill_id": skill_id, "updated_at": datetime.utcnow()}
        )

        return {
            "success": True,
            "message": "Skill deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting skill: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete skill"
        )


@router.post("/extract")
async def extract_skills_from_text(
    request: SkillExtractionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Extract skills from text using AI"""
    try:
        if not permission_checker.has_permission(current_user, "ai_features", "use"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required for AI skill extraction"
            )

        ai_client = get_ai_client()

        if request.extraction_type == "resume":
            prompt = f"""Analyze the following resume content and extract technical skills, programming languages, frameworks, tools, and soft skills.

Resume Content:
{request.text}

Return a JSON array of skills with the following format:
[
  {{"name": "Python", "category": "programming_language", "confidence": 0.9}},
  {{"name": "React", "category": "framework", "confidence": 0.8}},
  {{"name": "Project Management", "category": "soft_skill", "confidence": 0.7}}
]

Categories: programming_language, framework, tool, database, cloud_platform, soft_skill, certification, methodology

Only include skills that are clearly mentioned or strongly implied in the text."""

        elif request.extraction_type == "job_description":
            prompt = f"""Analyze the following job description and extract required skills, technologies, and qualifications.

Job Description:
{request.text}

Return a JSON array of required skills with the following format:
[
  {{"name": "Java", "category": "programming_language", "required": true, "years_experience": 3}},
  {{"name": "AWS", "category": "cloud_platform", "required": true, "years_experience": 2}},
  {{"name": "Leadership", "category": "soft_skill", "required": false, "years_experience": null}}
]

Categories: programming_language, framework, tool, database, cloud_platform, soft_skill, certification, methodology

Extract both required and preferred skills."""

        else:
            prompt = f"""Extract skills and competencies from the following text:

Text:
{request.text}

Return a JSON array of skills in this format:
[
  {{"name": "Skill Name", "category": "category", "confidence": 0.8}}
]"""

        ai_response = await ai_client.generate_text(prompt)

        # Parse AI response
        import json
        try:
            extracted_skills = json.loads(ai_response)
        except json.JSONDecodeError:
            # Fallback: try to extract skills using simple text processing
            extracted_skills = await fallback_skill_extraction(request.text, request.extraction_type)

        # Filter and clean skills
        cleaned_skills = []
        for skill in extracted_skills:
            if isinstance(skill, dict) and "name" in skill:
                skill_name = skill["name"].strip()
                if len(skill_name) > 1 and skill_name.lower() not in ["and", "or", "the", "a", "an"]:
                    cleaned_skills.append(skill)

        return {
            "success": True,
            "extracted_skills": cleaned_skills,
            "extraction_type": request.extraction_type,
            "total_found": len(cleaned_skills)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting skills: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract skills from text"
        )


@router.post("/bulk-add")
async def bulk_add_skills(
    skills: List[SkillRequest],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add multiple skills at once"""
    try:
        if not permission_checker.has_permission(current_user, "skills", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to add skills"
            )

        if len(skills) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add more than 50 skills at once"
            )

        added_skills = []
        skipped_skills = []

        for skill in skills:
            # Check if skill already exists
            existing_query = """
                SELECT id FROM user_skills
                WHERE user_id = :user_id AND LOWER(name) = LOWER(:name) AND status = 'active'
            """

            existing = await database.fetch_one(
                query=existing_query,
                values={"user_id": current_user["id"], "name": skill.name}
            )

            if existing:
                skipped_skills.append(skill.name)
                continue

            # Add skill
            insert_query = """
                INSERT INTO user_skills (
                    user_id, name, level, years_experience, is_featured, status, created_at, updated_at
                ) VALUES (
                    :user_id, :name, :level, :years_experience, :is_featured, :status, :created_at, :updated_at
                ) RETURNING id, name, level, years_experience, is_featured, created_at
            """

            values = {
                "user_id": current_user["id"],
                "name": skill.name.strip(),
                "level": skill.level,
                "years_experience": skill.years_experience,
                "is_featured": skill.is_featured,
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            try:
                result = await database.fetch_one(query=insert_query, values=values)
                added_skills.append(SkillResponse(
                    id=str(result["id"]),
                    name=result["name"],
                    level=result["level"],
                    years_experience=result["years_experience"],
                    is_featured=result["is_featured"],
                    created_at=result["created_at"]
                ))
            except Exception as e:
                logger.warning(f"Failed to add skill {skill.name}: {str(e)}")
                skipped_skills.append(skill.name)

        return {
            "success": True,
            "added_skills": added_skills,
            "skipped_skills": skipped_skills,
            "summary": {
                "total_requested": len(skills),
                "added": len(added_skills),
                "skipped": len(skipped_skills)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk adding skills: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk add skills"
        )


@router.get("/suggestions")
async def get_skill_suggestions(
    query: Optional[str] = None,
    category: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get skill suggestions based on user's profile and industry trends"""
    try:
        # Get popular skills from database
        popular_skills_query = """
            SELECT name, COUNT(*) as usage_count
            FROM user_skills
            WHERE status = 'active'
            GROUP BY name
            ORDER BY usage_count DESC
            LIMIT 50
        """

        popular_skills = await database.fetch_all(popular_skills_query)

        # Filter by category if provided
        if category:
            # This would require a skills taxonomy table in a real implementation
            pass

        # Filter by query if provided
        filtered_skills = []
        if query:
            query_lower = query.lower()
            for skill in popular_skills:
                if query_lower in skill["name"].lower():
                    filtered_skills.append(skill)
        else:
            filtered_skills = popular_skills

        # Get user's current skills to exclude from suggestions
        user_skills_query = """
            SELECT name FROM user_skills
            WHERE user_id = :user_id AND status = 'active'
        """

        user_skills = await database.fetch_all(
            query=user_skills_query,
            values={"user_id": current_user["id"]}
        )

        user_skill_names = {skill["name"].lower() for skill in user_skills}

        # Filter out skills user already has
        suggestions = [
            {
                "name": skill["name"],
                "popularity": skill["usage_count"],
                "category": "general"  # Would come from taxonomy table
            }
            for skill in filtered_skills
            if skill["name"].lower() not in user_skill_names
        ]

        return {
            "suggestions": suggestions[:20],  # Limit to top 20
            "total_suggestions": len(suggestions),
            "query": query,
            "category": category
        }

    except Exception as e:
        logger.error(f"Error getting skill suggestions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get skill suggestions"
        )


async def fallback_skill_extraction(text: str, extraction_type: str) -> List[Dict[str, Any]]:
    """Fallback skill extraction using simple text processing"""
    import re

    # Common technical skills patterns
    tech_skills = [
        "Python", "Java", "JavaScript", "React", "Angular", "Vue.js", "Node.js",
        "AWS", "Docker", "Kubernetes", "Git", "SQL", "MongoDB", "PostgreSQL",
        "Machine Learning", "Data Analysis", "Project Management", "Agile",
        "Scrum", "Leadership", "Communication", "Problem Solving"
    ]

    found_skills = []
    text_lower = text.lower()

    for skill in tech_skills:
        if skill.lower() in text_lower:
            found_skills.append({
                "name": skill,
                "category": "general",
                "confidence": 0.7
            })

    return found_skills