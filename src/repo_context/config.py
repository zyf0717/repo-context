from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from repo_context.types import ExplorerError


@dataclass(frozen=True, slots=True)
class Settings:
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    max_turns: int = 6
    max_read_bytes: int = 12_000
    max_grep_results: int = 50
    traj_dir: Path | None = None
    ignore: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0

    def require_endpoint(self) -> None:
        if not self.base_url:
            raise ExplorerError(
                "CONFIG_MISSING_ENDPOINT",
                "FASTCONTEXT_BASE_URL is required",
            )
        if not self.model:
            raise ExplorerError(
                "CONFIG_INVALID",
                "FASTCONTEXT_MODEL is required",
            )


@dataclass(frozen=True, slots=True)
class SettingsOverrides:
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_turns: int | None = None
    max_read_bytes: int | None = None
    max_grep_results: int | None = None
    traj_dir: Path | None = None
    ignore: list[str] | None = None


def load_settings(
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
    overrides: SettingsOverrides | None = None,
) -> Settings:
    settings = Settings()
    toml_path = config_path or _default_config_path(repo_root)
    if toml_path is not None and toml_path.exists():
        settings = _apply_toml(settings, toml_path)
    settings = _apply_env(settings, os.environ)
    if overrides is not None:
        settings = _apply_overrides(settings, overrides)
    _validate_settings(settings)
    return settings


def _default_config_path(repo_root: Path | None) -> Path | None:
    root = repo_root if repo_root is not None else Path.cwd()
    return root / ".repo-context.toml"


def _apply_toml(settings: Settings, path: Path) -> Settings:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ExplorerError(
            "CONFIG_INVALID",
            f"Invalid TOML config: {path}",
            details={"error": str(exc)},
        ) from exc

    model = _section(data, "model")
    explorer = _section(data, "explorer")
    tools = _section(data, "tools")

    return replace(
        settings,
        base_url=str(model.get("base_url", settings.base_url) or ""),
        model=str(model.get("model", settings.model) or ""),
        api_key=_optional_str(model.get("api_key", settings.api_key)),
        max_turns=_int_value(
            explorer.get("max_turns", settings.max_turns), "max_turns"
        ),
        max_read_bytes=_int_value(
            tools.get("max_read_bytes", settings.max_read_bytes), "max_read_bytes"
        ),
        max_grep_results=_int_value(
            tools.get("max_grep_results", settings.max_grep_results),
            "max_grep_results",
        ),
        traj_dir=_optional_path(
            explorer.get("traj_dir", settings.traj_dir)
            or data.get("traj_dir")
            or settings.traj_dir
        ),
        ignore=_str_list(explorer.get("ignore", settings.ignore), "ignore"),
    )


def _apply_env(settings: Settings, env: os._Environ[str]) -> Settings:
    return replace(
        settings,
        base_url=env.get("FASTCONTEXT_BASE_URL", settings.base_url),
        model=env.get("FASTCONTEXT_MODEL", settings.model),
        api_key=env.get("FASTCONTEXT_API_KEY", settings.api_key),
        max_turns=_env_int(env, "FASTCONTEXT_MAX_TURNS", settings.max_turns),
        max_read_bytes=_env_int(
            env, "FASTCONTEXT_MAX_READ_BYTES", settings.max_read_bytes
        ),
        max_grep_results=_env_int(
            env, "FASTCONTEXT_MAX_GREP_RESULTS", settings.max_grep_results
        ),
        traj_dir=_optional_path(env.get("FASTCONTEXT_TRAJ_DIR")) or settings.traj_dir,
    )


def _apply_overrides(settings: Settings, overrides: SettingsOverrides) -> Settings:
    return replace(
        settings,
        base_url=overrides.base_url
        if overrides.base_url is not None
        else settings.base_url,
        model=overrides.model if overrides.model is not None else settings.model,
        api_key=overrides.api_key
        if overrides.api_key is not None
        else settings.api_key,
        max_turns=overrides.max_turns
        if overrides.max_turns is not None
        else settings.max_turns,
        max_read_bytes=overrides.max_read_bytes
        if overrides.max_read_bytes is not None
        else settings.max_read_bytes,
        max_grep_results=overrides.max_grep_results
        if overrides.max_grep_results is not None
        else settings.max_grep_results,
        traj_dir=overrides.traj_dir
        if overrides.traj_dir is not None
        else settings.traj_dir,
        ignore=overrides.ignore if overrides.ignore is not None else settings.ignore,
    )


def _validate_settings(settings: Settings) -> None:
    int_fields = {
        "max_turns": settings.max_turns,
        "max_read_bytes": settings.max_read_bytes,
        "max_grep_results": settings.max_grep_results,
    }
    for name, value in int_fields.items():
        if value <= 0:
            raise ExplorerError(
                "CONFIG_INVALID",
                f"{name} must be positive",
                details={name: value},
            )


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ExplorerError("CONFIG_INVALID", f"[{name}] must be a table")
    return value


def _env_int(env: os._Environ[str], name: str, default: int) -> int:
    value = env.get(name)
    return default if value is None else _int_value(value, name)


def _int_value(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ExplorerError("CONFIG_INVALID", f"{name} must be an integer")
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ExplorerError("CONFIG_INVALID", f"{name} must be an integer")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ExplorerError("CONFIG_INVALID", f"{name} must be an integer") from exc
    return parsed


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_path(value: object) -> Path | None:
    if value is None or value == "":
        return None
    return Path(str(value))


def _str_list(value: object, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ExplorerError("CONFIG_INVALID", f"{name} must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ExplorerError("CONFIG_INVALID", f"{name} entries must be strings")
    return list(value)
