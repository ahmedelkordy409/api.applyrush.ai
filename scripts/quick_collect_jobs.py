"""
Quick Job Collection Script
Collect 1000+ jobs quickly from Indeed, LinkedIn, Glassdoor
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import hashlib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_fetcher import JobFetcher
from bson import ObjectId


# Quick high-value queries
QUICK_QUERIES = [
    "Software Engineer Remote",
    "Full Stack Developer",
    "Backend Engineer",
    "Frontend Developer",
    "DevOps Engineer",
    "Data Engineer",
    "Product Manager",
    "Data Scientist",
]

# Focus on remote and major hubs
QUICK_LOCATIONS = [
    "Remote",
    "United States",
    "San Francisco, CA",
    "New York, NY",
    "Seattle, WA",
    "Austin, TX",
]


async def quick_collect():
    """Quickly collect 1000+ jobs"""
    try:
        db = MongoDB.get_async_db()
        fetcher = JobFetcher()

        print("=" * 80)
        print("⚡ QUICK JOB COLLECTION")
        print("=" * 80)
        print()

        total_collected = 0
        total_saved = 0
        total_duplicates = 0

        for query in QUICK_QUERIES:
            print(f"\n🔍 Searching: {query}")

            for location in QUICK_LOCATIONS:
                try:
                    # Fetch 5 pages = 50 jobs per query+location
                    result = await fetcher.search_jobs(
                        query=query,
                        location=location,
                        num_pages=5,
                        date_posted="month"
                    )

                    jobs = result.get("jobs", [])
                    total_collected += len(jobs)
                    print(f"   📍 {location}: {len(jobs)} jobs")

                    # Save to database
                    for job in jobs:
                        try:
                            # Create job hash for deduplication
                            job_url = job.get("job_apply_link", "")
                            job_hash = hashlib.md5(job_url.encode()).hexdigest() if job_url else None

                            # Check for duplicate
                            if job_hash:
                                existing = await db.jobs.find_one({"job_hash": job_hash})
                                if existing:
                                    total_duplicates += 1
                                    continue

                            # Create job document
                            job_doc = {
                                "job_hash": job_hash,
                                "title": job.get("job_title", ""),
                                "company": job.get("employer_name", ""),
                                "location": job.get("job_city", location),
                                "remote": job.get("job_is_remote", False),
                                "description": job.get("job_description", ""),
                                "job_type": job.get("job_employment_type", "Full-time"),
                                "salary_min": job.get("job_min_salary"),
                                "salary_max": job.get("job_max_salary"),
                                "salary_currency": "USD",
                                "apply_url": job.get("job_apply_link", ""),
                                "source": job.get("job_publisher", "JSearch"),
                                "is_active": True,
                                "created_at": datetime.utcnow(),
                            }

                            await db.jobs.insert_one(job_doc)
                            total_saved += 1

                        except Exception as e:
                            continue

                    await asyncio.sleep(0.5)  # Rate limit

                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    continue

        # Summary
        total_in_db = await db.jobs.count_documents({"is_active": True})

        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✅ Jobs Collected: {total_collected}")
        print(f"💾 Jobs Saved: {total_saved}")
        print(f"🔄 Duplicates: {total_duplicates}")
        print(f"🗄️  Total in DB: {total_in_db:,}")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n⚡ Quick Job Collection - Getting 1000+ jobs...\n")
    asyncio.run(quick_collect())
