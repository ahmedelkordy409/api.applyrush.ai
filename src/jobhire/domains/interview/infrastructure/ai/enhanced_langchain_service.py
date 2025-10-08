"""
Enhanced LangChain-powered AI service for maximum interview accuracy.
Includes advanced conversation memory, industry-specific analysis, and sophisticated scoring.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
import structlog
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.memory import ConversationSummaryBufferMemory, ConversationBufferWindowMemory
from langchain.chains import ConversationChain, LLMChain, SequentialChain
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import re
from datetime import datetime

from jobhire.domains.interview.domain.value_objects.interview_config import (
    QuestionCategory, InterviewPersonality
)
from jobhire.domains.interview.domain.entities.interview_session import InterviewFeedback

logger = structlog.get_logger(__name__)


class JobAnalysis(BaseModel):
    """Comprehensive job description analysis."""
    company_info: Dict[str, str] = Field(description="Company details extracted")
    role_details: Dict[str, Any] = Field(description="Role-specific information")
    required_skills: List[str] = Field(description="Technical and soft skills required")
    experience_level: str = Field(description="Experience level category")
    industry_sector: str = Field(description="Industry sector identification")
    compensation_range: Optional[str] = Field(description="Salary/compensation if mentioned")
    key_responsibilities: List[str] = Field(description="Main job responsibilities")
    culture_indicators: List[str] = Field(description="Company culture indicators")


class EnhancedQuestionGeneration(BaseModel):
    """Enhanced question generation with detailed reasoning."""
    questions: List[Dict[str, Any]] = Field(description="Generated interview questions")
    job_analysis: JobAnalysis = Field(description="Comprehensive job analysis")
    question_strategy: str = Field(description="Strategy used for question selection")
    difficulty_reasoning: str = Field(description="Reasoning for difficulty level")


class STARAnalysis(BaseModel):
    """STAR method analysis for behavioral questions."""
    has_situation: bool = Field(description="Contains situation context")
    has_task: bool = Field(description="Describes task or objective")
    has_action: bool = Field(description="Details specific actions taken")
    has_result: bool = Field(description="Provides measurable results")
    star_score: float = Field(description="STAR completeness score 0-100", ge=0, le=100)
    missing_elements: List[str] = Field(description="Missing STAR components")
    suggestions: List[str] = Field(description="Specific suggestions to improve")


class TechnicalAssessment(BaseModel):
    """Technical answer assessment."""
    technical_accuracy: float = Field(description="Technical accuracy score", ge=0, le=100)
    depth_of_knowledge: float = Field(description="Knowledge depth score", ge=0, le=100)
    practical_application: float = Field(description="Practical application score", ge=0, le=100)
    industry_relevance: float = Field(description="Industry relevance score", ge=0, le=100)
    technical_gaps: List[str] = Field(description="Identified knowledge gaps")
    strong_areas: List[str] = Field(description="Areas of technical strength")


class EnhancedAnswerEvaluation(BaseModel):
    """Comprehensive answer evaluation."""
    overall_score: float = Field(description="Overall answer score", ge=0, le=100)
    communication_score: float = Field(description="Communication clarity score", ge=0, le=100)
    content_score: float = Field(description="Content quality score", ge=0, le=100)
    star_analysis: Optional[STARAnalysis] = Field(description="STAR method analysis if applicable")
    technical_assessment: Optional[TechnicalAssessment] = Field(description="Technical assessment if applicable")
    feedback: str = Field(description="Detailed personalized feedback")
    strengths: List[str] = Field(description="Key strengths identified")
    improvements: List[str] = Field(description="Specific improvement suggestions")
    industry_insights: List[str] = Field(description="Industry-specific insights")
    follow_up_suggestions: List[str] = Field(description="Suggested follow-up questions")


class InterviewStrategy(BaseModel):
    """Interview strategy and flow management."""
    next_question_type: str = Field(description="Recommended next question type")
    difficulty_adjustment: str = Field(description="Suggested difficulty adjustment")
    focus_areas: List[str] = Field(description="Areas to focus on next")
    interview_flow_rating: float = Field(description="Interview flow quality", ge=0, le=100)
    strategic_recommendations: List[str] = Field(description="Strategic interview recommendations")


class EnhancedLangChainInterviewService:
    """Enhanced LangChain service with maximum accuracy and intelligence."""

    def __init__(self, openai_api_key: str, model: str = "gpt-4o"):
        # Use GPT-4o for maximum accuracy
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=3000
        )

        # Enhanced memory management
        self.conversation_memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=2000,
            return_messages=True,
            memory_key="chat_history"
        )

        # Detailed conversation tracking
        self.detailed_memory = ConversationBufferWindowMemory(
            k=10,  # Keep last 10 exchanges
            return_messages=True,
            memory_key="recent_history"
        )

        # Enhanced output parsers
        self.job_analysis_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=JobAnalysis),
            llm=self.llm
        )
        self.question_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=EnhancedQuestionGeneration),
            llm=self.llm
        )
        self.evaluation_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=EnhancedAnswerEvaluation),
            llm=self.llm
        )
        self.strategy_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=InterviewStrategy),
            llm=self.llm
        )

        # Interview session context
        self.session_context = {}

    async def analyze_job_description(self, job_description: str) -> JobAnalysis:
        """Comprehensive job description analysis."""
        try:
            analysis_prompt = ChatPromptTemplate.from_template("""
            As an expert recruiter and job market analyst, perform a comprehensive analysis of this job description.

            Job Description:
            {job_description}

            Analyze and extract:
            1. Company information (name, size, industry, culture indicators)
            2. Role details (title, level, department, reporting structure)
            3. Required skills (technical, soft, certifications)
            4. Experience level and years required
            5. Industry sector and domain
            6. Compensation information if mentioned
            7. Key responsibilities and deliverables
            8. Company culture and values indicators

            Be thorough and extract nuanced details that would help create highly relevant interview questions.

            {format_instructions}
            """)

            analysis_prompt = analysis_prompt.partial(
                format_instructions=self.job_analysis_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=analysis_prompt)
            response = await chain.arun(job_description=job_description)

            return self.job_analysis_parser.parse(response)

        except Exception as e:
            logger.error("Error in job analysis", error=str(e))
            return JobAnalysis(
                company_info={"name": "Unknown Company"},
                role_details={"title": "Software Engineer"},
                required_skills=["Problem solving", "Communication"],
                experience_level="mid-level",
                industry_sector="technology",
                key_responsibilities=["Software development"],
                culture_indicators=["Team collaboration"]
            )

    async def generate_enhanced_questions(
        self,
        job_analysis: JobAnalysis,
        interview_type: str = "general",
        difficulty_level: str = "medium",
        total_questions: int = 8,
        session_context: Optional[Dict] = None
    ) -> EnhancedQuestionGeneration:
        """Generate highly targeted interview questions with advanced analysis."""
        try:
            question_prompt = ChatPromptTemplate.from_template("""
            As an expert interview coach and recruiter with deep knowledge of {industry_sector} industry,
            generate {total_questions} highly strategic interview questions.

            Job Analysis:
            Company: {company_name} in {industry_sector}
            Role: {role_title} ({experience_level})
            Key Skills: {required_skills}
            Responsibilities: {responsibilities}
            Culture: {culture_indicators}

            Interview Parameters:
            - Type: {interview_type}
            - Difficulty: {difficulty_level}
            - Session Context: {session_context}

            Question Generation Strategy:
            1. Create questions that directly assess the required skills
            2. Include behavioral questions that reveal cultural fit
            3. Add technical questions that test practical application
            4. Design scenarios that mirror actual job challenges
            5. Include questions that assess growth potential

            For each question, provide:
            - Strategic reasoning for why this question is crucial
            - Expected answer depth and quality indicators
            - Follow-up question possibilities
            - Assessment criteria specific to this role

            Question Categories to include:
            - Technical/Skills Assessment (40%)
            - Behavioral/Experience (30%)
            - Problem-solving/Scenarios (20%)
            - Culture/Motivation Fit (10%)

            Make questions industry-specific and role-appropriate. Avoid generic questions.

            {format_instructions}
            """)

            question_prompt = question_prompt.partial(
                format_instructions=self.question_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=question_prompt)

            response = await chain.arun(
                industry_sector=job_analysis.industry_sector,
                company_name=job_analysis.company_info.get("name", "the company"),
                role_title=job_analysis.role_details.get("title", "this position"),
                experience_level=job_analysis.experience_level,
                required_skills=", ".join(job_analysis.required_skills),
                responsibilities=", ".join(job_analysis.key_responsibilities),
                culture_indicators=", ".join(job_analysis.culture_indicators),
                interview_type=interview_type,
                difficulty_level=difficulty_level,
                total_questions=total_questions,
                session_context=str(session_context or {})
            )

            return self.question_parser.parse(response)

        except Exception as e:
            logger.error("Error generating enhanced questions", error=str(e))
            # Fallback to basic questions
            return EnhancedQuestionGeneration(
                questions=self._generate_fallback_questions(total_questions),
                job_analysis=job_analysis,
                question_strategy="fallback_basic_questions",
                difficulty_reasoning="Generated due to processing error"
            )

    async def evaluate_answer_enhanced(
        self,
        question: str,
        answer: str,
        question_category: str,
        job_analysis: JobAnalysis,
        conversation_history: Optional[List[BaseMessage]] = None
    ) -> EnhancedAnswerEvaluation:
        """Enhanced answer evaluation with comprehensive analysis."""
        try:
            evaluation_prompt = ChatPromptTemplate.from_template("""
            As an expert interview assessor specializing in {industry_sector}, evaluate this candidate's response
            with precision and provide actionable feedback.

            Interview Context:
            Company: {company_name}
            Role: {role_title} ({experience_level})
            Required Skills: {required_skills}
            Industry: {industry_sector}

            Question Details:
            Category: {question_category}
            Question: {question}

            Candidate's Answer:
            {answer}

            Conversation History:
            {conversation_history}

            Comprehensive Evaluation Framework:

            1. OVERALL SCORING (0-100):
            - Content Quality: Relevance, depth, accuracy
            - Communication: Clarity, structure, confidence
            - Industry Knowledge: Sector-specific insights
            - Role Alignment: Fit for this specific position

            2. BEHAVIORAL QUESTIONS (if applicable):
            Assess STAR Method Completeness:
            - Situation: Clear context and background
            - Task: Specific objective or challenge
            - Action: Detailed steps taken by candidate
            - Result: Measurable outcomes and impact

            3. TECHNICAL QUESTIONS (if applicable):
            - Technical Accuracy: Correctness of information
            - Depth of Knowledge: Understanding level
            - Practical Application: Real-world application
            - Industry Standards: Adherence to best practices

            4. INDUSTRY-SPECIFIC INSIGHTS:
            - Provide insights specific to {industry_sector}
            - Reference current industry trends and challenges
            - Assess candidate's market awareness

            5. IMPROVEMENT RECOMMENDATIONS:
            - Specific, actionable suggestions
            - Examples of better responses
            - Skills to develop further

            6. FOLLOW-UP SUGGESTIONS:
            - Natural follow-up questions based on this answer
            - Areas to probe deeper
            - Clarification questions

            Be thorough, fair, and constructive in your assessment.

            {format_instructions}
            """)

            evaluation_prompt = evaluation_prompt.partial(
                format_instructions=self.evaluation_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=evaluation_prompt)

            # Format conversation history
            history_text = ""
            if conversation_history:
                history_text = "\n".join([
                    f"{'Human' if isinstance(msg, HumanMessage) else 'AI'}: {msg.content}"
                    for msg in conversation_history[-6:]  # Last 6 messages
                ])

            response = await chain.arun(
                industry_sector=job_analysis.industry_sector,
                company_name=job_analysis.company_info.get("name", "the company"),
                role_title=job_analysis.role_details.get("title", "this position"),
                experience_level=job_analysis.experience_level,
                required_skills=", ".join(job_analysis.required_skills),
                question_category=question_category,
                question=question,
                answer=answer,
                conversation_history=history_text
            )

            result = self.evaluation_parser.parse(response)

            # Store in conversation memory
            self.conversation_memory.chat_memory.add_user_message(f"Q: {question}")
            self.conversation_memory.chat_memory.add_ai_message(f"A: {answer}")
            self.detailed_memory.chat_memory.add_user_message(f"Q: {question}")
            self.detailed_memory.chat_memory.add_ai_message(f"A: {answer}")

            return result

        except Exception as e:
            logger.error("Error in enhanced answer evaluation", error=str(e))
            return self._fallback_evaluation()

    async def generate_intelligent_follow_up(
        self,
        original_question: str,
        answer: str,
        evaluation: EnhancedAnswerEvaluation,
        job_analysis: JobAnalysis
    ) -> Optional[str]:
        """Generate intelligent follow-up questions based on answer analysis."""
        try:
            # Use evaluation suggestions if available
            if evaluation.follow_up_suggestions:
                return evaluation.follow_up_suggestions[0]

            followup_prompt = ChatPromptTemplate.from_template("""
            Based on the candidate's response, generate a strategic follow-up question that:

            1. Probes deeper into their experience
            2. Seeks specific examples or metrics
            3. Challenges critical thinking
            4. Assesses problem-solving approach
            5. Maintains natural conversation flow

            Original Question: {original_question}
            Candidate's Answer: {answer}
            Answer Score: {score}/100
            Key Strengths: {strengths}
            Areas to Improve: {improvements}

            Job Context:
            Role: {role_title}
            Industry: {industry_sector}
            Required Skills: {required_skills}

            Generate ONE insightful follow-up question. If the answer is already comprehensive
            and further questioning would be redundant, return "COMPLETE".

            Focus on areas where the candidate can demonstrate deeper expertise or clarify gaps.
            """)

            chain = LLMChain(llm=self.llm, prompt=followup_prompt)

            response = await chain.arun(
                original_question=original_question,
                answer=answer,
                score=evaluation.overall_score,
                strengths=", ".join(evaluation.strengths),
                improvements=", ".join(evaluation.improvements),
                role_title=job_analysis.role_details.get("title", "this position"),
                industry_sector=job_analysis.industry_sector,
                required_skills=", ".join(job_analysis.required_skills)
            )

            return None if "COMPLETE" in response else response.strip()

        except Exception as e:
            logger.error("Error generating intelligent follow-up", error=str(e))
            return None

    async def generate_interview_strategy(
        self,
        question_responses: List[Dict[str, Any]],
        job_analysis: JobAnalysis,
        remaining_questions: int
    ) -> InterviewStrategy:
        """Generate strategic recommendations for interview continuation."""
        try:
            strategy_prompt = ChatPromptTemplate.from_template("""
            As an expert interview strategist, analyze the interview progress and provide strategic guidance.

            Job Context:
            Role: {role_title}
            Industry: {industry_sector}
            Experience Level: {experience_level}
            Required Skills: {required_skills}

            Interview Progress:
            Questions Asked: {questions_asked}
            Average Score: {average_score}
            Remaining Questions: {remaining_questions}

            Answer Quality Summary:
            {answer_summary}

            Provide strategic recommendations for:
            1. Next question type to focus on
            2. Difficulty adjustment needs
            3. Key areas still to explore
            4. Interview flow quality assessment
            5. Strategic recommendations for remaining questions

            Consider the candidate's performance pattern and optimize the remaining interview time.

            {format_instructions}
            """)

            strategy_prompt = strategy_prompt.partial(
                format_instructions=self.strategy_parser.get_format_instructions()
            )

            # Calculate statistics
            scores = [resp.get("score", 70) for resp in question_responses]
            average_score = sum(scores) / len(scores) if scores else 70

            answer_summary = "\n".join([
                f"Q{i+1}: {resp.get('question', 'Unknown')} - Score: {resp.get('score', 70)}"
                for i, resp in enumerate(question_responses)
            ])

            chain = LLMChain(llm=self.llm, prompt=strategy_prompt)

            response = await chain.arun(
                role_title=job_analysis.role_details.get("title", "this position"),
                industry_sector=job_analysis.industry_sector,
                experience_level=job_analysis.experience_level,
                required_skills=", ".join(job_analysis.required_skills),
                questions_asked=len(question_responses),
                average_score=average_score,
                remaining_questions=remaining_questions,
                answer_summary=answer_summary
            )

            return self.strategy_parser.parse(response)

        except Exception as e:
            logger.error("Error generating interview strategy", error=str(e))
            return InterviewStrategy(
                next_question_type="behavioral",
                difficulty_adjustment="maintain",
                focus_areas=["communication", "technical skills"],
                interview_flow_rating=75.0,
                strategic_recommendations=["Continue with planned questions"]
            )

    def _generate_fallback_questions(self, total_questions: int) -> List[Dict[str, Any]]:
        """Enhanced fallback questions."""
        questions = [
            {
                "id": "q_1",
                "question": "Walk me through your professional journey and what led you to apply for this role.",
                "category": "experience",
                "difficulty": "medium",
                "estimated_time_minutes": 4,
                "reasoning": "Establishes baseline and motivation"
            },
            {
                "id": "q_2",
                "question": "Describe a complex technical challenge you faced and your approach to solving it.",
                "category": "problem_solving",
                "difficulty": "medium",
                "estimated_time_minutes": 5,
                "reasoning": "Assesses problem-solving methodology"
            },
            {
                "id": "q_3",
                "question": "Tell me about a time when you had to work with a difficult team member. How did you handle it?",
                "category": "behavioral",
                "difficulty": "medium",
                "estimated_time_minutes": 4,
                "reasoning": "Tests interpersonal skills and conflict resolution"
            },
            {
                "id": "q_4",
                "question": "What technologies or skills are you most excited to develop in your next role?",
                "category": "motivation",
                "difficulty": "easy",
                "estimated_time_minutes": 3,
                "reasoning": "Assesses growth mindset and alignment"
            }
        ]
        return questions[:total_questions]

    def _fallback_evaluation(self) -> EnhancedAnswerEvaluation:
        """Enhanced fallback evaluation."""
        return EnhancedAnswerEvaluation(
            overall_score=75.0,
            communication_score=75.0,
            content_score=75.0,
            feedback="Thank you for your response. Your answer demonstrates relevant experience and clear communication.",
            strengths=["Clear communication", "Relevant experience"],
            improvements=["Consider providing more specific examples", "Include measurable outcomes"],
            industry_insights=["Focus on current industry trends", "Highlight technical proficiency"],
            follow_up_suggestions=["Can you provide more specific metrics or outcomes?"]
        )