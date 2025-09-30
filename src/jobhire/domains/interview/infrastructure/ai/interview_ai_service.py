"""
AI service for mock interviews - question generation and feedback.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
import structlog

from jobhire.domains.interview.domain.value_objects.interview_config import (
    QuestionTemplate, QuestionCategory, InterviewPersonality, FeedbackCriteria,
    QUESTION_TEMPLATES, INTERVIEW_PERSONALITIES
)
from jobhire.domains.interview.domain.entities.interview_session import InterviewFeedback
from .langchain_interview_service import LangChainInterviewService
from .enhanced_langchain_service import EnhancedLangChainInterviewService

logger = structlog.get_logger(__name__)


class InterviewAIService:
    """AI service for conducting mock interviews with LangChain integration."""

    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key
        self.question_templates = QUESTION_TEMPLATES
        self.personalities = INTERVIEW_PERSONALITIES

        # Initialize Enhanced LangChain service if API key is available
        self.langchain_service = None
        self.enhanced_service = None
        if openai_api_key:
            try:
                # Try to initialize enhanced service first
                self.enhanced_service = EnhancedLangChainInterviewService(openai_api_key)
                logger.info("Enhanced LangChain interview service initialized successfully")
            except Exception as e:
                logger.warning("Failed to initialize enhanced service, trying standard LangChain", error=str(e))
                try:
                    self.langchain_service = LangChainInterviewService(openai_api_key)
                    logger.info("Standard LangChain interview service initialized successfully")
                except Exception as e2:
                    logger.warning("Failed to initialize LangChain service, falling back to basic service", error=str(e2))
                    self.langchain_service = None

    async def generate_welcome_message(
        self,
        job_description: str,
        ai_personality: str = "professional",
        candidate_name: Optional[str] = None
    ) -> str:
        """Generate personalized welcome message using LangChain if available."""
        # Use Enhanced LangChain service if available
        if self.enhanced_service:
            try:
                # Enhanced service uses job analysis for better welcome messages
                job_analysis = await self.enhanced_service.analyze_job_description(job_description)

                # Generate enhanced welcome message (we'll add this method)
                return await self._generate_enhanced_welcome_message(
                    job_analysis, ai_personality, candidate_name
                )
            except Exception as e:
                logger.warning("Enhanced service welcome message failed, trying standard", error=str(e))

        # Use standard LangChain service if available
        if self.langchain_service:
            try:
                return await self.langchain_service.generate_welcome_message(
                    job_description, ai_personality, candidate_name
                )
            except Exception as e:
                logger.warning("LangChain welcome message failed, falling back", error=str(e))

        # Fallback to original logic
        try:
            personality = self.personalities.get(ai_personality, self.personalities["professional"])

            # Extract key info from job description
            job_info = self._parse_job_description(job_description)

            if personality.tone == "friendly":
                greeting = f"Hi{' ' + candidate_name if candidate_name else ''}! 👋"
                intro = "I'm excited to help you practice for your upcoming interview!"
            elif personality.tone == "professional":
                greeting = f"Good day{' ' + candidate_name if candidate_name else ''}."
                intro = "I'll be conducting your mock interview today."
            else:
                greeting = f"Hello{' ' + candidate_name if candidate_name else ''}."
                intro = "Let's begin your interview preparation session."

            role_context = ""
            if job_info.get("title"):
                role_context = f" for the {job_info['title']} position"
                if job_info.get("company"):
                    role_context += f" at {job_info['company']}"

            return f"""{greeting}

{intro}{role_context}.

I've reviewed the job description you provided, and I'll be asking you questions that are relevant to this role. This session will help you practice your responses and build confidence for the real interview.

**What to expect:**
• 6-8 targeted questions based on the job requirements
• Mix of behavioral and technical questions
• Real-time feedback and suggestions
• Detailed performance analysis at the end

Feel free to answer naturally as you would in a real interview. Take your time to think through your responses.

