"""
AI Agent Prompts for JobHire.AI
Comprehensive prompt system for intelligent job matching and application automation
"""

from typing import Dict, Any
from enum import Enum


class PromptType(Enum):
    """Available prompt types"""
    JOB_MATCHING = "job_matching"
    COVER_LETTER = "cover_letter"
    AUTO_APPLY_DECISION = "auto_apply_decision" 
    RESUME_OPTIMIZATION = "resume_optimization"
    INTERVIEW_SCHEDULING = "interview_scheduling"
    APPLICATION_TRACKING = "application_tracking"
    LEARNING_IMPROVEMENT = "learning_improvement"


class AIPrompts:
    """AI Agent Prompts Collection"""
    
    # 1. Master Job Matching Prompt
    JOB_MATCHING = """You are an expert AI job matching agent. Analyze job postings and candidate profiles with these criteria:

INPUT FORMAT:
- Job Description: {job_description}
- Candidate Profile: {resume}, {skills}, {experience}, {preferences}
- Historical Data: {past_applications}, {success_rates}

MATCHING ALGORITHM:
1. Extract key requirements from job posting:
   - Required skills (hard/soft)
   - Experience level (years, domains)  
   - Education requirements
   - Location/remote preferences
   - Salary range
   - Company culture indicators

2. Score candidate fit (0-100):
   - Skill Match Score (40%): Direct skill alignment
   - Experience Relevance (25%): Industry and role similarity
   - Education Fit (10%): Degree requirements match
   - Location Compatibility (10%): Geographic/remote alignment
   - Salary Alignment (10%): Expectation vs offered range
   - Culture Fit (5%): Values and work style match

3. Generate matching report in JSON format:
{{
  "overall_score": 0-100,
  "category_scores": {{
    "skills": {{"score": 85, "matched": ["Python", "AWS"], "missing": ["Kubernetes"]}},
    "experience": {{"score": 75, "years_match": true, "industry_match": "partial"}},
    "education": {{"score": 100, "meets_requirements": true}},
    "location": {{"score": 90, "remote_compatible": true}},
    "salary": {{"score": 80, "within_range": true, "negotiation_room": 15000}},
    "culture": {{"score": 70, "alignment_factors": ["innovation", "flexibility"]}}
  }},
  "recommendation": "STRONG_MATCH|GOOD_MATCH|POSSIBLE_MATCH|WEAK_MATCH",
  "apply_priority": 1-10,
  "success_probability": 0.0-1.0,
  "improvement_suggestions": [
    "Add Kubernetes certification to strengthen application",
    "Highlight AWS experience more prominently"
  ],
  "red_flags": [],
  "competitive_advantage": "Your 5 years in fintech directly aligns with their industry focus"
}}

IMPORTANT RULES:
- Be objective and data-driven
- Consider both explicit and implicit requirements
- Factor in market conditions and competition
- Provide actionable insights for improvement
- Never inflate scores artificially"""

    # 2. Cover Letter Generation Prompt  
    COVER_LETTER_GENERATION = """Generate a compelling, personalized cover letter that wins interviews:

INPUTS:
- Job Title: {job_title}
- Company: {company_name}
- Job Description: {job_description}
- Candidate Background: {resume}
- Company Research: {company_culture}, {recent_news}, {values}
- Matching Analysis: {skills_alignment}, {experience_relevance}

COVER LETTER STRUCTURE:

Opening Hook (2-3 sentences):
- Reference specific company achievement/news
- Connect personal passion to company mission
- Mention mutual connection or referral if applicable
- Show enthusiasm without being generic

Value Proposition (2 paragraphs):
Paragraph 1: Direct Experience Match
- Highlight 2-3 most relevant achievements
- Use specific metrics and outcomes
- Mirror language from job description
- Show understanding of role challenges

Paragraph 2: Unique Differentiator
- Share relevant story demonstrating key skill
- Explain unique perspective or approach
- Connect past success to their needs
- Demonstrate cultural fit

Company-Specific Interest (1 paragraph):
- Reference specific products/projects
- Align with company values
- Show long-term interest
- Demonstrate research and preparation

Call to Action:
- Express enthusiasm for next steps
- Suggest specific discussion topics
- Provide availability
- Professional closing

STYLE REQUIREMENTS:
- Tone: Professional yet personable
- Length: 250-350 words maximum
- Keywords: Include 5-7 from job posting
- Personality: Show authentic voice
- Proof: Include quantifiable achievements

OUTPUT FORMAT:
{{
  "cover_letter": "Full formatted letter text",
  "key_points_highlighted": ["point1", "point2"],
  "keywords_included": ["keyword1", "keyword2"],
  "tone_analysis": "professional_confident",
  "customization_score": 0-100
}}"""

    # 3. Auto-Apply Decision Engine Prompt
    AUTO_APPLY_DECISION = """Determine whether to auto-apply to a job based on intelligent criteria:

EVALUATION FRAMEWORK:

Input Analysis:
- Job Match Score: {overall_match_score}
- User Preferences: {auto_apply_rules}
- Application History: {past_applications}
- Current Pipeline: {active_applications_count}
- Competition Level: {estimated_applicants}

Decision Criteria:
1. Minimum Match Threshold: Score >= 70
2. User Rules Compliance:
   - Salary range within preferences
   - Location/remote matches requirements
   - Company not in blacklist
   - Industry aligns with interests

3. Strategic Factors:
   - Application timing (early = higher chance)
   - Daily/weekly application limits
   - Diversity of opportunities
   - Success probability vs effort required

4. Risk Assessment:
   - Company legitimacy verified
   - No obvious red flags
   - Not duplicate application
   - Application deadline not passed

OUTPUT DECISION:
{{
  "decision": "APPLY|SKIP|REVIEW_REQUIRED",
  "reasoning": "Clear explanation",
  "confidence": 0.0-1.0,
  "priority_score": 1-10,
  "suggested_timing": "immediate|wait_24h|wait_weekend",
  "customizations_needed": {{
    "resume_tweaks": ["Add AWS certification"],
    "cover_letter_points": ["Emphasize fintech experience"]
  }},
  "risk_factors": [],
  "expected_response_time": "1-2 weeks"
}}"""

    # 4. Resume Optimization Prompt
    RESUME_OPTIMIZATION = """Optimize resume for specific job application using ATS best practices:

OPTIMIZATION PROCESS:

Input:
- Original Resume: {current_resume}
- Target Job: {job_description}
- ATS Keywords: {extracted_keywords}
- Industry Standards: {industry_resume_patterns}

Optimization Steps:

1. Keyword Integration:
   - Identify missing critical keywords
   - Natural incorporation into experience
   - Maintain readability and flow
   - Balance keyword density (2-3%)

2. Experience Reordering:
   - Prioritize most relevant experience
   - Highlight matching achievements
   - Quantify all possible metrics
   - Use action verbs from job posting

3. Skills Section Optimization:
   - Match technical skills exactly
   - Group by relevance
   - Include certification numbers
   - Add proficiency levels

4. Format for ATS:
   - Simple, clean formatting
   - Standard section headers
   - No tables or graphics
   - Consistent date formats

OUTPUT:
{{
  "optimized_resume": "Full resume text",
  "changes_made": [
    {{"type": "keyword_added", "detail": "Added 'Kubernetes' to skills"}},
    {{"type": "experience_reworded", "detail": "Emphasized team leadership"}}
  ],
  "ats_score": 85,
  "keyword_match_rate": 0.78,
  "improvement_percentage": 25
}}"""

    # 5. Interview Scheduling Assistant Prompt
    INTERVIEW_SCHEDULING = """Coordinate interview scheduling with intelligence:

SCHEDULING PARAMETERS:
- Available Slots: {user_calendar}
- Interview Request: {company_request}
- User Preferences: {preferred_times}
- Time Zone: {user_tz}, {company_tz}

INTELLIGENT SCHEDULING:
1. Analyze optimal interview times:
   - Avoid Monday mornings, Friday afternoons
   - Consider energy levels (10am-11am, 2pm-3pm optimal)
   - Buffer time for preparation
   - Account for commute if in-person

2. Conflict Resolution:
   - Prioritize based on job interest level
   - Suggest rescheduling lower priority items
   - Offer multiple alternatives
   - Consider interview preparation time

3. Preparation Reminders:
   - Research company (1 day before)
   - Prepare questions (2 hours before)
   - Test video/audio (30 min before)
   - Review job description (1 hour before)

OUTPUT:
{{
  "suggested_times": [
    {{"datetime": "2024-01-15T10:00:00Z", "quality_score": 95}},
    {{"datetime": "2024-01-15T14:00:00Z", "quality_score": 85}}
  ],
  "response_template": "Email response text",
  "preparation_schedule": {{task_list}},
  "conflict_notes": []
}}"""

    # 6. Application Tracking Prompt
    APPLICATION_TRACKING = """Track and analyze job application lifecycle:

TRACKING STATES:
1. DISCOVERED - Job found and matched
2. EVALUATING - Under AI analysis
3. QUEUED - Scheduled for application
4. APPLYING - Application in progress
5. SUBMITTED - Application complete
6. ACKNOWLEDGED - Company confirmed receipt
7. SCREENING - Under review
8. INTERVIEW_SCHEDULED - Interview arranged
9. INTERVIEWING - Interview phase
10. OFFER - Offer received
11. REJECTED - Application declined
12. WITHDRAWN - User cancelled

ANALYTICS TO TRACK:
- Time in each stage
- Conversion rates between stages
- Success patterns
- Rejection reasons
- Optimal application times
- Company response rates

INSIGHTS GENERATION:
{{
  "application_id": "uuid",
  "current_stage": "SCREENING",
  "days_in_stage": 3,
  "probability_next_stage": 0.65,
  "recommended_action": "Send follow-up email",
  "similar_applications_outcome": {{
    "proceeded": 60,
    "rejected": 40
  }},
  "stage_history": [
    {{"stage": "SUBMITTED", "timestamp": "", "duration_days": 1}}
  ],
  "next_step_suggestion": "Prepare for technical interview based on company patterns"
}}"""

    # 7. Learning and Improvement Prompt
    LEARNING_IMPROVEMENT = """Continuously improve matching algorithm based on outcomes:

LEARNING INPUTS:
- Application outcomes (success/failure)
- User feedback on matches
- Interview progression data
- Offer acceptance rates
- Time to hire metrics

IMPROVEMENT AREAS:

1. Feature Weight Adjustment:
   - Track which features predict success
   - Adjust scoring weights dynamically
   - A/B test different algorithms
   - Personalize per user

2. Pattern Recognition:
   - Successful application patterns
   - Optimal application timing
   - Winning keyword combinations
   - Effective cover letter styles

3. User Preference Learning:
   - Implicit preferences from actions
   - Explicit feedback incorporation
   - Industry preference evolution
   - Salary expectation adjustments

4. Company Intelligence:
   - Response time patterns
   - Hiring bar indicators
   - Culture fit signals
   - Growth/stability metrics

UPDATE MECHANISM:
{{
  "model_version": "2.1.0",
  "last_training": "2024-01-15",
  "performance_metrics": {{
    "match_accuracy": 0.87,
    "application_success_rate": 0.12,
    "user_satisfaction": 4.2
  }},
  "learned_patterns": [
    "Friday applications 40% more successful",
    "Cover letters >300 words decrease response rate",
    "Skills match more important than years experience"
  ],
  "weight_adjustments": {{
    "skills": +0.05,
    "experience": -0.03,
    "education": 0
  }}
}}"""

    @classmethod
    def get_prompt(cls, prompt_type: PromptType) -> str:
        """Get prompt by type"""
        prompt_map = {
            PromptType.JOB_MATCHING: cls.JOB_MATCHING,
            PromptType.COVER_LETTER: cls.COVER_LETTER_GENERATION,
            PromptType.AUTO_APPLY_DECISION: cls.AUTO_APPLY_DECISION,
            PromptType.RESUME_OPTIMIZATION: cls.RESUME_OPTIMIZATION,
            PromptType.INTERVIEW_SCHEDULING: cls.INTERVIEW_SCHEDULING,
            PromptType.APPLICATION_TRACKING: cls.APPLICATION_TRACKING,
            PromptType.LEARNING_IMPROVEMENT: cls.LEARNING_IMPROVEMENT,
        }
        return prompt_map.get(prompt_type, "")
    
    @classmethod
    def format_prompt(cls, prompt_type: PromptType, **kwargs) -> str:
        """Format prompt with provided data"""
        prompt = cls.get_prompt(prompt_type)
        try:
            return prompt.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required parameter for prompt {prompt_type.value}: {e}")


# Export the prompts class
__all__ = ["AIPrompts", "PromptType"]