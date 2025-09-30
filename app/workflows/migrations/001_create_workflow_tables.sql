-- Migration for LangGraph workflow database tables
-- Create tables for storing workflow executions, job applications, and analytics

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Workflow executions table
CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id VARCHAR(255) UNIQUE NOT NULL,
    workflow_type VARCHAR(100) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    job_id VARCHAR(255),
    
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    current_node VARCHAR(100),
    
    -- JSON fields for flexible data storage
    initial_state JSONB,
    final_state JSONB,
    user_profile JSONB,
    job_data JSONB,
    company_data JSONB,
    
    -- Results and metrics
    analysis_results JSONB,
    decisions JSONB,
    actions_taken JSONB,
    results JSONB,
    
    -- Performance metrics
    match_score FLOAT,
    processing_time_seconds FLOAT,
    ai_cost_usd FLOAT DEFAULT 0.0,
    
    -- Error handling
    errors JSONB,
    warnings JSONB,
    
    -- Metadata
    user_tier VARCHAR(50) DEFAULT 'free',
    config JSONB,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Job applications table
CREATE TABLE IF NOT EXISTS job_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    job_id VARCHAR(255) NOT NULL,
    workflow_execution_id UUID REFERENCES workflow_executions(id),
    
    -- Application details
    application_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    applied_at TIMESTAMP,
    application_method VARCHAR(50),
    
    -- Generated content
    cover_letter JSONB,
    resume_optimizations JSONB,
    
    -- Matching and scoring
    match_score FLOAT,
    success_probability FLOAT,
    recommendation VARCHAR(100),
    
    -- Follow-up tracking
    follow_up_scheduled BOOLEAN DEFAULT FALSE,
    follow_up_timeline JSONB,
    last_follow_up TIMESTAMP,
    
    -- Response tracking
    employer_response VARCHAR(100),
    response_received_at TIMESTAMP,
    interview_scheduled BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Workflow analytics table
CREATE TABLE IF NOT EXISTS workflow_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_execution_id UUID NOT NULL REFERENCES workflow_executions(id),
    user_id VARCHAR(255) NOT NULL,
    
    -- Performance metrics
    total_processing_time FLOAT,
    ai_processing_time FLOAT,
    node_count INTEGER,
    error_count INTEGER,
    warning_count INTEGER,
    
    -- AI usage metrics
    ai_calls_made INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_ai_cost FLOAT DEFAULT 0.0,
    
    -- Success metrics
    workflow_success BOOLEAN,
    application_submitted BOOLEAN,
    match_quality_score FLOAT,
    
    -- User tier for cost analysis
    user_tier VARCHAR(50),
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_job_id ON workflow_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_type ON workflow_executions(workflow_type);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_created_at ON workflow_executions(created_at);

CREATE INDEX IF NOT EXISTS idx_job_applications_user_id ON job_applications(user_id);
CREATE INDEX IF NOT EXISTS idx_job_applications_job_id ON job_applications(job_id);
CREATE INDEX IF NOT EXISTS idx_job_applications_status ON job_applications(application_status);
CREATE INDEX IF NOT EXISTS idx_job_applications_applied_at ON job_applications(applied_at);

CREATE INDEX IF NOT EXISTS idx_workflow_analytics_user_id ON workflow_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_execution_id ON workflow_analytics(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_created_at ON workflow_analytics(created_at);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_workflow_executions_updated_at 
    BEFORE UPDATE ON workflow_executions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_applications_updated_at 
    BEFORE UPDATE ON job_applications 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();