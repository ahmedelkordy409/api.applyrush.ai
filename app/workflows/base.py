"""
Base LangGraph workflow components for JobHire.AI
Provides common workflow utilities and state management
"""

from typing import Dict, Any, List, Optional, TypedDict, Literal
from enum import Enum
import asyncio
from datetime import datetime
import structlog
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver

logger = structlog.get_logger()


class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowNode(str, Enum):
    """Common workflow nodes"""
    START_NODE = "start"
    ANALYZE_NODE = "analyze"
    DECISION_NODE = "decision"
    ACTION_NODE = "action"
    VALIDATION_NODE = "validation"
    END_NODE = "end"


class BaseWorkflowState(TypedDict, total=False):
    """Base state for all JobHire.AI workflows"""
    # Core identifiers
    user_id: str
    job_id: Optional[str]
    workflow_id: str
    
    # Execution metadata
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime]
    current_node: Optional[str]
    
    # User data
    user_profile: Dict[str, Any]
    user_preferences: Dict[str, Any]
    user_tier: str  # free, premium, enterprise
    
    # Job data
    job_data: Optional[Dict[str, Any]]
    company_data: Optional[Dict[str, Any]]
    
    # Processing results
    analysis_results: Dict[str, Any]
    decisions: Dict[str, Any]
    actions_taken: List[Dict[str, Any]]
    
    # AI interaction
    messages: List[BaseMessage]
    ai_responses: Dict[str, Any]
    
    # Error handling
    errors: List[Dict[str, Any]]
    warnings: List[str]
    
    # Workflow configuration
    config: Dict[str, Any]
    
    # Output data
    results: Dict[str, Any]


class BaseWorkflowConfig(BaseModel):
    """Base configuration for workflows"""
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout_seconds: int = Field(default=300, description="Workflow timeout")
    enable_logging: bool = Field(default=True, description="Enable detailed logging")
    user_tier: str = Field(default="free", description="User subscription tier")
    ai_model_preference: Literal["openai", "replicate"] = Field(default="openai")
    parallel_execution: bool = Field(default=True, description="Enable parallel processing")


