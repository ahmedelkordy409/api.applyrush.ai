-- Migration for User Management Tables
-- Creates tables for user profiles, search settings, queue management, onboarding, and documents

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- User Profiles Table (Enhanced)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) UNIQUE NOT NULL,
    
    -- Basic info
    email VARCHAR(255),
    full_name VARCHAR(255),
    phone VARCHAR(50),
    
    -- Onboarding status
    onboarding_status VARCHAR(50) DEFAULT 'not_started',
    onboarding_completed_at TIMESTAMP,
    onboarding_data JSONB,
    
    -- Profile data
    skills JSONB,
    experience_years INTEGER,
    education JSONB,
    certifications JSONB,
    
    -- Resume and documents
    resume_text TEXT,
    resume_file_url VARCHAR(500),
    cover_letter_template TEXT,
    
    -- Location and remote preferences
    location JSONB,
    remote_preference VARCHAR(50) DEFAULT 'hybrid',
    willing_to_relocate BOOLEAN DEFAULT FALSE,
    
    -- Career preferences
    target_roles JSONB,
    industries JSONB,
    company_sizes JSONB,
    
    -- Salary expectations
    salary_minimum FLOAT,
    salary_target FLOAT,
    salary_currency VARCHAR(10) DEFAULT 'USD',
    
    -- Work preferences
    work_visa_required BOOLEAN DEFAULT FALSE,
    security_clearance VARCHAR(100),
    availability VARCHAR(50) DEFAULT 'immediate',
    
    -- Culture preferences
    culture_preferences JSONB,
    benefits_priorities JSONB,
    
    -- Account settings
    user_tier VARCHAR(50) DEFAULT 'free',
    ai_model_preference VARCHAR(50) DEFAULT 'balanced',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User Search Settings Table
CREATE TABLE IF NOT EXISTS user_search_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    
    -- Search status and control
    search_status VARCHAR(50) DEFAULT 'active',
    search_paused_at TIMESTAMP,
    search_pause_reason VARCHAR(255),
    auto_resume_at TIMESTAMP,
    
    -- Search parameters
    keywords JSONB,
    excluded_keywords JSONB,
    job_titles JSONB,
    excluded_titles JSONB,
    
    -- Location filters
    locations JSONB,
    remote_only BOOLEAN DEFAULT FALSE,
    max_commute_distance INTEGER,
    
    -- Company filters
    target_companies JSONB,
    excluded_companies JSONB,
    company_size_filters JSONB,
    industry_filters JSONB,
    
    -- Job criteria
    experience_level JSONB,
    employment_type JSONB,
    minimum_salary FLOAT,
    maximum_salary FLOAT,
    
    -- Application filters
    minimum_match_score FLOAT DEFAULT 70.0,
    auto_apply_threshold FLOAT DEFAULT 85.0,
    require_manual_review BOOLEAN DEFAULT TRUE,
    
    -- Search frequency and limits
    max_applications_per_day INTEGER DEFAULT 10,
    max_applications_per_week INTEGER DEFAULT 50,
    search_frequency_hours INTEGER DEFAULT 4,
    
    -- Time restrictions
    search_active_hours JSONB,
    search_active_days JSONB,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Platform settings
    enabled_platforms JSONB,
    platform_credentials JSONB, -- Encrypted
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User Queue Table
CREATE TABLE IF NOT EXISTS user_queues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    job_id VARCHAR(255) NOT NULL,
    
    -- Queue management
    priority VARCHAR(50) DEFAULT 'normal',
    queued_at TIMESTAMP DEFAULT NOW(),
    scheduled_for TIMESTAMP,
    
    -- Job data snapshot
    job_data JSONB NOT NULL,
    match_score FLOAT,
    
    -- Queue status
    status VARCHAR(50) DEFAULT 'queued',
    processed_at TIMESTAMP,
    workflow_execution_id UUID,
    
    -- Processing results
    application_submitted BOOLEAN DEFAULT FALSE,
    application_id UUID,
    processing_error TEXT,
    
    -- User actions
    user_flagged BOOLEAN DEFAULT FALSE,
    user_notes TEXT,
    user_action VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Onboarding Steps Table
CREATE TABLE IF NOT EXISTS onboarding_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    
    step_name VARCHAR(100) NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    
    -- Step data
    step_data JSONB,
    completion_percentage FLOAT DEFAULT 0.0,
    
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User Documents Table
CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    
    -- Document metadata
    document_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    
    -- File information
    file_format VARCHAR(20) NOT NULL,
    file_size INTEGER,
    file_url VARCHAR(500),
    file_content BYTEA,
    
    -- Document content
    extracted_text TEXT,
    structured_data JSONB,
    
    -- Versioning
    version INTEGER DEFAULT 1,
    parent_document_id UUID,
    is_latest_version BOOLEAN DEFAULT TRUE,
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- AI optimization data
    ai_optimized BOOLEAN DEFAULT FALSE,
    optimization_data JSONB,
    keywords JSONB,
    skills_identified JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cover Letter Templates Table
