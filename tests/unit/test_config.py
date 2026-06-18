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
)


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

[explorer]
max_turns = 3
ignore = ["vendor"]

[tools]
max_read_bytes = 10
max_grep_results = 11
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("FASTCONTEXT_BASE_URL", "http://env/v1")
    monkeypatch.setenv("FASTCONTEXT_MAX_TURNS", "4")

    settings = load_settings(
        repo_root=tmp_path,
        overrides=SettingsOverrides(max_turns=5, max_read_bytes=20),
    )

    assert settings.base_url == "http://env/v1"
    assert settings.model == "toml-model"
    assert settings.max_turns == 5
    assert settings.max_read_bytes == 20
    assert settings.max_grep_results == 11
    assert settings.ignore == ["vendor"]


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

