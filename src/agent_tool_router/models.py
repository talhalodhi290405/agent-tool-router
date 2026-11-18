"""Pydantic request, tool-input, and execution-trace models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ToolName = Literal["calculator", "text_analyzer", "json_validator"]


class TaskRequest(BaseModel):
    """Validated task description and tool-specific input payload."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class CalculatorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=128)


class TextAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=20_000)
    top_words: int = Field(default=5, ge=1, le=10)


class JSONValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    json_text: str = Field(min_length=1, max_length=50_000)


class ExecutionTrace(BaseModel):
    """Structured record of one routing and tool-execution attempt."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    task: str
    selected_tool: ToolName | None = None
    status: Literal["success", "error"]
    started_at: datetime
    finished_at: datetime
    duration_ms: float = Field(ge=0)
    result: dict[str, Any] | None = None
    error: str | None = None