CREATE TABLE IF NOT EXISTS cover_letter_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    
    -- Template metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template_type VARCHAR(50) DEFAULT 'general',
    
    -- Template content
    content TEXT NOT NULL,
    variables JSONB,
    
    -- Usage and performance
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT,
    
    -- Targeting
    industries JSONB,
    job_types JSONB,
    company_sizes JSONB,
    
    -- AI enhancement
    ai_generated BOOLEAN DEFAULT FALSE,
    ai_optimization_score FLOAT,
    
    is_default BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'active',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Generated Documents Table
CREATE TABLE IF NOT EXISTS generated_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    job_id VARCHAR(255) NOT NULL,
    
    -- Source information
    template_id UUID,
    base_document_id UUID,
    
    -- Document details
    document_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    file_format VARCHAR(20) DEFAULT 'pdf',
    file_url VARCHAR(500),
    
    -- Generation metadata
    ai_model_used VARCHAR(100),
    generation_prompt TEXT,
    generation_cost FLOAT,
    generation_time FLOAT,
    
    -- Customization data
    job_data JSONB,
    company_research JSONB,
    customizations JSONB,
    
    -- Quality metrics
    quality_score FLOAT,
    keyword_match_score FLOAT,
    readability_score FLOAT,
    
    -- Usage tracking
    submitted BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMP,
    application_id UUID,
    
    -- Performance tracking
    employer_opened BOOLEAN,
    employer_downloaded BOOLEAN,
    led_to_interview BOOLEAN,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Document Analysis Table
CREATE TABLE IF NOT EXISTS document_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    
    -- Analysis results
    analysis_type VARCHAR(50) NOT NULL,
    results JSONB NOT NULL,
    confidence_score FLOAT,
    
    -- Improvement suggestions
    suggestions JSONB,
    missing_elements JSONB,
    strengths JSONB,
    weaknesses JSONB,
    
    -- Benchmarking
    industry_benchmark_score FLOAT,
    role_relevance_score FLOAT,
    ats_compatibility_score FLOAT,
    
    -- Analysis metadata
    ai_model_used VARCHAR(100),
    analysis_cost FLOAT,
    processing_time FLOAT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_onboarding_status ON user_profiles(onboarding_status);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_tier ON user_profiles(user_tier);

CREATE INDEX IF NOT EXISTS idx_user_search_settings_user_id ON user_search_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_search_settings_status ON user_search_settings(search_status);
CREATE INDEX IF NOT EXISTS idx_user_search_settings_auto_resume ON user_search_settings(auto_resume_at) WHERE auto_resume_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_queues_user_id ON user_queues(user_id);
CREATE INDEX IF NOT EXISTS idx_user_queues_job_id ON user_queues(job_id);
CREATE INDEX IF NOT EXISTS idx_user_queues_status ON user_queues(status);
CREATE INDEX IF NOT EXISTS idx_user_queues_priority ON user_queues(priority);
CREATE INDEX IF NOT EXISTS idx_user_queues_scheduled ON user_queues(scheduled_for) WHERE scheduled_for IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_queues_processing ON user_queues(user_id, status, priority, queued_at) WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_onboarding_steps_user_id ON onboarding_steps(user_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_steps_step_name ON onboarding_steps(user_id, step_name);
CREATE INDEX IF NOT EXISTS idx_onboarding_steps_order ON onboarding_steps(user_id, step_order);

CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(user_id, document_type);
CREATE INDEX IF NOT EXISTS idx_user_documents_status ON user_documents(user_id, status);

CREATE INDEX IF NOT EXISTS idx_cover_letter_templates_user_id ON cover_letter_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_cover_letter_templates_type ON cover_letter_templates(user_id, template_type);
CREATE INDEX IF NOT EXISTS idx_cover_letter_templates_default ON cover_letter_templates(user_id, is_default) WHERE is_default = TRUE;

CREATE INDEX IF NOT EXISTS idx_generated_documents_user_id ON generated_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_documents_job_id ON generated_documents(job_id);
CREATE INDEX IF NOT EXISTS idx_generated_documents_type ON generated_documents(user_id, document_type);

CREATE INDEX IF NOT EXISTS idx_document_analyses_document_id ON document_analyses(document_id);
CREATE INDEX IF NOT EXISTS idx_document_analyses_user_id ON document_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_document_analyses_type ON document_analyses(document_id, analysis_type);

-- Create trigger to automatically update updated_at timestamp for all tables
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers to all tables with updated_at column
CREATE TRIGGER update_user_profiles_updated_at 
    BEFORE UPDATE ON user_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_search_settings_updated_at 
    BEFORE UPDATE ON user_search_settings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_queues_updated_at 
    BEFORE UPDATE ON user_queues 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_onboarding_steps_updated_at 
    BEFORE UPDATE ON onboarding_steps 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_documents_updated_at 
    BEFORE UPDATE ON user_documents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cover_letter_templates_updated_at 
    BEFORE UPDATE ON cover_letter_templates 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_generated_documents_updated_at 
    BEFORE UPDATE ON generated_documents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();