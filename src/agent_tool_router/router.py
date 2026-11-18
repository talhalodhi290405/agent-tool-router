"""Task classification, argument validation, dispatch, and execution tracing."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from agent_tool_router.models import (
    CalculatorInput,
    ExecutionTrace,
    JSONValidationInput,
    TaskRequest,
    TextAnalysisInput,
    ToolName,
)
from agent_tool_router.tools import (
    ToolExecutionError,
    calculator_tool,
    json_validator_tool,
    text_analyzer_tool,
)


class RoutingError(ValueError):
    """Raised when a task has no unique matching tool intent."""


INTENT_PATTERNS: dict[ToolName, tuple[str, ...]] = {
    "calculator": (
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\barithmetic\b",
        r"\bmath(?:ematics)?\b",
    ),
    "text_analyzer": (
        r"\banaly[sz]e\s+(?:this\s+)?text\b",
        r"\btext\s+analysis\b",
        r"\bword\s+count\b",
        r"\bcharacter\s+count\b",
        r"\bcount\s+words\b",
    ),
    "json_validator": (
        r"\bvalidate\s+(?:this\s+)?json\b",
        r"\bjson\s+validation\b",
        r"\bcheck\s+(?:this\s+)?json\b",
        r"\bparse\s+(?:this\s+)?json\b",
    ),
}


def select_tool(task: str) -> ToolName:
    """Choose one tool from explicit deterministic intent phrases."""

    if not task.strip():
        raise RoutingError("Task description cannot be empty.")

    matches = [
        tool_name
        for tool_name, patterns in INTENT_PATTERNS.items()
        if any(re.search(pattern, task, flags=re.IGNORECASE) for pattern in patterns)
    ]
    if not matches:
        raise RoutingError(
            "No tool matched. Try 'calculate', 'analyze text', or 'validate JSON'."
        )
    if len(matches) > 1:
        raise RoutingError(
            "Task matches multiple tools. Submit one clear intent at a time."
        )
    return matches[0]


def execute_task(request: TaskRequest) -> ExecutionTrace:
    """Validate, route, execute a single task, and return a structured trace."""

    started_at = datetime.now(timezone.utc)
    clock_start = time.perf_counter()
    selected_tool: ToolName | None = None
    result: dict[str, object] | None = None
    error: str | None = None
    status: str = "success"

    try:
        selected_tool = select_tool(request.task)
        if selected_tool == "calculator":
            arguments = CalculatorInput.model_validate(request.payload)
            result = calculator_tool(arguments)
        elif selected_tool == "text_analyzer":
            arguments = TextAnalysisInput.model_validate(request.payload)
            result = text_analyzer_tool(arguments)
        elif selected_tool == "json_validator":
            arguments = JSONValidationInput.model_validate(request.payload)
            result = json_validator_tool(arguments)
    except RoutingError as exc:
        status = "error"
        error = str(exc)
    except ValidationError as exc:
        status = "error"
        details = [
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in exc.errors(include_url=False)
        ]
        error = "Invalid tool input: " + "; ".join(details)
    except ToolExecutionError as exc:
        status = "error"
        error = str(exc)
    except Exception as exc:  # Preserve a trace if a tool unexpectedly fails.
        status = "error"
        error = f"Unexpected tool error: {type(exc).__name__}"

    finished_at = datetime.now(timezone.utc)
    duration_ms = round((time.perf_counter() - clock_start) * 1000, 3)
    return ExecutionTrace(
        trace_id=str(uuid4()),
        task=request.task,
        selected_tool=selected_tool,
        status=status,  # type: ignore[arg-type]
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        result=result,
        error=error,
    )
