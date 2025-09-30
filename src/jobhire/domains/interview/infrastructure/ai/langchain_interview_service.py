"""
LangChain-powered AI service for mock interviews with advanced accuracy.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
import structlog
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory import ConversationSummaryBufferMemory
from langchain.chains import ConversationChain, LLMChain
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from pydantic import BaseModel, Field

from jobhire.domains.interview.domain.value_objects.interview_config import (
    QuestionCategory, InterviewPersonality
)
from jobhire.domains.interview.domain.entities.interview_session import InterviewFeedback

logger = structlog.get_logger(__name__)


class QuestionGeneration(BaseModel):
    """Structured output for question generation."""
    questions: List[Dict[str, Any]] = Field(description="List of interview questions")
    reasoning: str = Field(description="Reasoning behind question selection")


class AnswerEvaluation(BaseModel):
    """Structured output for answer evaluation."""
    score: float = Field(description="Score from 0-100", ge=0, le=100)
    feedback: str = Field(description="Detailed feedback for the answer")
    strengths: List[str] = Field(description="Identified strengths in the answer")
    improvements: List[str] = Field(description="Areas for improvement")
    follows_star: bool = Field(description="Whether answer follows STAR method", default=False)


class InterviewAnalysis(BaseModel):
    """Structured output for interview analysis."""
    overall_score: float = Field(description="Overall interview score", ge=0, le=100)
    performance_level: str = Field(description="Performance level assessment")
    key_strengths: List[str] = Field(description="Top strengths identified")
    improvement_areas: List[str] = Field(description="Key areas for improvement")
    detailed_feedback: str = Field(description="Comprehensive feedback")
    recommendations: List[str] = Field(description="Specific recommendations")


class LangChainInterviewService:
    """LangChain-powered interview AI service for enhanced accuracy."""

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0.7,
            max_tokens=2000
        )
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=1000,
            return_messages=True
        )

        # Output parsers
        self.question_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=QuestionGeneration),
            llm=self.llm
        )
        self.evaluation_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=AnswerEvaluation),
            llm=self.llm
        )
        self.analysis_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=InterviewAnalysis),
            llm=self.llm
        )

    async def generate_welcome_message(
        self,
        job_description: str,
        ai_personality: str = "professional",
        candidate_name: Optional[str] = None
    ) -> str:
        """Generate personalized welcome message using LangChain."""
        try:
            welcome_prompt = ChatPromptTemplate.from_template("""
            As an expert AI interview coach with a {personality} personality, create a warm, personalized welcome message for a mock interview candidate.

            Job Description: {job_description}
            Candidate Name: {candidate_name}

            Generate a welcome message that:
            1. Greets the candidate appropriately for the {personality} style
            2. References specific aspects of the job description
            3. Sets clear expectations for the interview process
            4. Builds confidence and reduces anxiety
            5. Explains the structure (6-8 questions, feedback, etc.)

            Make it conversational and encouraging while maintaining professionalism.
            """)

            chain = LLMChain(llm=self.llm, prompt=welcome_prompt)

            response = await chain.arun(
                personality=ai_personality,
                job_description=job_description,
                candidate_name=candidate_name or "there"
            )

            return response.strip()

        except Exception as e:
            logger.error("Error generating welcome message with LangChain", error=str(e))
            return self._fallback_welcome_message(candidate_name)

    async def generate_questions_for_job(
        self,
        job_description: str,
        interview_type: str = "general",
        difficulty_level: str = "medium",
        total_questions: int = 8
    ) -> List[Dict[str, Any]]:
        """Generate intelligent interview questions using LangChain."""
        try:
            question_prompt = ChatPromptTemplate.from_template("""
            You are an expert technical recruiter and interview coach. Analyze this job description and generate {total_questions} highly relevant, insightful interview questions.

            Job Description:
            {job_description}

            Interview Type: {interview_type}
            Difficulty Level: {difficulty_level}

            Requirements:
            1. Mix behavioral (STAR method), technical, and situational questions
            2. Questions should be specific to the role and industry
            3. Include follow-up question templates
            4. Vary difficulty appropriately
            5. Focus on skills and experiences mentioned in the job description

            Categories to cover:
            - Behavioral/Experience (3-4 questions)
            - Technical Skills (2-3 questions)
            - Problem-solving/Situational (1-2 questions)
            - Motivation/Culture fit (1 question)

            For each question, provide:
            - id: unique identifier
            - question: the actual question text
            - category: question category
            - difficulty: easy/medium/hard
            - estimated_time_minutes: 3-6 minutes
            - follow_up_templates: 2-3 follow-up questions
            - reasoning: why this question is relevant

            {format_instructions}
            """)

            question_prompt = question_prompt.partial(
                format_instructions=self.question_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=question_prompt)

            response = await chain.arun(
                job_description=job_description,
                interview_type=interview_type,
                difficulty_level=difficulty_level,
                total_questions=total_questions
            )

            parsed_result = self.question_parser.parse(response)
            return parsed_result.questions[:total_questions]

        except Exception as e:
            logger.error("Error generating questions with LangChain", error=str(e))
            return self._fallback_questions(total_questions)

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        question_category: str,
        job_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate answer using LangChain with advanced analysis."""
        try:
            evaluation_prompt = ChatPromptTemplate.from_template("""
            You are an expert interview coach evaluating a candidate's response. Provide detailed, constructive feedback.

            Question: {question}
            Question Category: {question_category}
            Candidate's Answer: {answer}
            Job Context: {job_context}

            Evaluate the answer based on:
            1. Content quality and relevance
            2. Structure and clarity
            3. Specific examples and evidence
            4. STAR method usage (for behavioral questions)
            5. Technical accuracy (for technical questions)
            6. Communication skills

            Scoring Guidelines:
            - 90-100: Exceptional answer with specific examples, clear structure, perfect fit
            - 80-89: Strong answer with good examples and structure
            - 70-79: Good answer but missing some details or structure
            - 60-69: Adequate answer but lacks depth or examples
            - 50-59: Weak answer with minimal relevance or structure
            - Below 50: Poor answer with significant issues

            For behavioral questions, check if they follow STAR method:
            - Situation: Context and background
            - Task: What needed to be accomplished
            - Action: Specific steps taken
            - Result: Outcomes and impact

            {format_instructions}
            """)

            evaluation_prompt = evaluation_prompt.partial(
                format_instructions=self.evaluation_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=evaluation_prompt)

            response = await chain.arun(
                question=question,
                answer=answer,
                question_category=question_category,
                job_context=job_context or "General interview context"
            )

            parsed_result = self.evaluation_parser.parse(response)

            return {
                "score": parsed_result.score,
                "feedback": parsed_result.feedback,
                "strengths": parsed_result.strengths,
                "improvements": parsed_result.improvements,
                "follows_star": parsed_result.follows_star
            }

        except Exception as e:
            logger.error("Error evaluating answer with LangChain", error=str(e))
            return self._fallback_evaluation()

    async def generate_follow_up_question(
        self,
        original_question: str,
        answer: str,
        conversation_context: Optional[List[BaseMessage]] = None
    ) -> Optional[str]:
        """Generate intelligent follow-up questions using conversation context."""
        try:
            followup_prompt = ChatPromptTemplate.from_template("""
            Based on the candidate's answer, generate an intelligent follow-up question that:
            1. Probes deeper into their experience
            2. Seeks specific examples or outcomes
            3. Challenges them to think critically
            4. Maintains natural conversation flow

            Original Question: {original_question}
            Candidate's Answer: {answer}
            Conversation Context: {context}

            Generate ONE insightful follow-up question that would help assess the candidate further.
            If the answer is already comprehensive, return "NO_FOLLOWUP".
            """)

            chain = LLMChain(llm=self.llm, prompt=followup_prompt)

            context_str = ""
            if conversation_context:
                context_str = "\n".join([
                    f"{'Human' if isinstance(msg, HumanMessage) else 'AI'}: {msg.content}"
                    for msg in conversation_context[-4:]  # Last 4 messages
                ])

            response = await chain.arun(
                original_question=original_question,
                answer=answer,
                context=context_str
            )

            return None if "NO_FOLLOWUP" in response else response.strip()

        except Exception as e:
            logger.error("Error generating follow-up question", error=str(e))
            return None

    async def generate_final_feedback(
        self,
        questions_and_answers: List[Dict[str, Any]],
        answer_evaluations: List[Dict[str, Any]],
        job_description: str
    ) -> InterviewFeedback:
        """Generate comprehensive final feedback using LangChain analysis."""
        try:
            analysis_prompt = ChatPromptTemplate.from_template("""
            You are an expert interview coach providing comprehensive feedback for a mock interview.

            Job Description: {job_description}

            Questions and Answers:
            {qa_pairs}

            Individual Answer Evaluations:
            {evaluations}

            Provide a comprehensive analysis including:
            1. Overall performance assessment
            2. Key strengths demonstrated
            3. Critical improvement areas
            4. Specific recommendations for interview success
            5. Performance level (excellent/good/average/needs_improvement)

            Consider:
            - Consistency across answers
            - Use of STAR method for behavioral questions
            - Technical competency demonstration
            - Communication clarity
            - Cultural fit indicators
            - Areas where candidate excelled or struggled

            {format_instructions}
            """)

            analysis_prompt = analysis_prompt.partial(
                format_instructions=self.analysis_parser.get_format_instructions()
            )

            # Format Q&A pairs and evaluations
            qa_text = "\n".join([
                f"Q{i+1}: {qa['question']}\nA{i+1}: {qa.get('answer', 'No answer provided')}\n"
                for i, qa in enumerate(questions_and_answers)
            ])

            eval_text = "\n".join([
                f"Q{i+1} Score: {eval.get('score', 0)}/100 - {eval.get('feedback', 'No feedback')}"
                for i, eval in enumerate(answer_evaluations)
            ])

            chain = LLMChain(llm=self.llm, prompt=analysis_prompt)

            response = await chain.arun(
                job_description=job_description,
                qa_pairs=qa_text,
                evaluations=eval_text
            )

            parsed_result = self.analysis_parser.parse(response)

            # Calculate question scores
            question_scores = {}
            for i, evaluation in enumerate(answer_evaluations):
                question_scores[f"question_{i+1}"] = evaluation.get("score", 70)

            return InterviewFeedback(
                overall_score=parsed_result.overall_score,
                strengths=parsed_result.key_strengths,
                areas_for_improvement=parsed_result.improvement_areas,
                detailed_feedback=parsed_result.detailed_feedback,
                question_scores=question_scores,
                recommendations=parsed_result.recommendations,
                estimated_performance=parsed_result.performance_level
            )

        except Exception as e:
            logger.error("Error generating final feedback with LangChain", error=str(e))
            return self._fallback_feedback()

    async def maintain_conversation_context(
        self,
        question: str,
        answer: str
    ) -> None:
        """Maintain conversation context in memory."""
        try:
            self.memory.chat_memory.add_user_message(question)
            self.memory.chat_memory.add_ai_message(answer)
        except Exception as e:
            logger.error("Error maintaining conversation context", error=str(e))

    def _fallback_welcome_message(self, candidate_name: Optional[str]) -> str:
        """Fallback welcome message if LangChain fails."""
        name_part = f" {candidate_name}" if candidate_name else ""
        return f"""Hello{name_part}! I'm your AI interview coach.

I'll help you practice for your upcoming interview with personalized questions based on the job description you provided.

**What to expect:**
• 6-8 targeted questions
• Real-time feedback
• Detailed performance analysis

Are you ready to begin? Just say "yes" when ready!"""

    def _fallback_questions(self, total_questions: int) -> List[Dict[str, Any]]:
        """Fallback questions if LangChain generation fails."""
        questions = [
            {
                "id": "q_1",
                "question": "Tell me about yourself and your relevant experience.",
                "category": "behavioral",
                "difficulty": "medium",
                "estimated_time_minutes": 4,
                "follow_up_templates": ["What specific achievements are you most proud of?"]
            },
            {
                "id": "q_2",
                "question": "Why are you interested in this position?",
                "category": "motivation",
                "difficulty": "easy",
                "estimated_time_minutes": 3,
                "follow_up_templates": ["What aspects of the role excite you most?"]
            },
            {
                "id": "q_3",
                "question": "Describe a challenging project you worked on and how you handled it.",
                "category": "behavioral",
                "difficulty": "medium",
                "estimated_time_minutes": 5,
                "follow_up_templates": ["What would you do differently if you faced a similar situation again?"]
            },
            {
                "id": "q_4",
                "question": "What are your greatest strengths and how do they apply to this role?",
                "category": "strengths",
                "difficulty": "medium",
                "estimated_time_minutes": 4,
                "follow_up_templates": ["Can you give me a specific example of when you demonstrated this strength?"]
            }
        ]

        return questions[:total_questions]

    def _fallback_evaluation(self) -> Dict[str, Any]:
        """Fallback evaluation if LangChain fails."""
        return {
            "score": 75.0,
            "feedback": "Thank you for your response. Your answer shows relevant experience and good communication skills.",
            "strengths": ["Clear communication", "Relevant experience"],
            "improvements": ["Consider providing more specific examples", "Use the STAR method for behavioral questions"],
            "follows_star": False
        }

    def _fallback_feedback(self) -> InterviewFeedback:
        """Fallback feedback if LangChain fails."""
        return InterviewFeedback(
            overall_score=75.0,
            strengths=["Professional communication", "Relevant experience"],
            areas_for_improvement=["Provide more specific examples", "Practice STAR method"],
            detailed_feedback="Overall good performance. Focus on providing more detailed examples with specific outcomes and impacts.",
            question_scores={"question_1": 75.0, "question_2": 75.0, "question_3": 75.0, "question_4": 75.0},
            recommendations=[
                "Practice the STAR method for behavioral questions",
                "Prepare specific examples with quantified results",
                "Research the company and role thoroughly"
            ],
            estimated_performance="good"
        )