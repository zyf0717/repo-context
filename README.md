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

## Interfaces

CLI MVP:

```bash
uv run repo-context explore \
  --query "Find the request validation logic" \
  --repo . \
  --max-turns 6 \
  --citation
```

MCP adapter:

```bash
uv run repo-context mcp --transport stdio
```

Tool: `explore_repository(query, repo_root?, max_turns?, citation?)`

Configuration sources:

- Environment variables such as `FASTCONTEXT_BASE_URL`,
  `FASTCONTEXT_MODEL`, and `FASTCONTEXT_API_KEY`.
- Optional project file: `.repo-context.toml`.

Copy `.repo-context.toml.example` or set the environment variables in
`.env.example`. `FASTCONTEXT_BASE_URL` and `FASTCONTEXT_MODEL` are required for
real exploration runs.

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