class BaseWorkflow:
    """Base class for all JobHire.AI LangGraph workflows"""
    
    def __init__(self, config: BaseWorkflowConfig = None):
        self.config = config or BaseWorkflowConfig()
        self.graph: Optional[CompiledStateGraph] = None
        self.checkpointer = MemorySaver()
        self.logger = logger.bind(workflow=self.__class__.__name__)
        
    async def build_graph(self) -> CompiledStateGraph:
        """Build the LangGraph workflow graph"""
        raise NotImplementedError("Subclasses must implement build_graph")
    
    async def initialize_state(self, **kwargs) -> BaseWorkflowState:
        """Initialize workflow state"""
        workflow_id = kwargs.get("workflow_id", f"{self.__class__.__name__}_{datetime.utcnow().isoformat()}")
        
        state: BaseWorkflowState = {
            "workflow_id": workflow_id,
            "user_id": kwargs.get("user_id", ""),
            "job_id": kwargs.get("job_id"),
            "status": WorkflowStatus.PENDING,
            "started_at": datetime.utcnow(),
            "current_node": None,
            "user_profile": kwargs.get("user_profile", {}),
            "user_preferences": kwargs.get("user_preferences", {}),
            "user_tier": kwargs.get("user_tier", "free"),
            "job_data": kwargs.get("job_data"),
            "company_data": kwargs.get("company_data"),
            "analysis_results": {},
            "decisions": {},
            "actions_taken": [],
            "messages": [],
            "ai_responses": {},
            "errors": [],
            "warnings": [],
            "config": self.config.model_dump(),
            "results": {}
        }
        
        return state
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the workflow with database integration"""
        try:
            # Initialize state
            initial_state = await self.initialize_state(**kwargs)
            
            # Build graph if not already built
            if self.graph is None:
                self.graph = await self.build_graph()
            
            # Execute workflow
            self.logger.info("Starting workflow execution", 
                           workflow_id=initial_state["workflow_id"],
                           user_id=initial_state["user_id"])
            
            config = {"configurable": {"thread_id": initial_state["workflow_id"]}}
            
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            # Update completion status
            final_state["status"] = WorkflowStatus.COMPLETED
            final_state["completed_at"] = datetime.utcnow()
            
            self.logger.info("Workflow execution completed",
                           workflow_id=final_state["workflow_id"],
                           status=final_state["status"])
            
            return final_state
            
        except Exception as e:
            self.logger.error("Workflow execution failed",
                            workflow_id=kwargs.get("workflow_id", "unknown"),
                            error=str(e))
            
            # Return error state
            error_state = await self.initialize_state(**kwargs)
            error_state.update({
                "status": WorkflowStatus.FAILED,
                "completed_at": datetime.utcnow(),
                "errors": [{"error": str(e), "timestamp": datetime.utcnow().isoformat()}]
            })
            
            return error_state
    
    async def add_error(self, state: BaseWorkflowState, error: str, node: str = None) -> BaseWorkflowState:
        """Add error to workflow state"""
        error_entry = {
            "error": error,
            "node": node or state.get("current_node", "unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if "errors" not in state:
            state["errors"] = []
        
        state["errors"].append(error_entry)
        
        self.logger.error("Workflow error", 
                        workflow_id=state["workflow_id"],
                        node=node,
                        error=error)
        
        return state
    
    async def add_warning(self, state: BaseWorkflowState, warning: str) -> BaseWorkflowState:
        """Add warning to workflow state"""
        if "warnings" not in state:
            state["warnings"] = []
        
        state["warnings"].append(warning)
        
        self.logger.warning("Workflow warning",
                          workflow_id=state["workflow_id"],
                          warning=warning)
        
        return state
    
    async def update_progress(self, state: BaseWorkflowState, node: str, progress_data: Dict[str, Any] = None) -> BaseWorkflowState:
        """Update workflow progress"""
        state["current_node"] = node
        state["status"] = WorkflowStatus.RUNNING
        
        if progress_data:
            if "progress" not in state:
                state["progress"] = {}
            state["progress"][node] = progress_data
        
        self.logger.info("Workflow progress update",
                       workflow_id=state["workflow_id"],
                       current_node=node)
        
        return state


class ConditionalEdge:
    """Helper class for creating conditional workflow edges"""
    
    def __init__(self, condition_func, mapping: Dict[str, str]):
        self.condition_func = condition_func
        self.mapping = mapping
    
    async def evaluate(self, state: BaseWorkflowState) -> str:
        """Evaluate condition and return next node"""
        try:
            condition_result = await self.condition_func(state)
            return self.mapping.get(condition_result, END)
        except Exception as e:
            logger.error("Conditional edge evaluation failed", error=str(e))
            return END


class WorkflowMetrics:
    """Collect workflow performance metrics"""
    
    @staticmethod
    def calculate_duration(state: BaseWorkflowState) -> float:
        """Calculate workflow duration in seconds"""
        if state.get("completed_at") and state.get("started_at"):
            return (state["completed_at"] - state["started_at"]).total_seconds()
        return 0.0
    
    @staticmethod
    def get_node_count(state: BaseWorkflowState) -> int:
        """Get number of nodes processed"""
        return len(state.get("progress", {}))
    
    @staticmethod
    def get_error_count(state: BaseWorkflowState) -> int:
        """Get number of errors encountered"""
        return len(state.get("errors", []))
    
    @staticmethod
    def calculate_success_rate(state: BaseWorkflowState) -> float:
        """Calculate workflow success rate"""
        if state.get("status") == WorkflowStatus.COMPLETED:
            return 1.0 if state.get("error_count", 0) == 0 else 0.8
        return 0.0


# Common workflow utility functions
async def should_retry(state: BaseWorkflowState, max_retries: int = 3) -> bool:
    """Determine if workflow should retry after failure"""
    retry_count = state.get("retry_count", 0)
    return retry_count < max_retries


async def is_premium_user(state: BaseWorkflowState) -> bool:
    """Check if user is premium tier"""
    return state.get("user_tier", "free") in ["premium", "enterprise"]


async def get_ai_model_tier(state: BaseWorkflowState) -> str:
    """Get appropriate AI model tier based on user tier and task complexity"""
    user_tier = state.get("user_tier", "free")
    task_complexity = state.get("config", {}).get("task_complexity", "medium")
    
    if user_tier == "enterprise":
        return "premium"
    elif user_tier == "premium" and task_complexity == "high":
        return "premium" 
    elif task_complexity == "low":
        return "cheap"
    else:
        return "balanced"


# Export public components
__all__ = [
    "BaseWorkflow",
    "BaseWorkflowState", 
    "BaseWorkflowConfig",
    "WorkflowStatus",
    "WorkflowNode",
    "ConditionalEdge",
    "WorkflowMetrics",
    "should_retry",
    "is_premium_user", 
    "get_ai_model_tier"
]