# Agent Tool Router

A lightweight Python orchestration engine that accepts a task, selects one of three specialized tools using explicit intent patterns, validates tool arguments with Pydantic, executes the selected tool, and returns a structured execution trace.

> **Scope:** This is a deterministic tool-routing prototype. It demonstrates core orchestration patterns—intent routing, schema validation, tool dispatch, error handling, and execution tracing—without an LLM, external API, or autonomous planning loop.

## Features

- Route task descriptions to a calculator, text analyzer, or JSON validator.
- Use explicit, case-insensitive intent patterns for deterministic tool selection.
- Validate request and tool-specific inputs with Pydantic v2.
- Reject unexpected input fields.
- Execute arithmetic through a restricted AST evaluator rather than Python `eval()`.
- Capture successful results and handled failures in a trace.
- Record a trace ID, selected tool, timestamps, duration, status, and result/error.
- Expose a command-line interface that prints JSON.

## Requirements

- Python 3.10 or newer
- pip

Runtime dependency: [Pydantic v2](https://docs.pydantic.dev/).

## Installation

Clone the repository:

```bash
git clone https://github.com/talhalodhi290405/agent-tool-router.git
cd agent-tool-router
```

Create and activate a virtual environment.

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project and its development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Quick start

The CLI accepts a task phrase and a JSON object containing the selected tool's arguments.

### Calculator

```bash
agent-router "calculate this expression" --payload '{"expression":"2 + 3 * 4"}'
```

### Text analysis

```bash
agent-router "analyze this text" --payload '{"text":"Agents use tools. Tools help agents complete tasks.","top_words":3}'
```

### JSON validation

```bash
agent-router "validate this JSON" --payload '{"json_text":"{\\"name\\":\\"Talha\\",\\"active\\":true}"}'
```

Show command-line help:

```bash
agent-router --help
```

The equivalent module invocation is:

```bash
python -m agent_tool_router.cli "calculate this expression" --payload '{"expression":"2 + 3"}'
```

## Available tools

| Tool | Example intent phrases | Required payload |
| --- | --- | --- |
| `calculator` | `calculate`, `compute`, `arithmetic`, `math` | `expression` |
| `text_analyzer` | `analyze this text`, `text analysis`, `word count`, `character count`, `count words` | `text`; optional `top_words` |
| `json_validator` | `validate JSON`, `JSON validation`, `check JSON`, `parse JSON` | `json_text` |

The router selects a tool from explicit phrase patterns in the task description. If no tool matches, it returns a routing error. If a task matches more than one tool, it rejects the ambiguous request rather than guessing.

### 1. Calculator

Performs basic arithmetic using numeric constants, parentheses, and these operators:

- Addition: `+`
- Subtraction: `-`
- Multiplication: `*`
- Division: `/`
- Floor division: `//`
- Modulo: `%`
- Exponentiation: `**`

The expression is parsed into an Abstract Syntax Tree (AST). Only approved numeric and operator nodes are evaluated. Names, function calls, attribute access, and arbitrary Python statements are rejected. Expression length, AST size, nesting depth, exponent magnitude, and numeric result magnitude are limited.

Example payload:

```json
{
  "expression": "2 + 3 * 4"
}
```

Example tool result:

```json
{
  "expression": "2 + 3 * 4",
  "result": 14
}
```

### 2. Text Analyzer

Returns:
- Total characters.
- Characters excluding whitespace.
- Word count.
- Sentence count based on punctuation delimiters.
- Most frequent words, up to the requested limit.

Example payload:

```json
{
  "text": "Agents use tools. Tools help agents complete tasks.",
  "top_words": 3
}
```

### 3. JSON Validator

Attempts to parse the supplied JSON string and reports whether it is valid. For valid JSON, it returns the top-level type and, for objects or arrays, basic key/item counts. Invalid JSON returns the parser message and location.

Example payload:

```json
{
  "json_text": "{\\"name\\":\\"Talha\\",\\"active\\":true}"
}
```

## Execution traces

Each task execution returns an `ExecutionTrace` containing:

| Field | Meaning |
| --- | --- |
| `trace_id` | Unique identifier for the execution |
| `task` | Original task description |
| `selected_tool` | Tool name, or `null` if routing failed |
| `status` | `success` or `error` |
| `started_at` | UTC start timestamp |
| `finished_at` | UTC finish timestamp |
| `duration_ms` | Elapsed execution time in milliseconds |
| `result` | Tool result when execution succeeds |
| `error` | Error description when routing, validation, or execution fails |

Example trace (timestamps and trace ID are illustrative):

```json
{
  "trace_id": "8b1f53d6-ec6a-4c6f-a9d7-7a8fa77e0235",
  "task": "calculate this expression",
  "selected_tool": "calculator",
  "status": "success",
  "started_at": "2026-11-18T06:00:00Z",
  "finished_at": "2026-11-18T06:00:00Z",
  "duration_ms": 0.42,
  "result": {
    "expression": "2 + 3 * 4",
    "result": 14
  },
  "error": null
}
```

A JSON string that is syntactically invalid is a completed validator operation: the trace status can be `success` while the validator's own result contains `"valid": false`. This distinguishes tool execution status from the content being validated.

## Input validation

Pydantic models define the accepted request and tool arguments:

- Task descriptions: 1–500 characters.
- Calculator expressions: 1–128 characters.
- Text analyzer input: 1–20,000 characters; `top_words` between 1 and 10.
- JSON input: 1–50,000 characters.
- Extra fields are rejected.

The CLI requires `--payload` to decode to a JSON object. Invalid command input is reported as JSON and exits with code `2`.

## Run tests

Install development dependencies, then run:

```bash
python -m pytest -v
```

The test suite covers tool behavior, calculator safety, text statistics, JSON parsing, intent selection, unknown and ambiguous intents, Pydantic validation, and execution trace creation/serialization.

## Architecture

```text
Task description + JSON payload
              |
              v
        TaskRequest
        (Pydantic)
              |
              v
       Intent selector
    (explicit regex patterns)
              |
              v
       Tool dispatcher
              |
      +-------+--------+
      |       |        |
      v       v        v
 Calculator  Text     JSON
             Analyzer Validator
      |       |        |
      +-------+--------+
              |
              v
       ExecutionTrace
       (Pydantic model)
              |
              v
         JSON output
```

## Project structure

```text
agent-tool-router/
├── src/
│   └── agent_tool_router/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── router.py
│       └── tools.py
├── tests/
│   └── test_router.py
├── .gitignore
├── LICENSE
├── README.md
└── pyproject.toml
```

## Current scope and limitations

This project is intentionally deterministic. It does not use an LLM to interpret arbitrary natural-language requests, plan multi-step tasks, or decide dynamically which tools to call. Intent selection is based on explicit patterns. It handles one tool execution per request and keeps traces in the returned response; it does not yet persist them to a database or log service.

Possible extensions include an LLM-backed planner, a registry for dynamically added tools, multi-step workflows, persisted execution history, retry policies, and observability integrations.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
