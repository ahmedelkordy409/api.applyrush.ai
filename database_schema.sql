-- ApplyRush.AI Database Schema
-- This script creates all necessary tables for the Python backend

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255), -- Nullable for magic link users
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user' NOT NULL, -- user, admin, moderator

    -- Account status
    active BOOLEAN DEFAULT true NOT NULL,
    email_verified BOOLEAN DEFAULT false NOT NULL,
    email_verified_at TIMESTAMP,

    -- Subscription info
    subscription_status VARCHAR(50) DEFAULT 'inactive', -- active, inactive, cancelled, past_due
    subscription_plan VARCHAR(50), -- basic, premium, enterprise
    subscription_expires_at TIMESTAMP,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),

    -- Onboarding
    from_onboarding BOOLEAN DEFAULT false NOT NULL,
    onboarding_completed BOOLEAN DEFAULT false NOT NULL,
    onboarding_step INTEGER DEFAULT 0 NOT NULL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_login TIMESTAMP
);

-- User profiles table
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL, -- Denormalized for faster queries

    -- Personal information
    full_name VARCHAR(255),
    phone_number VARCHAR(50),
    location VARCHAR(255),
    timezone VARCHAR(100) DEFAULT 'UTC',

    -- Professional information
    job_title VARCHAR(255),
    years_experience INTEGER,
    desired_salary INTEGER, -- In USD
    work_type JSONB, -- ["remote", "hybrid", "on-site"]
    location_preferences JSONB, -- List of preferred locations
    education_level VARCHAR(100),
    skills JSONB, -- List of skills

    -- Job preferences
    preferred_industries JSONB,
    preferred_company_sizes JSONB,
    work_authorization VARCHAR(100), -- "US_citizen", "green_card", "visa_required", etc.

    -- Resume and documents
    resume_uploaded BOOLEAN DEFAULT false NOT NULL,
    resume_url VARCHAR(500),
    resume_filename VARCHAR(255),
    cover_letter_template TEXT,

    -- AI preferences
    ai_apply_enabled BOOLEAN DEFAULT false NOT NULL,
    ai_cover_letter_enabled BOOLEAN DEFAULT true NOT NULL,
    ai_interview_prep_enabled BOOLEAN DEFAULT true NOT NULL,

    -- Privacy settings
    profile_public BOOLEAN DEFAULT false NOT NULL,
    share_analytics BOOLEAN DEFAULT true NOT NULL,

    -- Computed fields
    profile_completion_percentage INTEGER DEFAULT 0 NOT NULL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Magic link tokens table
CREATE TABLE IF NOT EXISTS magic_link_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT false NOT NULL,
    used_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ip_address VARCHAR(45), -- Support IPv6
    user_agent TEXT
);

-- Refresh tokens table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked BOOLEAN DEFAULT false NOT NULL,
    revoked_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Password reset tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT false NOT NULL,
    used_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Email verification tokens table
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT false NOT NULL,
    used_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Basic job information
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    description TEXT NOT NULL,
    requirements JSONB, -- List of requirements
    benefits JSONB, -- List of benefits

    -- Salary information
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency VARCHAR(3) DEFAULT 'USD' NOT NULL,

    -- Job details
    job_type VARCHAR(20) DEFAULT 'full-time' NOT NULL,
    remote BOOLEAN DEFAULT false NOT NULL,

    -- Application information
    apply_url VARCHAR(500) NOT NULL,
    company_logo_url VARCHAR(500),

    -- Source tracking
    source VARCHAR(50) DEFAULT 'manual' NOT NULL,
    source_job_id VARCHAR(255), -- External job ID from source

    -- SEO and categorization
    keywords JSONB, -- Extracted keywords
    skills_required JSONB, -- Required skills
    experience_level VARCHAR(50), -- entry, mid, senior
    industry VARCHAR(100),
    company_size VARCHAR(50),

    -- Status and moderation
    active BOOLEAN DEFAULT true NOT NULL,
    featured BOOLEAN DEFAULT false NOT NULL,
    verified BOOLEAN DEFAULT false NOT NULL,

    -- Analytics
    view_count INTEGER DEFAULT 0 NOT NULL,
    application_count INTEGER DEFAULT 0 NOT NULL,

    -- Timestamps
    date_posted TIMESTAMP NOT NULL,
    date_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Applications table
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Application details
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, -- pending, applied, viewed, interview, offer, rejected, withdrawn
    cover_letter TEXT,
    notes TEXT,

    -- Application tracking
    applied_at TIMESTAMP,
    viewed_at TIMESTAMP,
    response_received_at TIMESTAMP,

    -- AI-generated content tracking
    ai_generated_cover_letter BOOLEAN DEFAULT false NOT NULL,
    ai_auto_applied BOOLEAN DEFAULT false NOT NULL,

    -- External tracking
    external_application_id VARCHAR(255),
    application_method VARCHAR(50) DEFAULT 'manual' NOT NULL, -- manual, auto, bulk

    -- Analytics
    resume_version_used VARCHAR(100),
    time_to_apply_minutes INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Ensure unique application per user per job
    UNIQUE(user_id, job_id)
);

