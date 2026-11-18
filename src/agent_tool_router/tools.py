"""Specialized tools used by the deterministic agent tool router."""

from __future__ import annotations

import ast
import json
import math
import operator
import re
from collections import Counter
from typing import Callable

from agent_tool_router.models import (
    CalculatorInput,
    JSONValidationInput,
    TextAnalysisInput,
)


class ToolExecutionError(ValueError):
    """Raised when a selected tool cannot safely complete its operation."""


MAX_CALC_RESULT = 1_000_000_000_000
MAX_POWER_EXPONENT = 10
MAX_AST_NODES = 64
BINARY_OPERATORS: dict[type[ast.operator], Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPERATORS: dict[type[ast.unaryop], Callable] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _check_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolExecutionError("Only numeric constants are permitted.")
    if isinstance(value, int):
        if abs(value) > MAX_CALC_RESULT:
            raise ToolExecutionError("Calculation exceeds the supported numeric range.")
    elif not math.isfinite(value) or abs(value) > MAX_CALC_RESULT:
        raise ToolExecutionError("Calculation exceeds the supported numeric range.")
    return value


def _safe_eval(node: ast.AST, depth: int = 0) -> int | float:
    if depth > 16:
        raise ToolExecutionError("Expression is nested too deeply.")
    if isinstance(node, ast.Constant):
        return _check_number(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
        return _check_number(UNARY_OPERATORS[type(node.op)](_safe_eval(node.operand, depth + 1)))
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
        left = _safe_eval(node.left, depth + 1)
        right = _safe_eval(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER_EXPONENT:
            raise ToolExecutionError(f"Exponent magnitude must not exceed {MAX_POWER_EXPONENT}.")
        try:
            value = BINARY_OPERATORS[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise ToolExecutionError("Division by zero is not allowed.") from exc
        except (OverflowError, ValueError) as exc:
            raise ToolExecutionError("Calculation could not be completed.") from exc
        return _check_number(value)
    raise ToolExecutionError("Unsupported expression. Use numbers, parentheses, and +, -, *, /, //, %, **.")


def calculator_tool(arguments: CalculatorInput) -> dict[str, object]:
    """Evaluate a restricted arithmetic expression without eval()."""

    expression = arguments.expression.strip()
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolExecutionError("Expression has invalid syntax.") from exc
    if sum(1 for _ in ast.walk(parsed)) > MAX_AST_NODES:
        raise ToolExecutionError("Expression is too complex.")
    result = _safe_eval(parsed.body)
    return {"expression": expression, "result": result}


def text_analyzer_tool(arguments: TextAnalysisInput) -> dict[str, object]:
    """Return basic character, word, sentence, and frequent-word statistics."""

    text = arguments.text
    words = re.findall(r"\b[\w'-]+\b", text.casefold(), flags=re.UNICODE)
    sentences = [part for part in re.split(r"[.!?]+", text) if part.strip()]
    common_words = [
        {"word": word, "count": count}
        for word, count in Counter(words).most_common(arguments.top_words)
    ]
    return {
        "characters": len(text),
        "characters_without_whitespace": sum(not char.isspace() for char in text),
        "words": len(words),
        "sentences": len(sentences),
        "top_words": common_words,
    }


def json_validator_tool(arguments: JSONValidationInput) -> dict[str, object]:
    """Parse JSON and report its top-level type and object keys when present."""

    try:
        value = json.loads(arguments.json_text)
    except json.JSONDecodeError as exc:
        return {
            "valid": False,
            "error": exc.msg,
            "line": exc.lineno,
            "column": exc.colno,
        }

    type_name = (
        "null" if value is None else
        "boolean" if isinstance(value, bool) else
        "object" if isinstance(value, dict) else
        "array" if isinstance(value, list) else
        "number" if isinstance(value, (int, float)) else
        "string"
    )
    result: dict[str, object] = {"valid": True, "top_level_type": type_name}
    if isinstance(value, dict):
        result["keys"] = list(value.keys())
        result["key_count"] = len(value)
    elif isinstance(value, list):
        result["item_count"] = len(value)
    return result
