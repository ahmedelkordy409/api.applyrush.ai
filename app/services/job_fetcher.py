"""
Job fetching service using JSearch API
Efficiently fetch and process job listings from LinkedIn, Indeed, Glassdoor
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import hashlib
from app.core.config import settings
from app.core.monitoring import performance_monitor
import structlog

logger = structlog.get_logger()


class JobFetcherError(Exception):
    """Custom exception for job fetcher errors"""
    pass


class JobSource:
    """Job board source constants"""
    LINKEDIN = "linkedin.com"
    INDEED = "indeed.com" 
    GLASSDOOR = "glassdoor.com"
    ZIPRECRUITER = "ziprecruiter.com"
    ALL = "all"


class JobFetcher:
    """Handles job fetching from JSearch API with intelligent processing"""
    
    def __init__(self):
        self.base_url = "https://jsearch.p.rapidapi.com"
        self.headers = {
            "X-RapidAPI-Key": settings.JSEARCH_API_KEY,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = settings.JOB_CACHE_TTL
    
    async def search_jobs(
        self,
        query: str,
        location: str = "",
        remote_only: bool = False,
        page: int = 1,
        num_pages: int = 1,
        date_posted: str = "all",  # all, today, 3days, week, month
        employment_types: List[str] = None,  # FULLTIME, PARTTIME, CONTRACTOR, INTERN
        job_requirements: List[str] = None,  # under_3_years_experience, more_than_3_years_experience, no_experience, no_degree
        company_types: List[str] = None,  # jobs_on_indeed, direct_hire
        radius: int = 100,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search for jobs with comprehensive filtering options
        """
        
        # Create cache key
        cache_key = self._generate_cache_key(locals())
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info("Returning cached job search results", query=query)
            return cached_result
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                all_jobs = []
                total_processed = 0
                
                for current_page in range(1, num_pages + 1):
                    logger.info(f"Fetching jobs page {current_page}", query=query, page=current_page)
                    
                    # Build search parameters
                    params = self._build_search_params(
                        query, location, remote_only, current_page,
                        date_posted, employment_types, job_requirements,
                        company_types, radius, salary_min, salary_max
                    )
                    
                    # Make API request
                    response = await client.get(
                        f"{self.base_url}/search",
                        headers=self.headers,
                        params=params
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    if not data.get("status") == "OK":
                        logger.error("JSearch API error", error=data.get("error"))
                        break
                    
                    # Process jobs from this page
                    page_jobs = data.get("data", [])
                    processed_jobs = await self._process_job_listings(page_jobs)
                    all_jobs.extend(processed_jobs)
                    total_processed += len(processed_jobs)
                    
                    # Check if we have more pages
                    if len(page_jobs) == 0 or total_processed >= settings.MAX_JOBS_PER_SEARCH:
                        break
                    
                    # Rate limiting - small delay between requests
                    await asyncio.sleep(0.5)
                
                result = {
                    "success": True,
                    "jobs": all_jobs,
                    "total_count": total_processed,
                    "search_params": {
                        "query": query,
                        "location": location,
                        "remote_only": remote_only,
                        "pages_fetched": current_page
                    },
                    "fetched_at": datetime.utcnow().isoformat()
                }
                
                # Cache the result
                self._store_in_cache(cache_key, result)
                
                logger.info("Job search completed", 
                          query=query, 
                          total_jobs=total_processed, 
                          pages=current_page)
                
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error("JSearch API HTTP error", 
                        status_code=e.response.status_code,
                        response=e.response.text)
            raise JobFetcherError(f"API request failed: {e.response.status_code}")
        except Exception as e:
            logger.error("Job search error", error=str(e))
            raise JobFetcherError(f"Job search failed: {str(e)}")
    
    def _build_search_params(
        self,
        query: str,
        location: str,
        remote_only: bool,
        page: int,
        date_posted: str,
        employment_types: List[str],
        job_requirements: List[str],
        company_types: List[str],
        radius: int,
        salary_min: Optional[int],
        salary_max: Optional[int]
    ) -> Dict[str, Any]:
        """Build search parameters for JSearch API"""
        
        params = {
            "query": query,
            "page": page,
            "num_pages": 1,
            "country": "US",  # Default to US, can be made configurable
        }
        
        if location:
            params["location"] = location
        
        if remote_only:
            params["remote_jobs_only"] = "true"
        
        if date_posted != "all":
            params["date_posted"] = date_posted
        
        if employment_types:
            params["employment_types"] = ",".join(employment_types)
        
        if job_requirements:
            params["job_requirements"] = ",".join(job_requirements)
        
        if company_types:
            params["company_types"] = ",".join(company_types)
        
        if radius:
            params["radius"] = radius
        
        if salary_min:
            params["salary_min"] = salary_min
        
        if salary_max:
            params["salary_max"] = salary_max
        
        return params
    
    async def _process_job_listings(self, raw_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and normalize job listings"""
        
        processed_jobs = []
        
        for job_data in raw_jobs:
            try:
                processed_job = await self._normalize_job_data(job_data)
                if processed_job and self._is_valid_job(processed_job):
                    processed_jobs.append(processed_job)
            except Exception as e:
                logger.warning("Failed to process job", 
                             job_id=job_data.get("job_id"), 
                             error=str(e))
                continue
        
        return processed_jobs
    
    async def _normalize_job_data(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize job data from JSearch API to our format"""
        
        # Extract basic information
        job_id = raw_job.get("job_id")
        title = raw_job.get("job_title", "").strip()
        company_name = raw_job.get("employer_name", "").strip()
        description = raw_job.get("job_description", "").strip()
        
        # Location processing
        location_data = {
            "city": raw_job.get("job_city"),
            "state": raw_job.get("job_state"), 
            "country": raw_job.get("job_country", "US"),
            "is_remote": raw_job.get("job_is_remote", False)
        }
        
        # Salary processing
        salary_min = self._extract_salary(raw_job.get("job_min_salary"))
        salary_max = self._extract_salary(raw_job.get("job_max_salary"))
        
        # Skills extraction from description
        required_skills = await self._extract_skills_from_description(description)
        
        # Employment type mapping
        employment_type = self._normalize_employment_type(
            raw_job.get("job_employment_type", "FULLTIME")
        )
        
        # Date processing
        posted_date = self._parse_date(raw_job.get("job_posted_at_datetime_utc"))
        
        # Company information
        company_info = {
            "name": company_name,
            "logo": raw_job.get("employer_logo"),
            "website": raw_job.get("employer_website"),
            "company_type": raw_job.get("employer_company_type")
        }
        
        return {
            "external_id": job_id,
            "title": title,
            "description": description,
            "company": company_info,
            "location": location_data,
            "remote_option": "full" if location_data["is_remote"] else "no",
            "employment_type": employment_type,
            "required_skills": required_skills,
            "preferred_skills": [],  # Could be extracted with more advanced NLP
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": "USD",  # Default, could be extracted
            "source": self._identify_source(raw_job.get("job_apply_link", "")),
            "posted_date": posted_date,
            "application_url": raw_job.get("job_apply_link"),
            "benefits": self._extract_benefits(description),
            "experience_level": await self._extract_experience_level(description),
            "education_requirements": await self._extract_education_requirements(description),
            "raw_data": raw_job  # Keep original for debugging
        }
    
    def _extract_salary(self, salary_data) -> Optional[int]:
        """Extract and normalize salary information"""
        if not salary_data:
            return None
        
        # Handle different salary formats
        if isinstance(salary_data, (int, float)):
            return int(salary_data)
        
        if isinstance(salary_data, str):
            # Remove non-numeric characters and convert
            import re
            numbers = re.findall(r'\d+', salary_data.replace(',', ''))
            if numbers:
                return int(numbers[0])
        
        return None
    
    async def _extract_skills_from_description(self, description: str) -> List[str]:
        """Extract skills from job description using keyword matching"""
        
        if not description:
            return []
        
        # Common technical skills to look for
        common_skills = [
            "Python", "Java", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker",
            "Kubernetes", "Git", "HTML", "CSS", "TypeScript", "C++", "C#", "Ruby",
            "Go", "Rust", "PHP", "Swift", "Kotlin", "Flutter", "Django", "Flask",
            "Express", "Spring", "Angular", "Vue.js", "MongoDB", "PostgreSQL",
            "Redis", "GraphQL", "REST", "API", "Microservices", "DevOps", "CI/CD",
            "Machine Learning", "Data Science", "AI", "TensorFlow", "PyTorch"
        ]
        
        found_skills = []
        description_lower = description.lower()
        
        for skill in common_skills:
            if skill.lower() in description_lower:
                found_skills.append(skill)
        
        return found_skills
    
    def _normalize_employment_type(self, raw_type: str) -> str:
        """Normalize employment type"""
        mapping = {
            "FULLTIME": "full-time",
            "PARTTIME": "part-time", 
            "CONTRACTOR": "contract",
            "INTERN": "internship"
        }
        return mapping.get(raw_type, "full-time")
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats"""
        if not date_str:
            return None
        
        try:
            # Handle ISO format
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            try:
                # Handle other common formats
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except:
                return None
    
    def _identify_source(self, apply_link: str) -> str:
        """Identify job source from apply link"""
        if not apply_link:
            return "unknown"
        
        apply_link_lower = apply_link.lower()
        
        if "linkedin" in apply_link_lower:
            return "linkedin"
        elif "indeed" in apply_link_lower:
            return "indeed"
        elif "glassdoor" in apply_link_lower:
            return "glassdoor"
        elif "ziprecruiter" in apply_link_lower:
            return "ziprecruiter"
        else:
            return "other"
    
    def _extract_benefits(self, description: str) -> List[str]:
        """Extract benefits from job description"""
        if not description:
            return []
        
        benefits_keywords = [
            "health insurance", "dental", "vision", "401k", "retirement",
            "vacation", "pto", "remote work", "flexible hours", "stock options",
            "bonus", "gym", "wellness", "education", "tuition", "parental leave"
        ]
        
        found_benefits = []
        description_lower = description.lower()
        
        for benefit in benefits_keywords:
            if benefit in description_lower:
                found_benefits.append(benefit.title())
        
        return found_benefits
    
    async def _extract_experience_level(self, description: str) -> str:
        """Extract experience level requirements"""
        if not description:
            return "mid-level"
        
        description_lower = description.lower()
        
        if any(word in description_lower for word in ["entry", "junior", "0-2 years", "new grad"]):
            return "entry-level"
        elif any(word in description_lower for word in ["senior", "lead", "5+ years", "7+ years"]):
            return "senior-level"
        else:
            return "mid-level"
    
    async def _extract_education_requirements(self, description: str) -> str:
        """Extract education requirements"""
        if not description:
            return "bachelor"
        
        description_lower = description.lower()
        
        if "phd" in description_lower or "doctorate" in description_lower:
            return "doctorate"
        elif "master" in description_lower or "mba" in description_lower:
            return "masters"
        elif "bachelor" in description_lower or "bs" in description_lower or "ba" in description_lower:
            return "bachelor"
        elif "associate" in description_lower:
            return "associate"
        else:
            return "bachelor"  # Default assumption
    
    def _is_valid_job(self, job: Dict[str, Any]) -> bool:
        """Validate job data quality"""
        
        # Required fields
        required_fields = ["external_id", "title", "company", "description"]
        
        for field in required_fields:
            if not job.get(field):
                return False
        
        # Filter out spam/scam indicators
        spam_indicators = [
            "work from home", "make money fast", "no experience required",
            "earn $", "guaranteed income", "pyramid", "mlm"
        ]
        
        title_lower = job["title"].lower()
        desc_lower = job["description"].lower()
        
        for indicator in spam_indicators:
            if indicator in title_lower or indicator in desc_lower:
                return False
        
        return True
    
    def _generate_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate cache key from search parameters"""
        # Remove 'self' and None values
        clean_params = {k: v for k, v in params.items() if k != 'self' and v is not None}
        param_string = json.dumps(clean_params, sort_keys=True)
        return hashlib.md5(param_string.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get result from cache if not expired"""
        if key in self.cache:
            cached_data = self.cache[key]
            if datetime.utcnow() - cached_data["cached_at"] < timedelta(seconds=self.cache_ttl):
                return cached_data["data"]
            else:
                # Remove expired entry
                del self.cache[key]
        return None
    
    def _store_in_cache(self, key: str, data: Dict[str, Any]):
        """Store result in cache with timestamp"""
        self.cache[key] = {
            "data": data,
            "cached_at": datetime.utcnow()
        }
        
        # Simple cache cleanup - keep only last 100 entries
        if len(self.cache) > 100:
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k]["cached_at"])
            del self.cache[oldest_key]
    
    async def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific job"""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/job-details",
                    headers=self.headers,
                    params={"job_id": job_id}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("status") == "OK" and data.get("data"):
                    job_details = await self._normalize_job_data(data["data"][0])
                    return {
                        "success": True,
                        "job": job_details
                    }
                else:
                    return {
                        "success": False,
                        "error": "Job not found or API error"
                    }
                    
        except Exception as e:
            logger.error("Job details fetch error", job_id=job_id, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_similar_jobs(
        self,
        reference_job: Dict[str, Any],
        location: str = "",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find similar jobs based on a reference job"""
        
        # Build search query from reference job
        title = reference_job.get("title", "")
        skills = reference_job.get("required_skills", [])
        
        # Create search query
        query_parts = [title]
        if skills:
            query_parts.extend(skills[:3])  # Use top 3 skills
        
        search_query = " ".join(query_parts)
        
        # Search for similar jobs
        result = await self.search_jobs(
            query=search_query,
            location=location,
            num_pages=2,  # Search more pages for variety
            date_posted="month"  # Recent jobs only
        )
        
        if result["success"]:
            # Filter out the reference job itself
            similar_jobs = [
                job for job in result["jobs"] 
                if job.get("external_id") != reference_job.get("external_id")
            ]
            
            return similar_jobs[:limit]
        
        return []


# Global job fetcher instance
job_fetcher = JobFetcher()


# Export public interfaces
__all__ = ["JobFetcher", "JobSource", "JobFetcherError", "job_fetcher"]