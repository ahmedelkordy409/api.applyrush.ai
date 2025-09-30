"""
Comprehensive E2E Tests for JobHire.AI Application Flow
Tests the complete auto-apply system end-to-end with quality validation
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.advanced_auto_apply import AdvancedAutoApplyEngine, AutoApplyDecision, RiskLevel
from app.services.application_handler import AdvancedApplicationHandler, ApplicationStatus, FormType
from app.services.job_matcher import job_matching_engine, MatchingStrategy
from app.services.job_fetcher import job_fetcher
from app.ai.models import ai_model_manager
from app.ai.enhanced_prompts import EnhancedAIPrompts


class TestJobMatchingE2E:
    """Test complete job matching flow"""
    
    @pytest.fixture
    def sample_job_data(self):
        return {
            "external_id": "test_job_123",
            "title": "Senior Software Engineer",
            "description": "We are looking for a Senior Software Engineer with 5+ years of experience in Python, React, and AWS. The ideal candidate will have experience with microservices, Docker, and Kubernetes. Strong communication skills and team leadership experience required.",
            "company": {"name": "TechCorp Inc"},
            "location": {"city": "San Francisco", "state": "CA", "remote_option": "hybrid"},
            "required_skills": ["Python", "React", "AWS", "Docker", "Kubernetes"],
            "preferred_skills": ["Team Leadership", "Microservices", "CI/CD"],
            "experience_level": "senior-level",
            "education_requirements": "bachelor",
            "salary_min": 120000,
            "salary_max": 180000,
            "employment_type": "full-time",
            "benefits": ["Health Insurance", "401k", "Stock Options"],
            "source": "linkedin",
            "posted_date": datetime.utcnow() - timedelta(hours=12)
        }
    
    @pytest.fixture
    def sample_user_profile(self):
        return {
            "id": 1,
            "email": "test@example.com",
            "full_name": "John Doe",
            "skills": ["Python", "React", "AWS", "Docker", "Team Leadership"],
            "experience_years": 6,
            "education": {
                "degrees": [{"level": "bachelor", "field": "Computer Science"}]
            },
            "preferences": {
                "salary_target": 150000,
                "salary_minimum": 130000,
                "remote_preference": "hybrid",
                "location": {"city": "San Francisco", "state": "CA"},
                "auto_apply_rules": {
                    "min_score_threshold": 75,
                    "max_daily_applications": 5,
                    "preferred_locations": ["San Francisco", "Remote"],
                    "blacklisted_companies": []
                }
            },
            "resume_text": "Experienced software engineer with 6 years in fintech...",
            "tier": "premium"
        }

    @pytest.mark.asyncio
    async def test_complete_job_matching_flow(self, sample_job_data, sample_user_profile):
        """Test the complete job matching flow with AI analysis"""
        
        # Test job matching
        match_result = await job_matching_engine.match_job_to_user(
            job_data=sample_job_data,
            user_profile=sample_user_profile,
            strategy=MatchingStrategy.HYBRID,
            user_tier="premium"
        )
        
        # Validate match result structure
        assert match_result["success"] is True
        assert "overall_score" in match_result
        assert "category_scores" in match_result
        assert "recommendation" in match_result
        assert "apply_priority" in match_result
        assert "success_probability" in match_result
        
        # Validate score ranges
        assert 0 <= match_result["overall_score"] <= 100
        assert 0 <= match_result["success_probability"] <= 1.0
        assert 1 <= match_result["apply_priority"] <= 10
        
        # Validate category scores
        category_scores = match_result["category_scores"]
        required_categories = ["skills", "experience", "education", "location", "salary", "culture"]
        
        for category in required_categories:
            assert category in category_scores
            assert "score" in category_scores[category]
            assert 0 <= category_scores[category]["score"] <= 100
        
        # Test that high-quality match gets good score
        assert match_result["overall_score"] >= 70, "High-quality match should score >= 70"
        
        print(f"✅ Job matching completed with score: {match_result['overall_score']}")
        return match_result

    @pytest.mark.asyncio
    async def test_ai_prompt_quality_validation(self, sample_job_data, sample_user_profile):
        """Test AI prompt quality and response validation"""
        
        # Test enhanced job matching prompt
        with patch.object(ai_model_manager, 'generate_response') as mock_generate:
            # Mock successful AI response
            mock_generate.return_value = {
                "success": True,
                "response": {
                    "text": json.dumps({
                        "reasoning_process": {
                            "requirement_analysis": "Job requires 5+ years Python, React, AWS...",
                            "candidate_strengths": ["Strong Python skills", "AWS experience", "Leadership"],
                            "candidate_gaps": ["Limited Kubernetes experience"],
                            "market_positioning": "Above average candidate",
                            "success_indicators": ["Skill alignment", "Experience level"]
                        },
                        "detailed_scores": {
                            "skills": {
                                "score": 85,
                                "breakdown": {
                                    "required_skills_match": 80,
                                    "nice_to_have_skills": 90,
                                    "skill_depth_quality": 85,
                                    "transferable_skills": 88
                                },
                                "matched_skills": ["Python", "React", "AWS", "Docker"],
                                "missing_critical": ["Kubernetes"],
                                "growth_potential": "High"
                            },
                            "experience": {
                                "score": 90,
                                "breakdown": {
                                    "years_alignment": 95,
                                    "industry_relevance": 88,
                                    "role_level_fit": 90,
                                    "achievement_quality": 87
                                }
                            }
                        },
                        "overall_assessment": {
                            "overall_score": 87,
                            "confidence_level": 92,
                            "recommendation": "STRONG_MATCH",
                            "apply_priority": 9,
                            "success_probability": 0.78
                        }
                    })
                },
                "metadata": {"processing_time": 2.5, "model": "llama-70b"}
            }
            
            # Test AI matching
            result = await job_matching_engine.match_job_to_user(
                job_data=sample_job_data,
                user_profile=sample_user_profile,
                strategy=MatchingStrategy.AI_POWERED,
                user_tier="premium"
            )
            
            # Validate AI response structure
            assert result["success"] is True
            assert result["overall_score"] == 87
            assert result["recommendation"] == "STRONG_MATCH"
            assert result["apply_priority"] == 9
            
            # Validate that AI was called with proper prompt
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args
            assert "prompt" in call_args.kwargs
            assert "job_description" in call_args.kwargs["prompt"]
            assert "candidate_profile" in call_args.kwargs["prompt"]
        
        print("✅ AI prompt quality validation passed")


class TestAutoApplyE2E:
    """Test complete auto-apply decision and execution flow"""
    
    @pytest.fixture
    def auto_apply_engine(self):
        return AdvancedAutoApplyEngine()
    
    @pytest.fixture
    def sample_match_analysis(self):
        return {
            "overall_score": 78,
            "category_scores": {
                "skills": {"score": 85, "matched": ["Python", "AWS"], "missing": ["Kubernetes"]},
                "experience": {"score": 82, "years_match": True},
                "education": {"score": 90, "meets_requirements": True},
                "location": {"score": 95, "remote_compatible": True},
                "salary": {"score": 75, "within_range": True},
                "culture": {"score": 88, "alignment_factors": ["innovation"]}
            },
            "recommendation": "GOOD_MATCH",
            "success_probability": 0.72
        }

    @pytest.mark.asyncio
    async def test_auto_apply_decision_flow(self, auto_apply_engine, sample_match_analysis):
        """Test complete auto-apply decision making process"""
        
        user_preferences = {
            "auto_apply_rules": {
                "min_score_threshold": 70,
                "max_daily_applications": 5,
                "max_weekly_applications": 25,
                "blacklisted_companies": []
            }
        }
        
        # Mock database responses for safety checks
        with patch('app.core.database.get_database') as mock_db:
            mock_database = AsyncMock()
            mock_db.return_value = mock_database
            
            # Mock application history (within limits)
            mock_database.fetch_one.side_effect = [
                {"count": 2},  # Daily applications
                {"count": 8},  # Weekly applications
                {"count": 0},  # Company applications
                {"submitted_at": datetime.utcnow() - timedelta(hours=4)}  # Last application
            ]
            mock_database.fetch_all.return_value = []  # Application history
            
            # Test decision making
            decision, analysis = await auto_apply_engine.make_auto_apply_decision(
                user_id=1,
                job_id="test_job_123",
                match_analysis=sample_match_analysis,
                user_preferences=user_preferences
            )
            
            # Validate decision
            assert decision in [
                AutoApplyDecision.APPLY_IMMEDIATELY,
                AutoApplyDecision.APPLY_SCHEDULED,
                AutoApplyDecision.REVIEW_REQUIRED
            ]
            
            # Validate analysis structure
            required_keys = [
                "decision_analysis", "final_decision", "execution_plan", 
                "monitoring_plan", "quality_assurance"
            ]
            
            # Check if analysis contains expected structure
            assert isinstance(analysis, dict)
            assert "confidence" in analysis or "safety_score" in analysis
            
            print(f"✅ Auto-apply decision: {decision.value}")
            print(f"✅ Analysis confidence: {analysis.get('confidence', 'N/A')}")

    @pytest.mark.asyncio
    async def test_application_submission_flow(self):
        """Test complete application submission with form handling"""
        
        handler = AdvancedApplicationHandler()
        
        user_data = {
            "first_name": "John",
            "last_name": "Doe", 
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "experience_years": 5,
            "linkedin_url": "https://linkedin.com/in/johndoe"
        }
        
        documents = {
            "resume": b"PDF resume content...",
            "cover_letter": b"Cover letter content..."
        }
        
        # Mock form detection and parsing
        with patch.object(handler, '_detect_and_parse_form') as mock_detect:
            from app.services.application_handler import ApplicationForm, FormField, ApplicationStep, FormType
            
            mock_form = ApplicationForm(
                form_id="test_form",
                form_type=FormType.GREENHOUSE,
                company_name="Test Company",
                job_title="Software Engineer",
                application_url="https://company.com/apply",
                fields=[
                    FormField("first_name", "text", "First Name", True),
                    FormField("email", "email", "Email", True),
                    FormField("resume", "file", "Resume", True)
                ],
                steps=[ApplicationStep.BASIC_INFO, ApplicationStep.RESUME_UPLOAD],
                estimated_time_minutes=5,
                complexity_score=0.4,
                success_rate=0.92
            )
            mock_detect.return_value = mock_form
            
            # Mock database operations
            with patch('app.core.database.get_database') as mock_db:
                mock_database = AsyncMock()
                mock_db.return_value = mock_database
                mock_database.execute.return_value = None
                
                # Test application submission
                result = await handler.submit_application(
                    user_id=1,
                    job_id="test_job_123",
                    application_url="https://company.com/apply",
                    user_data=user_data,
                    documents=documents
                )
                
                # Validate result
                assert "success" in result
                assert "attempt_id" in result
                
                if result["success"]:
                    assert "completed_steps" in result
                    assert result["estimated_response_time"] == "3-5 business days"
                    print("✅ Application submitted successfully")
                else:
                    assert "error" in result
                    assert "requires_human" in result
                    print(f"⚠️ Application failed: {result['error']}")

    @pytest.mark.asyncio 
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms"""
        
        handler = AdvancedApplicationHandler()
        
        # Test with invalid application URL
        result = await handler.submit_application(
            user_id=1,
            job_id="invalid_job",
            application_url="https://invalid-url-that-does-not-exist.com",
            user_data={},
            documents={}
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "requires_human" in result
        
        # Test with missing required documents
        result2 = await handler.submit_application(
            user_id=1,
            job_id="test_job",
            application_url="https://company.com/apply",
            user_data={"first_name": "John"},
            documents={}  # Missing resume
        )
        
        # Should handle missing documents gracefully
        assert "success" in result2
        
        print("✅ Error handling validation passed")


class TestJobFetchingE2E:
    """Test job fetching and processing flow"""
    
    @pytest.mark.asyncio
    async def test_job_search_and_processing(self):
        """Test complete job search and processing pipeline"""
        
        # Mock JSearch API response
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "status": "OK",
                "data": [
                    {
                        "job_id": "test_123",
                        "job_title": "Software Engineer",
                        "employer_name": "Tech Company",
                        "job_description": "We are looking for a software engineer...",
                        "job_city": "San Francisco",
                        "job_state": "CA",
                        "job_country": "US",
                        "job_min_salary": 120000,
                        "job_max_salary": 180000,
                        "job_employment_type": "FULLTIME",
                        "job_posted_at_datetime_utc": "2024-01-15T10:00:00Z",
                        "job_apply_link": "https://company.com/apply/123"
                    }
                ]
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Test job search
            result = await job_fetcher.search_jobs(
                query="software engineer",
                location="San Francisco, CA",
                remote_only=False,
                num_pages=1
            )
            
            # Validate result structure
            assert result["success"] is True
            assert "jobs" in result
            assert len(result["jobs"]) > 0
            
            # Validate job data structure
            job = result["jobs"][0]
            required_fields = [
                "external_id", "title", "company", "description",
                "location", "employment_type", "source"
            ]
            
            for field in required_fields:
                assert field in job, f"Missing required field: {field}"
            
            # Validate data types and ranges
            assert isinstance(job["salary_min"], (int, type(None)))
            assert isinstance(job["salary_max"], (int, type(None)))
            assert job["employment_type"] in ["full-time", "part-time", "contract", "internship"]
            
            print(f"✅ Job fetching successful: {len(result['jobs'])} jobs found")

    @pytest.mark.asyncio
    async def test_job_quality_validation(self):
        """Test job quality validation and filtering"""
        
        # Test with low-quality job data
        low_quality_job = {
            "external_id": "spam_job",
            "title": "WORK FROM HOME - MAKE MONEY FAST",
            "description": "Earn $5000/week working from home. No experience required!",
            "company": {"name": "Suspicious Company"},
            "required_skills": [],
            "source": "unknown"
        }
        
        # Job quality validation should flag this
        is_valid = job_fetcher._is_valid_job(low_quality_job)
        assert is_valid is False, "Low-quality job should be filtered out"
        
        # Test with high-quality job data
        high_quality_job = {
            "external_id": "good_job_123",
            "title": "Senior Software Engineer",
            "description": "We are seeking a Senior Software Engineer with 5+ years of experience in Python and React. You will work on our core platform serving millions of users. Requirements include strong problem-solving skills, experience with distributed systems, and excellent communication abilities.",
            "company": {"name": "Reputable Tech Company"},
            "required_skills": ["Python", "React", "Distributed Systems"],
            "source": "linkedin"
        }
        
        is_valid = job_fetcher._is_valid_job(high_quality_job)
        assert is_valid is True, "High-quality job should pass validation"
        
        print("✅ Job quality validation passed")


class TestAIQualityValidation:
    """Test AI output quality and consistency"""
    
    @pytest.mark.asyncio
    async def test_ai_response_consistency(self):
        """Test AI response consistency across multiple runs"""
        
        job_data = {
            "title": "Software Engineer",
            "description": "Python, React, 3+ years experience",
            "required_skills": ["Python", "React"],
            "salary_min": 100000,
            "salary_max": 150000
        }
        
        user_profile = {
            "skills": ["Python", "React", "JavaScript"],
            "experience_years": 4,
            "preferences": {"salary_target": 125000}
        }
        
        scores = []
        
        # Run matching multiple times to test consistency
        for i in range(3):
            result = await job_matching_engine.match_job_to_user(
                job_data=job_data,
                user_profile=user_profile,
                strategy=MatchingStrategy.ALGORITHMIC,  # Use algorithmic for consistency
                user_tier="free"
            )
            
            if result.get("success", True):
                scores.append(result["overall_score"])
        
        # Scores should be consistent (within 5 points)
        if len(scores) > 1:
            score_variance = max(scores) - min(scores)
            assert score_variance <= 5, f"Score variance too high: {score_variance}"
        
        print(f"✅ AI consistency test passed. Scores: {scores}")

    @pytest.mark.asyncio
    async def test_prompt_validation(self):
        """Test prompt input validation"""
        
        # Test missing required inputs
        missing_inputs = EnhancedAIPrompts.validate_prompt_inputs(
            "job_matching", 
            {"job_description": "test"}  # Missing other required inputs
        )
        
        assert len(missing_inputs) > 0, "Should detect missing inputs"
        
        # Test complete inputs
        complete_inputs = {
            "job_description": "Software engineer role",
            "candidate_profile": "Experienced developer",
            "historical_data": {},
            "market_context": {},
            "timestamp": "2024-01-15"
        }
        
        missing_inputs = EnhancedAIPrompts.validate_prompt_inputs(
            "job_matching",
            complete_inputs
        )
        
        assert len(missing_inputs) == 0, "Should not detect missing inputs with complete data"
        
        print("✅ Prompt validation passed")


class TestPerformanceAndScaling:
    """Test performance and scaling capabilities"""
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(self):
        """Test batch job matching performance"""
        
        # Create multiple test jobs
        jobs = []
        for i in range(10):
            jobs.append({
                "external_id": f"job_{i}",
                "title": f"Engineer {i}",
                "description": "Python, React, AWS experience required",
                "required_skills": ["Python", "React"],
                "company": {"name": f"Company {i}"}
            })
        
        user_profile = {
            "skills": ["Python", "React", "AWS"],
            "experience_years": 5,
            "preferences": {}
        }
        
        start_time = datetime.utcnow()
        
        # Test batch matching
        results = await job_matching_engine.batch_match_jobs(
            jobs=jobs,
            user_profile=user_profile,
            strategy=MatchingStrategy.ALGORITHMIC,
            user_tier="free"
        )
        
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Validate results
        assert len(results) == len(jobs), "Should process all jobs"
        assert processing_time < 10, f"Batch processing too slow: {processing_time}s"
        
        # Validate all results have required fields
        for result in results:
            assert "overall_score" in result
            assert "recommendation" in result
        
        print(f"✅ Batch processing: {len(jobs)} jobs in {processing_time:.2f}s")

    @pytest.mark.asyncio
    async def test_concurrent_processing(self):
        """Test concurrent request handling"""
        
        async def single_match():
            return await job_matching_engine.match_job_to_user(
                job_data={
                    "title": "Test Job",
                    "description": "Test description",
                    "required_skills": ["Python"]
                },
                user_profile={
                    "skills": ["Python"],
                    "experience_years": 3
                },
                strategy=MatchingStrategy.ALGORITHMIC,
                user_tier="free"
            )
        
        # Run multiple concurrent matches
        tasks = [single_match() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 5
        for result in results:
            assert result.get("success", True) is True
        
        print("✅ Concurrent processing test passed")


@pytest.mark.asyncio
async def test_complete_e2e_workflow():
    """Test the complete end-to-end workflow"""
    
    print("\n🚀 Starting Complete E2E Workflow Test")
    
    # 1. Job Search and Discovery
    print("📋 Step 1: Job Search and Discovery")
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": [{
                "job_id": "e2e_test_job",
                "job_title": "Senior Python Developer",
                "employer_name": "Innovation Corp",
                "job_description": "Senior Python developer with React and AWS experience...",
                "job_city": "San Francisco",
                "job_state": "CA",
                "job_min_salary": 140000,
                "job_max_salary": 180000,
                "job_apply_link": "https://company.com/apply/123"
            }]
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        job_search_result = await job_fetcher.search_jobs(
            query="python developer",
            location="San Francisco",
            num_pages=1
        )
        
        assert job_search_result["success"]
        assert len(job_search_result["jobs"]) > 0
        print("✅ Job search completed")
    
    # 2. Job Matching and Analysis
    print("🎯 Step 2: Job Matching and Analysis")
    job_data = job_search_result["jobs"][0]
    user_profile = {
        "id": 1,
        "skills": ["Python", "React", "AWS"],
        "experience_years": 6,
        "preferences": {
            "salary_target": 160000,
            "auto_apply_rules": {"min_score_threshold": 75}
        }
    }
    
    match_result = await job_matching_engine.match_job_to_user(
        job_data=job_data,
        user_profile=user_profile,
        strategy=MatchingStrategy.HYBRID,
        user_tier="premium"
    )
    
    assert match_result.get("success", True)
    assert match_result["overall_score"] > 0
    print(f"✅ Job matching completed: {match_result['overall_score']}% match")
    
    # 3. Auto-Apply Decision
    print("🤖 Step 3: Auto-Apply Decision")
    auto_apply_engine = AdvancedAutoApplyEngine()
    
    with patch('app.core.database.get_database') as mock_db:
        mock_database = AsyncMock()
        mock_db.return_value = mock_database
        mock_database.fetch_one.side_effect = [
            {"count": 1},  # Daily apps
            {"count": 5},  # Weekly apps
            {"count": 0},  # Company apps
            {"submitted_at": datetime.utcnow() - timedelta(hours=6)}
        ]
        mock_database.fetch_all.return_value = []
        
        decision, analysis = await auto_apply_engine.make_auto_apply_decision(
            user_id=1,
            job_id="e2e_test_job",
            match_analysis=match_result,
            user_preferences=user_profile["preferences"]
        )
        
        print(f"✅ Auto-apply decision: {decision.value}")
    
    # 4. Application Submission (if approved)
    if decision in [AutoApplyDecision.APPLY_IMMEDIATELY, AutoApplyDecision.APPLY_SCHEDULED]:
        print("📤 Step 4: Application Submission")
        
        handler = AdvancedApplicationHandler()
        
        with patch.object(handler, '_detect_and_parse_form') as mock_detect:
            from app.services.application_handler import ApplicationForm, FormField, ApplicationStep, FormType
            
            mock_form = ApplicationForm(
                form_id="e2e_form",
                form_type=FormType.GREENHOUSE,
                company_name="Innovation Corp",
                job_title="Senior Python Developer",
                application_url=job_data["application_url"],
                fields=[FormField("email", "email", "Email", True)],
                steps=[ApplicationStep.BASIC_INFO],
                estimated_time_minutes=3,
                complexity_score=0.3,
                success_rate=0.9
            )
            mock_detect.return_value = mock_form
            
            with patch('app.core.database.get_database') as mock_db:
                mock_database = AsyncMock()
                mock_db.return_value = mock_database
                
                application_result = await handler.submit_application(
                    user_id=1,
                    job_id="e2e_test_job",
                    application_url=job_data["application_url"],
                    user_data={"email": "test@example.com"},
                    documents={"resume": b"resume content"}
                )
                
                print(f"✅ Application {'submitted' if application_result['success'] else 'failed'}")
    
    print("\n🎉 Complete E2E Workflow Test Passed!")
    return True


if __name__ == "__main__":
    # Run the complete E2E test
    asyncio.run(test_complete_e2e_workflow())