Are you ready to begin? Just say "yes" or "let's start" when you're ready! 🚀"""

        except Exception as e:
            logger.error("Error generating welcome message", error=str(e))
            return """Hello! I'm your AI interview coach, and I'm here to help you practice for your upcoming interview.

I'll ask you relevant questions based on the job description you provided, and give you feedback to help you improve your interview skills.

Are you ready to begin? Just say "yes" when you're ready to start!"""

    async def generate_questions_for_job(
        self,
        job_description: str,
        interview_type: str = "general",
        difficulty_level: str = "medium",
        total_questions: int = 8
    ) -> List[Dict[str, Any]]:
        """Generate interview questions using LangChain if available."""
        # Use Enhanced LangChain service if available
        if self.enhanced_service:
            try:
                # First analyze the job description
                job_analysis = await self.enhanced_service.analyze_job_description(job_description)

                # Generate enhanced questions
                enhanced_result = await self.enhanced_service.generate_enhanced_questions(
                    job_analysis, interview_type, difficulty_level, total_questions
                )

                return enhanced_result.questions
            except Exception as e:
                logger.warning("Enhanced question generation failed, trying standard", error=str(e))

        # Use standard LangChain service if available
        if self.langchain_service:
            try:
                return await self.langchain_service.generate_questions_for_job(
                    job_description, interview_type, difficulty_level, total_questions
                )
            except Exception as e:
                logger.warning("LangChain question generation failed, falling back", error=str(e))

        # Fallback to original logic
        try:
            # Parse job description for key information
            job_info = self._parse_job_description(job_description)

            # Select appropriate question categories
            categories = self._select_question_categories(job_info, interview_type)

            # Generate questions using templates and AI
            questions = []
            questions_per_category = max(1, total_questions // len(categories))

            for i, category in enumerate(categories):
                if len(questions) >= total_questions:
                    break

                # Get templates for this category
                category_templates = [t for t in self.question_templates if t.category == category]

                if category_templates:
                    # Use template-based generation
                    template = category_templates[0]  # Use first template for now
                    question = self._generate_question_from_template(template, job_info)

                    questions.append({
                        "id": f"q_{i+1}",
                        "question": question,
                        "category": category.value,
                        "difficulty": difficulty_level,
                        "estimated_time_minutes": template.estimated_time_minutes,
                        "follow_up_templates": template.follow_up_templates or []
                    })
                else:
                    # Fallback to AI generation
                    question = await self._generate_ai_question(category, job_info, difficulty_level)
                    questions.append({
                        "id": f"q_{i+1}",
                        "question": question,
                        "category": category.value,
                        "difficulty": difficulty_level,
                        "estimated_time_minutes": 4
                    })

            # Add a few more general questions if needed
            while len(questions) < total_questions:
                general_questions = [
                    "What are your greatest strengths and how do they apply to this role?",
                    "Where do you see yourself in 5 years?",
                    "Why are you looking to leave your current position?",
                    "What questions do you have for us about the role or company?"
                ]

                q_index = len(questions) % len(general_questions)
                questions.append({
                    "id": f"q_{len(questions)+1}",
                    "question": general_questions[q_index],
                    "category": "general",
                    "difficulty": "medium",
                    "estimated_time_minutes": 3
                })

            return questions[:total_questions]

        except Exception as e:
            logger.error("Error generating questions", error=str(e))
            return self._get_fallback_questions(total_questions)

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        question_category: str,
        job_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate answer using LangChain if available."""
        # Use LangChain service if available
        if self.langchain_service:
            try:
                return await self.langchain_service.evaluate_answer(
                    question, answer, question_category, job_context
                )
            except Exception as e:
                logger.warning("LangChain answer evaluation failed, falling back", error=str(e))

        # Fallback to original logic
        try:
            # Simple evaluation logic (can be enhanced with actual AI)
            score = self._calculate_answer_score(answer, question_category)

            feedback = self._generate_answer_feedback(answer, question, question_category)

            return {
                "score": score,
                "feedback": feedback,
                "strengths": self._identify_answer_strengths(answer),
                "improvements": self._identify_answer_improvements(answer, question_category)
            }

        except Exception as e:
            logger.error("Error evaluating answer", error=str(e))
            return {
                "score": 70.0,
                "feedback": "Thank you for your response. Your answer demonstrates relevant experience.",
                "strengths": ["Clear communication"],
                "improvements": ["Consider providing more specific examples"]
            }

    async def generate_follow_up_question(
        self,
        original_question: str,
        answer: str,
        follow_up_templates: List[str]
    ) -> Optional[str]:
        """Generate follow-up question using LangChain if available."""
        # Use LangChain service if available
        if self.langchain_service:
            try:
                return await self.langchain_service.generate_follow_up_question(
                    original_question, answer
                )
            except Exception as e:
                logger.warning("LangChain follow-up generation failed, falling back", error=str(e))

        # Fallback to original logic
        try:
            if not follow_up_templates:
                return None

            # Simple logic to select appropriate follow-up
            if len(answer.split()) < 20:  # Short answer
                return "Could you elaborate on that with a specific example?"

            if "challenge" in answer.lower() or "difficult" in answer.lower():
                return "What would you do differently if faced with a similar situation again?"

            # Use first template as fallback
            return follow_up_templates[0] if follow_up_templates else None

        except Exception as e:
            logger.error("Error generating follow-up question", error=str(e))
            return None

    async def generate_final_feedback(
        self,
        questions_and_answers: List[Dict[str, Any]],
        answer_evaluations: List[Dict[str, Any]],
        job_description: str = ""
    ) -> InterviewFeedback:
        """Generate comprehensive feedback using LangChain if available."""
        # Use LangChain service if available
        if self.langchain_service:
            try:
                return await self.langchain_service.generate_final_feedback(
                    questions_and_answers, answer_evaluations, job_description
                )
            except Exception as e:
                logger.warning("LangChain final feedback failed, falling back", error=str(e))

        # Fallback to original logic
        try:
            # Calculate overall score
            if answer_evaluations:
                overall_score = sum(eval.get("score", 70) for eval in answer_evaluations) / len(answer_evaluations)
            else:
                overall_score = 70.0

            # Aggregate strengths and improvements
            all_strengths = []
            all_improvements = []

            for evaluation in answer_evaluations:
                all_strengths.extend(evaluation.get("strengths", []))
                all_improvements.extend(evaluation.get("improvements", []))

            # Remove duplicates and get top items
            unique_strengths = list(set(all_strengths))[:5]
            unique_improvements = list(set(all_improvements))[:5]

            # Generate detailed feedback
            detailed_feedback = self._generate_detailed_feedback(
                overall_score, questions_and_answers, answer_evaluations
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(overall_score, unique_improvements)

            # Determine performance level
            if overall_score >= 90:
                performance = "excellent"
            elif overall_score >= 80:
                performance = "good"
            elif overall_score >= 70:
                performance = "average"
            else:
                performance = "needs_improvement"

            # Create question scores
            question_scores = {}
            for i, evaluation in enumerate(answer_evaluations):
                question_scores[f"question_{i+1}"] = evaluation.get("score", 70)

            return InterviewFeedback(
                overall_score=overall_score,
                strengths=unique_strengths,
                areas_for_improvement=unique_improvements,
                detailed_feedback=detailed_feedback,
                question_scores=question_scores,
                recommendations=recommendations,
                estimated_performance=performance
            )

        except Exception as e:
            logger.error("Error generating final feedback", error=str(e))
            return self._get_fallback_feedback()

    def _parse_job_description(self, job_description: str) -> Dict[str, Any]:
        """Extract key information from job description."""
        info = {}

        # Extract job title (look for common patterns)
        title_patterns = [
            r'(?:job title|position|role):\s*([^\n]+)',
            r'(?:seeking|hiring)\s+(?:a\s+)?([^\n,]+?)(?:\s+to|\s+at|\s+with|\s*$)',
            r'^([^\n]+?)(?:\s+at\s+|\s+-\s+|\s*$)'
        ]

        for pattern in title_patterns:
            match = re.search(pattern, job_description, re.IGNORECASE | re.MULTILINE)
            if match:
                info["title"] = match.group(1).strip()
                break

        # Extract company name
        company_patterns = [
            r'(?:company|organization):\s*([^\n]+)',
            r'at\s+([A-Z][a-zA-Z\s&,.-]+?)(?:\s+we|\s+is|\s*$)',
            r'join\s+([A-Z][a-zA-Z\s&,.-]+?)(?:\s+as|\s+team|\s*$)'
        ]

        for pattern in company_patterns:
            match = re.search(pattern, job_description, re.IGNORECASE)
            if match:
                info["company"] = match.group(1).strip()
                break

        # Extract key skills/technologies
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'angular', 'node.js', 'aws', 'docker',
            'kubernetes', 'sql', 'mongodb', 'git', 'agile', 'scrum', 'api', 'rest',
            'microservices', 'machine learning', 'ai', 'data science', 'cloud'
        ]

        found_skills = []
        for skill in tech_keywords:
            if skill.lower() in job_description.lower():
                found_skills.append(skill)

        info["required_skills"] = found_skills

        # Extract experience level
        experience_patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'(?:senior|junior|mid-level|entry-level|lead)',
            r'experience:\s*(\d+)\+?\s*years?'
        ]

        for pattern in experience_patterns:
            match = re.search(pattern, job_description, re.IGNORECASE)
            if match:
                if match.group(1).isdigit():
                    info["experience_years"] = int(match.group(1))
                else:
                    info["experience_level"] = match.group(0).lower()
                break

        return info

    def _select_question_categories(
        self,
        job_info: Dict[str, Any],
        interview_type: str
    ) -> List[QuestionCategory]:
        """Select appropriate question categories based on job info."""
        categories = []

        # Always include behavioral questions
        categories.append(QuestionCategory.BEHAVIORAL)
        categories.append(QuestionCategory.EXPERIENCE)

        # Add technical if required skills are present
        if job_info.get("required_skills"):
            categories.append(QuestionCategory.TECHNICAL_SKILLS)
            categories.append(QuestionCategory.PROBLEM_SOLVING)

        # Add based on role level
        experience_years = job_info.get("experience_years", 0)
        if experience_years >= 5 or "senior" in str(job_info.get("experience_level", "")):
            categories.append(QuestionCategory.LEADERSHIP)

        # Add motivation and company fit
        categories.append(QuestionCategory.MOTIVATION)
        categories.append(QuestionCategory.STRENGTHS)

        # Limit to 6 categories max
        return categories[:6]

    def _generate_question_from_template(
        self,
        template: QuestionTemplate,
        job_info: Dict[str, Any]
    ) -> str:
        """Generate question from template with job-specific variables."""
        variables = {
            "job_title": job_info.get("title", "this position"),
            "company_name": job_info.get("company", "the company"),
            "company_context": job_info.get("company", "your previous workplace"),
            "role_type": "colleague",
            "project_context": "your projects",
            "technology": job_info.get("required_skills", ["technology"])[0] if job_info.get("required_skills") else "technology"
        }

        return template.generate_question(variables)

    async def _generate_ai_question(
        self,
        category: QuestionCategory,
        job_info: Dict[str, Any],
        difficulty: str
    ) -> str:
        """Generate AI-powered question for category."""
        # Fallback questions by category
        fallback_questions = {
            QuestionCategory.BEHAVIORAL: "Tell me about a time when you had to overcome a significant challenge at work.",
            QuestionCategory.TECHNICAL_SKILLS: "What technical skills do you bring to this role?",
            QuestionCategory.PROBLEM_SOLVING: "Describe a complex problem you solved and your approach.",
            QuestionCategory.LEADERSHIP: "Tell me about a time when you had to lead a team or project.",
            QuestionCategory.COMMUNICATION: "How do you handle difficult conversations with colleagues?",
            QuestionCategory.MOTIVATION: "What motivates you in your career?",
            QuestionCategory.STRENGTHS: "What are your greatest strengths?"
        }

        return fallback_questions.get(category, "Tell me about yourself and your experience.")

    def _calculate_answer_score(self, answer: str, category: str) -> float:
        """Calculate score for an answer."""
        # Simple scoring logic
        words = len(answer.split())

        base_score = 70.0

        # Length scoring
        if words > 100:
            base_score += 15
        elif words > 50:
            base_score += 10
        elif words > 20:
            base_score += 5
        elif words < 10:
            base_score -= 20

        # Keyword scoring
        positive_keywords = [
            'achieved', 'improved', 'led', 'managed', 'developed', 'created', 'increased',
            'successful', 'effective', 'efficiently', 'team', 'collaborate', 'solution'
        ]

        keyword_count = sum(1 for word in positive_keywords if word in answer.lower())
        base_score += keyword_count * 2

        # Cap at 100
        return min(100.0, max(10.0, base_score))

    def _generate_answer_feedback(self, answer: str, question: str, category: str) -> str:
        """Generate feedback for an answer."""
        words = len(answer.split())

        if words < 20:
            return "Your answer is quite brief. Consider providing more detail and specific examples to strengthen your response."
        elif words > 150:
            return "Good comprehensive answer! You might want to be more concise in a real interview setting."
        else:
            return "Well-structured response with good detail. Your examples help illustrate your points effectively."

    def _identify_answer_strengths(self, answer: str) -> List[str]:
        """Identify strengths in an answer."""
        strengths = []

        if len(answer.split()) > 50:
            strengths.append("Detailed response")

        if any(word in answer.lower() for word in ['example', 'instance', 'specifically']):
            strengths.append("Specific examples provided")

        if any(word in answer.lower() for word in ['result', 'outcome', 'achieved', 'improved']):
            strengths.append("Results-oriented")

        if any(word in answer.lower() for word in ['team', 'collaborate', 'together']):
            strengths.append("Team-focused approach")

        return strengths or ["Clear communication"]

    def _identify_answer_improvements(self, answer: str, category: str) -> List[str]:
        """Identify areas for improvement."""
        improvements = []

        if len(answer.split()) < 30:
            improvements.append("Provide more detailed examples")

        if not any(word in answer.lower() for word in ['result', 'outcome', 'impact']):
            improvements.append("Include specific results and outcomes")

        if category == "behavioral" and not any(word in answer.lower() for word in ['situation', 'action', 'result']):
            improvements.append("Use STAR method (Situation, Task, Action, Result)")

        return improvements or ["Consider adding more specific details"]

    def _generate_detailed_feedback(
        self,
        overall_score: float,
        questions_and_answers: List[Dict[str, Any]],
        evaluations: List[Dict[str, Any]]
    ) -> str:
        """Generate detailed feedback summary."""
        performance_level = "excellent" if overall_score >= 90 else "good" if overall_score >= 80 else "solid" if overall_score >= 70 else "developing"

        return f"""Overall, you demonstrated {performance_level} interview performance with a score of {overall_score:.1f}/100.

**Key Observations:**
• You answered {len(questions_and_answers)} questions with varying levels of detail
• Your responses showed good understanding of the role requirements
• Communication style was professional and clear

**Performance Highlights:**
• Strong examples and specific details in most responses
• Good grasp of technical concepts and industry knowledge
• Professional demeanor throughout the interview

**Areas to Focus On:**
• Practice the STAR method for behavioral questions
• Prepare more quantified examples of your achievements
• Work on concise yet comprehensive responses

This mock interview has prepared you well for your actual interview. Keep practicing these key areas!"""

    def _generate_recommendations(self, overall_score: float, improvements: List[str]) -> List[str]:
        """Generate specific recommendations."""
        recommendations = []

        if overall_score < 80:
            recommendations.append("Practice more behavioral questions using the STAR method")
            recommendations.append("Prepare specific examples with quantified results")

        if "detailed examples" in str(improvements):
            recommendations.append("Develop a bank of 5-7 detailed stories you can adapt to different questions")

        if "specific results" in str(improvements):
            recommendations.append("Quantify your achievements with numbers, percentages, or timelines")

        recommendations.extend([
            "Research the company and role thoroughly before your interview",
            "Prepare thoughtful questions to ask the interviewer",
            "Practice your responses out loud to improve delivery"
        ])

        return recommendations[:5]

    def _get_fallback_questions(self, total_questions: int) -> List[Dict[str, Any]]:
        """Get fallback questions if generation fails."""
        fallback = [
            "Tell me about yourself and your background.",
            "Why are you interested in this position?",
            "What are your greatest strengths?",
            "Describe a challenge you overcame at work.",
            "Where do you see yourself in 5 years?",
            "Why are you leaving your current role?",
            "What questions do you have for us?",
            "Tell me about a project you're proud of."
        ]

        questions = []
        for i in range(min(total_questions, len(fallback))):
            questions.append({
                "id": f"q_{i+1}",
                "question": fallback[i],
                "category": "general",
                "difficulty": "medium",
                "estimated_time_minutes": 4
            })

        return questions

    async def _generate_enhanced_welcome_message(
        self,
        job_analysis,
        ai_personality: str = "professional",
        candidate_name: Optional[str] = None
    ) -> str:
        """Generate enhanced welcome message using job analysis."""
        try:
            personality = self.personalities.get(ai_personality, self.personalities["professional"])

            if personality.tone == "friendly":
                greeting = f"Hi{' ' + candidate_name if candidate_name else ''}! 👋"
                intro = "I'm excited to help you practice for your upcoming interview!"
            elif personality.tone == "professional":
                greeting = f"Good day{' ' + candidate_name if candidate_name else ''}."
                intro = "I'll be conducting your mock interview today."
            else:
                greeting = f"Hello{' ' + candidate_name if candidate_name else ''}."
                intro = "Let's begin your interview preparation session."

            company_name = job_analysis.company_info.get("name", "the company")
            role_title = job_analysis.role_details.get("title", "this position")
            industry = job_analysis.industry_sector

            role_context = f" for the {role_title} position at {company_name}"
            if industry and industry != "technology":
                role_context += f" in the {industry} industry"

            skills_preview = ""
            if len(job_analysis.required_skills) > 0:
                top_skills = job_analysis.required_skills[:3]
                skills_preview = f"\n\nI'll be focusing on your experience with {', '.join(top_skills)} and related competencies."

            return f"""{greeting}

{intro}{role_context}.

I've analyzed the job description and will be asking you targeted questions that assess your fit for this specific role. This session will help you practice your responses and build confidence for the real interview.{skills_preview}

**What to expect:**
• 6-8 strategically selected questions based on the role requirements
• Mix of behavioral, technical, and situational questions
• Real-time feedback with industry-specific insights
• Detailed performance analysis with improvement suggestions

Feel free to answer naturally as you would in a real interview. Take your time to think through your responses and provide specific examples when possible.

Are you ready to begin? Just say "yes" or "let's start" when you're ready! 🚀"""

        except Exception as e:
            logger.error("Error generating enhanced welcome message", error=str(e))
            return f"""Hello{' ' + candidate_name if candidate_name else ''}! I'm your AI interview coach.

I'll help you practice for your upcoming interview with personalized questions based on the job description you provided.

Are you ready to begin? Just say "yes" when ready!"""

    def _get_fallback_feedback(self) -> InterviewFeedback:
        """Get fallback feedback if generation fails."""
        return InterviewFeedback(
            overall_score=75.0,
            strengths=["Clear communication", "Professional demeanor"],
            areas_for_improvement=["Provide more specific examples", "Practice the STAR method"],
            detailed_feedback="You demonstrated good interview skills overall. Continue practicing with specific examples to enhance your responses.",
            question_scores={"question_1": 75.0, "question_2": 75.0},
            recommendations=[
                "Practice behavioral questions using the STAR method",
                "Prepare specific examples with quantified results",
                "Research the company thoroughly before interviews"
            ],
            estimated_performance="good"
        )