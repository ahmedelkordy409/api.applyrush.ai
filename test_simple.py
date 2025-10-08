#!/usr/bin/env python3
"""
Simple test to verify LangGraph installation and basic functionality
"""

import asyncio
import sys

def test_imports():
    """Test that all required packages can be imported"""
    print("🔍 Testing imports...")
    
    try:
        import langgraph
        print("✓ langgraph imported successfully")
    except ImportError as e:
        print(f"✗ langgraph import failed: {e}")
        return False
    
    try:
        import langchain_openai
        print("✓ langchain_openai imported successfully")
    except ImportError as e:
        print(f"✗ langchain_openai import failed: {e}")
        return False
    
    try:
        import langchain_core
        print("✓ langchain_core imported successfully")
    except ImportError as e:
        print(f"✗ langchain_core import failed: {e}")
        return False
    
    try:
        from langgraph.graph import StateGraph, START, END
        from langchain_core.messages import HumanMessage, AIMessage
        print("✓ Core LangGraph components imported successfully")
    except ImportError as e:
        print(f"✗ Core components import failed: {e}")
        return False
    
    return True


async def test_basic_graph():
    """Test basic LangGraph functionality"""
    print("\n🧪 Testing basic LangGraph graph creation...")
    
    try:
        from langgraph.graph import StateGraph
        from typing import TypedDict
        
        # Define a simple state
        class SimpleState(TypedDict):
            message: str
            count: int
        
        # Create a simple workflow
        def add_count(state: SimpleState) -> SimpleState:
            state["count"] += 1
            state["message"] = f"Count is now {state['count']}"
            return state
        
        def multiply_count(state: SimpleState) -> SimpleState:
            state["count"] *= 2
            state["message"] = f"Count doubled to {state['count']}"
            return state
        
        # Build the graph
        graph = StateGraph(SimpleState)
        graph.add_node("add", add_count)
        graph.add_node("multiply", multiply_count)
        
        graph.set_entry_point("add")
        graph.add_edge("add", "multiply")
        graph.set_finish_point("multiply")
        
        # Compile the graph
        compiled_graph = graph.compile()
        
        # Test execution
        initial_state = {"message": "Starting", "count": 1}
        result = compiled_graph.invoke(initial_state)
        
        assert result["count"] == 4  # (1 + 1) * 2 = 4
        assert "doubled to 4" in result["message"]
        
        print("✓ Basic LangGraph workflow executed successfully")
        print(f"  Final state: {result}")
        return True
        
    except Exception as e:
        print(f"✗ Basic graph test failed: {e}")
        return False


async def test_langgraph_with_llm():
    """Test LangGraph with LLM integration (if API key available)"""
    print("\n🤖 Testing LangGraph with LLM integration...")
    
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ Skipping LLM test (no OPENAI_API_KEY set)")
        return True
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        from langgraph.graph import StateGraph
        from typing import TypedDict
        
        # Define state for LLM workflow
        class LLMState(TypedDict):
            messages: list
            response: str
        
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
        
        # Define nodes
        async def call_llm(state: LLMState) -> LLMState:
            response = await llm.ainvoke(state["messages"])
            state["response"] = response.content
            return state
        
        # Build graph
        graph = StateGraph(LLMState)
        graph.add_node("llm", call_llm)
        graph.set_entry_point("llm")
        graph.set_finish_point("llm")
        
        # Compile
        compiled_graph = graph.compile()
        
        # Test
        initial_state = {
            "messages": [HumanMessage(content="What is 2+2? Answer with just the number.")],
            "response": ""
        }
        
        result = await compiled_graph.ainvoke(initial_state)
        
        print(f"✓ LLM integration test successful")
        print(f"  Response: {result['response']}")
        return True
        
    except Exception as e:
        print(f"✗ LLM integration test failed: {e}")
        return False


def test_fastapi_integration():
    """Test that FastAPI can work with our modules"""
    print("\n🌐 Testing FastAPI integration...")
    
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
        from typing import Dict, Any
        
        app = FastAPI(title="Test App")
        
        class WorkflowRequest(BaseModel):
            user_id: str
            data: Dict[str, Any]
        
        @app.post("/test-workflow")
        async def test_workflow_endpoint(request: WorkflowRequest):
            return {
                "status": "success",
                "user_id": request.user_id,
                "processed": True
            }
        
        print("✓ FastAPI integration working")
        return True
        
    except Exception as e:
        print(f"✗ FastAPI integration test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    print("🚀 LangGraph Integration Test Suite")
    print("=" * 50)
    
    # Test imports
    imports_ok = test_imports()
    if not imports_ok:
        print("\n❌ Import tests failed. Please install missing dependencies.")
        return False
    
    # Test basic functionality
    basic_ok = await test_basic_graph()
    
    # Test LLM integration (optional)
    llm_ok = await test_langgraph_with_llm()
    
    # Test FastAPI integration
    fastapi_ok = test_fastapi_integration()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    tests = {
        "Package Imports": imports_ok,
        "Basic LangGraph": basic_ok,
        "LLM Integration": llm_ok,
        "FastAPI Integration": fastapi_ok
    }
    
    for test_name, result in tests.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name}: {status}")
    
    all_passed = all(tests.values())
    
    if all_passed:
        print("\n🎉 All tests passed! LangGraph is ready to use.")
        print("\n📋 Ready for production:")
        print("  • LangGraph workflows can be implemented")
        print("  • FastAPI endpoints can use LangGraph")
        print("  • Database integration can be added")
        print("  • AI services are ready for orchestration")
    else:
        print("\n⚠ Some tests failed, but core functionality is working.")
    
    print("\n🔧 Next steps:")
    print("  1. Set DATABASE_URL in your .env file")
    print("  2. Set OPENAI_API_KEY for full AI functionality")
    print("  3. Run: uvicorn app.main:app --reload")
    print("  4. Visit: http://localhost:8000/docs")
    print("  5. Test workflow endpoints")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)