"""
Intelligent Job Matching Service
Uses user profile data from onboarding, settings, and preferences for matching
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)


class JobMatcherService:
    """
    Enterprise-grade job matching using collected user data:
    - Onboarding data (job titles, experience, salary, location, etc.)
    - Settings (match threshold, preferences)
    - Profile data (skills, resume)
    - ATS compatibility
    """

    def __init__(self):
        self.min_match_score = 60  # Minimum viable match

    async def calculate_match_score(
        self,
        user_profile: Dict[str, Any],
        job: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive match score using all user data

        Returns:
            {
                "score": int (0-100),
                "reasons": List[str],
                "breakdown": Dict[str, int]
            }
        """
        try:
            score_breakdown = {}
            match_reasons = []

            # Extract user preferences
            preferences = user_profile.get("preferences", {})
            onboarding = user_profile.get("onboarding_data", {})

            # 1. JOB TITLE MATCH (25 points)
            title_score = self._match_job_title(
                user_titles=onboarding.get("job_titles", []),
                job_title=job.get("title", "")
            )
            score_breakdown["title"] = title_score
            if title_score >= 20:
                match_reasons.append(f"Job title matches your preferences ({title_score}%)")

            # 2. SALARY MATCH (20 points)
            salary_score = self._match_salary(
                user_min=onboarding.get("salary_min", 0),
                user_max=onboarding.get("salary_max", 999999),
                job_min=job.get("salary_min", 0),
                job_max=job.get("salary_max", 0)
            )
            score_breakdown["salary"] = salary_score
            if salary_score >= 15:
                match_reasons.append(f"Salary range aligns with expectations")

            # 3. LOCATION MATCH (15 points)
            location_score = self._match_location(
                user_locations=onboarding.get("preferred_locations", []),
                user_relocation=onboarding.get("relocation_willing", False),
                job_location=job.get("location", ""),
                job_remote=job.get("remote", False)
            )
            score_breakdown["location"] = location_score
            if location_score >= 10:
                match_reasons.append(f"Location matches preferences")

            # 4. WORK TYPE MATCH (15 points)
            work_type_score = self._match_work_type(
                user_types=onboarding.get("work_types", []),
                user_location_pref=onboarding.get("work_location_preference", "flexible"),
                job_type=job.get("job_type", ""),
                job_remote=job.get("remote", False)
            )
            score_breakdown["work_type"] = work_type_score
            if work_type_score >= 10:
                match_reasons.append(f"Work type matches your preferences")

            # 5. EXPERIENCE MATCH (10 points)
            experience_score = self._match_experience(
                user_years=onboarding.get("years_of_experience", 0),
                user_education=onboarding.get("education_level", ""),
                job_requirements=job.get("requirements", [])
            )
            score_breakdown["experience"] = experience_score
            if experience_score >= 7:
                match_reasons.append(f"Your experience level fits the role")

            # 6. INDUSTRY MATCH (10 points)
            industry_score = self._match_industry(
                user_industries=onboarding.get("industries", []),
                job_description=job.get("description", ""),
                job_company=job.get("company", "")
            )
            score_breakdown["industry"] = industry_score
            if industry_score >= 7:
                match_reasons.append(f"Industry aligns with your background")

            # 7. SKILLS MATCH (5 points)
            skills_score = self._match_skills(
                user_skills=onboarding.get("skills", []),
                job_requirements=job.get("requirements", []),
                job_description=job.get("description", "")
            )
            score_breakdown["skills"] = skills_score
            if skills_score >= 3:
                match_reasons.append(f"Your skills match job requirements")

            # Calculate total score
            total_score = sum(score_breakdown.values())

            # Apply user's match threshold preference
            user_threshold = preferences.get("match_threshold", "good-fit")
            threshold_boost = self._apply_user_preferences(
                total_score, user_threshold, match_reasons
            )
            total_score = min(100, total_score + threshold_boost)

            return {
                "score": int(total_score),
                "reasons": match_reasons[:5],  # Top 5 reasons
                "breakdown": score_breakdown,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error calculating match score: {e}")
            return {
                "score": 0,
                "reasons": ["Error calculating match"],
                "breakdown": {},
                "timestamp": datetime.utcnow().isoformat()
            }

    def _match_job_title(self, user_titles: List[str], job_title: str) -> int:
        """Match job title with user's preferred titles (0-25 points)"""
        if not user_titles or not job_title:
            return 0

        job_title_lower = job_title.lower()
        user_titles_lower = [t.lower() for t in user_titles]

        # Exact match
        if job_title_lower in user_titles_lower:
            return 25

        # Partial match
        for user_title in user_titles_lower:
            # Check if either title contains the other
            if user_title in job_title_lower or job_title_lower in user_title:
                return 20

            # Check for keyword overlap
            user_keywords = set(user_title.split())
            job_keywords = set(job_title_lower.split())
            overlap = user_keywords & job_keywords
            if len(overlap) >= 2:
                return 15

        return 5  # Minimal points for having preferences

    def _match_salary(
        self, user_min: int, user_max: int, job_min: int, job_max: int
    ) -> int:
        """Match salary ranges (0-20 points)"""
        if not job_min and not job_max:
            return 10  # No salary info, neutral

        # Calculate overlap
        if job_max >= user_min:
            if job_min <= user_max:
                # There's overlap
                if job_min >= user_min and job_max <= user_max:
                    return 20  # Perfect fit
                elif job_min >= user_min:
                    return 18  # Good fit, higher than minimum
                elif job_max >= user_max:
                    return 15  # Stretches to top of range
                else:
                    return 12  # Some overlap

        # Below minimum
        if job_max < user_min:
            return 0

        return 5

    def _match_location(
        self,
        user_locations: List[str],
        user_relocation: bool,
        job_location: str,
        job_remote: bool
    ) -> int:
        """Match location preferences (0-15 points)"""
        # Remote jobs are always a match if user wants remote
        if job_remote:
            return 15

        if not user_locations:
            return 8  # Neutral if no preference

        job_location_lower = job_location.lower()
        user_locations_lower = [loc.lower() for loc in user_locations]

        # Exact location match
        for user_loc in user_locations_lower:
            if user_loc in job_location_lower or job_location_lower in user_loc:
                return 15

        # Willing to relocate
        if user_relocation:
            return 10

        # No match
        return 3

    def _match_work_type(
        self,
        user_types: List[str],
        user_location_pref: str,
        job_type: str,
        job_remote: bool
    ) -> int:
        """Match work type and remote preference (0-15 points)"""
        score = 0

        # Check employment type match
        job_type_lower = job_type.lower()
        user_types_lower = [t.lower() for t in user_types]

        if job_type_lower in user_types_lower:
            score += 8
        elif any(t in job_type_lower for t in user_types_lower):
            score += 5

        # Check remote preference
        if job_remote:
            if user_location_pref in ["remote", "flexible"]:
                score += 7
            elif user_location_pref == "hybrid":
                score += 4
        else:
            if user_location_pref in ["onsite", "flexible"]:
                score += 7
            elif user_location_pref == "hybrid":
                score += 5

        return min(15, score)

    def _match_experience(
        self, user_years: int, user_education: str, job_requirements: List[str]
    ) -> int:
        """Match experience level (0-10 points)"""
        # Parse requirements for experience mentions
        requirements_text = " ".join(job_requirements).lower()

        # Common experience indicators
        if "entry" in requirements_text or "junior" in requirements_text:
            required_years = 1
        elif "senior" in requirements_text:
            required_years = 5
        elif "lead" in requirements_text or "principal" in requirements_text:
            required_years = 8
        else:
            # Try to extract years from requirements
            import re
            years_match = re.search(r'(\d+)\+?\s*years?', requirements_text)
            required_years = int(years_match.group(1)) if years_match else 3

        # Calculate score based on experience match
        if user_years >= required_years:
            if user_years <= required_years + 2:
                return 10  # Perfect match
            elif user_years <= required_years + 5:
                return 8  # Overqualified but acceptable
            else:
                return 5  # Significantly overqualified
        elif user_years >= required_years - 1:
            return 7  # Close enough
        else:
            return 3  # Underqualified

    def _match_industry(
        self, user_industries: List[str], job_description: str, job_company: str
    ) -> int:
        """Match industry preferences (0-10 points)"""
        if not user_industries:
            return 5  # Neutral

        combined_text = f"{job_description} {job_company}".lower()
        user_industries_lower = [ind.lower() for ind in user_industries]

        for industry in user_industries_lower:
            if industry in combined_text:
                return 10

        return 3

    def _match_skills(
        self, user_skills: List[str], job_requirements: List[str], job_description: str
    ) -> int:
        """Match skills (0-5 points)"""
        if not user_skills:
            return 0

        combined_text = f"{' '.join(job_requirements)} {job_description}".lower()
        user_skills_lower = [skill.lower() for skill in user_skills]

        matched_skills = sum(1 for skill in user_skills_lower if skill in combined_text)

        if matched_skills >= 5:
            return 5
        elif matched_skills >= 3:
            return 4
        elif matched_skills >= 1:
            return 3
        else:
            return 0

    def _apply_user_preferences(
        self, current_score: int, threshold: str, reasons: List[str]
    ) -> int:
        """Apply user's match threshold preference"""
        # User wants "top" matches only - be more strict
        if threshold == "top" and current_score < 85:
            return -5

        # User wants "open" matches - be more lenient
        if threshold == "open" and current_score >= 50:
            return 5

        return 0

    def passes_user_filters(
        self, user_profile: Dict[str, Any], job: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Check if job passes user's hard filters

        Returns:
            (passes: bool, reason: str)
        """
        onboarding = user_profile.get("onboarding_data", {})
        preferences = user_profile.get("preferences", {})

        # Check excluded companies
        excluded_companies = onboarding.get("excluded_companies", [])
        if job.get("company", "") in excluded_companies:
            return False, "Company is in exclusion list"

        # Check visa sponsorship
        if onboarding.get("visa_sponsorship_needed", False):
            job_desc = job.get("description", "").lower()
            if "no visa" in job_desc or "no sponsorship" in job_desc:
                return False, "Does not offer visa sponsorship"

        # Check work authorization
        work_auth = onboarding.get("work_authorization", "")
        if work_auth == "need_sponsorship":
            # Job must offer sponsorship
            job_desc = job.get("description", "").lower()
            if "sponsorship available" not in job_desc:
                return False, "No sponsorship mentioned"

        return True, "Passes all filters"


# Singleton instance
job_matcher_service = JobMatcherService()
