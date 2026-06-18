# Implementation Order

This project should be built as a CLI-first repository explorer. MCP remains an
adapter over the same core so the product has one exploration engine and one
security boundary. The architecture follows Microsoft FastContext's delegated
explorer shape: read-only Read/Glob/Grep-style tools, same-turn parallel local
tool calls, and compact file-line evidence.

## 1. Spec/contracts and package skeleton

Create the Python 3.13+ package baseline with `uv`, `pyproject.toml`, source
layout, test layout, and documentation examples. Freeze the public contracts
before writing the tool loop:

- CLI command: `repo-context explore`.
- Config sources: env plus `.repo-context.toml`.
- Local read-only tool contract: `read_file`, `repo_glob`, `repo_grep`.
- MCP adapter contract: `explore_repository`.

Exit criteria:

- `uv run repo-context --help` is expected to be possible once code exists.
- Contracts in `specs/001-repo-context-explorer/contracts/` are stable enough
  for tests to target.

## 2. Root-scoped read-only tools

Implement local repository tools before involving the model endpoint.

- Resolve all paths under `repo_root`.
- Reject absolute paths outside the root and symlink escapes.
- Enforce denylisted paths such as `.git`, `.env*`, secrets, virtualenvs, and
  build outputs.
- Cap read bytes and grep result counts.
- Return structured observations with relative paths and line ranges.

Exit criteria:

- Unit tests cover traversal, symlink escape, denylist, byte caps, result caps,
  and normal file reads/searches.

## 3. OpenAI-compatible exploration loop

Implement the FastContext-style harness around the local tools. Spec
`002-deterministic-explorer-harness` hardens this phase with controller-owned
finalization and citation validation. Spec `003-latency-bounded-explorer-harness`
adds endpoint latency controls and bounded model observations. Spec
`004-fastcontext-parallel-tool-executor` aligns local execution with
FastContext same-turn parallel tool-call behavior.

- Send the user query, tool schemas, and bounded observations to the configured
  OpenAI-compatible chat completion endpoint.
- Execute only allowed read-only tool-call intents.
- Validate citation content before continuing with trailing tool calls.
- Stop on valid controller-verified citations, repeated tool-call loops, final
  answer, or max turns.
- Persist optional trajectory logs under `FASTCONTEXT_TRAJ_DIR`.
- Normalize citation-mode output to concise controller-rendered citations by
  default.
- Bound prompt growth with observation caps, read-line caps, completion-token
  limits, and deterministic early finalization from narrow evidence.
- Execute same-turn model tool calls concurrently while preserving deterministic
  observation order in the transcript.

Exit criteria:

- Mock endpoint tests can drive READ/GLOB/GREP calls and return final cited
  paths without touching real external services.
- Mocked parallel tool-call tests preserve transcript order and prove repeated
  calls stop before scheduling tool work.

## 4. CLI MVP

Expose the exploration core through:

```bash
repo-context explore --query TEXT --repo PATH --max-turns 6 --citation
```

Required behavior:

- Defaults to citation-only text output.
- Supports JSON output for integration tests and future agent consumers.
- Reports endpoint/configuration failures with explicit exit codes and messages.
- Does not print secrets or unrestricted file contents in errors.

Exit criteria:

- Fixture repository integration test returns expected file-line evidence.
- CLI contract tests validate arguments, defaults, and output shape.

## 5. MCP adapter

Add an MCP server command that registers one tool:

```text
explore_repository(query, repo_root?, max_turns?, citation?)
```

The adapter must call the same exploration core as the CLI. It must not
duplicate path safety, endpoint logic, or trajectory handling.

Exit criteria:

- MCP tool schema is discoverable.
- Mocked adapter invocation returns the same result as the core for equivalent
  inputs.

## 6. Hardening and distribution

Add operational guardrails after the core paths work:

- Config precedence tests.
- Structured stderr logging.
- Optional trajectory retention controls.
- `ruff` and `pyright` or `mypy` checks for Python 3.13+.
- README quickstart and examples for Codex, Copilot, and MCP clients.
- Packaging path suitable for `uvx` once published.

Exit criteria:

- `uv run pytest`, `uv run ruff check .`, and type checks pass.
- Daily local use is safe against accidental writes or path escapes.
