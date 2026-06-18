from __future__ import annotations

from pathlib import Path

import pytest

from repo_context.config import SettingsOverrides, load_settings
from repo_context.types import ExplorerError

ENV_KEYS = (
    "FASTCONTEXT_BASE_URL",
    "FASTCONTEXT_MODEL",
    "FASTCONTEXT_API_KEY",
    "FASTCONTEXT_MAX_TURNS",
    "FASTCONTEXT_MAX_READ_BYTES",
    "FASTCONTEXT_MAX_GREP_RESULTS",
    "FASTCONTEXT_TRAJ_DIR",
    "FASTCONTEXT_TIMEOUT_SECONDS",
    "FASTCONTEXT_MAX_OBSERVATION_CHARS",
    "FASTCONTEXT_MAX_READ_LINES",
    "FASTCONTEXT_MAX_COMPLETION_TOKENS",
    "FASTCONTEXT_TEMPERATURE",
)


def test_config_defaults_include_latency_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(repo_root=tmp_path)

    assert settings.timeout_seconds == 120.0
    assert settings.max_observation_chars == 6000
    assert settings.max_read_lines == 120
    assert settings.max_completion_tokens == 512
    assert settings.temperature == 0.0


def test_config_precedence_defaults_toml_env_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".repo-context.toml").write_text(
        """
[model]
base_url = "http://toml/v1"
model = "toml-model"
timeout_seconds = 45
max_completion_tokens = 300
temperature = 0.3

[explorer]
max_turns = 3
ignore = ["vendor"]

[tools]
max_read_bytes = 10
max_grep_results = 11
max_observation_chars = 12
max_read_lines = 13
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("FASTCONTEXT_BASE_URL", "http://env/v1")
    monkeypatch.setenv("FASTCONTEXT_MAX_TURNS", "4")
    monkeypatch.setenv("FASTCONTEXT_MAX_READ_LINES", "14")
    monkeypatch.setenv("FASTCONTEXT_TEMPERATURE", "0.1")

    settings = load_settings(
        repo_root=tmp_path,
        overrides=SettingsOverrides(
            max_turns=5,
            max_read_bytes=20,
            max_observation_chars=30,
        ),
    )

    assert settings.base_url == "http://env/v1"
    assert settings.model == "toml-model"
    assert settings.max_turns == 5
    assert settings.max_read_bytes == 20
    assert settings.max_grep_results == 11
    assert settings.ignore == ["vendor"]
    assert settings.timeout_seconds == 45.0
    assert settings.max_observation_chars == 30
    assert settings.max_read_lines == 14
    assert settings.max_completion_tokens == 300
    assert settings.temperature == 0.1


def test_invalid_integer_env_raises_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("FASTCONTEXT_MAX_TURNS", "nope")

    with pytest.raises(ExplorerError) as exc_info:
        load_settings(repo_root=tmp_path)

    assert exc_info.value.code == "CONFIG_INVALID"
