"""Core autonomous execution engine with DAG planning, verification, and budgeting."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .state import ExecutionTrace, StateManager, StepRecord
from .tools import ToolRegistry, ToolResult


class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"


@dataclass
class ExecutionStep:
    step_id: str
    description: str
    tool_name: str
    parameters: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    expected_output_pattern: Optional[str] = None
    custom_verifier: Optional[Callable[[ToolResult], bool]] = None
    status: StepStatus = StepStatus.PENDING
    retries: int = 0
    max_retries: int = 2


@dataclass
class ExecutionPlan:
    goal: str
    steps: List[ExecutionStep]
    max_steps: int = 15
    timeout_seconds: float = 60.0
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def get_step(self, step_id: str) -> Optional[ExecutionStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def validate_dag(self) -> bool:
        """Validates that step dependencies form an acyclic directed graph."""
        step_ids = {s.step_id for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"Step '{s.step_id}' depends on missing step '{dep}'")
        # Check for cycles
        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(node_id: str) -> bool:
            state = visited.get(node_id, 0)
            if state == 1:
                return False  # Cycle detected
            if state == 2:
                return True
            visited[node_id] = 1
            step = self.get_step(node_id)
            if step:
                for dep in step.depends_on:
                    if not dfs(dep):
                        return False
            visited[node_id] = 2
            return True

        for s in self.steps:
            if not dfs(s.step_id):
                return False
        return True


class AgentEngine:
    """Orchestrates plan decomposition, step verification, budget checks, and recovery."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None, state_manager: Optional[StateManager] = None):
        self.tools = tool_registry or ToolRegistry()
        self.state_manager = state_manager or StateManager()

    def build_plan_from_spec(self, goal: str, step_specs: List[Dict[str, Any]], timeout: float = 60.0) -> ExecutionPlan:
        steps: List[ExecutionStep] = []
        for idx, spec in enumerate(step_specs, 1):
            step_id = spec.get("step_id", f"step_{idx}")
            steps.append(
                ExecutionStep(
                    step_id=step_id,
                    description=spec.get("description", f"Execute {spec.get('tool_name')}"),
                    tool_name=spec["tool_name"],
                    parameters=spec.get("parameters", {}),
                    depends_on=spec.get("depends_on", []),
                    expected_output_pattern=spec.get("expected_output_pattern"),
                    max_retries=spec.get("max_retries", 2),
                )
            )
        plan = ExecutionPlan(goal=goal, steps=steps, timeout_seconds=timeout)
        if not plan.validate_dag():
            raise ValueError("Invalid plan: Cyclic dependencies detected in step graph.")
        return plan

    def verify_step(self, step: ExecutionStep, result: ToolResult) -> bool:
        """Verifies step outcome using custom verifier or regex pattern matching."""
        if not result.success:
            return False
        if step.custom_verifier:
            try:
                return bool(step.custom_verifier(result))
            except Exception:
                return False
        if step.expected_output_pattern:
            import re
            return bool(re.search(step.expected_output_pattern, result.output))
        return True

    def execute(self, plan: ExecutionPlan) -> ExecutionTrace:
        """Executes plan with budget gates, checkpointing, and verification loops."""
        start_time = time.time()
        trace = ExecutionTrace(
            run_id=plan.plan_id,
            goal=plan.goal,
            status="RUNNING",
            start_time=start_time,
            metadata={"max_steps": plan.max_steps, "timeout_seconds": plan.timeout_seconds},
        )

        completed_steps: set[str] = set()
        failed_steps: set[str] = set()

        for step in plan.steps:
            # Check budgets
            elapsed = time.time() - start_time
            if elapsed > plan.timeout_seconds:
                step.status = StepStatus.SKIPPED
                trace.status = "TIMEOUT"
                trace.metadata["error"] = f"Execution exceeded timeout budget of {plan.timeout_seconds}s"
                break

            if len(trace.steps) >= plan.max_steps:
                step.status = StepStatus.SKIPPED
                trace.status = "BUDGET_EXCEEDED"
                trace.metadata["error"] = f"Exceeded maximum step budget of {plan.max_steps} steps"
                break

            # Check DAG dependencies
            unmet_deps = [dep for dep in step.depends_on if dep not in completed_steps]
            if unmet_deps:
                step.status = StepStatus.SKIPPED
                failed_steps.add(step.step_id)
                continue

            # Save pre-step checkpoint
            self.state_manager.save_checkpoint(trace, step.step_id)

            # Execution with verification retry loop
            step.status = StepStatus.RUNNING
            success = False
            last_result: Optional[ToolResult] = None

            while step.retries <= step.max_retries:
                step_start = time.time()
                last_result = self.tools.execute(step.tool_name, **step.parameters)
                step_duration = time.time() - step_start

                is_verified = self.verify_step(step, last_result)
                if is_verified:
                    success = True
                    step.status = StepStatus.COMPLETED
                    completed_steps.add(step.step_id)
                    record = StepRecord(
                        step_id=step.step_id,
                        description=step.description,
                        tool_name=step.tool_name,
                        parameters=step.parameters,
                        status="COMPLETED",
                        result=last_result.output,
                        duration_seconds=round(step_duration, 4),
                        verified=True,
                    )
                    trace.steps.append(record)
                    trace.context[step.step_id] = last_result.output
                    break
                else:
                    step.retries += 1
                    if step.retries <= step.max_retries:
                        step.status = StepStatus.RETRYING
                    else:
                        step.status = StepStatus.FAILED
                        failed_steps.add(step.step_id)
                        record = StepRecord(
                            step_id=step.step_id,
                            description=step.description,
                            tool_name=step.tool_name,
                            parameters=step.parameters,
                            status="FAILED",
                            result=last_result.output if last_result else None,
                            error=last_result.error or "Verification check failed",
                            duration_seconds=round(step_duration, 4),
                            verified=False,
                        )
                        trace.steps.append(record)
                        # Rollback context on step failure
                        self.state_manager.rollback_to_checkpoint(trace, step.step_id)

        trace.end_time = time.time()
        if trace.status == "RUNNING":
            trace.status = "SUCCESS" if not failed_steps else "PARTIAL_FAILURE"
        self.state_manager.save_trace(trace)
        return trace
