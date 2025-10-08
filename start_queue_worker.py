"""
Start the Auto-Apply Queue Worker
Processes applications from queue one by one
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.services.auto_apply_queue_worker import queue_worker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Start the queue worker"""

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    logger.info(f"📊 Connected to MongoDB: {settings.MONGODB_DATABASE}")
    logger.info(f"🚀 Starting Auto-Apply Queue Worker...")

    try:
        # Start the queue worker
        await queue_worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Stopping queue worker...")
        await queue_worker.stop()
        client.close()
        logger.info("👋 Queue worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
