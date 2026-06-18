# Quickstart: Repo Context Explorer

This quickstart describes the implemented CLI-first behavior for spec `001`.

## Prerequisites

- Python 3.13+
- `uv`
- OpenAI-compatible FastContext endpoint
- Local repository to inspect

## Install for Development

```bash
uv sync
uv run repo-context --help
```

## Configure Endpoint

Preferred project-local config:

```bash
cp .repo-context.toml.example .repo-context.toml
```

Or export environment variables:

```bash
export FASTCONTEXT_BASE_URL=http://localhost:8000/v1
export FASTCONTEXT_MODEL=your-model-name
export FASTCONTEXT_API_KEY=
export FASTCONTEXT_MAX_TURNS=6
export FASTCONTEXT_MAX_READ_BYTES=12000
export FASTCONTEXT_MAX_GREP_RESULTS=50
export FASTCONTEXT_TRAJ_DIR=.fastcontext
export FASTCONTEXT_TIMEOUT_SECONDS=120
export FASTCONTEXT_MAX_OBSERVATION_CHARS=6000
export FASTCONTEXT_MAX_READ_LINES=120
export FASTCONTEXT_MAX_COMPLETION_TOKENS=512
export FASTCONTEXT_TEMPERATURE=0
```

Optional project config:

```toml
[explorer]
max_turns = 6
citation = true
ignore = [".git", ".venv", "node_modules", "dist", "build"]

[model]
base_url = "http://localhost:8000/v1"
model = "your-model-name"
api_key = ""
timeout_seconds = 120
max_completion_tokens = 512
temperature = 0

[tools]
max_read_bytes = 12000
max_grep_results = 50
max_observation_chars = 6000
max_read_lines = 120
```

The repository includes `.repo-context.toml.example` with this shape.

## Run CLI Exploration

Use the CLI first for direct local runs and debugging:

```bash
uv run repo-context explore \
  --query "Find the request validation logic" \
  --repo . \
  --max-turns 6 \
  --citation
```

Expected text shape:

```text
src/api/validation.py:42-88
tests/test_validation.py:101-140
```

JSON output:

```bash
uv run repo-context explore \
  --query "Find the request validation logic" \
  --repo . \
  --format json
```

## Run MCP Adapter

Use MCP when an MCP-capable editor or agent should call repository exploration
as a tool. The MCP adapter delegates to the same core as the CLI.

Install the optional MCP dependency before using the adapter:

```bash
uv sync --extra mcp
```

Server command:

```bash
uv run repo-context mcp --transport stdio
```

Expected tool:

```text
explore_repository(query, repo_root?, max_turns?, citation?)
```

Generic MCP client config shape:

```json
{
  "mcpServers": {
    "repo-context": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/repo-context",
        "--extra",
        "mcp",
        "repo-context",
        "mcp",
        "--transport",
        "stdio"
      ],
      "env": {
        "FASTCONTEXT_BASE_URL": "http://localhost:8000/v1",
        "FASTCONTEXT_MODEL": "your-model-name"
      }
    }
  }
}
```

## Validate

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

Errors are printed to stderr as `CODE: message`; denied paths never include file
contents in the error payload.
