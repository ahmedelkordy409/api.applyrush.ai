"""
LangGraph Job Application Workflow
End-to-end automated job application process with AI decision making
"""

from typing import Dict, Any, TypedDict, Literal
from datetime import datetime
import asyncio

from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from .base import (
    BaseWorkflow, BaseWorkflowState, BaseWorkflowConfig, 
    WorkflowStatus, ConditionalEdge, get_ai_model_tier
)
from .database_integration import workflow_db_manager
from ..ai.models import ai_model_manager, generate_job_match_analysis, generate_cover_letter
from ..services.job_matcher import job_matching_engine, MatchingStrategy
from ..core.monitoring import performance_monitor


class JobApplicationState(BaseWorkflowState):
    """Extended state for job application workflow"""
    # Job application specific fields
    match_score: float
    should_apply: bool
    application_strategy: str
    cover_letter: Dict[str, Any]
    resume_optimizations: Dict[str, Any]
    company_research: Dict[str, Any]
    application_timeline: Dict[str, Any]
    application_submitted: bool
    follow_up_scheduled: bool


class ApplicationDecision(str):
    """Application decision options"""
    APPLY_IMMEDIATELY = "apply_immediately"
    APPLY_WITH_PREP = "apply_with_prep"
    SAVE_FOR_LATER = "save_for_later"
    SKIP = "skip"


