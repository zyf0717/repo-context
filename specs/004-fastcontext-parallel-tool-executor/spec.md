# Spec 004: FastContext-Compatible Parallel Tool Executor

Status: planned

Extends: `003-latency-bounded-explorer-harness`

## Summary

The explorer should match the FastContext runtime shape more closely by
executing independent same-turn local tool calls concurrently. The model remains
the exploration planner and final citation proposer. The controller remains
responsible for safety, execution, observation ordering, evidence tracking,
citation validation, loop termination, and public output rendering.

This spec is a performance hardening pass. It does not change the product shape:
CLI remains the primary path, MCP remains an adapter, and the only repository
tools remain read-only `read_file`, `repo_glob`, and `repo_grep`.

## Requirements

- Execute multiple tool calls emitted by the same assistant message with a
  bounded thread pool.
- Default local tool parallelism to `4` workers.
- Preserve deterministic transcript order:
  - tool calls may complete out of order;
  - observations must be appended to the model transcript in the original
    tool-call order.
- Keep all repository safety and caps centralized in the existing tool execution
  path.
- Update evidence state, truncation state, and trajectory logs only after worker
  results are collected on the main controller thread.
- Keep model calls serial. Do not issue concurrent chat-completion requests.
- Preserve the existing controller stop conditions:
  - content citation validation before tool execution;
  - early stop on valid citations with trailing tool calls;
  - repeated-call break before executing repeated tools;
  - early finalization from sufficient narrow evidence;
  - max-turn fallback behavior.

## Configuration

Add one tool-execution concurrency setting when this spec is implemented:

```text
FASTCONTEXT_MAX_PARALLEL_TOOLS=4
```

TOML shape:

```toml
[tools]
max_parallel_tools = 4
```

The setting must be a positive integer. Effective workers for a turn are:

```text
min(max_parallel_tools, len(tool_calls))
```

When the effective worker count is `1`, execution should use the existing
serial path.

## Non-Goals

- No async rewrite.
- No concurrent LLM requests.
- No controller-side semantic search planner.
- No vector store, embeddings, or context-pack output.
- No new repository tools.
- No repository mutation tools.
- No timing threshold as a default CI gate.

## Implementation Notes

Add a private helper around the existing execution primitive:

```python
def _execute_tool_calls_parallel(
    tool_calls: list[ToolCall],
    *,
    repo_root: Path,
    settings: Settings,
) -> list[ToolObservation]:
    ...
```

The helper should:

- call existing `_execute_tool_call()` for every tool call;
- preserve result order to match the input `tool_calls`;
- avoid mutating shared `EvidenceState` from worker threads;
- return per-tool errors as `ToolObservation` values, matching the current
  `_execute_tool_call()` behavior.

The `explore()` loop should continue to append one assistant tool-call message,
then one tool observation message per tool call in original order.

## Public Behavior

Citation-mode text remains controller-rendered `path:start-end` lines or
`NO_CITATIONS_FOUND`.

JSON output shape remains unchanged. Once implemented, latency may improve when
the model emits independent same-turn local tool calls, but public result fields
and safety behavior should remain compatible.

## Coverage

Implementation should add regression tests for:

- same-turn multi-tool execution with observations returned to the model in
  original order;
- `max_parallel_tools=1` preserving serial behavior;
- default `max_parallel_tools=4`;
- TOML, environment variable, and override precedence for
  `max_parallel_tools`;
- repeated-call detection stopping before scheduling any tool work;
- per-tool errors not cancelling sibling observations;
- a mocked slow-tool scenario showing concurrent execution is materially faster
  than serial execution without relying on endpoint-backed tests.

Opt-in endpoint-backed e2e timing tests may be used to compare before/after
behavior, but timing should not become a required CI assertion.
