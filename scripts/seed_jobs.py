"""
Seed Jobs Script
Populates the database with sample jobs for testing matching functionality
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from bson import ObjectId


# Sample job data
SAMPLE_JOBS = [
    {
        "title": "Senior Full Stack Developer",
        "company": "TechCorp Inc",
        "location": "San Francisco, CA (Remote)",
        "salary_min": 120000,
        "salary_max": 180000,
        "salary_currency": "USD",
        "description": "We're looking for an experienced Full Stack Developer to join our team. You'll work on cutting-edge web applications using React, Node.js, and PostgreSQL.",
        "requirements": ["5+ years of experience", "React", "Node.js", "PostgreSQL", "TypeScript", "AWS"],
        "benefits": ["Health insurance", "401k", "Remote work", "Flexible hours"],
        "job_type": "Full-time",
        "remote": True,
        "experience_years_min": 5,
        "experience_years_max": 10,
        "apply_url": "https://example.com/jobs/senior-fullstack-1",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(days=2)
    },
    {
        "title": "Frontend Developer (React)",
        "company": "StartupXYZ",
        "location": "New York, NY",
        "salary_min": 90000,
        "salary_max": 130000,
        "salary_currency": "USD",
        "description": "Join our fast-paced startup as a Frontend Developer. Work with React, TypeScript, and modern web technologies.",
        "requirements": ["3+ years React experience", "TypeScript", "CSS/SCSS", "Git", "Responsive design"],
        "benefits": ["Equity", "Health insurance", "Gym membership"],
        "job_type": "Full-time",
        "remote": False,
        "experience_years_min": 3,
        "experience_years_max": 7,
        "apply_url": "https://example.com/jobs/frontend-react-2",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(days=1)
    },
    {
        "title": "Backend Engineer (Python)",
        "company": "DataFlow Systems",
        "location": "Austin, TX (Hybrid)",
        "salary_min": 110000,
        "salary_max": 150000,
        "salary_currency": "USD",
        "description": "We need a Backend Engineer experienced in Python and microservices. You'll build scalable APIs and data pipelines.",
        "requirements": ["Python", "FastAPI/Django", "PostgreSQL", "Redis", "Docker", "Kubernetes"],
        "benefits": ["Health insurance", "Remote work", "Learning budget"],
        "job_type": "Full-time",
        "remote": True,
        "experience_years_min": 4,
        "experience_years_max": 8,
        "apply_url": "https://example.com/jobs/backend-python-3",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(days=3)
    },
    {
        "title": "DevOps Engineer",
        "company": "CloudNative Co",
        "location": "Remote (US)",
        "salary_min": 130000,
        "salary_max": 170000,
        "salary_currency": "USD",
        "description": "Looking for a DevOps Engineer to manage our cloud infrastructure. Experience with AWS, Kubernetes, and CI/CD required.",
        "requirements": ["AWS", "Kubernetes", "Terraform", "CI/CD", "Monitoring", "5+ years experience"],
        "benefits": ["Full remote", "Health insurance", "401k", "Unlimited PTO"],
        "job_type": "Full-time",
        "remote": True,
        "experience_years_min": 5,
        "experience_years_max": 10,
        "apply_url": "https://example.com/jobs/devops-4",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(hours=12)
    },
    {
        "title": "Machine Learning Engineer",
        "company": "AI Innovations",
        "location": "Seattle, WA (Remote)",
        "salary_min": 140000,
        "salary_max": 200000,
        "salary_currency": "USD",
        "description": "Join our ML team to build and deploy machine learning models. Experience with Python, TensorFlow, and production ML systems required.",
        "requirements": ["Python", "TensorFlow/PyTorch", "Machine Learning", "Data Science", "MLOps", "5+ years"],
        "benefits": ["Stock options", "Health insurance", "Remote work", "Conference budget"],
        "job_type": "Full-time",
        "remote": True,
        "experience_years_min": 5,
        "experience_years_max": 12,
        "apply_url": "https://example.com/jobs/ml-engineer-5",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(hours=6)
    },
    {
        "title": "Junior Full Stack Developer",
        "company": "WebDev Agency",
        "location": "Chicago, IL",
        "salary_min": 60000,
        "salary_max": 80000,
        "salary_currency": "USD",
        "description": "Entry-level position for a Full Stack Developer. We'll mentor you on React, Node.js, and modern web development.",
        "requirements": ["1-2 years experience", "JavaScript", "React basics", "Node.js", "Git"],
        "benefits": ["Mentorship", "Health insurance", "Learning budget"],
        "job_type": "Full-time",
        "remote": False,
        "experience_years_min": 1,
        "experience_years_max": 3,
        "apply_url": "https://example.com/jobs/junior-fullstack-6",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(hours=18)
    },
    {
        "title": "React Native Developer",
        "company": "MobileFirst Inc",
        "location": "Los Angeles, CA (Remote)",
        "salary_min": 100000,
        "salary_max": 140000,
        "salary_currency": "USD",
        "description": "Build cross-platform mobile applications with React Native. Experience with iOS and Android deployment required.",
        "requirements": ["React Native", "JavaScript/TypeScript", "Mobile development", "iOS/Android", "3+ years"],
        "benefits": ["Remote work", "Health insurance", "Equipment budget"],
        "job_type": "Full-time",
        "remote": True,
        "experience_years_min": 3,
        "experience_years_max": 7,
        "apply_url": "https://example.com/jobs/react-native-7",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(hours=4)
    },
    {
        "title": "Data Engineer",
        "company": "BigData Solutions",
        "location": "Boston, MA (Hybrid)",
        "salary_min": 120000,
        "salary_max": 160000,
        "salary_currency": "USD",
        "description": "Design and build data pipelines and ETL processes. Experience with Spark, Airflow, and cloud platforms required.",
        "requirements": ["Python", "Spark", "Airflow", "SQL", "AWS/GCP", "Data warehousing"],
        "benefits": ["Hybrid work", "Health insurance", "Stock options", "Learning budget"],
        "job_type": "Full-time",
        "remote": True,
        "experience_years_min": 4,
        "experience_years_max": 9,
        "apply_url": "https://example.com/jobs/data-engineer-8",
        "source": "seed_script",
        "date_posted": datetime.utcnow() - timedelta(days=1)
    }
]


async def seed_jobs():
    """Seed database with sample jobs"""
    try:
        # Connect to MongoDB
        await MongoDB.connect()
        db = MongoDB.get_async_db()

        print(f"Connected to MongoDB database: {db.name}")

        # Check if jobs already exist from seed script
        existing_count = await db.jobs.count_documents({"source": "seed_script"})

        if existing_count > 0:
            print(f"Found {existing_count} existing seed jobs. Deleting them...")
            result = await db.jobs.delete_many({"source": "seed_script"})
            print(f"Deleted {result.deleted_count} old seed jobs")

        # Insert new jobs
        print(f"Inserting {len(SAMPLE_JOBS)} sample jobs...")

        jobs_to_insert = []
        for job in SAMPLE_JOBS:
            job_doc = job.copy()
            job_doc["created_at"] = datetime.utcnow()
            job_doc["updated_at"] = datetime.utcnow()
            job_doc["is_active"] = True
            jobs_to_insert.append(job_doc)

        result = await db.jobs.insert_many(jobs_to_insert)
        print(f"✅ Successfully inserted {len(result.inserted_ids)} jobs")

        # Print sample jobs
        print("\nSample jobs added:")
        for i, job in enumerate(SAMPLE_JOBS, 1):
            print(f"{i}. {job['title']} at {job['company']} - {job['location']}")
            print(f"   Salary: ${job['salary_min']:,} - ${job['salary_max']:,}")
            print(f"   Remote: {'Yes' if job['remote'] else 'No'}")
            print()

        # Get total job count
        total_jobs = await db.jobs.count_documents({})
        print(f"Total jobs in database: {total_jobs}")

        await MongoDB.close()
        print("\n✅ Database seeding completed successfully!")

    except Exception as e:
        print(f"❌ Error seeding jobs: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(seed_jobs())
