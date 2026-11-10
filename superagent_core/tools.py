"""Tool registry and sandboxed execution primitives."""

from __future__ import annotations

import ast
import operator
import os
import platform
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafeMathEvaluator(ast.NodeVisitor):
    """Safely evaluates arithmetic expressions without arbitrary code execution."""

    ALLOWED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(self, expr: str) -> float:
        parsed = ast.parse(expr.strip(), mode="eval")
        return self.visit(parsed.body)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type not in self.ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
        return self.ALLOWED_OPERATORS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type not in self.ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return self.ALLOWED_OPERATORS[op_type](operand)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Disallowed syntax element: {type(node).__name__}")


class ToolRegistry:
    """Registry of executable agent tools."""

    def __init__(self, sandbox_dir: Optional[str] = None):
        self.sandbox_dir = os.path.abspath(sandbox_dir) if sandbox_dir else os.getcwd()
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register(self, name: str, description: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add_tool(name, fn, description)
            return fn
        return decorator

    def add_tool(self, name: str, fn: Callable[..., Any], description: str) -> None:
        self._tools[name] = {
            "fn": fn,
            "description": description,
        }

    def list_tools(self) -> Dict[str, str]:
        return {k: v["description"] for k, v in self._tools.items()}

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        if name not in self._tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: '{name}'. Available: {list(self._tools.keys())}",
            )
        try:
            fn = self._tools[name]["fn"]
            res = fn(**kwargs)
            if isinstance(res, ToolResult):
                return res
            return ToolResult(success=True, output=str(res))
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Tool execution failed: {type(exc).__name__}: {exc}")

    def _resolve_safe_path(self, path: str) -> str:
        full_path = os.path.abspath(os.path.join(self.sandbox_dir, path))
        # Ensure path stays within sandbox boundary
        common = os.path.commonpath([self.sandbox_dir, full_path])
        if common != self.sandbox_dir:
            raise PermissionError(f"Access denied: path '{path}' escapes sandbox root '{self.sandbox_dir}'")
        return full_path

    def _register_default_tools(self) -> None:
        def file_read(path: str) -> str:
            resolved = self._resolve_safe_path(path)
            if not os.path.exists(resolved):
                raise FileNotFoundError(f"File not found: {path}")
            with open(resolved, "r", encoding="utf-8") as f:
                return f.read()

        def file_write(path: str, content: str) -> str:
            resolved = self._resolve_safe_path(path)
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Wrote {len(content)} bytes to {path}"

        def calc(expression: str) -> str:
            val = SafeMathEvaluator().evaluate(expression)
            return str(val)

        def system_probe() -> Dict[str, Any]:
            return {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
                "cpu_count": os.cpu_count() or 1,
            }

        def regex_extract(text: str, pattern: str) -> List[str]:
            return re.findall(pattern, text)

        def http_probe(url: str, timeout: int = 5) -> Dict[str, Any]:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
            req = urllib.request.Request(url, headers={"User-Agent": "superagent-core/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "url": url,
                    "status_code": resp.getcode(),
                    "content_type": resp.headers.get("Content-Type", ""),
                }

        self.add_tool("file_read", file_read, "Reads file contents safely within the sandbox directory.")
        self.add_tool("file_write", file_write, "Writes text contents to a file safely within sandbox.")
        self.add_tool("calc", calc, "Evaluates safe arithmetic expressions (+, -, *, /, //, %, **).")
        self.add_tool("system_probe", system_probe, "Probes local system metrics and host environment.")
        self.add_tool("regex_extract", regex_extract, "Extracts regular expression matches from input text.")
        self.add_tool("http_probe", http_probe, "Probes an HTTP endpoint status code and headers.")