-- Interviews table
CREATE TABLE IF NOT EXISTS interviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Interview details
    interview_type VARCHAR(50) NOT NULL, -- phone, video, in-person, technical
    scheduled_at TIMESTAMP,
    duration_minutes INTEGER,
    location VARCHAR(255), -- Address or video link

    -- Interviewer information
    interviewer_name VARCHAR(255),
    interviewer_email VARCHAR(255),
    interviewer_title VARCHAR(255),

    -- Interview preparation
    preparation_notes TEXT,
    questions_prepared JSONB, -- List of prepared questions
    research_notes TEXT,

    -- Interview outcome
    status VARCHAR(50) DEFAULT 'scheduled' NOT NULL, -- scheduled, completed, cancelled, rescheduled
    feedback TEXT,
    rating INTEGER, -- 1-5 rating
    next_steps TEXT,

    -- AI assistance
    ai_prep_generated BOOLEAN DEFAULT false NOT NULL,
    ai_questions_suggested JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP
);

-- Resumes table
CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Resume details
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL, -- Size in bytes
    content_type VARCHAR(100) NOT NULL,

    -- Resume metadata
    version VARCHAR(50) DEFAULT '1.0' NOT NULL,
    is_default BOOLEAN DEFAULT false NOT NULL,
    extracted_text TEXT,

    -- AI analysis
    ai_analyzed BOOLEAN DEFAULT false NOT NULL,
    skills_extracted JSONB,
    experience_summary TEXT,
    improvements_suggested JSONB,
    ats_score INTEGER, -- ATS compatibility score 0-100

    -- Usage tracking
    application_count INTEGER DEFAULT 0 NOT NULL,
    last_used_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Cover letters table
CREATE TABLE IF NOT EXISTS cover_letters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,

    -- Cover letter details
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,

    -- Generation metadata
    ai_generated BOOLEAN DEFAULT false NOT NULL,
    template_used VARCHAR(100),
    personalization_level VARCHAR(50), -- basic, moderate, high

    -- Usage tracking
    usage_count INTEGER DEFAULT 0 NOT NULL,
    last_used_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Payment transactions table
CREATE TABLE IF NOT EXISTS payment_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Transaction details
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    amount INTEGER NOT NULL, -- Amount in cents
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    status VARCHAR(50) NOT NULL, -- pending, succeeded, failed, cancelled

    -- Transaction type
    transaction_type VARCHAR(50) NOT NULL, -- subscription, one_time, refund
    description TEXT,

    -- Metadata
    stripe_metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Subscription history table
CREATE TABLE IF NOT EXISTS subscription_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Subscription details
    plan VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,

    -- Billing details
    amount INTEGER, -- Amount in cents
    currency VARCHAR(3) DEFAULT 'USD',
    billing_cycle VARCHAR(20), -- monthly, yearly

    -- Stripe details
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),

    -- Reason for change
    change_reason VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Auto-apply rules table
CREATE TABLE IF NOT EXISTS auto_apply_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Rule details
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT true NOT NULL,

    -- Criteria
    keywords JSONB, -- Required keywords
    excluded_keywords JSONB, -- Keywords to exclude
    job_types JSONB, -- Allowed job types
    locations JSONB, -- Preferred locations
    remote_only BOOLEAN DEFAULT false,
    salary_min INTEGER,
    salary_max INTEGER,

    -- Limits
    daily_application_limit INTEGER DEFAULT 10,
    weekly_application_limit INTEGER DEFAULT 50,

    -- AI settings
    ai_cover_letter BOOLEAN DEFAULT true,
    cover_letter_template_id UUID,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Auto-apply logs table
CREATE TABLE IF NOT EXISTS auto_apply_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_id UUID REFERENCES auto_apply_rules(id) ON DELETE SET NULL,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    application_id UUID REFERENCES applications(id) ON DELETE SET NULL,

    -- Log details
    action VARCHAR(50) NOT NULL, -- applied, skipped, failed
    reason TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Analytics events table
CREATE TABLE IF NOT EXISTS analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Event details
    event_type VARCHAR(100) NOT NULL,
    event_name VARCHAR(255) NOT NULL,
    properties JSONB,

    -- Session tracking
    session_id VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Notification details
    type VARCHAR(50) NOT NULL, -- email, push, in_app
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,

    -- Status
    read BOOLEAN DEFAULT false NOT NULL,
    read_at TIMESTAMP,

    -- Delivery
    delivered BOOLEAN DEFAULT false NOT NULL,
    delivered_at TIMESTAMP,

    -- Metadata
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(active);
CREATE INDEX IF NOT EXISTS idx_users_subscription_status ON users(subscription_status);

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_completion ON profiles(profile_completion_percentage);

CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_token ON magic_link_tokens(token);
CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_user_id ON magic_link_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_expires_at ON magic_link_tokens(expires_at);

CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active);
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_remote ON jobs(remote);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at);

CREATE INDEX IF NOT EXISTS idx_interviews_application_id ON interviews(application_id);
CREATE INDEX IF NOT EXISTS idx_interviews_user_id ON interviews(user_id);
CREATE INDEX IF NOT EXISTS idx_interviews_scheduled_at ON interviews(scheduled_at);

CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_resumes_is_default ON resumes(is_default);

CREATE INDEX IF NOT EXISTS idx_payment_transactions_user_id ON payment_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_status ON payment_transactions(status);

CREATE INDEX IF NOT EXISTS idx_auto_apply_rules_user_id ON auto_apply_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_auto_apply_rules_enabled ON auto_apply_rules(enabled);

CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id ON analytics_events(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);

-- Update timestamps trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add update triggers to tables with updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_applications_updated_at BEFORE UPDATE ON applications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_interviews_updated_at BEFORE UPDATE ON interviews FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_resumes_updated_at BEFORE UPDATE ON resumes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_cover_letters_updated_at BEFORE UPDATE ON cover_letters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_payment_transactions_updated_at BEFORE UPDATE ON payment_transactions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_auto_apply_rules_updated_at BEFORE UPDATE ON auto_apply_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();