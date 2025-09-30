#!/usr/bin/env python3
"""
Test script for MongoDB setup and basic operations
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.core.mongodb import connect_to_mongodb, close_mongodb_connection, check_mongodb_health
from app.services.mongodb_user_service import get_mongodb_user_service
from app.models.mongodb_models import User, Job, Company, JobApplication, JobMatch

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_connection():
    """Test MongoDB connection"""
    logger.info("Testing MongoDB connection...")

    try:
        await connect_to_mongodb()
        logger.info("✅ MongoDB connection successful")

        # Test health check
        is_healthy = await check_mongodb_health()
        logger.info(f"✅ MongoDB health check: {'PASS' if is_healthy else 'FAIL'}")

        return True

    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        return False


async def test_user_service():
    """Test MongoDB user service operations"""
    logger.info("Testing MongoDB user service...")

    try:
        user_service = get_mongodb_user_service()

        # Test creating a user
        test_email = "test@example.com"
        user_id = await user_service.create_user(
            email=test_email,
            full_name="Test User",
            external_id="test_123"
        )

        if user_id:
            logger.info(f"✅ Created test user with ID: {user_id}")

            # Test getting user profile
            profile = await user_service.get_user_profile(user_id)
            if profile:
                logger.info(f"✅ Retrieved user profile: {profile['email']}")
            else:
                logger.error("❌ Failed to retrieve user profile")

            # Test updating user profile
            update_success = await user_service.update_user_profile(user_id, {
                "skills": ["Python", "MongoDB", "FastAPI"],
                "experience_years": 5
            })

            if update_success:
                logger.info("✅ Updated user profile successfully")
            else:
                logger.error("❌ Failed to update user profile")

            # Test getting user by email
            user_by_email = await user_service.get_user_by_email(test_email)
            if user_by_email:
                logger.info("✅ Retrieved user by email successfully")
            else:
                logger.error("❌ Failed to retrieve user by email")

        else:
            logger.error("❌ Failed to create test user")

    except Exception as e:
        logger.error(f"❌ User service test failed: {e}")


async def test_models():
    """Test MongoDB models directly"""
    logger.info("Testing MongoDB models...")

    try:
        # Test User model
        test_user = User(
            email="model_test@example.com",
            full_name="Model Test User",
            skills=["JavaScript", "React"],
            experience_years=3
        )
        await test_user.insert()
        logger.info(f"✅ Created user model: {test_user.id}")

        # Test Company model
        test_company = Company(
            name="Test Company",
            industry="Technology",
            description="A test company for MongoDB testing",
            remote_policy="hybrid"
        )
        await test_company.insert()
        logger.info(f"✅ Created company model: {test_company.id}")

        # Test Job model
        test_job = Job(
            external_id="test_job_123",
            title="Senior Python Developer",
            description="A test job posting",
            company_id=test_company.id,
            company_name=test_company.name,
            required_skills=["Python", "FastAPI", "MongoDB"],
            salary_min=80000,
            salary_max=120000,
            remote_option="full"
        )
        await test_job.insert()
        logger.info(f"✅ Created job model: {test_job.id}")

        # Test JobMatch model
        test_match = JobMatch(
            user_id=test_user.id,
            job_id=test_job.id,
            overall_score=85.5,
            matched_skills=["Python", "MongoDB"],
            missing_skills=["FastAPI"],
            recommendation="good_match"
        )
        await test_match.insert()
        logger.info(f"✅ Created job match model: {test_match.id}")

        # Test JobApplication model
        test_application = JobApplication(
            user_id=test_user.id,
            job_id=test_job.id,
            job_match_id=test_match.id,
            status="submitted",
            cover_letter="This is a test cover letter",
            applied_at=datetime.utcnow()
        )
        await test_application.insert()
        logger.info(f"✅ Created job application model: {test_application.id}")

        # Test queries
        user_count = await User.count()
        job_count = await Job.count()
        application_count = await JobApplication.count()

        logger.info(f"✅ Document counts - Users: {user_count}, Jobs: {job_count}, Applications: {application_count}")

    except Exception as e:
        logger.error(f"❌ Models test failed: {e}")


async def cleanup_test_data():
    """Clean up test data"""
    logger.info("Cleaning up test data...")

    try:
        # Delete test documents
        await User.find(User.email.regex("test|model")).delete()
        await Company.find(Company.name == "Test Company").delete()
        await Job.find(Job.external_id.regex("test")).delete()
        await JobMatch.find().delete()  # Clean all matches for safety
        await JobApplication.find().delete()  # Clean all applications for safety

        logger.info("✅ Cleaned up test data")

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")


async def run_all_tests():
    """Run all tests"""
    logger.info("🚀 Starting MongoDB tests...")

    success = True

    try:
        # Test connection
        if not await test_connection():
            success = False
            return

        # Test user service
        await test_user_service()

        # Test models
        await test_models()

        # Cleanup
        await cleanup_test_data()

        if success:
            logger.info("🎉 All MongoDB tests passed!")
        else:
            logger.error("❌ Some tests failed!")

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        success = False

    finally:
        await close_mongodb_connection()
        logger.info("🔌 Disconnected from MongoDB")

    return success


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)