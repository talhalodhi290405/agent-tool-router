from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent_tool_router.models import (
    CalculatorInput,
    JSONValidationInput,
    TaskRequest,
    TextAnalysisInput,
)
from agent_tool_router.router import RoutingError, execute_task, select_tool
from agent_tool_router.tools import (
    ToolExecutionError,
    calculator_tool,
    json_validator_tool,
    text_analyzer_tool,
)


def test_calculator_tool_respects_operator_precedence() -> None:
    result = calculator_tool(
        CalculatorInput(expression="2 + 3 * (4 - 1)")
    )

    assert result == {
        "expression": "2 + 3 * (4 - 1)",
        "result": 11,
    }


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo unsafe')",
        "open('secret.txt').read()",
        "value + 1",
        "math.sqrt(16)",
    ],
)
def test_calculator_tool_rejects_python_execution_and_names(
    expression: str,
) -> None:
    with pytest.raises(ToolExecutionError):
        calculator_tool(CalculatorInput(expression=expression))


def test_calculator_tool_handles_division_by_zero() -> None:
    with pytest.raises(ToolExecutionError, match="Division by zero"):
        calculator_tool(CalculatorInput(expression="5 / 0"))


def test_text_analyzer_returns_counts_and_top_words() -> None:
    result = text_analyzer_tool(
        TextAnalysisInput(
            text="Agent tools help agents. Tools make agents useful!",
            top_words=2,
        )
    )

    assert result["words"] == 8
    assert result["sentences"] == 2
    assert result["characters"] == len(
        "Agent tools help agents. Tools make agents useful!"
    )
    assert result["top_words"] == [
        {"word": "tools", "count": 2},
        {"word": "agents", "count": 2},
    ]


def test_json_validator_identifies_object_keys() -> None:
    result = json_validator_tool(
        JSONValidationInput(json_text='{"name":"Talha","active":true}')
    )

    assert result == {
        "valid": True,
        "top_level_type": "object",
        "keys": ["name", "active"],
        "key_count": 2,
    }


def test_json_validator_returns_parse_error_for_invalid_json() -> None:
    result = json_validator_tool(
        JSONValidationInput(json_text='{"name":')
    )

    assert result["valid"] is False
    assert isinstance(result["error"], str)
    assert result["line"] == 1
    assert isinstance(result["column"], int)


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("Calculate this expression", "calculator"),
        ("Please compute the total", "calculator"),
        ("Analyze this text", "text_analyzer"),
        ("Give me a word count", "text_analyzer"),
        ("Validate this JSON", "json_validator"),
        ("Check JSON input", "json_validator"),
    ],
)
def test_select_tool_maps_intent_to_tool(task: str, expected: str) -> None:
    assert select_tool(task) == expected


def test_select_tool_rejects_unknown_intent() -> None:
    with pytest.raises(RoutingError, match="No tool matched"):
        select_tool("Find the weather forecast")


def test_select_tool_rejects_ambiguous_intent() -> None:
    with pytest.raises(RoutingError, match="multiple tools"):
        select_tool("Calculate a value and analyze this text")


def test_task_request_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        TaskRequest.model_validate(
            {"task": "calculate", "payload": {}, "admin": True}
        )


def test_execute_task_returns_successful_execution_trace() -> None:
    trace = execute_task(
        TaskRequest(
            task="Calculate this expression",
            payload={"expression": "6 * 7"},
        )
    )

    assert trace.status == "success"
    assert trace.selected_tool == "calculator"
    assert trace.result == {
        "expression": "6 * 7",
        "result": 42,
    }
    assert trace.error is None
    assert trace.trace_id
    assert trace.duration_ms >= 0
    assert trace.finished_at >= trace.started_at
    assert isinstance(trace.started_at, datetime)
    assert trace.started_at.tzinfo == timezone.utc


def test_execute_task_records_validation_error_in_trace() -> None:
    trace = execute_task(
        TaskRequest(
            task="Calculate this expression",
            payload={"wrong_field": "2 + 2"},
        )
    )

    assert trace.status == "error"
    assert trace.selected_tool == "calculator"
    assert trace.result is None
    assert trace.error is not None
    assert "Invalid tool input" in trace.error
    assert trace.trace_id


def test_execute_task_records_unknown_intent_in_trace() -> None:
    trace = execute_task(
        TaskRequest(task="Tell me a joke", payload={})
    )

    assert trace.status == "error"
    assert trace.selected_tool is None
    assert trace.result is None
    assert trace.error is not None
    assert "No tool matched" in trace.error


def test_execute_task_trace_can_be_serialized_as_json() -> None:
    trace = execute_task(
        TaskRequest(
            task="Validate this JSON",
            payload={"json_text": '{"ready": true}'},
        )
    )

    serialized = trace.model_dump_json()
    parsed = json.loads(serialized)

    assert parsed["status"] == "success"
    assert parsed["selected_tool"] == "json_validator"
    assert parsed["result"]["valid"] is True
    assert parsed["trace_id"] == trace.trace_id
