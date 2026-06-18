# repo-context

Read-only repository context explorer for coding agents.

The canonical architecture is a local CLI-first exploration core that talks to an
OpenAI-compatible FastContext-style model endpoint. MCP is an adapter around the
same core, not the primary abstraction.

## Current Status

This repository is at specification stage. The implementation target is Python
3.13+ managed with `uv`.

Primary planning artifacts:

- [Spec Kit feature spec](specs/001-repo-context-explorer/spec.md)
- [Implementation plan](specs/001-repo-context-explorer/plan.md)
- [Task breakdown](specs/001-repo-context-explorer/tasks.md)
- [Implementation order](docs/implementation-order.md)

## Target Interfaces

CLI MVP:

```bash
repo-context explore \
  --query "Find the request validation logic" \
  --repo . \
  --max-turns 6 \
  --citation
```

MCP adapter:

```text
explore_repository(query, repo_root?, max_turns?, citation?)
```

Configuration sources:

- Environment variables such as `FASTCONTEXT_BASE_URL`,
  `FASTCONTEXT_MODEL`, and `FASTCONTEXT_API_KEY`.
- Optional project file: `.repo-context.toml`.

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
