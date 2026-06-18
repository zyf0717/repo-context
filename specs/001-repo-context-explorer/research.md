# Research: Repo Context Explorer

## Decision

Build the FastContext-style repository explorer harness first, expose it through
the CLI, then wrap it with MCP.

## Source Plan Reconciliation

Two source plans were considered:

- Local Context MCP Server: MCP-first context retrieval adapter over a ranked
  endpoint.
- FastContext Repository Explorer: CLI-first local read-only exploration harness
  around an OpenAI-compatible model endpoint.

The selected approach is the FastContext explorer shape because it makes local
read-only repository access and citation generation the core capability. MCP is
valuable, but it should be an adapter over that core rather than the component
that owns exploration logic.

## Rationale

- CLI-first is easier to test independently from MCP clients.
- A single core reduces duplicate safety checks and divergent behavior.
- FastContext-style exploration fits the desired use case: ask focused questions
  about unfamiliar code and get compact file-line evidence.
- OpenAI-compatible chat completions are a narrower first backend target than a
  generic ranked context-search endpoint.
- The deferred MCP-first tools (`context_search`, `context_pack`, `context_get`)
  require a different backend contract and should not block the MVP.

## Technology Choices

- Python 3.13+ for modern typing, local filesystem ergonomics, and endpoint
  client simplicity.
- `uv` for package and environment management.
- `httpx` for OpenAI-compatible HTTP requests.
- `pydantic` and `pydantic-settings` for config and structured model types.
- `pytest` plus mocked HTTP transport for endpoint-independent tests.
- `ruff` and `pyright` or `mypy` for release gates.
- Official MCP Python SDK for the adapter after the CLI/core path is stable.

## Security Conclusions

- The model may request tool calls, but local code owns enforcement.
- All file paths must be resolved under `repo_root` after symlink resolution.
- Denylisted files must be rejected before content is read or logged.
- Tool observations must be capped and truncation must be explicit.
- Repository writes are out of scope for every interface.

## Deferred Decisions

- Exact CLI framework: `argparse` is dependency-light; `typer` is more ergonomic.
  Choose during implementation based on desired dependency footprint.
- Type checker: `pyright` is stricter for modern typing; `mypy` is more common
  in Python package CI. Either is acceptable if enforced consistently.
- MCP transport details: defer until the core run contract is stable.
