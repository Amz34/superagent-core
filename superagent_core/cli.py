"""CLI interface for superagent-core."""

from __future__ import annotations

import argparse
import json
import sys
import time

from .engine import AgentEngine
from .state import StateManager
from .tools import ToolRegistry


def print_banner():
    print("┌──────────────────────────────────────────────┐")
    print("│             SUPERAGENT-CORE v1.0             │")
    print("│  Autonomous, Budget-Enforced Execution Loop  │")
    print("└──────────────────────────────────────────────┘")


def main():
    parser = argparse.ArgumentParser(description="superagent-core CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Execute an autonomous plan")
    run_parser.add_argument("--goal", required=True, help="The goal of the execution")
    run_parser.add_argument("--plan", required=True, help="Path to JSON file containing step specifications")
    run_parser.add_argument("--timeout", type=float, default=60.0, help="Plan execution timeout in seconds")

    # List tools
    subparsers.add_parser("list-tools", help="List all available tools")

    # History
    subparsers.add_parser("history", help="List execution history run IDs")

    # Inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a specific execution trace")
    inspect_parser.add_argument("run_id", help="The run ID to inspect")

    # Clean
    subparsers.add_parser("clean", help="Clear workspace checkpoints and traces")

    args = parser.parse_args()

    state_manager = StateManager()
    registry = ToolRegistry()
    engine = AgentEngine(registry, state_manager)

    if args.command == "run":
        try:
            with open(args.plan, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception as e:
            print(f"Error loading plan: {e}")
            sys.exit(1)

        print_banner()
        print(f"[*] Goal: {args.goal}")
        print(f"[*] Loading plan with {len(specs)} step(s)...")

        try:
            plan = engine.build_plan_from_spec(args.goal, specs, timeout=args.timeout)
            print(f"[*] Plan ID: {plan.plan_id}")
            print("[*] Starting execution loop...")

            trace = engine.execute(plan)

            print(f"\n[+] Execution finished with status: {trace.status}")
            print(f"[+] Total steps: {len(trace.steps)}")
            print(f"[+] Total time: {round(trace.end_time - trace.start_time, 2)}s")

            for i, step in enumerate(trace.steps, 1):
                color = "\033[92m" if step.status == "COMPLETED" else "\033[91m"
                reset = "\033[0m"
                print(f"  {i}. {step.description}: {color}{step.status}{reset} ({step.duration_seconds}s)")

            print(f"\n[+] Trace saved to: {state_manager.workspace_dir}/traces/{trace.run_id}.json")

        except Exception as e:
            print(f"Fatal execution error: {e}")
            sys.exit(1)

    elif args.command == "list-tools":
        print_banner()
        print("[*] Registered Tools:")
        tools = registry.list_tools()
        for name, desc in tools.items():
            print(f" - {name:15}: {desc}")

    elif args.command == "history":
        runs = state_manager.list_traces()
        if not runs:
            print("No execution history found.")
        else:
            print("[*] Execution History (Run IDs):")
            for run_id in runs:
                print(f" - {run_id}")

    elif args.command == "inspect":
        trace_data = state_manager.load_trace(args.run_id)
        if not trace_data:
            print(f"Trace not found: {args.run_id}")
            sys.exit(1)
        print(json.dumps(trace_data, indent=2))

    elif args.command == "clean":
        import shutil
        if os.path.exists(state_manager.workspace_dir):
            shutil.rmtree(state_manager.workspace_dir)
            print(f"[*] Workspace {state_manager.workspace_dir} cleared.")
        else:
            print("Workspace does not exist.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
