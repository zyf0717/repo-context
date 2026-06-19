# Spec 006: Project-Root YAML and Env Configuration

## Summary

`repo-context` configuration is owned by this project, not by the target folder
being inspected and not by the caller's current working directory.

The default config file is `config.yaml` at the `repo-context` project root.
Only project-root `.env` and explicit process environment variables may override
that YAML config. There is no public `--config` option, no
`REPO_CONTEXT_CONFIG`, and no discovery of external YAML or TOML config files.

## Requirements

- The loader MUST read `config.yaml` from the installed/source `repo-context`
  project root when it exists.
- The loader MUST read project-root `.env` after `config.yaml`.
- The loader MUST apply process environment variables after project-root `.env`.
- CLI overrides such as `--max-turns` MAY apply after environment variables.
- The loader MUST NOT inspect the target folder for `config.yaml`,
  `.repo-context.yaml`, `.repo-context.toml`, `.env`, or any other config file.
- The loader MUST NOT inspect the caller's current working directory for config.
- Relative paths in `config.yaml` MUST resolve from the `repo-context` project
  root.
- Environment path overrides MUST be used as supplied.
- The CLI and MCP server MUST NOT expose `--config`.
- `REPO_CONTEXT_CONFIG` MUST NOT be recognized.
- YAML parse errors and invalid `.env` lines MUST return `CONFIG_INVALID`
  without logging secret values.

## Precedence

```text
defaults < repo-context/config.yaml < repo-context/.env < process env < CLI overrides
```

## Acceptance Tests

- A target folder containing `config.yaml` and `.env` does not affect settings.
- A caller working directory containing `config.yaml` and `.env` does not affect
  settings.
- Project-root `.env` overrides project-root `config.yaml`.
- Process environment variables override project-root `.env`.
- `repo-context explore --config ...` is rejected as a CLI usage error.
- MCP launch has no `--config` option and still uses the shared loader.
