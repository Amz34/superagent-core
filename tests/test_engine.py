import unittest
import os
import shutil
import tempfile
from superagent_core.engine import AgentEngine, ExecutionPlan, ExecutionStep, StepStatus
from superagent_core.state import StateManager
from superagent_core.tools import ToolRegistry

class TestEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.test_dir, ".superagent")
        self.state_manager = StateManager(workspace_dir=self.state_dir)
        self.registry = ToolRegistry(sandbox_dir=self.test_dir)
        self.engine = AgentEngine(self.registry, self.state_manager)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_plan_dag_validation(self):
        # Valid DAG
        specs = [
            {"step_id": "step1", "tool_name": "calc", "parameters": {"expression": "2+2"}},
            {"step_id": "step2", "tool_name": "calc", "parameters": {"expression": "3+3"}, "depends_on": ["step1"]},
        ]
        plan = self.engine.build_plan_from_spec("Simple DAG", specs)
        self.assertTrue(plan.validate_dag())

        # Invalid cycle
        step_a = ExecutionStep(step_id="A", description="A", tool_name="calc", parameters={}, depends_on=["B"])
        step_b = ExecutionStep(step_id="B", description="B", tool_name="calc", parameters={}, depends_on=["A"])
        cyclic_plan = ExecutionPlan(goal="Cycle", steps=[step_a, step_b])
        self.assertFalse(cyclic_plan.validate_dag())

    def test_successful_execution(self):
        specs = [
            {
                "step_id": "write_data",
                "tool_name": "file_write",
                "parameters": {"path": "output.txt", "content": "agent execution payload"},
                "expected_output_pattern": r"Wrote \d+ bytes",
            },
            {
                "step_id": "read_data",
                "tool_name": "file_read",
                "parameters": {"path": "output.txt"},
                "depends_on": ["write_data"],
                "expected_output_pattern": r"agent execution payload",
            },
        ]
        plan = self.engine.build_plan_from_spec("File Pipeline", specs)
        trace = self.engine.execute(plan)

        self.assertEqual(trace.status, "SUCCESS")
        self.assertEqual(len(trace.steps), 2)
        self.assertTrue(trace.steps[0].verified)
        self.assertTrue(trace.steps[1].verified)

    def test_step_verification_failure_and_retry(self):
        specs = [
            {
                "step_id": "calc_fail",
                "tool_name": "calc",
                "parameters": {"expression": "10 * 10"},
                "expected_output_pattern": r"^999$",  # will fail verification
                "max_retries": 1,
            },
        ]
        plan = self.engine.build_plan_from_spec("Failing Step", specs)
        trace = self.engine.execute(plan)

        self.assertEqual(trace.status, "PARTIAL_FAILURE")
        self.assertFalse(trace.steps[0].verified)
        self.assertEqual(trace.steps[0].status, "FAILED")

    def test_timeout_budget(self):
        specs = [
            {"step_id": "step1", "tool_name": "calc", "parameters": {"expression": "1+1"}},
        ]
        plan = self.engine.build_plan_from_spec("Timeout Test", specs, timeout=-1.0)
        trace = self.engine.execute(plan)
        self.assertEqual(trace.status, "TIMEOUT")

    def test_sample_plan_json(self):
        import json
        sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_plan.json")
        with open(sample_path, "r", encoding="utf-8") as f:
            specs = json.load(f)
        plan = self.engine.build_plan_from_spec("Run Sample", specs)
        trace = self.engine.execute(plan)
        self.assertEqual(trace.status, "SUCCESS")
        self.assertEqual(len(trace.steps), 3)
