#!/usr/bin/env python3
"""
Test script for LangGraph integration
Tests basic functionality without full database setup
"""

import asyncio
import json
import os
from datetime import datetime

# Mock the database modules to avoid import errors
import sys
import types

def mock_database_modules():
    """Mock database modules for testing"""
    # Mock app.core.database
    database_mock = types.ModuleType("database")
    database_mock.database = types.SimpleNamespace()
    database_mock.database.connect = lambda: None
    database_mock.database.disconnect = lambda: None
    database_mock.database.fetch_one = lambda q, p=None: None
    database_mock.database.fetch_all = lambda q, p=None: []
    database_mock.database.execute = lambda q, p=None: None
    
    database_mock.Base = types.SimpleNamespace()
    database_mock.Base.metadata = types.SimpleNamespace()
    database_mock.Base.metadata.create_all = lambda bind=None: None
    
    sys.modules['app.core.database'] = database_mock
    
    # Mock app.core.config
    config_mock = types.ModuleType("config")
    config_mock.settings = types.SimpleNamespace()
    config_mock.settings.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "test-key")
    config_mock.settings.REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "test-token")
    config_mock.settings.DATABASE_URL = "postgresql://test:test@localhost/test"
    
    sys.modules['app.core.config'] = config_mock
    
    # Mock app.core.monitoring
    monitoring_mock = types.ModuleType("monitoring")
    monitoring_mock.performance_monitor = types.SimpleNamespace()
    monitoring_mock.performance_monitor.record_ai_processing_time = lambda **kwargs: None
    monitoring_mock.performance_monitor.record_job_matching_accuracy = lambda **kwargs: None
    monitoring_mock.performance_monitor.record_application_submitted = lambda **kwargs: None
    monitoring_mock.performance_monitor.record_api_call = lambda name: None
    monitoring_mock.performance_monitor.record_workflow_completion = lambda **kwargs: None
    
    sys.modules['app.core.monitoring'] = monitoring_mock

# Apply mocks before importing our modules
mock_database_modules()

# Now import our modules
try:
    from app.workflows.base import BaseWorkflow, BaseWorkflowState, WorkflowStatus
    from app.ai.langgraph_service import LangGraphAIService
    print("✓ Successfully imported LangGraph modules")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)


async def test_workflow_state():
    """Test basic workflow state management"""
    print("\n=== Testing Workflow State ===")
    
    try:
        # Create a mock workflow
        class TestWorkflow(BaseWorkflow):
            async def build_graph(self):
                return None  # Mock graph
        
        workflow = TestWorkflow()
        
        # Test state initialization
        state = await workflow.initialize_state(
            user_id="test_user_123",
            job_id="test_job_456",
            user_profile={"name": "Test User", "skills": ["Python", "AI"]},
            user_tier="free"
        )
        
        assert state["user_id"] == "test_user_123"
        assert state["job_id"] == "test_job_456"
        assert state["status"] == WorkflowStatus.PENDING
        assert "workflow_id" in state
        
        print("✓ Workflow state initialization working")
        
        # Test error handling
        state = await workflow.add_error(state, "Test error", "test_node")
        assert len(state["errors"]) == 1
        assert state["errors"][0]["error"] == "Test error"
        
        print("✓ Error handling working")
        
        # Test warning handling  
        state = await workflow.add_warning(state, "Test warning")
        assert len(state["warnings"]) == 1
        assert state["warnings"][0] == "Test warning"
        
        print("✓ Warning handling working")
        
        return True
        
    except Exception as e:
        print(f"✗ Workflow state test failed: {e}")
        return False


async def test_langgraph_service():
    """Test LangGraph AI service"""
    print("\n=== Testing LangGraph AI Service ===")
    
    try:
        service = LangGraphAIService()
        print("✓ LangGraph AI service initialized")
        
        # Test simple AI response (mock)
        if os.getenv("OPENAI_API_KEY"):
            response = await service.get_simple_ai_response(
                prompt="What is 2+2?",
                model="fast"
            )
            print(f"✓ Simple AI response: {response.get('success', False)}")
        else:
            print("⚠ Skipping AI response test (no API key)")
        
        # Test job match analysis (mock data)
        mock_job_data = {
            "external_id": "test_job_123",
            "title": "Software Engineer",
            "description": "Python developer needed",
            "required_skills": ["Python", "FastAPI"],
            "company": {"name": "Test Company"}
        }
        
        mock_user_profile = {
            "id": "test_user_123",
            "skills": ["Python", "JavaScript"],
            "experience_years": 3,
            "resume_text": "Experienced Python developer"
        }
        
        # This will use the mocked job matching engine
        match_result = await service.analyze_job_match_only(
            job_data=mock_job_data,
            user_profile=mock_user_profile
        )
        
        print(f"✓ Job match analysis completed: {match_result.get('success', False)}")
        
        return True
        
    except Exception as e:
        print(f"✗ LangGraph service test failed: {e}")
        return False


async def test_json_serialization():
    """Test JSON serialization of workflow states"""
    print("\n=== Testing JSON Serialization ===")
    
    try:
        # Create test state with various data types
        test_state = {
            "workflow_id": "test_123",
            "user_id": "user_456", 
            "status": WorkflowStatus.COMPLETED,
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "match_score": 85.5,
            "analysis_results": {
                "job_match": {
                    "overall_score": 85.5,
                    "category_scores": {
                        "skills": {"score": 90.0, "matched": ["Python"]},
                        "experience": {"score": 80.0, "years": 3}
                    }
                }
            },
            "decisions": {
                "application": {
                    "decision": "apply_immediately",
                    "reasoning": "High match score"
                }
            },
            "actions_taken": [
                {
                    "action": "submit_application",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True
                }
            ],
            "errors": [],
            "warnings": ["Test warning"]
        }
        
        # Test conversion to JSON-safe format
        from app.workflows.database_integration import WorkflowDatabaseManager
        
        db_manager = WorkflowDatabaseManager()
        sanitized = db_manager._sanitize_json(test_state)
        
        # Try to serialize to JSON
        json_str = json.dumps(sanitized, indent=2)
        
        # Try to deserialize back
        parsed = json.loads(json_str)
        
        assert parsed["workflow_id"] == "test_123"
        assert parsed["match_score"] == 85.5
        
        print("✓ JSON serialization working")
        return True
        
    except Exception as e:
        print(f"✗ JSON serialization test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    print("🚀 Starting LangGraph Integration Tests")
    print("=" * 50)
    
    tests = [
        test_workflow_state,
        test_langgraph_service, 
        test_json_serialization
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All tests passed! LangGraph integration is working.")
    else:
        print("❌ Some tests failed. Check the output above.")
    
    print("\n📋 Next Steps:")
    print("1. Set up your database connection in .env")
    print("2. Run database migrations")
    print("3. Add OpenAI API key for full functionality")
    print("4. Start the FastAPI server: uvicorn app.main:app --reload")
    print("5. Test the API endpoints at http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(run_all_tests())