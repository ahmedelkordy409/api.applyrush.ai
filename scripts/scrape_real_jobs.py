"""
Real Job Scraper Script
Scrapes real jobs from job boards and populates the database
Uses free APIs like Adzuna, JSearch (RapidAPI), and GitHub Jobs
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import aiohttp
from typing import List, Dict, Any
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB

logger = logging.getLogger(__name__)


class JobScraper:
    """Scrapes jobs from various sources"""

    def __init__(self):
        self.session = None

    async def init_session(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    async def scrape_adzuna(self, query: str = "software engineer", location: str = "us", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape jobs from Adzuna API
        Free API - Register at https://developer.adzuna.com/
        """
        try:
            # You need to get API credentials from https://developer.adzuna.com/
            # For now, using sample structure
            app_id = os.getenv("ADZUNA_APP_ID", "")
            app_key = os.getenv("ADZUNA_APP_KEY", "")

            if not app_id or not app_key:
                print("⚠️  Adzuna API credentials not found. Skipping Adzuna...")
                return []

            url = f"https://api.adzuna.com/v1/api/jobs/{location}/search/1"
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": limit,
                "what": query,
                "content-type": "application/json"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    jobs = []

                    for job in data.get("results", []):
                        jobs.append({
                            "title": job.get("title", ""),
                            "company": job.get("company", {}).get("display_name", "Unknown Company"),
                            "location": job.get("location", {}).get("display_name", ""),
                            "salary_min": job.get("salary_min"),
                            "salary_max": job.get("salary_max"),
                            "salary_currency": "USD",
                            "description": job.get("description", ""),
                            "requirements": self.extract_requirements(job.get("description", "")),
                            "benefits": [],
                            "job_type": "Full-time",
                            "remote": "remote" in job.get("title", "").lower() or "remote" in job.get("description", "").lower(),
                            "apply_url": job.get("redirect_url", ""),
                            "source": "adzuna",
                            "external_id": str(job.get("id", "")),
                            "date_posted": datetime.fromisoformat(job.get("created").replace("Z", "+00:00")) if job.get("created") else datetime.utcnow()
                        })

                    print(f"✅ Scraped {len(jobs)} jobs from Adzuna")
                    return jobs
                else:
                    print(f"⚠️  Adzuna API returned status {response.status}")
                    return []

        except Exception as e:
            print(f"❌ Error scraping Adzuna: {e}")
            return []

    async def scrape_remoteok(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape jobs from RemoteOK API
        Free API - No authentication required
        """
        try:
            url = "https://remoteok.com/api"

            headers = {
                "User-Agent": "ApplyRush Job Scraper/1.0"
            }

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    jobs = []

                    # Skip first element (metadata)
                    for job in data[1:limit+1]:
                        if not job.get("position"):
                            continue

                        jobs.append({
                            "title": job.get("position", ""),
                            "company": job.get("company", "Unknown Company"),
                            "location": job.get("location", "Remote"),
                            "salary_min": job.get("salary_min"),
                            "salary_max": job.get("salary_max"),
                            "salary_currency": "USD",
                            "description": job.get("description", ""),
                            "requirements": job.get("tags", []),
                            "benefits": [],
                            "job_type": "Full-time",
                            "remote": True,
                            "apply_url": job.get("url", ""),
                            "source": "remoteok",
                            "external_id": str(job.get("id", "")),
                            "date_posted": datetime.fromtimestamp(job.get("epoch", 0)) if job.get("epoch") else datetime.utcnow()
                        })

                    print(f"✅ Scraped {len(jobs)} jobs from RemoteOK")
                    return jobs
                else:
                    print(f"⚠️  RemoteOK API returned status {response.status}")
                    return []

        except Exception as e:
            print(f"❌ Error scraping RemoteOK: {e}")
            return []

    async def scrape_github_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape jobs from GitHub Jobs alternative (Jobs API)
        Note: GitHub Jobs was shut down, using alternative
        """
        try:
            # Using Arbeitnow API as alternative (free, no auth)
            url = "https://www.arbeitnow.com/api/job-board-api"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    jobs = []

                    for job in data.get("data", [])[:limit]:
                        jobs.append({
                            "title": job.get("title", ""),
                            "company": job.get("company_name", "Unknown Company"),
                            "location": job.get("location", "Remote"),
                            "salary_min": None,
                            "salary_max": None,
                            "salary_currency": "USD",
                            "description": job.get("description", ""),
                            "requirements": job.get("tags", []),
                            "benefits": [],
                            "job_type": "Full-time",
                            "remote": job.get("remote", False),
                            "apply_url": job.get("url", ""),
                            "source": "arbeitnow",
                            "external_id": job.get("slug", ""),
                            "date_posted": datetime.fromisoformat(job.get("created_at").replace("Z", "+00:00")) if job.get("created_at") else datetime.utcnow()
                        })

                    print(f"✅ Scraped {len(jobs)} jobs from Arbeitnow")
                    return jobs
                else:
                    print(f"⚠️  Arbeitnow API returned status {response.status}")
                    return []

        except Exception as e:
            print(f"❌ Error scraping Arbeitnow: {e}")
            return []

    async def scrape_remotive(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape jobs from Remotive API
        Free API - No authentication required
        """
        try:
            url = "https://remotive.com/api/remote-jobs"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    jobs = []

                    for job in data.get("jobs", [])[:limit]:
                        jobs.append({
                            "title": job.get("title", ""),
                            "company": job.get("company_name", "Unknown Company"),
                            "location": "Remote",
                            "salary_min": None,
                            "salary_max": None,
                            "salary_currency": "USD",
                            "description": job.get("description", ""),
                            "requirements": job.get("job_type", "").split(", ") if job.get("job_type") else [],
                            "benefits": [],
                            "job_type": job.get("job_type", "Full-time"),
                            "remote": True,
                            "apply_url": job.get("url", ""),
                            "source": "remotive",
                            "external_id": str(job.get("id", "")),
                            "date_posted": datetime.fromisoformat(job.get("publication_date").replace("Z", "+00:00")) if job.get("publication_date") else datetime.utcnow()
                        })

                    print(f"✅ Scraped {len(jobs)} jobs from Remotive")
                    return jobs
                else:
                    print(f"⚠️  Remotive API returned status {response.status}")
                    return []

        except Exception as e:
            print(f"❌ Error scraping Remotive: {e}")
            return []

    def extract_requirements(self, description: str) -> List[str]:
        """Extract common requirements from job description"""
        requirements = []
        keywords = ["python", "javascript", "react", "node", "java", "aws", "docker", "kubernetes",
                   "typescript", "mongodb", "postgresql", "sql", "git", "ci/cd", "agile", "django",
                   "fastapi", "vue", "angular", "golang", "rust", "c++", "c#", ".net", "php",
                   "ruby", "rails", "swift", "kotlin", "flutter", "tensorflow", "pytorch"]

        desc_lower = description.lower()
        for keyword in keywords:
            if keyword in desc_lower:
                requirements.append(keyword.title())

        return requirements[:10]  # Limit to 10


async def scrape_and_save_jobs():
    """Main function to scrape jobs and save to database"""
    try:
        # Get MongoDB database
        db = MongoDB.get_async_db()

        print(f"✅ Connected to MongoDB database: {db.name}\n")

        # Initialize scraper
        scraper = JobScraper()
        await scraper.init_session()

        # Scrape jobs from multiple sources
        print("🔍 Scraping jobs from multiple sources...\n")

        all_jobs = []

        # RemoteOK (no auth required) - Get ALL jobs
        print("📡 Scraping RemoteOK (no limits)...")
        remoteok_jobs = await scraper.scrape_remoteok(limit=99999)
        all_jobs.extend(remoteok_jobs)

        # Remotive - Get ALL jobs
        print("📡 Scraping Remotive (no limits)...")
        remotive_jobs = await scraper.scrape_remotive(limit=99999)
        all_jobs.extend(remotive_jobs)

        # Arbeitnow (GitHub Jobs alternative) - Get ALL jobs
        print("📡 Scraping Arbeitnow (no limits)...")
        arbeitnow_jobs = await scraper.scrape_github_jobs(limit=99999)
        all_jobs.extend(arbeitnow_jobs)

        # Adzuna (requires API key)
        print("📡 Scraping Adzuna...")
        adzuna_jobs = await scraper.scrape_adzuna(limit=99999)
        all_jobs.extend(adzuna_jobs)

        await scraper.close_session()

        if not all_jobs:
            print("\n❌ No jobs scraped. Please check API credentials or network connection.")
            await MongoDB.close()
            return

        print(f"\n📊 Total jobs scraped: {len(all_jobs)}")

        # Save to database
        print("\n💾 Saving jobs to database...")

        saved_count = 0
        skipped_count = 0
        duplicate_count = 0

        for job in all_jobs:
            try:
                # Add metadata
                job["created_at"] = datetime.utcnow()
                job["updated_at"] = datetime.utcnow()
                job["is_active"] = True

                # Estimate experience years from title
                title_lower = job["title"].lower()
                if "senior" in title_lower or "lead" in title_lower:
                    job["experience_years_min"] = 5
                    job["experience_years_max"] = 10
                elif "junior" in title_lower or "entry" in title_lower:
                    job["experience_years_min"] = 0
                    job["experience_years_max"] = 2
                else:
                    job["experience_years_min"] = 2
                    job["experience_years_max"] = 5

                # Try to insert - will fail if duplicate due to unique index
                await db.jobs.insert_one(job)
                saved_count += 1

            except Exception as e:
                error_msg = str(e)
                if "duplicate key error" in error_msg.lower() or "E11000" in error_msg:
                    duplicate_count += 1
                    continue
                else:
                    logger.error(f"Error saving job: {e}")
                    skipped_count += 1
                    continue

        print(f"✅ Saved {saved_count} new jobs")
        print(f"🔄 Skipped {duplicate_count} duplicate jobs")
        if skipped_count > 0:
            print(f"⚠️  Skipped {skipped_count} jobs due to errors")

        # Get total job count
        total_jobs = await db.jobs.count_documents({})
        print(f"\n📈 Total jobs in database: {total_jobs}")

        # Print summary by source
        print("\n📊 Jobs by source:")
        sources = await db.jobs.distinct("source")
        for source in sources:
            count = await db.jobs.count_documents({"source": source})
            print(f"  {source}: {count}")

        print("\n✅ Job scraping completed successfully!")

    except Exception as e:
        print(f"\n❌ Error scraping jobs: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ApplyRush Job Scraper")
    print("=" * 60)
    print()
    asyncio.run(scrape_and_save_jobs())
