"""superagent-core: A lightweight, zero-dependency autonomous agent execution engine.

Provides structured goal decomposition, execution DAG scheduling, tool sandboxing,
budget-enforced execution loops, post-condition verification, and state checkpointing.
"""

from .engine import AgentEngine, ExecutionPlan, ExecutionStep, StepStatus
from .state import StateManager, StepRecord, ExecutionTrace
from .tools import ToolRegistry, ToolResult

__version__ = "1.0.0"
__all__ = [
    "AgentEngine",
    "ExecutionPlan",
    "ExecutionStep",
    "StepStatus",
    "StateManager",
    "StepRecord",
    "ExecutionTrace",
    "ToolRegistry",
    "ToolResult",
]
