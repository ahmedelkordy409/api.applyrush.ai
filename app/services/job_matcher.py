"""
Intelligent Job Matching Engine
Analyzes job compatibility using AI and algorithmic scoring
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import math
from dataclasses import dataclass
from enum import Enum

from app.ai.models import ai_model_manager, generate_job_match_analysis
from app.ai.prompts import AIPrompts, PromptType
from app.core.monitoring import performance_monitor
from app.models.database import MatchRecommendation
import structlog

logger = structlog.get_logger()


class MatchingStrategy(Enum):
    """Matching strategy types"""
    AI_POWERED = "ai_powered"        # Full AI analysis
    ALGORITHMIC = "algorithmic"     # Rule-based scoring
    HYBRID = "hybrid"              # AI + algorithmic combined


@dataclass
class MatchingWeights:
    """Configurable weights for matching criteria"""
    skills: float = 0.40
    experience: float = 0.25
    education: float = 0.10
    location: float = 0.10
    salary: float = 0.10
    culture: float = 0.05


class JobMatchingEngine:
    """Advanced job matching engine with AI and algorithmic approaches"""
    
    def __init__(self):
        self.default_weights = MatchingWeights()
        self.skill_synonyms = self._load_skill_synonyms()
        self.title_hierarchies = self._load_title_hierarchies()
    
    async def match_job_to_user(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        strategy: MatchingStrategy = MatchingStrategy.HYBRID,
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """
        Main job matching function
        Returns comprehensive matching analysis
        """
        
        start_time = datetime.utcnow()
        
        try:
            if strategy == MatchingStrategy.AI_POWERED:
                result = await self._ai_powered_matching(job_data, user_profile, user_tier)
            elif strategy == MatchingStrategy.ALGORITHMIC:
                result = await self._algorithmic_matching(job_data, user_profile)
            else:  # HYBRID
                result = await self._hybrid_matching(job_data, user_profile, user_tier)
            
            # Add metadata
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            result["metadata"] = {
                "processing_time_seconds": processing_time,
                "strategy_used": strategy.value,
                "matched_at": start_time.isoformat(),
                "user_tier": user_tier
            }
            
            # Record performance metrics
            performance_monitor.record_job_matching_accuracy(
                user_tier=user_tier,
                accuracy=result.get("overall_score", 0) / 100.0
            )
            
            return result
            
        except Exception as e:
            logger.error("Job matching error", 
                        job_id=job_data.get("external_id"),
                        user_id=user_profile.get("id"),
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "overall_score": 0,
                "recommendation": MatchRecommendation.WEAK_MATCH.value
            }
    
    async def _ai_powered_matching(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        user_tier: str
    ) -> Dict[str, Any]:
        """Use AI model for job matching analysis"""
        
        logger.info("Running AI-powered job matching", 
                   job_id=job_data.get("external_id"),
                   user_tier=user_tier)
        
        # Generate AI analysis
        ai_result = await generate_job_match_analysis(job_data, user_profile, user_tier)
        
        if ai_result["success"]:
            analysis = ai_result["analysis"]
            
            # Enhance with algorithmic insights
            algo_scores = await self._calculate_algorithmic_scores(job_data, user_profile)
            
            # Merge AI and algorithmic results
            enhanced_result = self._merge_ai_and_algorithmic_results(analysis, algo_scores)
            
            return {
                "success": True,
                "source": "ai_powered",
                **enhanced_result,
                "ai_metadata": ai_result.get("metadata", {})
            }
        else:
            # Fallback to algorithmic matching if AI fails
            logger.warning("AI matching failed, falling back to algorithmic",
                          error=ai_result.get("error"))
            return await self._algorithmic_matching(job_data, user_profile)
    
    async def _algorithmic_matching(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rule-based algorithmic job matching"""
        
        logger.info("Running algorithmic job matching", 
                   job_id=job_data.get("external_id"))
        
        # Calculate individual scores
        scores = await self._calculate_algorithmic_scores(job_data, user_profile)
        
        # Calculate overall score
        weights = self.default_weights
        overall_score = (
            scores["skills"]["score"] * weights.skills +
            scores["experience"]["score"] * weights.experience +
            scores["education"]["score"] * weights.education +
            scores["location"]["score"] * weights.location +
            scores["salary"]["score"] * weights.salary +
            scores["culture"]["score"] * weights.culture
        )
        
        # Determine recommendation
        recommendation = self._score_to_recommendation(overall_score)
        
        # Generate improvement suggestions
        suggestions = self._generate_improvement_suggestions(scores, job_data, user_profile)
        
        # Calculate success probability
        success_probability = self._calculate_success_probability(overall_score, scores)
        
        return {
            "success": True,
            "source": "algorithmic",
            "overall_score": round(overall_score, 1),
            "category_scores": scores,
            "recommendation": recommendation.value,
            "apply_priority": self._calculate_priority(overall_score),
            "success_probability": success_probability,
            "improvement_suggestions": suggestions,
            "red_flags": self._identify_red_flags(job_data, scores),
            "competitive_advantage": self._identify_competitive_advantage(scores, user_profile)
        }
    
    async def _hybrid_matching(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        user_tier: str
    ) -> Dict[str, Any]:
        """Combine AI and algorithmic approaches for best accuracy"""
        
        logger.info("Running hybrid job matching", 
                   job_id=job_data.get("external_id"))
        
        # Run both approaches concurrently
        ai_task = asyncio.create_task(
            self._ai_powered_matching(job_data, user_profile, user_tier)
        )
        algo_task = asyncio.create_task(
            self._algorithmic_matching(job_data, user_profile)
        )
        
        ai_result, algo_result = await asyncio.gather(ai_task, algo_task, return_exceptions=True)
        
        # Handle any errors
        if isinstance(ai_result, Exception):
            logger.warning("AI matching failed in hybrid mode", error=str(ai_result))
            ai_result = {"success": False}
        
        if isinstance(algo_result, Exception):
            logger.warning("Algorithmic matching failed in hybrid mode", error=str(algo_result))
            algo_result = {"success": False}
        
        # Combine results
        if ai_result.get("success") and algo_result.get("success"):
            return self._combine_hybrid_results(ai_result, algo_result)
        elif ai_result.get("success"):
            return ai_result
        elif algo_result.get("success"):
            return algo_result
        else:
            return {
                "success": False,
                "error": "Both AI and algorithmic matching failed",
                "overall_score": 0,
                "recommendation": MatchRecommendation.WEAK_MATCH.value
            }
    
    async def _calculate_algorithmic_scores(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate detailed algorithmic scores for each category"""
        
        # Skills matching
        skills_score = await self._calculate_skills_score(job_data, user_profile)
        
        # Experience matching
        experience_score = await self._calculate_experience_score(job_data, user_profile)
        
        # Education matching
        education_score = await self._calculate_education_score(job_data, user_profile)
        
        # Location matching
        location_score = await self._calculate_location_score(job_data, user_profile)
        
        # Salary matching
        salary_score = await self._calculate_salary_score(job_data, user_profile)
        
        # Culture matching
        culture_score = await self._calculate_culture_score(job_data, user_profile)
        
        return {
            "skills": skills_score,
            "experience": experience_score,
            "education": education_score,
            "location": location_score,
            "salary": salary_score,
            "culture": culture_score
        }
    
    async def _calculate_skills_score(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate skills matching score"""
        
        required_skills = job_data.get("required_skills", [])
        preferred_skills = job_data.get("preferred_skills", [])
        user_skills = user_profile.get("skills", [])
        
        if not required_skills and not preferred_skills:
            return {
                "score": 50.0,  # Neutral score when no skills specified
                "matched": [],
                "missing": [],
                "details": "No specific skills requirements found"
            }
        
        # Normalize skills for comparison
        required_normalized = [self._normalize_skill(skill) for skill in required_skills]
        preferred_normalized = [self._normalize_skill(skill) for skill in preferred_skills]
        user_normalized = [self._normalize_skill(skill) for skill in user_skills]
        
        # Find matches
        matched_required = []
        matched_preferred = []
        
        for user_skill in user_normalized:
            if user_skill in required_normalized:
                matched_required.append(user_skill)
            elif user_skill in preferred_normalized:
                matched_preferred.append(user_skill)
        
        # Calculate score
        if required_skills:
            required_match_rate = len(matched_required) / len(required_skills)
            base_score = required_match_rate * 70  # Required skills worth 70 points
        else:
            base_score = 50  # Neutral base when no required skills
        
        # Bonus for preferred skills
        if preferred_skills:
            preferred_match_rate = len(matched_preferred) / len(preferred_skills)
            bonus_score = preferred_match_rate * 30  # Preferred skills worth 30 points
        else:
            bonus_score = 0
        
        total_score = min(base_score + bonus_score, 100)
        
        # Missing skills
        missing_required = [skill for skill in required_skills 
                          if self._normalize_skill(skill) not in user_normalized]
        
        return {
            "score": round(total_score, 1),
            "matched": matched_required + matched_preferred,
            "missing": missing_required,
            "required_match_rate": len(matched_required) / len(required_skills) if required_skills else 1.0,
            "preferred_match_rate": len(matched_preferred) / len(preferred_skills) if preferred_skills else 0.0
        }
    
    async def _calculate_experience_score(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate experience matching score"""
        
        job_experience_level = job_data.get("experience_level", "mid-level")
        user_experience_years = user_profile.get("experience_years", 0)
        
        # Experience level mappings
        level_years = {
            "entry-level": (0, 2),
            "mid-level": (2, 5),
            "senior-level": (5, float('inf'))
        }
        
        min_years, max_years = level_years.get(job_experience_level, (2, 5))
        
        # Calculate score based on experience alignment
        if min_years <= user_experience_years <= max_years:
            score = 100
            match_type = "perfect"
        elif user_experience_years < min_years:
            # Under-qualified
            gap = min_years - user_experience_years
            score = max(50 - gap * 10, 0)
            match_type = "under_qualified"
        else:
            # Over-qualified
            excess = user_experience_years - max_years
            score = max(90 - excess * 5, 60)  # Less penalty for being over-qualified
            match_type = "over_qualified"
        
        return {
            "score": round(score, 1),
            "years_match": match_type == "perfect",
            "user_years": user_experience_years,
            "required_range": f"{min_years}-{max_years if max_years != float('inf') else '10+'} years",
            "match_type": match_type
        }
    
    async def _calculate_education_score(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate education matching score"""
        
        required_education = job_data.get("education_requirements", "bachelor")
        user_education = user_profile.get("education", {})
        
        if not user_education:
            return {
                "score": 50.0,
                "meets_requirements": False,
                "details": "No education information provided"
            }
        
        # Education level hierarchy
        education_levels = {
            "high_school": 1,
            "associate": 2,
            "bachelor": 3,
            "masters": 4,
            "doctorate": 5
        }
        
        required_level = education_levels.get(required_education, 3)
        
        # Get highest user education level
        user_degrees = user_education.get("degrees", [])
        if not user_degrees:
            user_level = 1  # Assume high school if no degrees specified
        else:
            user_level = max(education_levels.get(degree.get("level", "bachelor"), 3) 
                           for degree in user_degrees)
        
        # Calculate score
        if user_level >= required_level:
            score = 100
            meets_requirements = True
        else:
            # Penalty for not meeting education requirements
            level_gap = required_level - user_level
            score = max(70 - level_gap * 15, 0)
            meets_requirements = False
        
        return {
            "score": round(score, 1),
            "meets_requirements": meets_requirements,
            "required": required_education,
            "user_level": user_level,
            "required_level": required_level
        }
    
    async def _calculate_location_score(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate location compatibility score"""
        
        job_location = job_data.get("location", {})
        job_remote = job_data.get("remote_option", "no")
        user_preferences = user_profile.get("preferences", {})
        user_location = user_preferences.get("location", {})
        user_remote_preference = user_preferences.get("remote_preference", "hybrid")
        
        # Full remote jobs are always compatible
        if job_remote == "full":
            return {
                "score": 100.0,
                "remote_compatible": True,
                "distance_km": 0,
                "details": "Fully remote position"
            }
        
        # User prefers remote but job is not remote
        if user_remote_preference == "remote_only" and job_remote == "no":
            return {
                "score": 10.0,
                "remote_compatible": False,
                "details": "User requires remote work but job is on-site"
            }
        
        # Calculate distance if both locations available
        if (job_location.get("city") and job_location.get("state") and
            user_location.get("city") and user_location.get("state")):
            
            # Simplified distance calculation (would use proper geo-calculation in production)
            if (job_location["city"].lower() == user_location["city"].lower() and
                job_location["state"].lower() == user_location["state"].lower()):
                distance = 0
                score = 100
            elif job_location["state"].lower() == user_location["state"].lower():
                distance = 100  # Estimated within-state distance
                score = 80
            else:
                distance = 500  # Estimated inter-state distance
                score = 30
            
            return {
                "score": float(score),
                "remote_compatible": job_remote in ["hybrid", "full"],
                "distance_km": distance,
                "same_city": distance == 0
            }
        
        # Default score when location data is incomplete
        return {
            "score": 70.0,
            "remote_compatible": job_remote != "no",
            "details": "Insufficient location data for precise matching"
        }
    
    async def _calculate_salary_score(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate salary alignment score"""
        
        job_salary_min = job_data.get("salary_min")
        job_salary_max = job_data.get("salary_max")
        user_preferences = user_profile.get("preferences", {})
        user_salary_min = user_preferences.get("salary_minimum")
        user_salary_target = user_preferences.get("salary_target")
        
        # If no salary information available, return neutral score
        if not any([job_salary_min, job_salary_max, user_salary_min, user_salary_target]):
            return {
                "score": 70.0,
                "within_range": None,
                "details": "No salary information available"
            }
        
        # Calculate job salary range midpoint
        if job_salary_min and job_salary_max:
            job_salary_mid = (job_salary_min + job_salary_max) / 2
        elif job_salary_min:
            job_salary_mid = job_salary_min * 1.2  # Estimate max as 20% higher
        elif job_salary_max:
            job_salary_mid = job_salary_max * 0.8  # Estimate min as 20% lower
        else:
            return {
                "score": 70.0,
                "within_range": None,
                "details": "No job salary information"
            }
        
        # Compare with user expectations
        if user_salary_target:
            salary_diff_percent = abs(job_salary_mid - user_salary_target) / user_salary_target
            if salary_diff_percent <= 0.1:  # Within 10%
                score = 100
            elif salary_diff_percent <= 0.2:  # Within 20%
                score = 80
            elif salary_diff_percent <= 0.3:  # Within 30%
                score = 60
            else:
                score = 30
        elif user_salary_min:
            if job_salary_mid >= user_salary_min:
                score = 90
            else:
                score = 20
        else:
            score = 70  # Neutral when no user expectations
        
        # Check if job meets minimum requirements
        within_range = True
        if user_salary_min and job_salary_max and job_salary_max < user_salary_min:
            within_range = False
        
        # Calculate negotiation room
        negotiation_room = 0
        if job_salary_max and user_salary_target:
            negotiation_room = max(0, job_salary_max - user_salary_target)
        
        return {
            "score": float(score),
            "within_range": within_range,
            "negotiation_room": negotiation_room,
            "job_range": f"${job_salary_min:,}-${job_salary_max:,}" if job_salary_min and job_salary_max else None
        }
    
    async def _calculate_culture_score(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate culture fit score"""
        
        # Extract culture indicators from job description
        job_description = job_data.get("description", "").lower()
        company_data = job_data.get("company", {})
        user_preferences = user_profile.get("preferences", {})
        
        # Culture keywords and their weights
        culture_indicators = {
            "innovation": ["innovative", "cutting-edge", "disruptive", "technology"],
            "collaboration": ["team", "collaborative", "together", "partnership"],
            "flexibility": ["flexible", "work-life balance", "remote", "hybrid"],
            "growth": ["growth", "learning", "development", "career"],
            "diversity": ["diverse", "inclusive", "equality", "belonging"],
            "entrepreneurial": ["startup", "entrepreneurial", "fast-paced", "agile"],
            "stability": ["stable", "established", "enterprise", "mature"]
        }
        
        # Find culture matches
        job_culture_scores = {}
        for culture_type, keywords in culture_indicators.items():
            score = sum(1 for keyword in keywords if keyword in job_description)
            job_culture_scores[culture_type] = score
        
        # User culture preferences (would be collected during onboarding)
        user_culture_prefs = user_preferences.get("culture_preferences", {})
        
        if not user_culture_prefs:
            # Default neutral score when no preferences specified
            return {
                "score": 70.0,
                "alignment_factors": [],
                "details": "No culture preferences specified"
            }
        
        # Calculate alignment
        total_alignment = 0
        alignment_factors = []
        
        for culture_type, user_importance in user_culture_prefs.items():
            if culture_type in job_culture_scores and user_importance > 0:
                job_presence = min(job_culture_scores[culture_type], 3) / 3  # Normalize to 0-1
                alignment = job_presence * user_importance
                total_alignment += alignment
                
                if alignment > 0.5:
                    alignment_factors.append(culture_type)
        
        # Normalize score to 0-100
        max_possible_alignment = sum(user_culture_prefs.values())
        if max_possible_alignment > 0:
            score = (total_alignment / max_possible_alignment) * 100
        else:
            score = 70
        
        return {
            "score": round(score, 1),
            "alignment_factors": alignment_factors,
            "culture_match_details": job_culture_scores
        }
    
    def _normalize_skill(self, skill: str) -> str:
        """Normalize skill name for comparison"""
        skill_lower = skill.lower().strip()
        
        # Check for synonyms
        for canonical, synonyms in self.skill_synonyms.items():
            if skill_lower in synonyms:
                return canonical
        
        return skill_lower
    
    def _load_skill_synonyms(self) -> Dict[str, List[str]]:
        """Load skill synonyms mapping"""
        return {
            "javascript": ["js", "javascript", "ecmascript"],
            "python": ["python", "py"],
            "react": ["react", "reactjs", "react.js"],
            "node.js": ["node", "nodejs", "node.js"],
            "aws": ["aws", "amazon web services"],
            "docker": ["docker", "containerization"],
            "kubernetes": ["kubernetes", "k8s"],
            "postgresql": ["postgresql", "postgres", "psql"],
            "mongodb": ["mongodb", "mongo"],
            "machine learning": ["ml", "machine learning", "artificial intelligence", "ai"]
        }
    
    def _load_title_hierarchies(self) -> Dict[str, int]:
        """Load job title hierarchies"""
        return {
            "intern": 1,
            "junior": 2,
            "associate": 3,
            "software engineer": 4,
            "senior": 5,
            "staff": 6,
            "principal": 7,
            "lead": 7,
            "manager": 8,
            "director": 9,
            "vp": 10,
            "cto": 11
        }
    
    def _score_to_recommendation(self, score: float) -> MatchRecommendation:
        """Convert numeric score to recommendation enum"""
        if score >= 85:
            return MatchRecommendation.STRONG_MATCH
        elif score >= 70:
            return MatchRecommendation.GOOD_MATCH
        elif score >= 50:
            return MatchRecommendation.POSSIBLE_MATCH
        else:
            return MatchRecommendation.WEAK_MATCH
    
    def _calculate_priority(self, score: float) -> int:
        """Calculate application priority (1-10)"""
        return min(10, max(1, int(score / 10)))
    
    def _calculate_success_probability(
        self,
        overall_score: float,
        category_scores: Dict[str, Dict[str, Any]]
    ) -> float:
        """Calculate probability of application success"""
        
        # Base probability from overall score
        base_prob = overall_score / 100.0
        
        # Adjust based on critical factors
        skills_score = category_scores["skills"]["score"]
        experience_score = category_scores["experience"]["score"]
        
        # Skills and experience are most predictive of success
        if skills_score >= 80 and experience_score >= 80:
            adjustment = 0.2
        elif skills_score >= 60 and experience_score >= 60:
            adjustment = 0.1
        else:
            adjustment = -0.1
        
        return max(0.0, min(1.0, base_prob + adjustment))
    
    def _generate_improvement_suggestions(
        self,
        scores: Dict[str, Dict[str, Any]],
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable improvement suggestions"""
        
        suggestions = []
        
        # Skills improvements
        skills_data = scores["skills"]
        if skills_data["score"] < 70 and skills_data.get("missing"):
            missing_skills = skills_data["missing"][:3]  # Top 3 missing skills
            suggestions.append(f"Consider learning these skills: {', '.join(missing_skills)}")
        
        # Experience improvements
        experience_data = scores["experience"]
        if experience_data["score"] < 70:
            match_type = experience_data.get("match_type")
            if match_type == "under_qualified":
                suggestions.append("Consider gaining more relevant experience or applying to entry-level positions")
            elif match_type == "over_qualified":
                suggestions.append("Highlight leadership and mentoring abilities to justify seniority")
        
        # Education improvements
        education_data = scores["education"]
        if not education_data.get("meets_requirements"):
            required = education_data.get("required", "bachelor")
            suggestions.append(f"Consider pursuing {required} degree or emphasize equivalent experience")
        
        return suggestions
    
    def _identify_red_flags(
        self,
        job_data: Dict[str, Any],
        scores: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Identify potential red flags in the job posting"""
        
        red_flags = []
        
        job_description = job_data.get("description", "").lower()
        
        # Common red flag indicators
        red_flag_patterns = [
            "no experience necessary",
            "make money fast",
            "work from home opportunity",
            "earn up to",
            "unlimited earning potential",
            "pyramid",
            "mlm"
        ]
        
        for pattern in red_flag_patterns:
            if pattern in job_description:
                red_flags.append(f"Potential scam indicator: '{pattern}'")
        
        # Salary red flags
        salary_data = scores["salary"]
        if not salary_data.get("within_range", True):
            red_flags.append("Salary below your minimum requirements")
        
        return red_flags
    
    def _identify_competitive_advantage(
        self,
        scores: Dict[str, Dict[str, Any]],
        user_profile: Dict[str, Any]
    ) -> str:
        """Identify user's competitive advantage for this role"""
        
        advantages = []
        
        # Skills advantage
        skills_data = scores["skills"]
        if skills_data["score"] >= 80:
            matched_count = len(skills_data.get("matched", []))
            if matched_count >= 3:
                advantages.append(f"Strong technical skill match ({matched_count} key skills)")
        
        # Experience advantage
        experience_data = scores["experience"]
        if experience_data["score"] >= 90:
            years = experience_data.get("user_years", 0)
            advantages.append(f"Excellent experience fit ({years} years relevant experience)")
        
        # Education advantage
        education_data = scores["education"]
        if education_data.get("meets_requirements") and education_data["score"] >= 90:
            advantages.append("Educational background aligns perfectly")
        
        if advantages:
            return "; ".join(advantages)
        else:
            return "Consider highlighting unique projects or achievements to stand out"
    
    def _merge_ai_and_algorithmic_results(
        self,
        ai_result: Dict[str, Any],
        algo_scores: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge AI and algorithmic results for enhanced accuracy"""
        
        # Use AI result as base, enhance with algorithmic details
        merged_result = ai_result.copy()
        
        # Enhance category scores with algorithmic details
        if "category_scores" in merged_result:
            for category, ai_score_data in merged_result["category_scores"].items():
                if category in algo_scores:
                    # Merge algorithmic details into AI scores
                    algo_data = algo_scores[category]
                    ai_score_data.update({
                        "algorithmic_score": algo_data.get("score", 0),
                        "algorithmic_details": algo_data
                    })
        
        return merged_result
    
    def _combine_hybrid_results(
        self,
        ai_result: Dict[str, Any],
        algo_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine AI and algorithmic results with weighted averaging"""
        
        # Weight AI results higher for premium users, algorithmic for free users
        ai_weight = 0.7
        algo_weight = 0.3
        
        # Combine overall scores
        ai_score = ai_result.get("overall_score", 0)
        algo_score = algo_result.get("overall_score", 0)
        combined_score = (ai_score * ai_weight) + (algo_score * algo_weight)
        
        # Use AI result as base structure
        result = ai_result.copy()
        result.update({
            "overall_score": round(combined_score, 1),
            "source": "hybrid",
            "component_scores": {
                "ai_score": ai_score,
                "algorithmic_score": algo_score,
                "weights": {"ai": ai_weight, "algorithmic": algo_weight}
            }
        })
        
        # Use more conservative success probability
        ai_prob = ai_result.get("success_probability", 0)
        algo_prob = algo_result.get("success_probability", 0)
        result["success_probability"] = min(ai_prob, algo_prob)
        
        return result
    
    async def batch_match_jobs(
        self,
        jobs: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        strategy: MatchingStrategy = MatchingStrategy.HYBRID,
        user_tier: str = "free"
    ) -> List[Dict[str, Any]]:
        """Batch process multiple job matches efficiently"""
        
        logger.info(f"Starting batch job matching for {len(jobs)} jobs")
        
        # Create matching tasks
        tasks = []
        for job in jobs:
            task = asyncio.create_task(
                self.match_job_to_user(job, user_profile, strategy, user_tier)
            )
            tasks.append(task)
        
        # Execute with concurrency limit
        semaphore = asyncio.Semaphore(10)  # Limit concurrent matches
        
        async def limited_match(task):
            async with semaphore:
                return await task
        
        # Wait for all matches to complete
        results = await asyncio.gather(*[limited_match(task) for task in tasks])
        
        # Sort by overall score
        successful_results = [r for r in results if r.get("success", False)]
        successful_results.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
        
        logger.info(f"Completed batch matching: {len(successful_results)} successful matches")
        
        return successful_results


# Global job matching engine instance
job_matching_engine = JobMatchingEngine()


# Export public interfaces
__all__ = [
    "JobMatchingEngine",
    "MatchingStrategy", 
    "MatchingWeights",
    "job_matching_engine"
]