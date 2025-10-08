"""
Job fetching service for external job boards and APIs.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from jobhire.shared.domain.types import EntityId
from jobhire.domains.job.domain.entities.job import Job, JobRequirements, JobCompensation, EmploymentType, ExperienceLevel

logger = structlog.get_logger(__name__)


class JobFetchingService:
    """Service for fetching jobs from external sources."""

    def __init__(self):
        self.sources = {
            "indeed": True,
            "linkedin": True,
            "glassdoor": False,  # Premium feature
            "stackoverflow": True,
            "github_jobs": False,  # Deprecated
            "remote_ok": True,
            "angel_list": False   # Premium feature
        }

    async def fetch_jobs_by_keywords(
        self,
        keywords: List[str],
        location: Optional[str] = None,
        remote_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch jobs by keywords from multiple sources."""
        try:
            tasks = []

            if self.sources["indeed"]:
                tasks.append(self._fetch_from_indeed(keywords, location, remote_only, limit // 4))

            if self.sources["linkedin"]:
                tasks.append(self._fetch_from_linkedin(keywords, location, remote_only, limit // 4))

            if self.sources["stackoverflow"]:
                tasks.append(self._fetch_from_stackoverflow(keywords, location, remote_only, limit // 4))

            if self.sources["remote_ok"]:
                tasks.append(self._fetch_from_remote_ok(keywords, location, limit // 4))

            # Execute all fetching tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine and deduplicate results
            all_jobs = []
            for result in results:
                if isinstance(result, list):
                    all_jobs.extend(result)
                elif isinstance(result, Exception):
                    logger.warning("Job fetching error", error=str(result))

            return self._deduplicate_jobs(all_jobs)[:limit]

        except Exception as e:
            logger.error("Job fetching failed", error=str(e))
            return []

    async def _fetch_from_indeed(
        self,
        keywords: List[str],
        location: Optional[str],
        remote_only: bool,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch jobs from Indeed."""
        # Mock implementation - in production this would use Indeed's API
        await asyncio.sleep(0.5)  # Simulate API call

        jobs = []
        for i in range(min(limit, 10)):
            jobs.append({
                "title": f"Software Engineer - {keywords[0] if keywords else 'Tech'}",
                "company": f"Tech Company {i + 1}",
                "location": location or "San Francisco, CA",
                "description": f"Looking for a skilled developer with {keywords[0] if keywords else 'programming'} experience.",
                "source": "indeed",
                "external_id": f"indeed_{i + 1}",
                "employment_type": EmploymentType.FULL_TIME.value,
                "experience_level": ExperienceLevel.MID.value,
                "remote_allowed": remote_only or (i % 3 == 0),
                "posted_at": datetime.utcnow().isoformat(),
                "requirements": {
                    "skills": keywords + ["Python", "SQL"],
                    "experience_years": 2 + (i % 3),
                    "education_level": "Bachelor's degree"
                },
                "compensation": {
                    "salary_min": 80000 + (i * 5000),
                    "salary_max": 120000 + (i * 5000),
                    "currency": "USD"
                } if i % 2 == 0 else None
            })

        logger.info("Fetched jobs from Indeed", count=len(jobs))
        return jobs

    async def _fetch_from_linkedin(
        self,
        keywords: List[str],
        location: Optional[str],
        remote_only: bool,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch jobs from LinkedIn."""
        # Mock implementation
        await asyncio.sleep(0.7)

        jobs = []
        for i in range(min(limit, 8)):
            jobs.append({
                "title": f"Senior {keywords[0] if keywords else 'Developer'} Engineer",
                "company": f"LinkedIn Company {i + 1}",
                "location": location or "New York, NY",
                "description": f"We're seeking an experienced {keywords[0] if keywords else 'software'} professional.",
                "source": "linkedin",
                "external_id": f"linkedin_{i + 1}",
                "employment_type": EmploymentType.FULL_TIME.value,
                "experience_level": ExperienceLevel.SENIOR.value,
                "remote_allowed": remote_only or (i % 2 == 0),
                "posted_at": datetime.utcnow().isoformat(),
                "requirements": {
                    "skills": keywords + ["Leadership", "Architecture"],
                    "experience_years": 5 + (i % 2),
                    "education_level": "Bachelor's or Master's degree"
                },
                "compensation": {
                    "salary_min": 120000 + (i * 10000),
                    "salary_max": 180000 + (i * 10000),
                    "currency": "USD",
                    "equity_min": 0.1,
                    "equity_max": 0.5
                }
            })

        logger.info("Fetched jobs from LinkedIn", count=len(jobs))
        return jobs

    async def _fetch_from_stackoverflow(
        self,
        keywords: List[str],
        location: Optional[str],
        remote_only: bool,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch jobs from Stack Overflow."""
        # Mock implementation
        await asyncio.sleep(0.3)

        jobs = []
        for i in range(min(limit, 6)):
            jobs.append({
                "title": f"{keywords[0] if keywords else 'Full Stack'} Developer",
                "company": f"Stack Company {i + 1}",
                "location": location or "Remote",
                "description": f"Join our team working with {keywords[0] if keywords else 'modern'} technologies.",
                "source": "stackoverflow",
                "external_id": f"stackoverflow_{i + 1}",
                "employment_type": EmploymentType.FULL_TIME.value,
                "experience_level": ExperienceLevel.MID.value,
                "remote_allowed": True,
                "posted_at": datetime.utcnow().isoformat(),
                "requirements": {
                    "skills": keywords + ["Git", "Agile"],
                    "experience_years": 3 + (i % 2),
                    "education_level": "Relevant experience"
                },
                "compensation": {
                    "salary_min": 90000 + (i * 8000),
                    "salary_max": 140000 + (i * 8000),
                    "currency": "USD"
                }
            })

        logger.info("Fetched jobs from Stack Overflow", count=len(jobs))
        return jobs

    async def _fetch_from_remote_ok(
        self,
        keywords: List[str],
        location: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch remote jobs from Remote OK."""
        # Mock implementation
        await asyncio.sleep(0.4)

        jobs = []
        for i in range(min(limit, 8)):
            jobs.append({
                "title": f"Remote {keywords[0] if keywords else 'Developer'}",
                "company": f"Remote Company {i + 1}",
                "location": "Remote",
                "description": f"100% remote position for {keywords[0] if keywords else 'talented'} developers.",
                "source": "remote_ok",
                "external_id": f"remote_ok_{i + 1}",
                "employment_type": EmploymentType.FULL_TIME.value,
                "experience_level": ExperienceLevel.MID.value,
                "remote_allowed": True,
                "posted_at": datetime.utcnow().isoformat(),
                "requirements": {
                    "skills": keywords + ["Remote Communication", "Self-motivated"],
                    "experience_years": 2 + (i % 3),
                    "education_level": "Any"
                },
                "compensation": {
                    "salary_min": 70000 + (i * 6000),
                    "salary_max": 110000 + (i * 6000),
                    "currency": "USD"
                }
            })

        logger.info("Fetched jobs from Remote OK", count=len(jobs))
        return jobs

    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on title and company."""
        seen = set()
        unique_jobs = []

        for job in jobs:
            key = (job["title"].lower(), job["company"].lower())
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        logger.info("Deduplicated jobs", original_count=len(jobs), unique_count=len(unique_jobs))
        return unique_jobs

    async def fetch_job_details(self, source: str, external_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a specific job."""
        try:
            if source == "indeed":
                return await self._fetch_indeed_details(external_id)
            elif source == "linkedin":
                return await self._fetch_linkedin_details(external_id)
            elif source == "stackoverflow":
                return await self._fetch_stackoverflow_details(external_id)
            elif source == "remote_ok":
                return await self._fetch_remote_ok_details(external_id)
            else:
                logger.warning("Unknown job source", source=source)
                return None

        except Exception as e:
            logger.error("Failed to fetch job details", source=source, external_id=external_id, error=str(e))
            return None

    async def _fetch_indeed_details(self, external_id: str) -> Dict[str, Any]:
        """Fetch detailed job information from Indeed."""
        await asyncio.sleep(0.2)
        return {
            "detailed_description": "Full job description with benefits and requirements...",
            "company_info": {
                "size": "100-500 employees",
                "industry": "Technology",
                "benefits": ["Health insurance", "401k", "Flexible hours"]
            },
            "application_process": "Apply through Indeed"
        }

    async def _fetch_linkedin_details(self, external_id: str) -> Dict[str, Any]:
        """Fetch detailed job information from LinkedIn."""
        await asyncio.sleep(0.3)
        return {
            "detailed_description": "Comprehensive role description with growth opportunities...",
            "company_info": {
                "size": "500-1000 employees",
                "industry": "Software",
                "benefits": ["Premium health", "Stock options", "Learning budget"]
            },
            "application_process": "Apply through LinkedIn"
        }

    async def _fetch_stackoverflow_details(self, external_id: str) -> Dict[str, Any]:
        """Fetch detailed job information from Stack Overflow."""
        await asyncio.sleep(0.2)
        return {
            "detailed_description": "Technical role with modern stack and great team...",
            "company_info": {
                "size": "50-200 employees",
                "industry": "Technology",
                "benefits": ["Remote work", "Tech budget", "Conference attendance"]
            },
            "application_process": "Apply through Stack Overflow Jobs"
        }

    async def _fetch_remote_ok_details(self, external_id: str) -> Dict[str, Any]:
        """Fetch detailed job information from Remote OK."""
        await asyncio.sleep(0.2)
        return {
            "detailed_description": "Fully remote position with global team...",
            "company_info": {
                "size": "10-50 employees",
                "industry": "Remote-first company",
                "benefits": ["100% remote", "Flexible timezone", "Equipment budget"]
            },
            "application_process": "Apply through company website"
        }