"""
User and authentication related database models
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any

Base = declarative_base()


class User(Base):
    """User model for authentication and basic user data"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for magic link users
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user", nullable=False)  # user, admin, moderator

    # Account status
    active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Subscription info
    subscription_status = Column(String(50), default="inactive")  # active, inactive, cancelled, past_due
    subscription_plan = Column(String(50), nullable=True)  # basic, premium, enterprise
    subscription_expires_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)

    # Onboarding
    from_onboarding = Column(Boolean, default=False, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    onboarding_step = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="user", cascade="all, delete-orphan")
    magic_link_tokens = relationship("MagicLinkToken", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    """Extended user profile information"""
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    email = Column(String(255), nullable=False)  # Denormalized for faster queries

    # Personal information
    full_name = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    timezone = Column(String(100), nullable=True, default="UTC")

    # Professional information
    job_title = Column(String(255), nullable=True)
    years_experience = Column(Integer, nullable=True)
    desired_salary = Column(Integer, nullable=True)  # In USD
    work_type = Column(JSON, nullable=True)  # ["remote", "hybrid", "on-site"]
    location_preferences = Column(JSON, nullable=True)  # List of preferred locations
    education_level = Column(String(100), nullable=True)
    skills = Column(JSON, nullable=True)  # List of skills

    # Job preferences
    preferred_industries = Column(JSON, nullable=True)
    preferred_company_sizes = Column(JSON, nullable=True)
    work_authorization = Column(String(100), nullable=True)  # "US_citizen", "green_card", "visa_required", etc.

    # Resume and documents
    resume_uploaded = Column(Boolean, default=False, nullable=False)
    resume_url = Column(String(500), nullable=True)
    resume_filename = Column(String(255), nullable=True)
    cover_letter_template = Column(Text, nullable=True)

    # AI preferences
    ai_apply_enabled = Column(Boolean, default=False, nullable=False)
    ai_cover_letter_enabled = Column(Boolean, default=True, nullable=False)
    ai_interview_prep_enabled = Column(Boolean, default=True, nullable=False)

    # Privacy settings
    profile_public = Column(Boolean, default=False, nullable=False)
    share_analytics = Column(Boolean, default=True, nullable=False)

    # Computed fields (updated by triggers or application logic)
    profile_completion_percentage = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile")


class MagicLinkToken(Base):
    """Magic link tokens for passwordless authentication"""
    __tablename__ = "magic_link_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="magic_link_tokens")


class RefreshToken(Base):
    """Refresh tokens for JWT authentication"""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)


class PasswordResetToken(Base):
    """Password reset tokens"""
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)


class EmailVerificationToken(Base):
    """Email verification tokens"""
    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)


# Pydantic models for API serialization
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "user"

    class Config:
        from_attributes = True


class UserCreate(UserBase):
    password: Optional[str] = None
    from_onboarding: bool = False


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: str
    active: bool
    email_verified: bool
    subscription_status: Optional[str] = None
    subscription_plan: Optional[str] = None
    onboarding_completed: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileBase(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    years_experience: Optional[int] = None
    desired_salary: Optional[int] = None
    work_type: Optional[List[str]] = None
    location_preferences: Optional[List[str]] = None
    education_level: Optional[str] = None
    skills: Optional[List[str]] = None
    preferred_industries: Optional[List[str]] = None
    work_authorization: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(UserProfileBase):
    ai_apply_enabled: Optional[bool] = None
    ai_cover_letter_enabled: Optional[bool] = None
    ai_interview_prep_enabled: Optional[bool] = None
    profile_public: Optional[bool] = None

    class Config:
        from_attributes = True


class UserProfileResponse(UserProfileBase):
    id: str
    user_id: str
    email: str
    resume_uploaded: bool
    ai_apply_enabled: bool
    ai_cover_letter_enabled: bool
    ai_interview_prep_enabled: bool
    profile_completion_percentage: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True