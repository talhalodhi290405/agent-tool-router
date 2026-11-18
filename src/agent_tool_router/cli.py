"""Command-line interface for the Agent Tool Router."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from pydantic import ValidationError

from agent_tool_router.models import TaskRequest
from agent_tool_router.router import execute_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-router",
        description="Route a task to one validated local tool and print an execution trace.",
    )
    parser.add_argument(
        "task",
        help="intent phrase: calculate, analyze text, or validate JSON",
    )
    parser.add_argument(
        "--payload",
        default="{}",
        help='tool input as a JSON object, e.g. \'{"expression":"2 + 2"}\'',
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload: Any = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("--payload must decode to a JSON object.")
        request = TaskRequest.model_validate({"task": args.task, "payload": payload})
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2

    trace = execute_task(request)
    print(trace.model_dump_json(indent=2))
    return 0 if trace.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
