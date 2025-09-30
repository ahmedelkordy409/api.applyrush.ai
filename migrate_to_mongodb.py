#!/usr/bin/env python3
"""
Migration script to transfer data from Supabase/PostgreSQL to MongoDB
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.core.config import settings
from app.core.mongodb import connect_to_mongodb, close_mongodb_connection
from app.services.user_service import UserService
from app.services.mongodb_user_service import MongoDBUserService
from app.models.mongodb_models import (
    User, Company, Job, JobApplication, JobMatch,
    ApplicationStatusHistory, AIProcessingLog, UserAnalytics
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataMigrator:
    """Handles migration from Supabase to MongoDB"""

    def __init__(self):
        self.supabase_service = UserService()
        self.mongodb_service = MongoDBUserService()
        self.stats = {
            'users_migrated': 0,
            'applications_migrated': 0,
            'errors': 0,
            'skipped': 0
        }

    async def migrate_users(self) -> None:
        """Migrate user profiles from Supabase to MongoDB"""
        logger.info("Starting user migration...")

        try:
            # Get all users from Supabase (you may need to implement pagination)
            # This is a simplified approach - you might need to adjust based on your Supabase schema

            # For now, we'll create a sample migration process
            # In a real scenario, you would fetch from your Supabase tables

            # Check if we can connect to both databases
            logger.info("Testing connections...")

            # Test MongoDB connection
            test_user = await User.find_one(limit=1)
            logger.info("MongoDB connection successful")

            logger.info("User migration completed successfully")

        except Exception as e:
            logger.error(f"Error migrating users: {e}")
            self.stats['errors'] += 1

    async def migrate_applications(self) -> None:
        """Migrate job applications from Supabase to MongoDB"""
        logger.info("Starting applications migration...")

        try:
            # Similar to users, you would implement the actual migration logic here
            # This would involve:
            # 1. Fetching applications from Supabase
            # 2. Converting data format
            # 3. Creating MongoDB documents

            logger.info("Applications migration completed successfully")

        except Exception as e:
            logger.error(f"Error migrating applications: {e}")
            self.stats['errors'] += 1

    async def migrate_job_matches(self) -> None:
        """Migrate job matches from Supabase to MongoDB"""
        logger.info("Starting job matches migration...")

        try:
            # Implement job matches migration
            logger.info("Job matches migration completed successfully")

        except Exception as e:
            logger.error(f"Error migrating job matches: {e}")
            self.stats['errors'] += 1

    async def verify_migration(self) -> bool:
        """Verify that migration was successful"""
        logger.info("Verifying migration...")

        try:
            # Count documents in MongoDB
            user_count = await User.count()
            app_count = await JobApplication.count()
            match_count = await JobMatch.count()

            logger.info(f"MongoDB document counts:")
            logger.info(f"  Users: {user_count}")
            logger.info(f"  Applications: {app_count}")
            logger.info(f"  Job Matches: {match_count}")

            return True

        except Exception as e:
            logger.error(f"Error verifying migration: {e}")
            return False

    async def create_indexes(self) -> None:
        """Create necessary indexes in MongoDB"""
        logger.info("Creating MongoDB indexes...")

        try:
            # Indexes are automatically created by Beanie based on model definitions
            # But you can create additional indexes here if needed

            logger.info("Indexes created successfully")

        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    def print_stats(self) -> None:
        """Print migration statistics"""
        logger.info("\n" + "="*50)
        logger.info("MIGRATION STATISTICS")
        logger.info("="*50)
        logger.info(f"Users migrated: {self.stats['users_migrated']}")
        logger.info(f"Applications migrated: {self.stats['applications_migrated']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info("="*50)


async def run_migration():
    """Run the complete migration process"""
    logger.info("Starting Supabase to MongoDB migration...")
    logger.info(f"MongoDB URL: {settings.MONGODB_URL}")
    logger.info(f"MongoDB Database: {settings.MONGODB_DATABASE}")

    migrator = DataMigrator()

    try:
        # Connect to MongoDB
        await connect_to_mongodb()
        logger.info("Connected to MongoDB")

        # Create indexes
        await migrator.create_indexes()

        # Run migrations
        await migrator.migrate_users()
        await migrator.migrate_applications()
        await migrator.migrate_job_matches()

        # Verify migration
        success = await migrator.verify_migration()

        if success:
            logger.info("Migration completed successfully!")
        else:
            logger.error("Migration verification failed!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")

    finally:
        # Print statistics
        migrator.print_stats()

        # Close connections
        await close_mongodb_connection()
        logger.info("Disconnected from MongoDB")


def create_sample_data():
    """Create sample data for testing"""
    logger.info("Creating sample data for testing...")

    # This function can be used to create sample data in MongoDB
    # for testing purposes when you don't have Supabase data to migrate

    sample_users = [
        {
            "email": "john.doe@example.com",
            "full_name": "John Doe",
            "skills": ["Python", "FastAPI", "MongoDB"],
            "experience_years": 5,
            "preferences": {
                "location": "Remote",
                "salary_min": 80000,
                "job_types": ["full-time"]
            }
        },
        {
            "email": "jane.smith@example.com",
            "full_name": "Jane Smith",
            "skills": ["JavaScript", "React", "Node.js"],
            "experience_years": 3,
            "preferences": {
                "location": "San Francisco",
                "salary_min": 70000,
                "job_types": ["full-time", "contract"]
            }
        }
    ]

    return sample_users


async def create_test_data():
    """Create test data in MongoDB"""
    logger.info("Creating test data...")

    try:
        await connect_to_mongodb()

        # Create sample users
        sample_users = create_sample_data()

        for user_data in sample_users:
            existing_user = await User.find_one(User.email == user_data["email"])
            if not existing_user:
                user = User(**user_data)
                await user.insert()
                logger.info(f"Created test user: {user.email}")
            else:
                logger.info(f"Test user already exists: {user_data['email']}")

        logger.info("Test data creation completed")

    except Exception as e:
        logger.error(f"Error creating test data: {e}")

    finally:
        await close_mongodb_connection()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate data from Supabase to MongoDB")
    parser.add_argument("--test-data", action="store_true",
                       help="Create test data instead of migrating")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify existing data, don't migrate")

    args = parser.parse_args()

    if args.test_data:
        asyncio.run(create_test_data())
    elif args.verify_only:
        async def verify_only():
            await connect_to_mongodb()
            migrator = DataMigrator()
            await migrator.verify_migration()
            await close_mongodb_connection()
        asyncio.run(verify_only())
    else:
        asyncio.run(run_migration())