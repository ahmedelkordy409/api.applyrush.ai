"""
Advanced Auto-Apply System
Highly sophisticated AI-powered application automation with safety controls
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import hashlib
from dataclasses import dataclass, asdict

from app.ai.enhanced_prompts import EnhancedAIPrompts
from app.ai.models import ai_model_manager
from app.core.database import get_database
from app.core.monitoring import performance_monitor
from app.models.database import JobStatus
import structlog

logger = structlog.get_logger()


class AutoApplyDecision(Enum):
    """Auto-apply decision types"""
    APPLY_IMMEDIATELY = "apply_immediately"
    APPLY_SCHEDULED = "apply_scheduled"
    REVIEW_REQUIRED = "review_required"
    SKIP_PERMANENTLY = "skip_permanently"
    SKIP_TEMPORARILY = "skip_temporarily"


class RiskLevel(Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApplicationStrategy:
    """Application strategy configuration"""
    cover_letter_template: str
    resume_customizations: List[str]
    application_timing: str
    follow_up_schedule: List[str]
    interview_prep_notes: List[str]
    success_probability: float
    confidence_score: float


@dataclass
class MarketIntelligence:
    """Market intelligence data"""
    industry_trends: Dict[str, Any]
    salary_benchmarks: Dict[str, Any]
    competition_analysis: Dict[str, Any]
    hiring_patterns: Dict[str, Any]
    seasonal_factors: Dict[str, Any]


@dataclass
class CompanyIntelligence:
    """Company-specific intelligence"""
    hiring_velocity: float
    response_patterns: Dict[str, Any]
    culture_fit_indicators: List[str]
    recent_news: List[str]
    growth_trajectory: str
    employee_satisfaction: float
    technical_stack: List[str]


class AdvancedAutoApplyEngine:
    """Sophisticated auto-apply decision engine with AI and safety controls"""

    def __init__(self):
        self.decision_cache = {}
        self.safety_limits = {
            "max_daily_applications": 10,
            "max_weekly_applications": 50,
            "max_monthly_applications": 200,
            "min_hours_between_apps": 2,
            "max_company_applications_per_month": 3,
            "quality_threshold": 0.7,
            "risk_tolerance": RiskLevel.MEDIUM
        }
        self.performance_metrics = {
            "total_decisions": 0,
            "applications_submitted": 0,
            "success_rate": 0.0,
            "avg_response_time": 0.0,
            "quality_score": 0.0
        }

    async def make_auto_apply_decision(
        self,
        user_id: int,
        job_id: str,
        match_analysis: Dict[str, Any],
        user_preferences: Dict[str, Any],
        force_analysis: bool = False
    ) -> Tuple[AutoApplyDecision, Dict[str, Any]]:
        """
        Make sophisticated auto-apply decision with comprehensive analysis
        """
        try:
            logger.info("Starting auto-apply decision analysis", 
                       user_id=user_id, job_id=job_id)
            
            # Check cache for recent decision
            cache_key = f"{user_id}_{job_id}"
            if not force_analysis and cache_key in self.decision_cache:
                cached_decision = self.decision_cache[cache_key]
                if (datetime.utcnow() - cached_decision["timestamp"]).seconds < 3600:
                    return cached_decision["decision"], cached_decision["analysis"]
            
            # Gather comprehensive data
            analysis_data = await self._gather_analysis_data(user_id, job_id, match_analysis)
            
            # Perform safety checks
            safety_result = await self._perform_safety_checks(user_id, analysis_data)
            if not safety_result["passed"]:
                return AutoApplyDecision.SKIP_TEMPORARILY, safety_result
            
            # AI-powered decision analysis
            ai_decision = await self._ai_decision_analysis(analysis_data, user_preferences)
            
            # Risk assessment
            risk_assessment = await self._assess_application_risk(analysis_data, ai_decision)
            
            # Strategic timing analysis
            timing_analysis = await self._analyze_optimal_timing(analysis_data)
            
            # Final decision synthesis
            final_decision, decision_analysis = await self._synthesize_final_decision(
                ai_decision, risk_assessment, timing_analysis, analysis_data
            )
            
            # Cache decision
            self.decision_cache[cache_key] = {
                "decision": final_decision,
                "analysis": decision_analysis,
                "timestamp": datetime.utcnow()
            }
            
            # Update metrics
            self.performance_metrics["total_decisions"] += 1
            
            logger.info("Auto-apply decision completed",
                       user_id=user_id,
                       job_id=job_id,
                       decision=final_decision.value,
                       confidence=decision_analysis.get("confidence", 0))
            
            return final_decision, decision_analysis
            
        except Exception as e:
            logger.error("Auto-apply decision failed", 
                        user_id=user_id, job_id=job_id, error=str(e))
            # Fail safe - require human review
            return AutoApplyDecision.REVIEW_REQUIRED, {
                "error": str(e),
                "fallback_reason": "System error - human review required"
            }

    async def _gather_analysis_data(
        self, 
        user_id: int, 
        job_id: str, 
        match_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gather comprehensive data for decision analysis"""
        
        database = await get_database()
        
        # User application history
        app_history = await database.fetch_all(
            """
            SELECT j.company_name, ja.status, ja.submitted_at, jm.overall_score
            FROM job_applications ja
            JOIN jobs j ON ja.job_id = j.id
            LEFT JOIN job_matches jm ON ja.job_match_id = jm.id
            WHERE ja.user_id = :user_id
            AND ja.submitted_at > NOW() - INTERVAL '90 days'
            ORDER BY ja.submitted_at DESC
            """,
            {"user_id": user_id}
        )
        
        # Current pipeline status
        active_apps = await database.fetch_all(
            """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status IN ('submitted', 'acknowledged', 'screening') THEN 1 END) as pending,
                   COUNT(CASE WHEN status = 'interview_scheduled' THEN 1 END) as interviews
            FROM job_applications
            WHERE user_id = :user_id
            AND submitted_at > NOW() - INTERVAL '30 days'
            """,
            {"user_id": user_id}
        )
        
        # Job and company details
        job_details = await database.fetch_one(
            """
            SELECT j.*, c.name as company_name, c.industry, c.size
            FROM jobs j
            LEFT JOIN companies c ON j.company_id = c.id
            WHERE j.external_id = :job_id
            """,
            {"job_id": job_id}
        )
        
        # Market intelligence
        market_data = await self._gather_market_intelligence(job_details)
        
        # Company intelligence
        company_data = await self._gather_company_intelligence(job_details)
        
        return {
            "user_id": user_id,
            "job_id": job_id,
            "match_analysis": match_analysis,
            "application_history": [dict(app) for app in app_history],
            "active_applications": dict(active_apps[0]) if active_apps else {},
            "job_details": dict(job_details) if job_details else {},
            "market_intelligence": market_data,
            "company_intelligence": company_data,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

    async def _perform_safety_checks(
        self, 
        user_id: int, 
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Comprehensive safety checks before auto-applying"""
        
        database = await get_database()
        checks = []
        
        # Daily application limit
        today_apps = await database.fetch_one(
            """
            SELECT COUNT(*) as count FROM job_applications
            WHERE user_id = :user_id AND DATE(submitted_at) = CURRENT_DATE
            """,
            {"user_id": user_id}
        )
        daily_count = today_apps["count"] if today_apps else 0
        
        checks.append({
            "check": "daily_limit",
            "passed": daily_count < self.safety_limits["max_daily_applications"],
            "current": daily_count,
            "limit": self.safety_limits["max_daily_applications"]
        })
        
        # Weekly application limit
        week_apps = await database.fetch_one(
            """
            SELECT COUNT(*) as count FROM job_applications
            WHERE user_id = :user_id AND submitted_at > NOW() - INTERVAL '7 days'
            """,
            {"user_id": user_id}
        )
        weekly_count = week_apps["count"] if week_apps else 0
        
        checks.append({
            "check": "weekly_limit",
            "passed": weekly_count < self.safety_limits["max_weekly_applications"],
            "current": weekly_count,
            "limit": self.safety_limits["max_weekly_applications"]
        })
        
        # Company application frequency
        company_name = analysis_data["job_details"].get("company_name", "")
        if company_name:
            company_apps = await database.fetch_one(
                """
                SELECT COUNT(*) as count FROM job_applications ja
                JOIN jobs j ON ja.job_id = j.id
                WHERE ja.user_id = :user_id 
                AND j.company_name = :company_name
                AND ja.submitted_at > NOW() - INTERVAL '30 days'
                """,
                {"user_id": user_id, "company_name": company_name}
            )
            company_count = company_apps["count"] if company_apps else 0
            
            checks.append({
                "check": "company_frequency",
                "passed": company_count < self.safety_limits["max_company_applications_per_month"],
                "current": company_count,
                "limit": self.safety_limits["max_company_applications_per_month"]
            })
        
        # Quality threshold check
        match_score = analysis_data["match_analysis"].get("overall_score", 0)
        quality_threshold = self.safety_limits["quality_threshold"] * 100
        
        checks.append({
            "check": "quality_threshold",
            "passed": match_score >= quality_threshold,
            "current": match_score,
            "limit": quality_threshold
        })
        
        # Minimum time between applications
        last_app = await database.fetch_one(
            """
            SELECT submitted_at FROM job_applications
            WHERE user_id = :user_id
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            {"user_id": user_id}
        )
        
        if last_app:
            hours_since_last = (datetime.utcnow() - last_app["submitted_at"]).total_seconds() / 3600
            time_check_passed = hours_since_last >= self.safety_limits["min_hours_between_apps"]
        else:
            time_check_passed = True
            hours_since_last = 24  # No previous applications
        
        checks.append({
            "check": "time_spacing",
            "passed": time_check_passed,
            "current": hours_since_last,
            "limit": self.safety_limits["min_hours_between_apps"]
        })
        
        all_passed = all(check["passed"] for check in checks)
        
        return {
            "passed": all_passed,
            "checks": checks,
            "safety_score": sum(1 for check in checks if check["passed"]) / len(checks),
            "recommendations": self._generate_safety_recommendations(checks)
        }

    async def _ai_decision_analysis(
        self, 
        analysis_data: Dict[str, Any], 
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use enhanced AI prompts for decision analysis"""
        
        try:
            # Prepare enhanced prompt inputs
            prompt_inputs = {
                "overall_match_score": analysis_data["match_analysis"].get("overall_score", 0),
                "auto_apply_rules": user_preferences.get("auto_apply_rules", {}),
                "past_applications": analysis_data["application_history"],
                "active_applications_count": analysis_data["active_applications"].get("total", 0),
                "market_data": analysis_data["market_intelligence"],
                "company_data": analysis_data["company_intelligence"],
                "min_threshold": user_preferences.get("min_score_threshold", 70)
            }
            
            # Validate inputs
            missing_inputs = EnhancedAIPrompts.validate_prompt_inputs("auto_apply_decision", prompt_inputs)
            if missing_inputs:
                logger.warning("Missing inputs for AI decision", missing=missing_inputs)
                # Fill with defaults
                for missing in missing_inputs:
                    if missing not in prompt_inputs:
                        prompt_inputs[missing] = {}
            
            # Generate enhanced prompt
            prompt = EnhancedAIPrompts.get_enhanced_prompt("auto_apply_decision", **prompt_inputs)
            
            # Get AI response
            ai_result = await ai_model_manager.generate_response(
                prompt=prompt,
                user_data={"user_id": analysis_data["user_id"]},
                model_tier="balanced",
                provider="replicate",
                temperature=0.3  # Lower temperature for more consistent decisions
            )
            
            if ai_result["success"]:
                ai_analysis = await ai_model_manager.parse_json_response(ai_result["response"]["text"])
                return {
                    "success": True,
                    "analysis": ai_analysis,
                    "metadata": ai_result["metadata"]
                }
            else:
                logger.error("AI decision analysis failed", error=ai_result.get("error"))
                return {"success": False, "error": ai_result.get("error")}
                
        except Exception as e:
            logger.error("AI decision analysis exception", error=str(e))
            return {"success": False, "error": str(e)}

    async def _assess_application_risk(
        self, 
        analysis_data: Dict[str, Any], 
        ai_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess risks associated with auto-applying to this job"""
        
        risk_factors = []
        risk_score = 0.0
        
        # Job posting quality risks
        job_details = analysis_data["job_details"]
        if not job_details.get("description") or len(job_details.get("description", "")) < 200:
            risk_factors.append("Low-quality job description")
            risk_score += 0.2
        
        # Company reputation risks
        company_data = analysis_data["company_intelligence"]
        if company_data.get("employee_satisfaction", 3.5) < 3.0:
            risk_factors.append("Low employee satisfaction ratings")
            risk_score += 0.3
        
        # Salary transparency risks
        if not job_details.get("salary_min") and not job_details.get("salary_max"):
            risk_factors.append("No salary information provided")
            risk_score += 0.1
        
        # Application frequency risks
        app_history = analysis_data["application_history"]
        recent_rejections = len([app for app in app_history[-10:] if app.get("status") == "rejected"])
        if recent_rejections >= 5:
            risk_factors.append("High recent rejection rate")
            risk_score += 0.4
        
        # Market timing risks
        market_data = analysis_data["market_intelligence"]
        if market_data.get("hiring_velocity", "normal") == "low":
            risk_factors.append("Low market hiring velocity")
            risk_score += 0.2
        
        # Determine risk level
        if risk_score <= 0.3:
            risk_level = RiskLevel.LOW
        elif risk_score <= 0.6:
            risk_level = RiskLevel.MEDIUM
        elif risk_score <= 0.8:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "mitigation_strategies": self._generate_risk_mitigation(risk_factors),
            "proceed_recommendation": risk_level.value in ["low", "medium"]
        }

    async def _analyze_optimal_timing(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze optimal timing for job application"""
        
        job_details = analysis_data["job_details"]
        company_data = analysis_data["company_intelligence"]
        
        # Calculate job posting age
        posted_date = job_details.get("posted_date")
        if posted_date:
            job_age_hours = (datetime.utcnow() - posted_date).total_seconds() / 3600
        else:
            job_age_hours = 24  # Assume 1 day if unknown
        
        # Optimal application window analysis
        if job_age_hours <= 24:
            urgency = "high"
            timing_score = 95
        elif job_age_hours <= 72:
            urgency = "medium"
            timing_score = 85
        elif job_age_hours <= 168:  # 1 week
            urgency = "low"
            timing_score = 70
        else:
            urgency = "very_low"
            timing_score = 50
        
        # Day of week considerations
        current_day = datetime.utcnow().weekday()  # 0 = Monday
        if current_day in [0, 1, 2]:  # Monday-Wednesday
            day_score = 90
        elif current_day in [3, 4]:  # Thursday-Friday
            day_score = 80
        else:  # Weekend
            day_score = 60
        
        # Time of day considerations
        current_hour = datetime.utcnow().hour
        if 9 <= current_hour <= 11 or 14 <= current_hour <= 16:
            hour_score = 90
        elif 8 <= current_hour <= 17:
            hour_score = 80
        else:
            hour_score = 60
        
        # Company response patterns
        avg_response_time = company_data.get("response_patterns", {}).get("avg_hours", 120)
        response_score = min(90, max(50, 90 - (avg_response_time - 48) / 24 * 10))
        
        overall_timing_score = (timing_score * 0.4 + day_score * 0.2 + 
                               hour_score * 0.2 + response_score * 0.2)
        
        return {
            "overall_timing_score": overall_timing_score,
            "urgency": urgency,
            "job_age_hours": job_age_hours,
            "optimal_window": "immediate" if job_age_hours <= 24 else "soon",
            "day_favorability": day_score,
            "hour_favorability": hour_score,
            "company_response_expectation": avg_response_time,
            "recommended_action": "apply_now" if overall_timing_score >= 80 else "schedule_later"
        }

    async def _synthesize_final_decision(
        self,
        ai_decision: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        timing_analysis: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Tuple[AutoApplyDecision, Dict[str, Any]]:
        """Synthesize all analyses into final decision"""
        
        # Extract key metrics
        ai_success = ai_decision.get("success", False)
        ai_analysis = ai_decision.get("analysis", {}) if ai_success else {}
        ai_confidence = ai_analysis.get("final_decision", {}).get("confidence", 0.5)
        
        risk_level = risk_assessment["risk_level"]
        risk_proceed = risk_assessment["proceed_recommendation"]
        
        timing_score = timing_analysis["overall_timing_score"]
        timing_action = timing_analysis["recommended_action"]
        
        match_score = analysis_data["match_analysis"].get("overall_score", 0)
        
        # Decision logic
        if not ai_success:
            decision = AutoApplyDecision.REVIEW_REQUIRED
            reason = "AI analysis failed - human review required"
        elif risk_level == RiskLevel.CRITICAL:
            decision = AutoApplyDecision.SKIP_PERMANENTLY
            reason = "Critical risk factors identified"
        elif not risk_proceed:
            decision = AutoApplyDecision.SKIP_TEMPORARILY
            reason = "High risk factors present"
        elif match_score < 60:
            decision = AutoApplyDecision.SKIP_PERMANENTLY
            reason = "Low match score"
        elif ai_confidence < 0.6:
            decision = AutoApplyDecision.REVIEW_REQUIRED
            reason = "Low AI confidence - human review recommended"
        elif timing_score >= 80 and ai_confidence >= 0.8 and match_score >= 75:
            decision = AutoApplyDecision.APPLY_IMMEDIATELY
            reason = "Optimal conditions for immediate application"
        elif timing_score >= 60 and ai_confidence >= 0.7 and match_score >= 70:
            decision = AutoApplyDecision.APPLY_SCHEDULED
            reason = "Good conditions for scheduled application"
        else:
            decision = AutoApplyDecision.REVIEW_REQUIRED
            reason = "Mixed signals - human review recommended"
        
        # Generate application strategy if applying
        strategy = None
        if decision in [AutoApplyDecision.APPLY_IMMEDIATELY, AutoApplyDecision.APPLY_SCHEDULED]:
            strategy = await self._generate_application_strategy(analysis_data, ai_analysis)
        
        # Compile comprehensive analysis
        decision_analysis = {
            "decision": decision.value,
            "confidence": ai_confidence,
            "reasoning": reason,
            "match_score": match_score,
            "risk_assessment": risk_assessment,
            "timing_analysis": timing_analysis,
            "ai_analysis": ai_analysis if ai_success else None,
            "application_strategy": asdict(strategy) if strategy else None,
            "quality_scores": {
                "overall": (match_score + timing_score + (1 - risk_assessment["risk_score"]) * 100) / 3,
                "match": match_score,
                "timing": timing_score,
                "risk": (1 - risk_assessment["risk_score"]) * 100,
                "ai_confidence": ai_confidence * 100
            },
            "metadata": {
                "analysis_duration_ms": 0,  # Would be calculated
                "models_used": ["enhanced_prompts", "risk_assessment", "timing_analysis"],
                "decision_factors": len([ai_success, risk_proceed, timing_score >= 60, match_score >= 70])
            }
        }
        
        return decision, decision_analysis

    async def _gather_market_intelligence(self, job_details: Dict[str, Any]) -> MarketIntelligence:
        """Gather market intelligence data"""
        # In production, this would integrate with market data APIs
        return MarketIntelligence(
            industry_trends={"growth_rate": "moderate", "hiring_velocity": "normal"},
            salary_benchmarks={"median": 120000, "range": [95000, 150000]},
            competition_analysis={"applicant_volume": "medium", "skill_demand": "high"},
            hiring_patterns={"seasonal_factor": 1.0, "economic_indicator": "stable"},
            seasonal_factors={"current_season": "normal", "hiring_peak": False}
        )

    async def _gather_company_intelligence(self, job_details: Dict[str, Any]) -> CompanyIntelligence:
        """Gather company-specific intelligence"""
        # In production, this would integrate with company data APIs
        return CompanyIntelligence(
            hiring_velocity=1.2,
            response_patterns={"avg_hours": 96, "response_rate": 0.65},
            culture_fit_indicators=["collaborative", "innovative", "fast-paced"],
            recent_news=["Series B funding", "New product launch"],
            growth_trajectory="positive",
            employee_satisfaction=4.2,
            technical_stack=["React", "Node.js", "AWS", "Python"]
        )

    async def _generate_application_strategy(
        self, 
        analysis_data: Dict[str, Any], 
        ai_analysis: Dict[str, Any]
    ) -> ApplicationStrategy:
        """Generate tailored application strategy"""
        
        execution_plan = ai_analysis.get("execution_plan", {})
        
        return ApplicationStrategy(
            cover_letter_template="enhanced_personalized",
            resume_customizations=execution_plan.get("resume_adjustments", []),
            application_timing="immediate",
            follow_up_schedule=["5_days", "2_weeks"],
            interview_prep_notes=execution_plan.get("interview_preparation", []),
            success_probability=ai_analysis.get("final_decision", {}).get("success_probability", 0.5),
            confidence_score=ai_analysis.get("final_decision", {}).get("confidence", 0.7)
        )

    def _generate_safety_recommendations(self, checks: List[Dict[str, Any]]) -> List[str]:
        """Generate safety recommendations based on failed checks"""
        recommendations = []
        for check in checks:
            if not check["passed"]:
                if check["check"] == "daily_limit":
                    recommendations.append("Wait until tomorrow to submit more applications")
                elif check["check"] == "weekly_limit":
                    recommendations.append("Weekly application limit reached - focus on quality over quantity")
                elif check["check"] == "company_frequency":
                    recommendations.append("Too many recent applications to this company - wait 30 days")
                elif check["check"] == "quality_threshold":
                    recommendations.append("Job match score below threshold - consider improving profile")
                elif check["check"] == "time_spacing":
                    recommendations.append("Wait longer between applications to maintain quality")
        return recommendations

    def _generate_risk_mitigation(self, risk_factors: List[str]) -> List[str]:
        """Generate risk mitigation strategies"""
        mitigations = []
        for factor in risk_factors:
            if "low-quality" in factor.lower():
                mitigations.append("Research company thoroughly before applying")
            elif "employee satisfaction" in factor.lower():
                mitigations.append("Investigate company culture through employee reviews")
            elif "salary" in factor.lower():
                mitigations.append("Research salary ranges before negotiating")
            elif "rejection rate" in factor.lower():
                mitigations.append("Review and improve application materials")
        return mitigations