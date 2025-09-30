-- Database initialization script for JobHire.AI

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create enum types
CREATE TYPE job_status AS ENUM (
    'discovered', 'evaluating', 'queued', 'applying', 'submitted', 
    'acknowledged', 'screening', 'interview_scheduled', 'interviewing', 
    'offer', 'rejected', 'withdrawn'
);

CREATE TYPE match_recommendation AS ENUM (
    'strong_match', 'good_match', 'possible_match', 'weak_match'
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    supabase_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    resume_text TEXT,
    skills JSONB DEFAULT '[]',
    experience_years INTEGER DEFAULT 0,
    education JSONB DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    auto_apply_enabled BOOLEAN DEFAULT false,
    auto_apply_rules JSONB DEFAULT '{}',
    notification_settings JSONB DEFAULT '{}',
    tier VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    size VARCHAR(50),
    description TEXT,
    website VARCHAR(255),
    logo_url VARCHAR(500),
    culture_keywords JSONB DEFAULT '[]',
    benefits JSONB DEFAULT '[]',
    remote_policy VARCHAR(50),
    avg_response_time_days REAL,
    hire_rate REAL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    company_id INTEGER REFERENCES companies(id),
    company_name VARCHAR(255),
    location JSONB DEFAULT '{}',
    remote_option VARCHAR(20) DEFAULT 'no',
    employment_type VARCHAR(50) DEFAULT 'full-time',
    required_skills JSONB DEFAULT '[]',
    preferred_skills JSONB DEFAULT '[]',
    experience_level VARCHAR(50),
    education_requirements VARCHAR(100),
    salary_min INTEGER,
    salary_max INTEGER,
    currency VARCHAR(10) DEFAULT 'USD',
    benefits JSONB DEFAULT '[]',
    source VARCHAR(50),
    posted_date TIMESTAMP,
    application_deadline TIMESTAMP,
    applicant_count INTEGER,
    application_url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    is_vetted BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Job matches table
CREATE TABLE IF NOT EXISTS job_matches (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    skill_match_score REAL DEFAULT 0,
    experience_score REAL DEFAULT 0,
    education_score REAL DEFAULT 0,
    location_score REAL DEFAULT 0,
    salary_score REAL DEFAULT 0,
    culture_score REAL DEFAULT 0,
    recommendation match_recommendation DEFAULT 'weak_match',
    apply_priority INTEGER DEFAULT 5,
    success_probability REAL DEFAULT 0.5,
    matched_skills JSONB DEFAULT '[]',
    missing_skills JSONB DEFAULT '[]',
    improvement_suggestions JSONB DEFAULT '[]',
    red_flags JSONB DEFAULT '[]',
    competitive_advantage TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, job_id)
);

-- Job applications table
CREATE TABLE IF NOT EXISTS job_applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    job_match_id INTEGER REFERENCES job_matches(id),
    status job_status DEFAULT 'discovered',
    applied_via VARCHAR(50),
    application_url VARCHAR(500),
    resume_version TEXT,
    cover_letter TEXT,
    submitted_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    last_contact_at TIMESTAMP,
    last_status_check TIMESTAMP,
    response_time_hours REAL,
    interview_count INTEGER DEFAULT 0,
    notes TEXT,
    rejection_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, job_id)
);

-- Application status history table
CREATE TABLE IF NOT EXISTS application_status_history (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES job_applications(id) ON DELETE CASCADE,
    from_status job_status,
    to_status job_status NOT NULL,
    changed_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

-- AI processing logs table
CREATE TABLE IF NOT EXISTS ai_processing_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    operation VARCHAR(100) NOT NULL,
    model_used VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    processing_time_ms REAL,
    cost_usd REAL,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    output_quality_score REAL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User analytics table
CREATE TABLE IF NOT EXISTS user_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_applications INTEGER DEFAULT 0,
    successful_applications INTEGER DEFAULT 0,
    interview_rate REAL DEFAULT 0.0,
    offer_rate REAL DEFAULT 0.0,
    avg_match_score REAL,
    ai_accuracy REAL,
    preferred_job_sources JSONB DEFAULT '[]',
    most_successful_times JSONB DEFAULT '{}',
    avg_response_time REAL,
    last_calculated TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Create indexes for better performance
CREATE INDEX idx_users_supabase_id ON users(supabase_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_jobs_external_id ON jobs(external_id);
CREATE INDEX idx_jobs_active ON jobs(is_active) WHERE is_active = true;
CREATE INDEX idx_jobs_posted_date ON jobs(posted_date);
CREATE INDEX idx_job_matches_user_id ON job_matches(user_id);
CREATE INDEX idx_job_matches_score ON job_matches(overall_score);
CREATE INDEX idx_job_applications_user_id ON job_applications(user_id);
CREATE INDEX idx_job_applications_status ON job_applications(status);
CREATE INDEX idx_job_applications_submitted ON job_applications(submitted_at);
CREATE INDEX idx_ai_logs_user_operation ON ai_processing_logs(user_id, operation);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_job_matches_updated_at BEFORE UPDATE ON job_matches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_job_applications_updated_at BEFORE UPDATE ON job_applications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();