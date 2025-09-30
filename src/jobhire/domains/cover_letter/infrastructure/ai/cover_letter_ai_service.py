"""
AI service for cover letter generation using LangChain and GPT-4o.
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
import structlog
from datetime import datetime
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from pydantic import BaseModel, Field

from ...domain.value_objects.cover_letter_config import (
    WritingStyle, WRITING_STYLE_TEMPLATES, CoverLetterLength,
    COVER_LETTER_TEMPLATES, CoverLetterTemplate
)

logger = structlog.get_logger(__name__)


class JobAnalysis(BaseModel):
    """Job description analysis for cover letter optimization."""
    company_details: Dict[str, str] = Field(description="Company information extracted")
    role_requirements: List[str] = Field(description="Key job requirements")
    required_skills: List[str] = Field(description="Technical and soft skills needed")
    experience_level: str = Field(description="Required experience level")
    industry_sector: str = Field(description="Industry classification")
    company_culture: List[str] = Field(description="Company culture indicators")
    key_responsibilities: List[str] = Field(description="Main job responsibilities")
    preferred_qualifications: List[str] = Field(description="Nice-to-have qualifications")
    compensation_info: Optional[str] = Field(description="Salary/benefits if mentioned")


class CoverLetterGeneration(BaseModel):
    """Structured output for cover letter generation."""
    cover_letter_content: str = Field(description="Generated cover letter text")
    word_count: int = Field(description="Number of words in the letter")
    paragraph_count: int = Field(description="Number of paragraphs")
    key_highlights: List[str] = Field(description="Key points emphasized in the letter")
    confidence_score: float = Field(description="AI confidence in generation quality", ge=0, le=100)
    keyword_matches: List[str] = Field(description="Job description keywords included")
    tone_analysis: str = Field(description="Analysis of achieved tone")
    improvement_suggestions: List[str] = Field(description="Suggestions for improvement")


class CoverLetterQualityAssessment(BaseModel):
    """Quality assessment of generated cover letter."""
    overall_score: float = Field(description="Overall quality score", ge=0, le=100)
    readability_score: float = Field(description="Readability assessment", ge=0, le=100)
    keyword_relevance: float = Field(description="Job keyword relevance", ge=0, le=100)
    tone_consistency: float = Field(description="Tone consistency score", ge=0, le=100)
    structure_quality: float = Field(description="Letter structure quality", ge=0, le=100)
    uniqueness_score: float = Field(description="Content uniqueness", ge=0, le=100)
    strengths: List[str] = Field(description="Identified strengths")
    weaknesses: List[str] = Field(description="Areas for improvement")
    recommendations: List[str] = Field(description="Specific improvement recommendations")


class CoverLetterAIService:
    """AI service for intelligent cover letter generation."""

    def __init__(self, openai_api_key: str, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0.7,  # Balance creativity with consistency
            max_tokens=2000
        )

        # Output parsers
        self.job_analysis_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=JobAnalysis),
            llm=self.llm
        )
        self.generation_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=CoverLetterGeneration),
            llm=self.llm
        )
        self.quality_parser = OutputFixingParser.from_llm(
            parser=PydanticOutputParser(pydantic_object=CoverLetterQualityAssessment),
            llm=self.llm
        )

    async def analyze_job_description(self, job_description: str, company_name: str) -> JobAnalysis:
        """Analyze job description for targeted cover letter generation."""
        try:
            analysis_prompt = ChatPromptTemplate.from_template("""
            As an expert HR analyst and career coach, perform a comprehensive analysis of this job posting
            to optimize cover letter generation.

            Company: {company_name}
            Job Description:
            {job_description}

            Analyze and extract:
            1. Company details (size, industry, culture, values, recent news)
            2. Essential role requirements (must-have qualifications)
            3. Required skills (technical, soft, certifications)
            4. Experience level and years required
            5. Industry sector and domain expertise needed
            6. Company culture indicators and work environment
            7. Key job responsibilities and deliverables
            8. Preferred/nice-to-have qualifications
            9. Compensation and benefits information if mentioned

            Focus on details that would help create a highly targeted, relevant cover letter
            that demonstrates clear alignment between candidate and role.

            {format_instructions}
            """)

            analysis_prompt = analysis_prompt.partial(
                format_instructions=self.job_analysis_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=analysis_prompt)
            response = await chain.arun(
                company_name=company_name,
                job_description=job_description
            )

            return self.job_analysis_parser.parse(response)

        except Exception as e:
            logger.error("Error analyzing job description", error=str(e))
            return self._fallback_job_analysis(company_name)

    async def generate_cover_letter(
        self,
        personal_info: Dict[str, str],
        job_analysis: JobAnalysis,
        writing_style: WritingStyle,
        length: str = "medium",
        tone: str = "professional",
        focus_areas: Optional[List[str]] = None,
        custom_instructions: Optional[str] = None
    ) -> CoverLetterGeneration:
        """Generate AI-powered cover letter."""
        try:
            # Get style template
            style_template = WRITING_STYLE_TEMPLATES.get(writing_style)
            if not style_template:
                style_template = WRITING_STYLE_TEMPLATES[WritingStyle.PROFESSIONAL]

            # Determine target word count
            word_count_targets = {
                "short": (150, 250),
                "medium": (250, 400),
                "long": (400, 600)
            }
            min_words, max_words = word_count_targets.get(length, (250, 400))

            generation_prompt = ChatPromptTemplate.from_template("""
            You are an expert cover letter writer and career coach. Create a compelling,
            personalized cover letter that will help the candidate stand out.

            CANDIDATE INFORMATION:
            Name: {full_name}
            Email: {email_address}
            Phone: {phone_number}
            Location: {city}

            JOB CONTEXT:
            Position: {desired_position}
            Company: {company_name}
            Industry: {industry_sector}
            Experience Level: {experience_level}

            COMPANY ANALYSIS:
            Company Details: {company_details}
            Required Skills: {required_skills}
            Key Responsibilities: {key_responsibilities}
            Company Culture: {company_culture}
            Role Requirements: {role_requirements}

            WRITING SPECIFICATIONS:
            Style: {writing_style}
            Tone: {tone}
            Length: {length} ({min_words}-{max_words} words)
            Focus Areas: {focus_areas}

            STYLE GUIDANCE:
            {style_guidance}
            Tone Descriptors: {tone_descriptors}
            Sample Phrases: {sample_phrases}

            CUSTOM INSTRUCTIONS:
            {custom_instructions}

            COVER LETTER REQUIREMENTS:
            1. Professional header with candidate contact information
            2. Proper business letter format with date and recipient
            3. Compelling opening that captures attention
            4. Body paragraphs that demonstrate clear job fit
            5. Specific examples that align with job requirements
            6. Quantified achievements when possible
            7. Genuine enthusiasm for the role and company
            8. Professional closing with clear call to action
            9. Appropriate sign-off

            CONTENT GUIDELINES:
            - Be specific and relevant to this exact role
            - Include keywords from the job description naturally
            - Show clear understanding of company culture and values
            - Demonstrate how candidate solves company's specific needs
            - Use active voice and strong action verbs
            - Avoid generic templates and clichés
            - Maintain consistent tone throughout
            - Include 2-3 specific, quantifiable achievements
            - Show genuine research about the company

            FORMATTING:
            - Use proper business letter format
            - Include appropriate spacing between sections
            - Professional and clean presentation
            - Consistent formatting throughout

            Generate a cover letter that will make this candidate stand out and get noticed.

            {format_instructions}
            """)

            generation_prompt = generation_prompt.partial(
                format_instructions=self.generation_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=generation_prompt)

            response = await chain.arun(
                full_name=personal_info.get("full_name", ""),
                email_address=personal_info.get("email_address", ""),
                phone_number=personal_info.get("phone_number", ""),
                city=personal_info.get("city", ""),
                desired_position=personal_info.get("desired_position", ""),
                company_name=personal_info.get("company_name", ""),
                industry_sector=job_analysis.industry_sector,
                experience_level=job_analysis.experience_level,
                company_details=str(job_analysis.company_details),
                required_skills=", ".join(job_analysis.required_skills),
                key_responsibilities=", ".join(job_analysis.key_responsibilities),
                company_culture=", ".join(job_analysis.company_culture),
                role_requirements=", ".join(job_analysis.role_requirements),
                writing_style=writing_style.value,
                tone=tone,
                length=length,
                min_words=min_words,
                max_words=max_words,
                focus_areas=", ".join(focus_areas or ["experience", "skills", "enthusiasm"]),
                style_guidance=style_template.get_tone_guidance(),
                tone_descriptors=", ".join(style_template.tone_descriptors),
                sample_phrases="; ".join(style_template.sample_phrases[:3]),
                custom_instructions=custom_instructions or "No additional instructions"
            )

            return self.generation_parser.parse(response)

        except Exception as e:
            logger.error("Error generating cover letter", error=str(e))
            return self._fallback_generation(personal_info, job_analysis)

    async def assess_cover_letter_quality(
        self,
        cover_letter_content: str,
        job_analysis: JobAnalysis,
        target_style: WritingStyle
    ) -> CoverLetterQualityAssessment:
        """Assess the quality of a generated cover letter."""
        try:
            quality_prompt = ChatPromptTemplate.from_template("""
            As an expert hiring manager and writing coach, assess the quality of this cover letter.

            COVER LETTER TO ASSESS:
            {cover_letter_content}

            JOB CONTEXT:
            Required Skills: {required_skills}
            Role Requirements: {role_requirements}
            Company Culture: {company_culture}
            Industry: {industry_sector}

            TARGET STYLE: {target_style}

            ASSESSMENT CRITERIA:
            1. Overall Quality (0-100): Comprehensive assessment of letter effectiveness
            2. Readability (0-100): Clarity, flow, and ease of reading
            3. Keyword Relevance (0-100): How well it incorporates job-relevant keywords
            4. Tone Consistency (0-100): Consistency with intended writing style
            5. Structure Quality (0-100): Professional format and logical organization
            6. Uniqueness (0-100): Originality and avoidance of generic language

            DETAILED ANALYSIS:
            - Identify specific strengths that make this letter effective
            - Point out weaknesses that could hurt the candidate's chances
            - Provide actionable recommendations for improvement
            - Assess alignment with job requirements
            - Evaluate professional presentation
            - Check for appropriate tone and style consistency

            Provide honest, constructive feedback that will help improve the letter's effectiveness.

            {format_instructions}
            """)

            quality_prompt = quality_prompt.partial(
                format_instructions=self.quality_parser.get_format_instructions()
            )

            chain = LLMChain(llm=self.llm, prompt=quality_prompt)

            response = await chain.arun(
                cover_letter_content=cover_letter_content,
                required_skills=", ".join(job_analysis.required_skills),
                role_requirements=", ".join(job_analysis.role_requirements),
                company_culture=", ".join(job_analysis.company_culture),
                industry_sector=job_analysis.industry_sector,
                target_style=target_style.value
            )

            return self.quality_parser.parse(response)

        except Exception as e:
            logger.error("Error assessing cover letter quality", error=str(e))
            return self._fallback_quality_assessment()

    async def customize_for_company(
        self,
        base_cover_letter: str,
        new_job_analysis: JobAnalysis,
        customization_focus: List[str]
    ) -> str:
        """Customize existing cover letter for a different company/role."""
        try:
            customization_prompt = ChatPromptTemplate.from_template("""
            Adapt this existing cover letter for a new job opportunity while maintaining
            the candidate's core value proposition.

            EXISTING COVER LETTER:
            {base_cover_letter}

            NEW JOB CONTEXT:
            Company: {company_name}
            Position: {desired_position}
            Required Skills: {required_skills}
            Company Culture: {company_culture}
            Key Responsibilities: {key_responsibilities}

            CUSTOMIZATION FOCUS:
            {customization_focus}

            ADAPTATION REQUIREMENTS:
            1. Update company name and position title throughout
            2. Adjust key achievements to align with new role requirements
            3. Modify opening and closing to reflect new opportunity
            4. Include relevant keywords for the new position
            5. Adjust tone if needed for company culture
            6. Maintain candidate's core strengths and experiences
            7. Ensure all references are relevant to new role

            Return the fully customized cover letter, ready to send.
            """)

            chain = LLMChain(llm=self.llm, prompt=customization_prompt)

            response = await chain.arun(
                base_cover_letter=base_cover_letter,
                company_name=new_job_analysis.company_details.get("name", "the company"),
                desired_position=customization_focus[0] if customization_focus else "the position",
                required_skills=", ".join(new_job_analysis.required_skills),
                company_culture=", ".join(new_job_analysis.company_culture),
                key_responsibilities=", ".join(new_job_analysis.key_responsibilities),
                customization_focus=", ".join(customization_focus)
            )

            return response.strip()

        except Exception as e:
            logger.error("Error customizing cover letter", error=str(e))
            return base_cover_letter

    def _fallback_job_analysis(self, company_name: str) -> JobAnalysis:
        """Fallback job analysis if AI processing fails."""
        return JobAnalysis(
            company_details={"name": company_name, "industry": "unknown"},
            role_requirements=["Relevant experience", "Strong communication skills"],
            required_skills=["Problem solving", "Team collaboration"],
            experience_level="mid-level",
            industry_sector="general",
            company_culture=["Professional environment", "Team-oriented"],
            key_responsibilities=["Core job functions", "Team collaboration"],
            preferred_qualifications=["Additional experience preferred"],
            compensation_info=None
        )

    def _fallback_generation(
        self,
        personal_info: Dict[str, str],
        job_analysis: JobAnalysis
    ) -> CoverLetterGeneration:
        """Fallback cover letter generation if AI fails."""
        fallback_content = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {personal_info.get('desired_position', 'position')} role at {personal_info.get('company_name', 'your company')}. With my background and experience, I am confident I would be a valuable addition to your team.

My skills and experience align well with your requirements, and I am particularly drawn to your company's mission and values. I have a proven track record of success and would bring dedication and enthusiasm to this role.

I would welcome the opportunity to discuss how my background and passion for this field would benefit your organization. Thank you for considering my application.

Sincerely,
{personal_info.get('full_name', 'Candidate Name')}"""

        return CoverLetterGeneration(
            cover_letter_content=fallback_content,
            word_count=len(fallback_content.split()),
            paragraph_count=4,
            key_highlights=["Interest in position", "Relevant experience", "Company alignment"],
            confidence_score=60.0,
            keyword_matches=["experience", "skills", "team"],
            tone_analysis="Professional and respectful",
            improvement_suggestions=["Add specific examples", "Include quantified achievements"]
        )

    def _fallback_quality_assessment(self) -> CoverLetterQualityAssessment:
        """Fallback quality assessment."""
        return CoverLetterQualityAssessment(
            overall_score=70.0,
            readability_score=75.0,
            keyword_relevance=65.0,
            tone_consistency=80.0,
            structure_quality=75.0,
            uniqueness_score=60.0,
            strengths=["Professional tone", "Clear structure"],
            weaknesses=["Limited specific examples", "Generic language"],
            recommendations=["Add quantified achievements", "Include more job-specific keywords"]
        )