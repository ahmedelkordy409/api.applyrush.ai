"""
AI Client Service
Handles integration with OpenAI and other AI services
"""

import openai
from typing import Dict, List, Any, Optional
import logging
import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    """AI client for handling OpenAI and other AI service integrations"""

    def __init__(self):
        self.openai_client = None
        if settings.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI API key not configured")

    async def generate_text(self, prompt: str, model: str = "gpt-4", max_tokens: int = 1500, temperature: float = 0.7) -> Optional[str]:
        """Generate text using OpenAI's GPT models"""
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return None

        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )

            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content

            return None

        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {str(e)}")
            return None

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        max_tokens: int = 800,
        temperature: float = 0
    ) -> Optional[str]:
        """Generate chat completion using OpenAI's chat models"""
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return None

        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content

            return None

        except Exception as e:
            logger.error(f"Error generating chat completion with OpenAI: {str(e)}")
            return None

    async def generate_cover_letter(
        self,
        candidate_info: Dict[str, Any],
        job_details: str,
        writing_style: str = "professional"
    ) -> Optional[str]:
        """Generate a personalized cover letter"""
        prompt = f"""You are a professional career coach and expert cover letter writer. Write compelling, personalized cover letters that help candidates stand out.

Write a professional cover letter for the following job application:

CANDIDATE INFORMATION:
- Name: {candidate_info.get('fullName', 'N/A')}
- Location: {candidate_info.get('city', 'N/A')}
- Email: {candidate_info.get('emailAddress', 'N/A')}
- Phone: {candidate_info.get('phoneNumber', 'N/A')}
- Desired Position: {candidate_info.get('desiredPosition', 'N/A')}
- Target Company: {candidate_info.get('companyName', 'N/A')}
- Writing Style: {writing_style}

JOB DETAILS:
{job_details}

REQUIREMENTS:
1. Keep it professional and concise (3-4 paragraphs, 250-400 words)
2. Start with "Dear Hiring Manager,"
3. Highlight relevant experience and skills based on job requirements
4. Show enthusiasm for the role and company
5. Include a strong opening and closing
6. Customize for this specific position and company
7. Do not include placeholders or [brackets]
8. Make it personal and engaging
9. End with "Sincerely," followed by the candidate's name
10. Return ONLY the cover letter text, no extra formatting or explanations"""

        return await self.generate_text(prompt, model="gpt-4", max_tokens=1500, temperature=0.7)

    async def analyze_job_fit(self, user_profile: Dict[str, Any], job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze how well a user fits a job using AI"""
        prompt = f"""Analyze the job fit between this candidate and job posting. Provide a detailed assessment.

CANDIDATE PROFILE:
{user_profile}

JOB POSTING:
{job_data}

Provide your analysis in the following JSON format:
{{
  "overall_score": 85,
  "fit_percentage": 85,
  "strengths": ["List of candidate strengths relevant to the job"],
  "weaknesses": ["Areas where candidate may be lacking"],
  "matched_skills": ["Skills that match job requirements"],
  "missing_skills": ["Required skills candidate doesn't have"],
  "recommendations": ["Suggestions for improving fit"],
  "confidence_level": "high|medium|low"
}}"""

        response = await self.generate_text(prompt, model="gpt-4", max_tokens=1000, temperature=0.3)

        if response:
            try:
                import json
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error("Failed to parse AI job fit analysis as JSON")
                return None

        return None

    async def generate_interview_questions(self, job_description: str, role_level: str = "mid") -> Optional[List[str]]:
        """Generate interview questions for a specific job"""
        prompt = f"""Generate {10 if role_level == 'senior' else 8} relevant interview questions for this job posting:

JOB DESCRIPTION:
{job_description}

ROLE LEVEL: {role_level}

Requirements:
1. Mix of technical, behavioral, and situational questions
2. Questions should be specific to the role and industry
3. Vary difficulty based on role level
4. Return as a JSON array of question strings
5. Each question should be clear and actionable

Format: ["Question 1", "Question 2", ...]"""

        response = await self.generate_text(prompt, model="gpt-4", max_tokens=800, temperature=0.5)

        if response:
            try:
                import json
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error("Failed to parse AI interview questions as JSON")
                return None

        return None


# Global AI client instance
_ai_client = None


def get_ai_client() -> AIClient:
    """Get the global AI client instance"""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client


async def initialize_ai_client():
    """Initialize the AI client"""
    global _ai_client
    _ai_client = AIClient()
    logger.info("AI client initialized")


async def shutdown_ai_client():
    """Shutdown the AI client"""
    global _ai_client
    if _ai_client and _ai_client.openai_client:
        await _ai_client.openai_client.close()
    _ai_client = None
    logger.info("AI client shutdown")