class JobApplicationWorkflow(BaseWorkflow):
    """
    Comprehensive job application workflow using LangGraph
    
    Flow:
    1. Analyze Job → 2. Company Research → 3. Match Evaluation → 4. Decision Gate
    5a. Apply Path: Optimize Resume → Generate Cover Letter → Submit Application → Schedule Follow-up
    5b. Skip Path: Log Decision → End
    """
    
    def __init__(self, config: BaseWorkflowConfig = None):
        super().__init__(config)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            timeout=30
        )
    
    async def build_graph(self) -> CompiledStateGraph:
        """Build the job application workflow graph"""
        
        # Create the state graph
        graph = StateGraph(JobApplicationState)
        
        # Add nodes
        graph.add_node("analyze_job", self.analyze_job_node)
        graph.add_node("research_company", self.research_company_node)
        graph.add_node("evaluate_match", self.evaluate_match_node)
        graph.add_node("optimize_resume", self.optimize_resume_node)
        graph.add_node("generate_cover_letter", self.generate_cover_letter_node)
        graph.add_node("submit_application", self.submit_application_node)
        graph.add_node("schedule_follow_up", self.schedule_follow_up_node)
        graph.add_node("log_skip_decision", self.log_skip_decision_node)
        
        # Add edges
        graph.add_edge(START, "analyze_job")
        graph.add_edge("analyze_job", "research_company")
        graph.add_edge("research_company", "evaluate_match")
        
        # Conditional edge based on application decision
        graph.add_conditional_edges(
            "evaluate_match",
            self.should_apply_condition,
            {
                ApplicationDecision.APPLY_IMMEDIATELY: "generate_cover_letter",
                ApplicationDecision.APPLY_WITH_PREP: "optimize_resume", 
                ApplicationDecision.SAVE_FOR_LATER: "log_skip_decision",
                ApplicationDecision.SKIP: "log_skip_decision"
            }
        )
        
        # Application path
        graph.add_edge("optimize_resume", "generate_cover_letter")
        graph.add_edge("generate_cover_letter", "submit_application")
        graph.add_edge("submit_application", "schedule_follow_up")
        graph.add_edge("schedule_follow_up", END)
        
        # Skip path
        graph.add_edge("log_skip_decision", END)
        
        # Compile the graph
        return graph.compile(checkpointer=self.checkpointer)
    
    async def analyze_job_node(self, state: JobApplicationState) -> JobApplicationState:
        """Analyze job posting and extract key information"""
        await self.update_progress(state, "analyze_job")
        
        try:
            job_data = state["job_data"]
            user_profile = state["user_profile"]
            
            # Use existing job matching engine for comprehensive analysis
            match_result = await job_matching_engine.match_job_to_user(
                job_data=job_data,
                user_profile=user_profile,
                strategy=MatchingStrategy.HYBRID,
                user_tier=state["user_tier"]
            )
            
            if match_result["success"]:
                state["analysis_results"]["job_match"] = match_result
                state["match_score"] = match_result["overall_score"]
                
                # Add AI-powered job insights
                ai_insights = await self._get_job_insights(job_data, user_profile)
                state["analysis_results"]["ai_insights"] = ai_insights
                
                self.logger.info("Job analysis completed",
                               job_id=state["job_id"],
                               match_score=state["match_score"])
            else:
                await self.add_error(state, f"Job analysis failed: {match_result.get('error')}", "analyze_job")
                state["match_score"] = 0.0
            
        except Exception as e:
            await self.add_error(state, f"Job analysis error: {str(e)}", "analyze_job")
            state["match_score"] = 0.0
        
        return state
    
    async def research_company_node(self, state: JobApplicationState) -> JobApplicationState:
        """Research company information and culture"""
        await self.update_progress(state, "research_company")
        
        try:
            job_data = state["job_data"]
            company_info = job_data.get("company", {})
            
            # Basic company research (in production, integrate with web scraping)
            company_research = {
                "name": company_info.get("name", "Unknown"),
                "industry": company_info.get("industry", "Unknown"),
                "size": company_info.get("size", "Unknown"),
                "culture": await self._research_company_culture(company_info),
                "recent_news": await self._get_company_news(company_info),
                "values": company_info.get("values", []),
                "glassdoor_rating": company_info.get("rating", "N/A")
            }
            
            state["company_research"] = company_research
            state["company_data"] = company_info
            
            self.logger.info("Company research completed",
                           company=company_research["name"])
            
        except Exception as e:
            await self.add_error(state, f"Company research error: {str(e)}", "research_company")
            state["company_research"] = {}
        
        return state
    
    async def evaluate_match_node(self, state: JobApplicationState) -> JobApplicationState:
        """Evaluate job match and make application decision"""
        await self.update_progress(state, "evaluate_match")
        
        try:
            match_score = state.get("match_score", 0)
            job_match_data = state["analysis_results"].get("job_match", {})
            user_tier = state["user_tier"]
            user_preferences = state["user_preferences"]
            
            # Decision making algorithm
            decision_factors = {
                "match_score": match_score,
                "user_tier": user_tier,
                "application_urgency": user_preferences.get("application_urgency", "medium"),
                "company_preference": self._evaluate_company_preference(state),
                "skill_gaps": len(job_match_data.get("improvement_suggestions", [])),
                "success_probability": job_match_data.get("success_probability", 0.5)
            }
            
            # Apply decision logic
            decision = await self._make_application_decision(decision_factors)
            
            state["application_strategy"] = decision
            state["decisions"]["application"] = {
                "decision": decision,
                "factors": decision_factors,
                "reasoning": await self._get_decision_reasoning(decision_factors, decision),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.logger.info("Application decision made",
                           decision=decision,
                           match_score=match_score)
            
        except Exception as e:
            await self.add_error(state, f"Evaluation error: {str(e)}", "evaluate_match")
            state["application_strategy"] = ApplicationDecision.SKIP
        
        return state
    
    async def optimize_resume_node(self, state: JobApplicationState) -> JobApplicationState:
        """Optimize resume for specific job application"""
        await self.update_progress(state, "optimize_resume")
        
        try:
            job_data = state["job_data"]
            user_profile = state["user_profile"]
            match_analysis = state["analysis_results"]["job_match"]
            
            # Generate resume optimization suggestions
            optimization_prompt = f"""
            Based on this job posting and user profile, suggest specific resume optimizations:
            
            Job Title: {job_data.get('title', 'Unknown')}
            Required Skills: {job_data.get('required_skills', [])}
            Job Description: {job_data.get('description', '')[:500]}...
            
            Missing Skills: {match_analysis.get('improvement_suggestions', [])}
            Current Experience: {user_profile.get('experience_years', 0)} years
            
            Provide 3-5 specific, actionable resume improvements focusing on:
            1. Keywords to add
            2. Experience sections to emphasize  
            3. Skills to highlight
            4. Accomplishments to feature
            """
            
            model_tier = await get_ai_model_tier(state)
            ai_result = await ai_model_manager.generate_response(
                prompt=optimization_prompt,
                user_data=user_profile,
                model_tier=model_tier,
                provider="openai",
                temperature=0.3
            )
            
            if ai_result["success"]:
                optimizations = await ai_model_manager.parse_json_response(ai_result["response"]["text"])
                state["resume_optimizations"] = optimizations
                
                self.logger.info("Resume optimization completed")
            else:
                await self.add_warning(state, "Resume optimization failed, proceeding with current resume")
                state["resume_optimizations"] = {}
            
        except Exception as e:
            await self.add_error(state, f"Resume optimization error: {str(e)}", "optimize_resume")
            state["resume_optimizations"] = {}
        
        return state
    
    async def generate_cover_letter_node(self, state: JobApplicationState) -> JobApplicationState:
        """Generate personalized cover letter"""
        await self.update_progress(state, "generate_cover_letter")
        
        try:
            job_data = state["job_data"]
            user_profile = state["user_profile"]
            company_research = state.get("company_research", {})
            
            # Generate cover letter using existing function
            cover_letter_result = await generate_cover_letter(
                job_data=job_data,
                user_profile=user_profile,
                company_research=company_research,
                user_tier=state["user_tier"]
            )
            
            if cover_letter_result["success"]:
                state["cover_letter"] = cover_letter_result["cover_letter"]
                
                # Store AI metadata for cost tracking
                if "ai_responses" not in state:
                    state["ai_responses"] = {}
                state["ai_responses"]["cover_letter"] = cover_letter_result.get("metadata", {})
                
                self.logger.info("Cover letter generated successfully")
            else:
                await self.add_error(state, f"Cover letter generation failed: {cover_letter_result.get('error')}", "generate_cover_letter")
                state["cover_letter"] = {}
            
        except Exception as e:
            await self.add_error(state, f"Cover letter error: {str(e)}", "generate_cover_letter")
            state["cover_letter"] = {}
        
        return state
    
    async def submit_application_node(self, state: JobApplicationState) -> JobApplicationState:
        """Submit the job application"""
        await self.update_progress(state, "submit_application")
        
        try:
            # In production, this would integrate with actual application APIs
            # For now, simulate application submission
            
            application_data = {
                "job_id": state["job_id"],
                "user_id": state["user_id"],
                "cover_letter": state.get("cover_letter", {}),
                "resume_optimizations": state.get("resume_optimizations", {}),
                "submitted_at": datetime.utcnow().isoformat(),
                "application_method": "api",  # or "manual", "email", etc.
                "match_score": state.get("match_score", 0)
            }
            
            # Record the application action
            state["actions_taken"].append({
                "action": "submit_application",
                "data": application_data,
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            })
            
            state["application_submitted"] = True
            
            # Update performance metrics
            performance_monitor.record_application_submitted(
                user_tier=state["user_tier"],
                match_score=state.get("match_score", 0),
                success=True
            )
            
            self.logger.info("Application submitted successfully",
                           job_id=state["job_id"],
                           user_id=state["user_id"])
            
        except Exception as e:
            await self.add_error(state, f"Application submission error: {str(e)}", "submit_application")
            state["application_submitted"] = False
        
        return state
    
    async def schedule_follow_up_node(self, state: JobApplicationState) -> JobApplicationState:
        """Schedule follow-up actions"""
        await self.update_progress(state, "schedule_follow_up")
        
        try:
            # Calculate follow-up timeline based on company type and role level
            follow_up_days = self._calculate_follow_up_timeline(state)
            
            follow_up_schedule = {
                "initial_follow_up": follow_up_days["initial"],
                "second_follow_up": follow_up_days["second"],
                "final_follow_up": follow_up_days["final"],
                "automated_tracking": True,
                "follow_up_methods": ["email", "linkedin"],
                "created_at": datetime.utcnow().isoformat()
            }
            
            state["application_timeline"] = follow_up_schedule
            state["follow_up_scheduled"] = True
            
            # Add to Celery task queue (in production)
            self.logger.info("Follow-up scheduled",
                           initial_days=follow_up_days["initial"])
            
        except Exception as e:
            await self.add_error(state, f"Follow-up scheduling error: {str(e)}", "schedule_follow_up")
            state["follow_up_scheduled"] = False
        
        return state
    
    async def log_skip_decision_node(self, state: JobApplicationState) -> JobApplicationState:
        """Log decision to skip application"""
        await self.update_progress(state, "log_skip_decision")
        
        try:
            skip_reason = state["decisions"]["application"]["reasoning"]
            
            state["actions_taken"].append({
                "action": "skip_application",
                "reason": skip_reason,
                "match_score": state.get("match_score", 0),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            state["should_apply"] = False
            
            self.logger.info("Application skipped",
                           reason=skip_reason,
                           match_score=state.get("match_score", 0))
            
        except Exception as e:
            await self.add_error(state, f"Skip logging error: {str(e)}", "log_skip_decision")
        
        return state
    
    async def should_apply_condition(self, state: JobApplicationState) -> str:
        """Conditional logic for application decision"""
        return state.get("application_strategy", ApplicationDecision.SKIP)
    
    # Helper methods
    async def _get_job_insights(self, job_data: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI-powered job insights"""
        try:
            insight_prompt = f"""
            Analyze this job posting and provide insights for application strategy:
            
            Job: {job_data.get('title', 'Unknown')}
            Company: {job_data.get('company', {}).get('name', 'Unknown')}
            Description: {job_data.get('description', '')[:300]}...
            
            Provide insights on:
            1. Key requirements focus areas
            2. Company culture indicators
            3. Application competitiveness 
            4. Negotiation opportunities
            5. Red flags (if any)
            
            Return as JSON with these keys: focus_areas, culture_indicators, competitiveness, negotiation, red_flags
            """
            
            result = await ai_model_manager.generate_response(
                prompt=insight_prompt,
                user_data=user_profile,
                model_tier="balanced",
                provider="openai",
                temperature=0.2
            )
            
            if result["success"]:
                return await ai_model_manager.parse_json_response(result["response"]["text"])
            return {}
            
        except Exception as e:
            self.logger.warning("Job insights generation failed", error=str(e))
            return {}
    
    async def _research_company_culture(self, company_info: Dict[str, Any]) -> str:
        """Research company culture (simplified version)"""
        # In production, this would scrape company websites, Glassdoor, etc.
        company_size = company_info.get("size", "Unknown")
        industry = company_info.get("industry", "Unknown")
        
        culture_indicators = {
            "startup": "Fast-paced, innovative, flexible",
            "enterprise": "Structured, stable, process-oriented", 
            "mid-size": "Balanced growth and stability"
        }
        
        if "startup" in company_size.lower():
            return culture_indicators["startup"]
        elif "enterprise" in company_size.lower() or int(company_info.get("employee_count", 0)) > 1000:
            return culture_indicators["enterprise"]
        else:
            return culture_indicators["mid-size"]
    
    async def _get_company_news(self, company_info: Dict[str, Any]) -> str:
        """Get recent company news (simplified version)"""
        # In production, integrate with news APIs
        return f"Recent developments at {company_info.get('name', 'Company')}"
    
    def _evaluate_company_preference(self, state: JobApplicationState) -> float:
        """Evaluate how well company aligns with user preferences"""
        company_research = state.get("company_research", {})
        user_preferences = state.get("user_preferences", {})
        
        # Simple scoring based on company size preference
        preferred_size = user_preferences.get("company_size_preference", "any")
        company_size = company_research.get("size", "").lower()
        
        if preferred_size == "any":
            return 0.8
        elif preferred_size in company_size:
            return 1.0
        else:
            return 0.6
    
    async def _make_application_decision(self, factors: Dict[str, Any]) -> str:
        """Make intelligent application decision"""
        match_score = factors["match_score"]
        success_probability = factors["success_probability"]
        user_tier = factors["user_tier"]
        skill_gaps = factors["skill_gaps"]
        
        # Decision matrix
        if match_score >= 85 and success_probability >= 0.7:
            return ApplicationDecision.APPLY_IMMEDIATELY
        elif match_score >= 70 and success_probability >= 0.5:
            if skill_gaps <= 2 or user_tier in ["premium", "enterprise"]:
                return ApplicationDecision.APPLY_WITH_PREP
            else:
                return ApplicationDecision.SAVE_FOR_LATER
        elif match_score >= 50:
            return ApplicationDecision.SAVE_FOR_LATER
        else:
            return ApplicationDecision.SKIP
    
    async def _get_decision_reasoning(self, factors: Dict[str, Any], decision: str) -> str:
        """Generate human-readable decision reasoning"""
        match_score = factors["match_score"]
        success_probability = factors["success_probability"]
        
        reasoning_map = {
            ApplicationDecision.APPLY_IMMEDIATELY: f"High match score ({match_score}%) and success probability ({success_probability:.0%}) - excellent opportunity",
            ApplicationDecision.APPLY_WITH_PREP: f"Good match ({match_score}%) - worth applying with preparation and optimization",
            ApplicationDecision.SAVE_FOR_LATER: f"Moderate match ({match_score}%) - save for future consideration or skill development",
            ApplicationDecision.SKIP: f"Low match score ({match_score}%) - not aligned with profile and goals"
        }
        
        return reasoning_map.get(decision, "Unknown decision reasoning")
    
    def _calculate_follow_up_timeline(self, state: JobApplicationState) -> Dict[str, int]:
        """Calculate follow-up timeline based on context"""
        company_size = state.get("company_research", {}).get("size", "").lower()
        job_level = state.get("job_data", {}).get("experience_level", "mid-level")
        
        # Adjust timeline based on company size and role level
        if "startup" in company_size:
            return {"initial": 5, "second": 10, "final": 15}  # Faster pace
        elif "enterprise" in company_size:
            return {"initial": 10, "second": 20, "final": 30}  # Slower process
        else:
            return {"initial": 7, "second": 14, "final": 21}  # Standard timeline


# Export the workflow
__all__ = ["JobApplicationWorkflow", "JobApplicationState", "ApplicationDecision"]