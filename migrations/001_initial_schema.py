"""
Initial Database Schema Migration
Creates comprehensive database structure for ApplyRush.AI platform
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Create initial database schema"""

    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # =========================================
    # CORE USER MANAGEMENT
    # =========================================

    # Users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('provider', sa.String(50), server_default='local'),
        sa.Column('provider_id', sa.String(255)),
        sa.Column('email_verified', sa.Boolean(), server_default='false'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('login_count', sa.Integer(), server_default='0')
    )

    # User profiles table
    op.create_table('user_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('full_name', sa.String(255)),
        sa.Column('first_name', sa.String(100)),
        sa.Column('last_name', sa.String(100)),
        sa.Column('phone', sa.String(20)),
        sa.Column('location', sa.String(255)),
        sa.Column('city', sa.String(100)),
        sa.Column('state', sa.String(100)),
        sa.Column('country', sa.String(100)),
        sa.Column('timezone', sa.String(50)),
        sa.Column('linkedin_url', sa.String(500)),
        sa.Column('github_url', sa.String(500)),
        sa.Column('portfolio_url', sa.String(500)),
        sa.Column('bio', sa.Text()),
        sa.Column('profile_image_url', sa.String(500)),
        sa.Column('subscription_status', sa.String(50), server_default='free'),
        sa.Column('subscription_expires_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('credits_remaining', sa.Integer(), server_default='0'),
        sa.Column('onboarding_completed', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # User settings table
    op.create_table('user_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),

        # Job Search Settings
        sa.Column('job_search_active', sa.Boolean(), server_default='true'),
        sa.Column('match_threshold', sa.Integer(), server_default='55'),
        sa.Column('approval_mode', sa.String(20), server_default='approval'),
        sa.Column('auto_apply_delay_hours', sa.Integer(), server_default='24'),
        sa.Column('max_applications_per_day', sa.Integer(), server_default='10'),

        # AI Features
        sa.Column('ai_cover_letters_enabled', sa.Boolean(), server_default='false'),
        sa.Column('ai_resume_optimization_enabled', sa.Boolean(), server_default='false'),
        sa.Column('ai_interview_prep_enabled', sa.Boolean(), server_default='true'),

        # Notification Preferences
        sa.Column('email_notifications', sa.Boolean(), server_default='true'),
        sa.Column('job_match_notifications', sa.Boolean(), server_default='true'),
        sa.Column('application_status_notifications', sa.Boolean(), server_default='true'),
        sa.Column('weekly_summary_notifications', sa.Boolean(), server_default='true'),

        # Privacy Settings
        sa.Column('profile_visibility', sa.String(20), server_default='private'),
        sa.Column('allow_recruiter_contact', sa.Boolean(), server_default='false'),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # =========================================
    # RESUME MANAGEMENT
    # =========================================

    # Resumes table
    op.create_table('resumes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500)),
        sa.Column('file_content', sa.LargeBinary()),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_type', sa.String(100), nullable=False),
        sa.Column('mime_type', sa.String(100)),

        # Resume metadata
        sa.Column('title', sa.String(255)),
        sa.Column('description', sa.Text()),
        sa.Column('version', sa.Integer(), server_default='1'),
        sa.Column('is_current', sa.Boolean(), server_default='false'),

        # AI parsing results
        sa.Column('parsed_content', postgresql.JSONB()),
        sa.Column('skills_extracted', postgresql.ARRAY(sa.Text())),
        sa.Column('experience_years', sa.Integer()),
        sa.Column('education_level', sa.String(50)),

        # Status and timestamps
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('upload_source', sa.String(50), server_default='manual'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # Enhanced resumes table
    op.create_table('enhanced_resumes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('original_resume_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('resumes.id', ondelete='CASCADE')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True)),

        # Generated content
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500)),
        sa.Column('file_content', sa.LargeBinary()),
        sa.Column('file_size', sa.Integer()),

        # Enhancement details
        sa.Column('ats_score', sa.Integer()),
        sa.Column('optimization_type', sa.String(50)),
        sa.Column('enhancements_applied', postgresql.ARRAY(sa.Text())),
        sa.Column('keywords_added', postgresql.ARRAY(sa.Text())),

        # AI metadata
        sa.Column('ai_model_used', sa.String(100)),
        sa.Column('processing_time_ms', sa.Integer()),
        sa.Column('confidence_score', sa.Numeric(5, 2)),

        # Status
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # =========================================
    # JOB DATA MANAGEMENT
    # =========================================

    # Companies table
    op.create_table('companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(255)),
        sa.Column('website', sa.String(500)),
        sa.Column('logo_url', sa.String(500)),

        # Company details
        sa.Column('description', sa.Text()),
        sa.Column('industry', sa.String(100)),
        sa.Column('size_category', sa.String(20)),
        sa.Column('employee_count_min', sa.Integer()),
        sa.Column('employee_count_max', sa.Integer()),
        sa.Column('founded_year', sa.Integer()),

        # Location information
        sa.Column('headquarters_location', sa.String(255)),
        sa.Column('locations', postgresql.ARRAY(sa.Text())),

        # Company metrics
        sa.Column('glassdoor_rating', sa.Numeric(3, 2)),
        sa.Column('linkedin_followers', sa.Integer()),

        # Status
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # Jobs table
    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('external_id', sa.String(255)),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000)),

        # Basic job information
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('company_id', sa.String(255)),
        sa.Column('location', sa.String(255)),
        sa.Column('remote_type', sa.String(20)),

        # Job details
        sa.Column('description', sa.Text()),
        sa.Column('requirements', sa.Text()),
        sa.Column('benefits', sa.Text()),
        sa.Column('salary_min', sa.Integer()),
        sa.Column('salary_max', sa.Integer()),
        sa.Column('salary_currency', sa.String(10), server_default='USD'),
        sa.Column('employment_type', sa.String(20)),
        sa.Column('experience_level', sa.String(20)),

        # Additional metadata
        sa.Column('company_size', sa.String(20)),
        sa.Column('industry', sa.String(100)),
        sa.Column('skills_required', postgresql.ARRAY(sa.Text())),
        sa.Column('education_required', sa.String(50)),

        # Job status and discovery
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('posted_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('expires_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('discovered_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),

        # Search and matching metadata
        sa.Column('processed_for_matching', sa.Boolean(), server_default='false'),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # =========================================
    # APPLICATION MANAGEMENT
    # =========================================

    # Applications table
    op.create_table('applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE')),
        sa.Column('resume_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('resumes.id')),
        sa.Column('cover_letter_id', postgresql.UUID(as_uuid=True)),

        # Application details
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('application_method', sa.String(50)),
        sa.Column('applied_at', sa.TIMESTAMP(timezone=True)),

        # Tracking information
        sa.Column('match_score', sa.Numeric(5, 2)),
        sa.Column('match_reasons', postgresql.ARRAY(sa.Text())),
        sa.Column('application_source', sa.String(50), server_default='auto'),

        # Follow-up tracking
        sa.Column('last_contact_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('follow_up_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('interview_scheduled_date', sa.TIMESTAMP(timezone=True)),

        # Response tracking
        sa.Column('company_response_received', sa.Boolean(), server_default='false'),
        sa.Column('company_response_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('company_response_type', sa.String(50)),

        # Notes and feedback
        sa.Column('notes', sa.Text()),
        sa.Column('feedback', sa.Text()),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # Application queue table
    op.create_table('application_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE')),

        # Queue metadata
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('priority', sa.Integer(), server_default='5'),
        sa.Column('match_score', sa.Numeric(5, 2)),
        sa.Column('match_reasons', postgresql.ARRAY(sa.Text())),

        # Auto-apply scheduling
        sa.Column('auto_apply_after', sa.TIMESTAMP(timezone=True)),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True)),

        # AI analysis
        sa.Column('cover_letter_generated', sa.Boolean(), server_default='false'),
        sa.Column('resume_optimized', sa.Boolean(), server_default='false'),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # =========================================
    # AI-POWERED FEATURES
    # =========================================

    # Cover letters table
    op.create_table('cover_letters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id')),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id')),

        # Content
        sa.Column('title', sa.String(255)),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('format', sa.String(20), server_default='text'),

        # Generation metadata
        sa.Column('generation_type', sa.String(20), server_default='ai'),
        sa.Column('ai_model_used', sa.String(100)),
        sa.Column('writing_style', sa.String(50)),
        sa.Column('tone', sa.String(50)),

        # Performance metrics
        sa.Column('generation_time_ms', sa.Integer()),
        sa.Column('confidence_score', sa.Numeric(5, 2)),
        sa.Column('word_count', sa.Integer()),

        # Usage tracking
        sa.Column('used_in_application', sa.Boolean(), server_default='false'),
        sa.Column('feedback_rating', sa.Integer()),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # Interview sessions table
    op.create_table('interview_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id')),

        # Session configuration
        sa.Column('session_type', sa.String(20), nullable=False),
        sa.Column('difficulty_level', sa.String(20), server_default='medium'),
        sa.Column('ai_personality', sa.String(20), server_default='professional'),
        sa.Column('candidate_name', sa.String(255)),

        # Session metadata
        sa.Column('total_questions', sa.Integer(), server_default='0'),
        sa.Column('questions_answered', sa.Integer(), server_default='0'),
        sa.Column('current_question_index', sa.Integer(), server_default='0'),

        # Session state
        sa.Column('status', sa.String(20), server_default='created'),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('duration_minutes', sa.Integer()),

        # Performance results
        sa.Column('overall_score', sa.Numeric(5, 2)),
        sa.Column('completion_rate', sa.Numeric(5, 2)),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # Interview questions table
    op.create_table('interview_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE')),

        # Question details
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(50)),
        sa.Column('question_category', sa.String(100)),
        sa.Column('order_index', sa.Integer(), nullable=False),

        # User response
        sa.Column('answer_text', sa.Text()),
        sa.Column('answer_submitted_at', sa.TIMESTAMP(timezone=True)),

        # AI evaluation
        sa.Column('score', sa.Integer()),
        sa.Column('feedback', sa.Text()),
        sa.Column('strengths', postgresql.ARRAY(sa.Text())),
        sa.Column('improvements', postgresql.ARRAY(sa.Text())),

        # Timing
        sa.Column('time_to_answer_seconds', sa.Integer()),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    # =========================================
    # ANALYTICS AND TRACKING
    # =========================================

    # User activity table
    op.create_table('user_activity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),

        # Activity details
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50)),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True)),

        # Context and metadata
        sa.Column('context', postgresql.JSONB()),
        sa.Column('ip_address', postgresql.INET()),
        sa.Column('user_agent', sa.Text()),
        sa.Column('session_id', sa.String(255)),

        # Performance metrics
        sa.Column('duration_ms', sa.Integer()),
        sa.Column('success', sa.Boolean(), server_default='true'),
        sa.Column('error_message', sa.Text()),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )


def downgrade():
    """Drop all tables"""

    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('user_activity')
    op.drop_table('interview_questions')
    op.drop_table('interview_sessions')
    op.drop_table('cover_letters')
    op.drop_table('application_queue')
    op.drop_table('applications')
    op.drop_table('jobs')
    op.drop_table('companies')
    op.drop_table('enhanced_resumes')
    op.drop_table('resumes')
    op.drop_table('user_settings')
    op.drop_table('user_profiles')
    op.drop_table('users')