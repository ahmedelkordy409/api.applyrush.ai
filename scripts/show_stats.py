"""
Show Database Statistics
Display current stats about jobs and users
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB


async def show_stats():
    """Show database statistics"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 60)
        print("📊 ApplyRush Database Statistics")
        print("=" * 60)
        print()

        # Jobs stats
        total_jobs = await db.jobs.count_documents({})
        active_jobs = await db.jobs.count_documents({"is_active": True})

        print(f"📋 JOBS:")
        print(f"  Total jobs: {total_jobs}")
        print(f"  Active jobs: {active_jobs}")
        print()

        # Jobs by source
        print("  Jobs by source:")
        sources = await db.jobs.distinct("source")
        for source in sources:
            count = await db.jobs.count_documents({"source": source})
            print(f"    {source}: {count}")
        print()

        # Users stats
        total_users = await db.users.count_documents({})
        active_users = await db.users.count_documents({"preferences.search_active": True})

        print(f"👥 USERS:")
        print(f"  Total users: {total_users}")
        print(f"  Active search users: {active_users}")
        print()

        # Application queue stats
        total_queue = await db.application_queue.count_documents({})
        pending_queue = await db.application_queue.count_documents({"status": "pending"})
        approved_queue = await db.application_queue.count_documents({"status": "approved"})

        print(f"📬 APPLICATION QUEUE:")
        print(f"  Total items: {total_queue}")
        print(f"  Pending: {pending_queue}")
        print(f"  Approved: {approved_queue}")
        print()

        # Sample jobs
        print("🔍 SAMPLE JOBS:")
        sample_jobs = await db.jobs.find({"is_active": True}).limit(5).to_list(length=5)
        for i, job in enumerate(sample_jobs, 1):
            print(f"\n  {i}. {job.get('title', 'N/A')}")
            print(f"     Company: {job.get('company', 'N/A')}")
            print(f"     Location: {job.get('location', 'N/A')}")
            print(f"     Remote: {'Yes' if job.get('remote') else 'No'}")
            print(f"     Source: {job.get('source', 'N/A')}")

        print()
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error getting stats: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(show_stats())
