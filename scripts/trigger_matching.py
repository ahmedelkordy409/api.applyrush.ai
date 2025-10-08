"""
Trigger Job Matching Script
Runs the job matching algorithm for all active users
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.background_jobs import background_job_service


async def trigger_matching():
    """Trigger job matching for all active users"""
    try:
        print("=" * 60)
        print("🔍 Starting Job Matching for Active Users")
        print("=" * 60)
        print()

        # Run the matching service
        await background_job_service.find_matches_for_active_users()

        print()
        print("=" * 60)
        print("✅ Job matching completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during job matching: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(trigger_matching())
