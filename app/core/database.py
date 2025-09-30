"""
Database configuration and connection management
"""

from databases import Database
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Database URL
DATABASE_URL = settings.DATABASE_URL

# Create database instance
database = Database(DATABASE_URL)

# SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base model
Base = declarative_base()

# Metadata
metadata = MetaData()


async def get_database() -> Database:
    """Get database instance"""
    return database


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Health check for database
async def check_database_health() -> bool:
    """Check if database is healthy"""
    try:
        await database.execute("SELECT 1")
        return True
    except Exception:
        return False