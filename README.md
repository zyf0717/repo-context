# repo-context

Read-only repository context explorer for coding agents.

The canonical architecture is a local CLI-first exploration core that talks to an
OpenAI-compatible FastContext-style model endpoint. MCP is an adapter around the
same core, not the primary abstraction.

## Current Status

This repository has the initial Python 3.13+ implementation for spec `001`:
CLI, shared exploration core, read-only repository tools, OpenAI-compatible
chat-completions client, optional trajectory logging, and a thin MCP adapter.

Primary planning artifacts:

- [Spec Kit feature spec](specs/001-repo-context-explorer/spec.md)
- [Implementation plan](specs/001-repo-context-explorer/plan.md)
- [Task breakdown](specs/001-repo-context-explorer/tasks.md)
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
