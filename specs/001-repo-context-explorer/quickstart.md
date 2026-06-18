# Quickstart: Repo Context Explorer

This quickstart describes the intended implementation behavior. It is not
expected to run until the package exists.

## Prerequisites

- Python 3.13+
- `uv`
- OpenAI-compatible FastContext endpoint
- Local repository to inspect

## Install for Development

```bash
uv sync
```

## Configure Endpoint

```bash
export FASTCONTEXT_BASE_URL=http://127.0.0.1:8000/v1
export FASTCONTEXT_MODEL=microsoft/FastContext-1.0-4B-SFT
export FASTCONTEXT_API_KEY=local-or-empty
export FASTCONTEXT_MAX_TURNS=6
export FASTCONTEXT_MAX_READ_BYTES=12000
export FASTCONTEXT_MAX_GREP_RESULTS=50
export FASTCONTEXT_TRAJ_DIR=.fastcontext
```

Optional project config:

```toml
[explorer]
max_turns = 6
citation = true
ignore = [".git", ".venv", "node_modules", "dist", "build"]

[model]
base_url = "http://127.0.0.1:8000/v1"
model = "microsoft/FastContext-1.0-4B-SFT"

[tools]
max_read_bytes = 12000
max_grep_results = 50
```

## Run CLI Exploration

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

The MCP server is added after CLI/core implementation.

Expected server command:

```bash
uv run repo-context mcp --transport stdio
```

Expected tool:

```text
explore_repository(query, repo_root?, max_turns?, citation?)
```

## Validate

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

If `mypy` is selected instead of `pyright`, use the equivalent type-check
command consistently in CI and docs.
