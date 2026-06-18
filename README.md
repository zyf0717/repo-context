# repo-context

Read-only repository context explorer for coding agents.

The canonical architecture is a local CLI-first exploration core that talks to an
OpenAI-compatible FastContext-style model endpoint. MCP is an adapter around the
same core, not the primary abstraction.

## Current Status

This repository has the initial Python 3.13+ implementation for spec `001`:
CLI, shared exploration core, read-only repository tools, OpenAI-compatible
chat-completions client, optional trajectory logging, and a thin MCP adapter.
It also includes spec `002` hardening for deterministic controller-owned
finalization and citation-mode rendering, plus spec `003` latency controls for
bounded endpoint prompt growth. Spec `004` is planned to align local tool
execution with FastContext same-turn parallel tool-call behavior.

Primary planning artifacts:

- [Spec Kit feature spec](specs/001-repo-context-explorer/spec.md)
- [Implementation plan](specs/001-repo-context-explorer/plan.md)
- [Task breakdown](specs/001-repo-context-explorer/tasks.md)
- [Deterministic explorer harness](specs/002-deterministic-explorer-harness/spec.md)
- [Latency-bounded explorer harness](specs/003-latency-bounded-explorer-harness/spec.md)
- [FastContext-compatible parallel tool executor](specs/004-fastcontext-parallel-tool-executor/spec.md)
- [Implementation order](docs/implementation-order.md)

## Usage

Use the CLI first for local debugging, scripts, CI checks, and one-off
questions. It has the smallest moving parts and exposes the exact core result.

Use MCP when an MCP-capable editor or agent should call repository exploration
as a tool during its workflow. MCP delegates to the same core as the CLI.

### Configure

Prefer `.repo-context.toml` for stable project-local settings:

```bash
cp .repo-context.toml.example .repo-context.toml
```

Use environment variables for temporary overrides, CI, or secrets:

```bash
cp .env.example .env
```

`repo-context` reads real environment variables from the process environment;
it does not load `.env` by itself. Configure at least:

```text
FASTCONTEXT_BASE_URL=http://localhost:8000/v1
FASTCONTEXT_MODEL=your-model-name
```

Endpoint requests use a 120 second default timeout. The harness also caps
model-observation payloads, model-requested read spans, completion tokens, and
temperature to reduce latency variance.

Planned spec `004` will execute independent same-turn local tool calls
concurrently with a default worker cap of `4`. Model endpoint requests will
remain serial.

Configuration precedence:

```text
defaults < .repo-context.toml < environment variables < CLI overrides
```

### CLI

Text output:

```bash
uv run repo-context explore \
  --query "Find the request validation logic" \
  --repo . \
  --max-turns 6 \
  --citation
```

In citation mode, `repo-context` validates and normalizes citations in the
controller. Text output is only repository-relative `path:start-end` labels, or
`NO_CITATIONS_FOUND`; model prose is not emitted. The model is prompted to use a
FastContext-style `<final_answer>` block, but the public text output is rendered
from controller-validated citations.

JSON output:

```bash
uv run repo-context explore \
  --query "Find the request validation logic" \
  --repo . \
  --format json
```

### MCP

Install optional MCP dependencies:

```bash
uv sync --extra mcp
```

Development server command:

```bash
uv run repo-context mcp --transport stdio
```

Tool: `explore_repository(query, repo_root?, max_turns?, citation?)`

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

Endpoint-backed e2e tests are opt-in and use this repository as the target repo:

```bash
REPO_CONTEXT_RUN_E2E=1 \
FASTCONTEXT_BASE_URL=http://localhost:8000/v1 \
FASTCONTEXT_MODEL=your-model-name \
uv run pytest tests/e2e
```

To print per-prompt timing for the current-repo multi-prompt e2e:

```bash
REPO_CONTEXT_RUN_E2E=1 \
FASTCONTEXT_BASE_URL=http://localhost:8000/v1 \
FASTCONTEXT_MODEL=your-model-name \
uv run pytest tests/e2e/test_current_repo_multi_prompt_timing.py -s
```

## Scope

In scope:

- Local, read-only repository exploration.
- Root-scoped `read_file`, `repo_glob`, and `repo_grep` tools.
- OpenAI-compatible chat completion loop with bounded tool observations.
- CLI output with file paths and line-range citations.
- MCP adapter that delegates to the CLI/core implementation.

Out of scope for the MVP:

- Repository mutation.
- Vector database ownership or embedding/model serving.
- MCP-first `context_search`, `context_pack`, and `context_get` tools.
- OKF bundle output.
