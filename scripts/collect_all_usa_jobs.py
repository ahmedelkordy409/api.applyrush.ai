"""
Massive USA Job Collection Script
Collects thousands of jobs from ALL sources with NO LIMITS
Sources: Indeed, LinkedIn, Glassdoor, ZipRecruiter, and more
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_fetcher import JobFetcher
from bson import ObjectId


# Popular job search queries to maximize coverage
JOB_QUERIES = [
    # Tech & Engineering
    "Software Engineer", "Full Stack Developer", "Backend Developer",
    "Frontend Developer", "DevOps Engineer", "Data Engineer",
    "Machine Learning Engineer", "AI Engineer", "Cloud Engineer",
    "Mobile Developer", "iOS Developer", "Android Developer",
    "QA Engineer", "Test Automation Engineer", "Security Engineer",
    "Site Reliability Engineer", "Platform Engineer", "Solutions Architect",

    # Data & Analytics
    "Data Scientist", "Data Analyst", "Business Intelligence Analyst",
    "Analytics Engineer", "Data Architect", "ML Ops Engineer",

    # Product & Design
    "Product Manager", "Product Designer", "UX Designer", "UI Designer",
    "UX Researcher", "Product Owner", "Technical Product Manager",

    # Management & Leadership
    "Engineering Manager", "Technical Lead", "CTO", "VP Engineering",
    "Director of Engineering", "Head of Product", "Head of Data",

    # Sales & Marketing
    "Sales Engineer", "Account Executive", "Customer Success Manager",
    "Marketing Manager", "Growth Manager", "Digital Marketing Manager",

    # Operations & Support
    "IT Support", "Systems Administrator", "Network Engineer",
    "Technical Support Engineer", "Customer Support", "IT Manager",

    # Emerging Tech
    "Blockchain Developer", "Web3 Engineer", "Smart Contract Developer",
    "AR/VR Developer", "Game Developer", "Robotics Engineer",

    # General
    "Remote Developer", "Remote Engineer", "Work from Home",
]

# Major USA tech hubs and remote
USA_LOCATIONS = [
    "United States",
    "Remote",
    "San Francisco, CA",
    "New York, NY",
    "Seattle, WA",
    "Austin, TX",
    "Boston, MA",
    "Los Angeles, CA",
    "Chicago, IL",
    "Denver, CO",
    "Atlanta, GA",
    "Miami, FL",
    "Dallas, TX",
    "Portland, OR",
    "San Diego, CA",
    "Phoenix, AZ",
    "Washington, DC",
    "Philadelphia, PA",
    "Minneapolis, MN",
    "Detroit, MI",
]

# Employment types
EMPLOYMENT_TYPES = ["FULLTIME", "PARTTIME", "CONTRACTOR", "INTERN"]

# Date ranges to get maximum coverage
DATE_RANGES = ["today", "3days", "week", "month", "all"]


async def collect_massive_jobs():
    """Collect massive amount of jobs from all sources"""
    try:
        db = MongoDB.get_async_db()
        fetcher = JobFetcher()

        print("=" * 100)
        print("🚀 MASSIVE USA JOB COLLECTION - NO LIMITS")
        print("=" * 100)
        print()
        print(f"📋 Job Queries: {len(JOB_QUERIES)}")
        print(f"📍 Locations: {len(USA_LOCATIONS)}")
        print(f"💼 Employment Types: {len(EMPLOYMENT_TYPES)}")
        print(f"📅 Date Ranges: {len(DATE_RANGES)}")
        print()

        total_jobs_collected = 0
        total_jobs_saved = 0
        total_duplicates = 0
        total_api_calls = 0
        errors = 0

        start_time = time.time()

        # Strategy: Collect jobs for each combination
        # To avoid rate limits, we'll batch and add delays

        for query_index, query in enumerate(JOB_QUERIES, 1):
            print(f"\n{'='*100}")
            print(f"🔍 Query {query_index}/{len(JOB_QUERIES)}: {query}")
            print(f"{'='*100}")

            for location_index, location in enumerate(USA_LOCATIONS, 1):
                try:
                    print(f"\n  📍 Location {location_index}/{len(USA_LOCATIONS)}: {location}")

                    # Fetch multiple pages for this query + location
                    NUM_PAGES = 10  # 10 pages × 10 jobs = 100 jobs per query+location

                    result = await fetcher.search_jobs(
                        query=query,
                        location=location,
                        remote_only=False,
                        page=1,
                        num_pages=NUM_PAGES,
                        date_posted="month",  # Last month for fresh jobs
                        employment_types=EMPLOYMENT_TYPES,
                        radius=100
                    )

                    total_api_calls += 1
                    jobs = result.get("jobs", [])

                    print(f"     ✅ Fetched {len(jobs)} jobs from API")
                    total_jobs_collected += len(jobs)

                    # Save jobs to database
                    saved_count = 0
                    duplicate_count = 0

                    for job in jobs:
                        try:
                            # Create unique job ID from URL or title+company
                            job_url = job.get("job_apply_link") or job.get("job_id", "")
                            job_hash = hashlib.md5(job_url.encode()).hexdigest() if job_url else None

                            # Check if job already exists
                            existing = None
                            if job_hash:
                                existing = await db.jobs.find_one({"job_hash": job_hash})

                            if existing:
                                duplicate_count += 1
                                continue

                            # Prepare job document
                            job_doc = {
                                "job_hash": job_hash,
                                "title": job.get("job_title", "Unknown"),
                                "company": job.get("employer_name", "Unknown"),
                                "location": job.get("job_city", location),
                                "country": job.get("job_country", "US"),
                                "state": job.get("job_state", ""),
                                "remote": job.get("job_is_remote", False),
                                "description": job.get("job_description", ""),
                                "requirements": job.get("job_required_skills", []),
                                "benefits": job.get("job_highlights", {}).get("Benefits", []),
                                "job_type": job.get("job_employment_type", "Full-time"),
                                "salary_min": job.get("job_min_salary"),
                                "salary_max": job.get("job_max_salary"),
                                "salary_currency": job.get("job_salary_currency", "USD"),
                                "salary_period": job.get("job_salary_period"),
                                "apply_url": job.get("job_apply_link", ""),
                                "apply_email": extract_email_from_job(job),
                                "date_posted": parse_date(job.get("job_posted_at_datetime_utc")),
                                "source": job.get("job_publisher", "JSearch"),
                                "source_platform": determine_source_platform(job),
                                "is_active": True,
                                "created_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow(),
                                "metadata": {
                                    "query": query,
                                    "search_location": location,
                                    "job_id": job.get("job_id"),
                                    "employer_logo": job.get("employer_logo"),
                                    "employer_website": job.get("employer_website"),
                                    "qualifications": job.get("job_highlights", {}).get("Qualifications", []),
                                    "responsibilities": job.get("job_highlights", {}).get("Responsibilities", []),
                                }
                            }

                            # Insert into database
                            result = await db.jobs.insert_one(job_doc)
                            saved_count += 1
                            total_jobs_saved += 1

                        except Exception as e:
                            print(f"     ❌ Error saving job: {e}")
                            continue

                    total_duplicates += duplicate_count
                    print(f"     💾 Saved: {saved_count} | Duplicates: {duplicate_count}")

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

                except Exception as e:
                    errors += 1
                    print(f"     ❌ Error for location {location}: {e}")
                    continue

            # Longer delay between queries to respect rate limits
            print(f"\n  ⏸️  Waiting 2 seconds before next query...")
            await asyncio.sleep(2)

        end_time = time.time()
        duration = end_time - start_time

        print("\n" + "=" * 100)
        print("📊 COLLECTION SUMMARY")
        print("=" * 100)
        print(f"⏱️  Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"🔍 API Calls: {total_api_calls}")
        print(f"📥 Jobs Collected: {total_jobs_collected}")
        print(f"💾 Jobs Saved: {total_jobs_saved}")
        print(f"🔄 Duplicates Skipped: {total_duplicates}")
        print(f"❌ Errors: {errors}")
        print()

        # Database statistics
        total_jobs_in_db = await db.jobs.count_documents({})
        active_jobs = await db.jobs.count_documents({"is_active": True})
        remote_jobs = await db.jobs.count_documents({"is_active": True, "remote": True})

        print("=" * 100)
        print("📊 DATABASE STATISTICS")
        print("=" * 100)
        print(f"🗄️  Total Jobs in Database: {total_jobs_in_db:,}")
        print(f"✅ Active Jobs: {active_jobs:,}")
        print(f"🏠 Remote Jobs: {remote_jobs:,}")
        print()

        # Breakdown by source
        sources = await db.jobs.aggregate([
            {"$match": {"is_active": True}},
            {"$group": {"_id": "$source_platform", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]).to_list(length=None)

        print("📊 JOBS BY SOURCE:")
        for source in sources:
            source_name = source["_id"] or "Unknown"
            count = source["count"]
            print(f"   • {source_name}: {count:,} jobs")
        print()

        print("=" * 100)
        print("✅ JOB COLLECTION COMPLETE!")
        print("=" * 100)
        print()
        print("💡 Next Steps:")
        print("   1. Jobs are now available for matching")
        print("   2. Automated matching will find relevant jobs for users")
        print("   3. Run this script daily/weekly to keep jobs fresh")
        print()

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()


def extract_email_from_job(job: Dict[str, Any]) -> str:
    """Try to extract email from job data"""
    import re

    # Check common fields
    for field in ["employer_email", "contact_email", "apply_email"]:
        if email := job.get(field):
            return email

    # Try to extract from description
    description = job.get("job_description", "")
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, description)
    if match:
        email = match.group(0)
        # Filter out no-reply emails
        if not any(x in email.lower() for x in ['noreply', 'no-reply', 'donotreply']):
            return email

    return None


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime"""
    if not date_str:
        return datetime.utcnow()

    try:
        # Try ISO format
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        return datetime.utcnow()


