"""
JobSpy Integration Service
Uses JobSpy library for multi-platform job scraping (Indeed, Google Jobs, etc.)
Safe and legal scraping with no ToS violations
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from jobspy import scrape_jobs
import pandas as pd

logger = logging.getLogger(__name__)


class JobSpyScraperService:
    """
    Enhanced job scraping using JobSpy library
    Focuses on Indeed (most reliable) and Google Jobs
    """

    SUPPORTED_SITES = {
        "indeed": "Indeed (Most reliable, no rate limits)",
        "google": "Google Jobs (No rate limits)",
        # "zip_recruiter": "ZipRecruiter (Has rate limits)",
        # "linkedin": "LinkedIn (High rate limits, risky)",
    }

    def __init__(self):
        self.session_jobs_scraped = 0

    async def scrape_jobs_for_user(
        self,
        search_terms: List[str],
        locations: List[str],
        job_types: Optional[List[str]] = None,
        remote_preference: Optional[str] = None,
        results_wanted: int = 50,
        hours_old: int = 168,  # Last 7 days
        country: str = "USA"
    ) -> List[Dict[str, Any]]:
        """
        Scrape jobs from multiple platforms based on user preferences

        Args:
            search_terms: List of job titles/keywords
            locations: List of locations
            job_types: full_time, part_time, contract, internship
            remote_preference: remote, hybrid, onsite
            results_wanted: Number of jobs to fetch
            hours_old: Only get jobs posted within X hours
            country: Country code

        Returns:
            List of job dictionaries
        """
        all_jobs = []

        try:
            for search_term in search_terms:
                for location in locations:
                    logger.info(f"🔍 Scraping {search_term} jobs in {location}")

                    # Scrape from Indeed and Google Jobs
                    jobs_df = scrape_jobs(
                        site_name=["indeed", "google"],
                        search_term=search_term,
                        location=location,
                        results_wanted=results_wanted,
                        hours_old=hours_old,
                        country_indeed=country,
                        is_remote=remote_preference == "remote" if remote_preference else None,
                    )

                    if len(jobs_df) > 0:
                        # Convert DataFrame to list of dicts
                        jobs_list = jobs_df.to_dict('records')

                        # Transform to our schema
                        transformed_jobs = self._transform_jobs(
                            jobs_list,
                            job_types,
                            remote_preference
                        )

                        all_jobs.extend(transformed_jobs)
                        logger.info(f"✅ Found {len(transformed_jobs)} jobs for {search_term} in {location}")
                    else:
                        logger.warning(f"⚠️  No jobs found for {search_term} in {location}")

            self.session_jobs_scraped += len(all_jobs)
            logger.info(f"📊 Total jobs scraped: {len(all_jobs)}")

            return self._deduplicate_jobs(all_jobs)

        except Exception as e:
            logger.error(f"❌ Error scraping jobs: {e}")
            return []

    def _transform_jobs(
        self,
        jobs_list: List[Dict],
        job_types: Optional[List[str]],
        remote_preference: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Transform JobSpy results to our job schema"""
        transformed = []

        for job in jobs_list:
            try:
                # Apply filters
                if job_types:
                    job_type = str(job.get('job_type', '')).lower()
                    if not any(jt in job_type for jt in job_types):
                        continue

                if remote_preference == "remote" and not job.get('is_remote'):
                    continue

                # Transform to our schema
                transformed_job = {
                    "title": job.get('title', ''),
                    "company": job.get('company', ''),
                    "location": job.get('location', ''),
                    "description": job.get('description', ''),
                    "apply_url": job.get('job_url', ''),
                    "job_type": self._normalize_job_type(job.get('job_type')),
                    "remote": job.get('is_remote', False),
                    "salary_min": job.get('min_amount'),
                    "salary_max": job.get('max_amount'),
                    "salary_currency": job.get('currency', 'USD'),
                    "date_posted": self._parse_date(job.get('date_posted')),
                    "source": job.get('site', 'unknown'),
                    "external_id": f"{job.get('site', 'unknown')}_{job.get('id', '')}",
                    "company_info": {
                        "url": job.get('company_url'),
                        "logo": job.get('company_logo'),
                        "industry": job.get('company_industry'),
                        "employees": job.get('company_num_employees'),
                        "revenue": job.get('company_revenue'),
                        "description": job.get('company_description'),
                        "rating": job.get('company_rating'),
                    },
                    "skills": job.get('skills', []),
                    "is_active": True,
                    "scraped_at": datetime.utcnow(),
                }

                transformed.append(transformed_job)

            except Exception as e:
                logger.error(f"❌ Error transforming job: {e}")
                continue

        return transformed

    def _normalize_job_type(self, job_type: Any) -> str:
        """Normalize job type to our standard values"""
        if pd.isna(job_type) or not job_type:
            return "full_time"

        job_type_str = str(job_type).lower()

        if "full" in job_type_str or "fulltime" in job_type_str:
            return "full_time"
        elif "part" in job_type_str or "parttime" in job_type_str:
            return "part_time"
        elif "contract" in job_type_str or "contractor" in job_type_str:
            return "contract"
        elif "intern" in job_type_str:
            return "internship"
        elif "temporary" in job_type_str or "temp" in job_type_str:
            return "temporary"
        else:
            return "full_time"

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date from various formats"""
        if pd.isna(date_value) or not date_value:
            return None

        try:
            if isinstance(date_value, datetime):
                return date_value
            elif isinstance(date_value, str):
                return datetime.fromisoformat(date_value)
            else:
                return None
        except Exception:
            return None

    def _deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs based on external_id"""
        seen = set()
        unique_jobs = []

        for job in jobs:
            external_id = job.get('external_id')
            if external_id and external_id not in seen:
                seen.add(external_id)
                unique_jobs.append(job)

        logger.info(f"🔄 Deduplicated: {len(jobs)} → {len(unique_jobs)} unique jobs")
        return unique_jobs

    async def scrape_and_save_to_db(
        self,
        db,
        user_preferences: Dict[str, Any],
        results_wanted: int = 50
    ) -> Dict[str, Any]:
        """
        Scrape jobs based on user preferences and save to database

        Args:
            db: Database connection
            user_preferences: User's job preferences from onboarding
            results_wanted: Number of jobs to fetch

        Returns:
            Statistics about the scraping operation
        """
        try:
            # Extract preferences
            search_terms = user_preferences.get('desired_positions', ['software engineer'])
            locations = user_preferences.get('preferred_locations', ['USA'])
            job_types = user_preferences.get('employment_types', ['full_time'])
            remote_preference = user_preferences.get('remote_preference', 'any')

            # Scrape jobs
            jobs = await self.scrape_jobs_for_user(
                search_terms=search_terms,
                locations=locations,
                job_types=job_types,
                remote_preference=remote_preference,
                results_wanted=results_wanted
            )

            # Save to database
            inserted_count = 0
            updated_count = 0

            for job in jobs:
                existing = await db.jobs.find_one({
                    "external_id": job['external_id']
                })

                if existing:
                    # Update existing job
                    await db.jobs.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {
                            **job,
                            "updated_at": datetime.utcnow()
                        }}
                    )
                    updated_count += 1
                else:
                    # Insert new job
                    job['created_at'] = datetime.utcnow()
                    job['updated_at'] = datetime.utcnow()
                    await db.jobs.insert_one(job)
                    inserted_count += 1

            return {
                "success": True,
                "total_scraped": len(jobs),
                "inserted": inserted_count,
                "updated": updated_count,
                "sources": list(set(job['source'] for job in jobs))
            }

        except Exception as e:
            logger.error(f"❌ Error in scrape_and_save_to_db: {e}")
            return {
                "success": False,
                "error": str(e)
            }
