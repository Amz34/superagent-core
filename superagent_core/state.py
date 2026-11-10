"""State management, execution tracing, and checkpointing."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepRecord:
    step_id: str
    description: str
    tool_name: str
    parameters: Dict[str, Any]
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    verified: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionTrace:
    run_id: str
    goal: str
    status: str
    start_time: float
    end_time: Optional[float] = None
    steps: List[StepRecord] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StateManager:
    """Handles persistence of execution traces and state checkpoints."""

    def __init__(self, workspace_dir: str = ".superagent"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.checkpoints_dir = os.path.join(self.workspace_dir, "checkpoints")
        self.traces_dir = os.path.join(self.workspace_dir, "traces")
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        os.makedirs(self.checkpoints_dir, exist_ok=True)
        os.makedirs(self.traces_dir, exist_ok=True)

    def save_checkpoint(self, trace: ExecutionTrace, step_id: str) -> str:
        """Persists an intermediate execution snapshot before step execution."""
        snapshot = {
            "run_id": trace.run_id,
            "step_id": step_id,
            "timestamp": time.time(),
            "context": trace.context.copy(),
            "completed_steps": len(trace.steps),
        }
        trace.checkpoints.append(snapshot)
        filename = f"{trace.run_id}_{step_id}.json"
        path = os.path.join(self.checkpoints_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        return path

    def rollback_to_checkpoint(self, trace: ExecutionTrace, step_id: str) -> bool:
        """Rolls back the context state to the snapshot matching step_id."""
        for cp in reversed(trace.checkpoints):
            if cp.get("step_id") == step_id:
                trace.context = cp.get("context", {}).copy()
                return True
        return False

    def save_trace(self, trace: ExecutionTrace) -> str:
        """Saves the final execution trace to disk."""
        filename = f"{trace.run_id}.json"
        path = os.path.join(self.traces_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trace.to_dict(), f, indent=2)
        return path

    def load_trace(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Loads an execution trace by run_id."""
        path = os.path.join(self.traces_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_traces(self) -> List[str]:
        """Lists available saved trace run IDs."""
        if not os.path.exists(self.traces_dir):
            return []
        traces = []
        for name in os.listdir(self.traces_dir):
            if name.endswith(".json"):
                traces.append(os.path.splitext(name)[0])
        return sorted(traces)