def determine_source_platform(job: Dict[str, Any]) -> str:
    """Determine which platform the job is from"""
    publisher = job.get("job_publisher", "").lower()
    apply_link = job.get("job_apply_link", "").lower()

    if "indeed" in publisher or "indeed" in apply_link:
        return "Indeed"
    elif "linkedin" in publisher or "linkedin" in apply_link:
        return "LinkedIn"
    elif "glassdoor" in publisher or "glassdoor" in apply_link:
        return "Glassdoor"
    elif "ziprecruiter" in publisher or "ziprecruiter" in apply_link:
        return "ZipRecruiter"
    elif "monster" in publisher or "monster" in apply_link:
        return "Monster"
    elif "dice" in publisher or "dice" in apply_link:
        return "Dice"
    elif "careerbuilder" in publisher or "careerbuilder" in apply_link:
        return "CareerBuilder"
    else:
        return publisher or "Other"


import hashlib

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                                                                          ║
    ║               🚀 MASSIVE USA JOB COLLECTION SCRIPT 🚀                    ║
    ║                                                                          ║
    ║  This script will collect THOUSANDS of jobs from:                       ║
    ║  • Indeed                                                                ║
    ║  • LinkedIn                                                              ║
    ║  • Glassdoor                                                             ║
    ║  • ZipRecruiter                                                          ║
    ║  • Monster                                                               ║
    ║  • And more...                                                           ║
    ║                                                                          ║
    ║  Expected Results:                                                       ║
    ║  • 50+ job queries × 20 locations × 100 jobs = ~100,000 job listings    ║
    ║  • Coverage: All major USA tech hubs + Remote                            ║
    ║  • Fresh jobs from the last month                                        ║
    ║                                                                          ║
    ║  ⚠️  This will take 30-60 minutes to complete                            ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """)

    print("\n🚀 Starting job collection...\n")
    asyncio.run(collect_massive_jobs())
