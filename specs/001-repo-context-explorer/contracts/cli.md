# CLI Contract

## Command

```bash
repo-context explore [OPTIONS]
```

## Required Options

- `--query TEXT`: Focused repository-context question. Must not be blank.
- `--repo PATH`: Repository root to inspect. Defaults may later resolve to `.`,
  but tests should cover explicit path first.

## Optional Options

- `--max-turns INTEGER`: Maximum model/tool iterations. Default: `6`.
- `--citation`: Prefer citation-only final text output.
- `--format text|json`: Output format. Default: `text`.

## Text Output

Citation mode returns compact evidence:

```text
src/api/validation.py:42-88
tests/test_validation.py:101-140
```

If the model provides explanatory text, citation-mode text output still emits
only controller-validated citations. If no citation is accepted, text output is
exactly `NO_CITATIONS_FOUND`.

The model is prompted to produce final citations in a `<final_answer>` block,
but the CLI does not print that block wrapper in citation mode.

Model-facing tool observations are latency bounded. Model-requested reads may
be returned as bounded previews, but local repository safety and read byte caps
still apply before any content is observed.

## JSON Output

```json
{
  "query": "Find the request validation logic",
  "repo_root": "/absolute/path/to/repo",
  "answer": "src/api/validation.py:42-88",
  "citations": [
    {
      "path": "src/api/validation.py",
      "start_line": 42,
      "end_line": 88,
      "reason": "request validation entrypoint"
    }
  ],
  "turns_used": 4,
  "truncated": false,
  "warnings": []
}
```

## Exit Codes

- `0`: Success.
- `2`: CLI usage or validation error.
- `3`: Configuration error.
- `4`: Repository/root safety error.
- `5`: Endpoint error.
- `6`: Exploration failed before final answer.

## Error Output

Errors are written to stderr and must not include unrestricted file contents or
secret values.

Example:

```text
CONFIG_MISSING_ENDPOINT: FASTCONTEXT_BASE_URL is required
```
