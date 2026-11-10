# superagent-core

[![CI](https://github.com/Amz34/superagent-core/actions/workflows/ci.yml/badge.svg)](https://github.com/Amz34/superagent-core/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A lightweight, zero-dependency autonomous agent execution engine with structured plan DAG scheduling, tool sandboxing, budget enforcement, post-condition verification, and atomic state checkpointing.

![superagent-core Architecture](assets/superagent-core-overview.jpg)

## Why superagent-core?

Most autonomous agent runtimes rely on complex third-party dependencies, unconstrained recursion, and loose error boundaries. In long-running workflows, uncontrolled tool loops can deplete token budgets or hang on unverified step outcomes.

`superagent-core` provides an embeddable, standard-library-only execution harness designed for predictability and crash-proof operation:

- **Directed Acyclic Graph (DAG) Execution**: Plan goals into ordered, dependency-aware step nodes with automated cycle detection.
- **Strict Budget Controls**: Hard enforcement of maximum step counts, execution timeouts, and retry ceilings.
- **Step-Level Verification**: Every step verifies its output against expected patterns or custom predicate verifiers before marking completion.
- **Atomic Checkpointing & Rollback**: Automatic state snapshotting before each step enables clean rollback upon verification failure.
- **Sandboxed Tool Registry**: Secure built-in file, mathematical, and system introspection tools restricted to a configurable sandbox root.

---

## Architecture

The execution loop follows a strict plan-validate-checkpoint-execute-verify cycle:

```
Goal Specification
       │
       ▼
 [Plan Builder] ──► [DAG Validator (Cycle Detection)]
       │
       ▼
 [Step Scheduler] ◄─── Dependency Resolution
       │
       ├─► [State Checkpoint Saved]
       │
       ├─► [Tool Execution (Sandboxed)]
       │
       ├─► [Post-Condition Verification]
       │         │
       │         ├──► PASS ──► Mark COMPLETED ──► Advance DAG
       │         └──► FAIL ──► Retry / Rollback State
       ▼
 [Final Execution Trace (JSON)]
```

![CI/CD Verification](assets/github-benefits-cicd.jpg)

---

## Quickstart

### Prerequisites

- Python 3.11 or higher (standard library only; no pip dependencies required)

### Installation

Clone the repository and inspect available tools:

```bash
git clone https://github.com/Amz34/superagent-core.git
cd superagent-core
python3 -m superagent_core.cli list-tools
```

### Running an Autonomous Plan

Define a plan specification file (e.g., `sample_plan.json`):

```json
[
  {
    "step_id": "probe_host",
    "description": "Probe host system architecture and Python runtime",
    "tool_name": "system_probe",
    "parameters": {},
    "expected_output_pattern": "python_version"
  },
  {
    "step_id": "compute_metric",
    "description": "Perform verification arithmetic",
    "tool_name": "calc",
    "parameters": {"expression": "1024 * 16"},
    "depends_on": ["probe_host"],
    "expected_output_pattern": "^16384$"
  },
  {
    "step_id": "persist_summary",
    "description": "Write execution artifact to sandbox",
    "tool_name": "file_write",
    "parameters": {
      "path": "summary.txt",
      "content": "Host probe and verification metrics completed successfully."
    },
    "depends_on": ["compute_metric"],
    "expected_output_pattern": "Wrote \\d+ bytes"
  }
]
```

Execute the plan via the command line:

```bash
python3 -m superagent_core.cli run --goal "Host audit and metric computation" --plan sample_plan.json
```

Output:

```text
┌──────────────────────────────────────────────┐
│             SUPERAGENT-CORE v1.0             │
│  Autonomous, Budget-Enforced Execution Loop  │
└──────────────────────────────────────────────┘
[*] Goal: Host audit and metric computation
[*] Loading plan with 3 step(s)...
[*] Starting execution loop...

[+] Execution finished with status: SUCCESS
[+] Total steps: 3
[+] Total time: 0.02s
  1. Probe host system architecture: COMPLETED (0.0012s)
  2. Perform verification arithmetic: COMPLETED (0.0008s)
  3. Write execution artifact to sandbox: COMPLETED (0.0014s)

[+] Trace saved to: .superagent/traces/a1b2c3d4e5f6.json
```

---

## Programmatic Usage

Integrate `superagent-core` directly into Python applications:

```python
from superagent_core import AgentEngine, ToolRegistry, StateManager

# Initialize registry and state management
registry = ToolRegistry(sandbox_dir="./workspace")
state = StateManager(workspace_dir="./.superagent")
engine = AgentEngine(registry, state)

# Register custom tools seamlessly
@registry.register("custom_greeter", "Returns a formatted greeting message.")
def custom_greeter(name: str) -> str:
    return f"Hello, {name}!"

# Build and execute structured execution plans
specs = [
    {
        "step_id": "greet_user",
        "description": "Generate greeting output",
        "tool_name": "custom_greeter",
        "parameters": {"name": "Ops Engineer"},
        "expected_output_pattern": r"Hello, Ops Engineer!"
    }
]

plan = engine.build_plan_from_spec(goal="Automated user greeting", step_specs=specs)
trace = engine.execute(plan)

print(f"Status: {trace.status}, Steps completed: {len(trace.steps)}")
```

---

## Verification & Testing

Run the full automated test suite using standard library `unittest`:

```bash
make test
```

Or run via Python directly:

```bash
python3 -m unittest discover -s tests -v
```

---

## Limitations

- **Single-Host Execution**: Designed for local process orchestration; distributed multi-host scheduling requires external network transport.
- **Python Standard Library Scope**: Out-of-the-box tools intentionally avoid third-party drivers or native C bindings.
- **Sandbox Boundary**: File tools enforce directory isolation via path resolution; root access or arbitrary subprocess spawning is excluded by design.

---

## License

MIT License. Copyright (c) 2026 Amz34. See [LICENSE](LICENSE) for details.
