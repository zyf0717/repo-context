from __future__ import annotations

from pathlib import Path

import pytest

from repo_context import config as config_module
from repo_context.config import SettingsOverrides, load_settings
from repo_context.types import ExplorerError

FASTCONTEXT_ENV_KEYS = (
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
    "FASTCONTEXT_MAX_PARALLEL_TOOLS",
)


def _clear_config_env(monkeypatch: pytest.MonkeyPatch, project_root: Path) -> None:
    for key in FASTCONTEXT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config_module, "_project_root", lambda: project_root)
    monkeypatch.chdir(project_root)


def test_config_defaults_include_latency_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)

    settings = load_settings(repo_root=tmp_path)

    assert settings.timeout_seconds == 120.0
    assert settings.max_observation_chars == 6000
    assert settings.max_read_lines == 120
    assert settings.max_completion_tokens == 512
    assert settings.temperature == 0.0
    assert settings.max_parallel_tools == 4


def test_config_precedence_defaults_yaml_dotenv_env_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)
    (tmp_path / "config.yaml").write_text(
        """
model:
  base_url: "http://yaml/v1"
  model: "yaml-model"
  timeout_seconds: 45
  max_completion_tokens: 300
  temperature: 0.3

explorer:
  max_turns: 3
  ignore: ["vendor"]

tools:
  max_read_bytes: 10
  max_grep_results: 11
  max_observation_chars: 12
  max_read_lines: 13
  max_parallel_tools: 15
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        """
FASTCONTEXT_BASE_URL=http://dotenv/v1
FASTCONTEXT_MODEL=dotenv-model
FASTCONTEXT_MAX_TURNS=4
FASTCONTEXT_MAX_READ_LINES=14
FASTCONTEXT_TEMPERATURE=0.2
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("FASTCONTEXT_BASE_URL", "http://env/v1")
    monkeypatch.setenv("FASTCONTEXT_MAX_PARALLEL_TOOLS", "16")
    monkeypatch.setenv("FASTCONTEXT_TEMPERATURE", "0.1")

    settings = load_settings(
        repo_root=tmp_path,
        overrides=SettingsOverrides(
            max_turns=5,
            max_read_bytes=20,
            max_observation_chars=30,
            max_parallel_tools=17,
        ),
    )

    assert settings.base_url == "http://env/v1"
    assert settings.model == "dotenv-model"
    assert settings.max_turns == 5
    assert settings.max_read_bytes == 20
    assert settings.max_grep_results == 11
    assert settings.ignore == ["vendor"]
    assert settings.timeout_seconds == 45.0
    assert settings.max_observation_chars == 30
    assert settings.max_read_lines == 14
    assert settings.max_completion_tokens == 300
    assert settings.temperature == 0.1
    assert settings.max_parallel_tools == 17


def test_target_root_config_and_env_are_not_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _clear_config_env(monkeypatch, project_root)
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "config.yaml").write_text(
        """
model:
  base_url: "http://target/v1"
  model: "target-model"
""",
        encoding="utf-8",
    )
    (repo / ".env").write_text(
        "FASTCONTEXT_BASE_URL=http://target-env/v1\n"
        "FASTCONTEXT_MODEL=target-env-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)

    settings = load_settings(repo_root=repo)

    assert settings.base_url == ""
    assert settings.model == ""


def test_invocation_local_config_and_env_are_not_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _clear_config_env(monkeypatch, project_root)
    repo = tmp_path / "target"
    repo.mkdir()
    caller = tmp_path / "caller"
    caller.mkdir()
    (caller / "config.yaml").write_text(
        """
model:
  base_url: "http://caller-cwd/v1"
  model: "caller-model"
""",
        encoding="utf-8",
    )
    (caller / ".env").write_text(
        "FASTCONTEXT_BASE_URL=http://caller-env/v1\n"
        "FASTCONTEXT_MODEL=caller-env-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(caller)

    settings = load_settings(repo_root=repo)

    assert settings.base_url == ""
    assert settings.model == ""


def test_yaml_traj_dir_is_project_root_relative_from_external_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _clear_config_env(monkeypatch, project_root)
    repo = tmp_path / "target"
    repo.mkdir()
    caller = tmp_path / "caller"
    caller.mkdir()
    (project_root / "config.yaml").write_text(
        """
explorer:
  traj_dir: ".fastcontext"
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(caller)

    settings = load_settings(repo_root=repo)

    assert settings.traj_dir == project_root / ".fastcontext"


def test_env_traj_dir_override_is_used_as_supplied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _clear_config_env(monkeypatch, project_root)
    (project_root / "config.yaml").write_text(
        """
explorer:
  traj_dir: ".fastcontext"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("FASTCONTEXT_TRAJ_DIR", "env-traj")

    settings = load_settings(repo_root=tmp_path / "target")

    assert settings.traj_dir == Path("env-traj")


def test_project_root_env_supports_quotes_comments_and_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        """
export FASTCONTEXT_BASE_URL="http://dotenv/v1"
FASTCONTEXT_MODEL='dotenv-model'
FASTCONTEXT_MAX_TURNS=4 # local override
""",
        encoding="utf-8",
    )

    settings = load_settings(repo_root=tmp_path)

    assert settings.base_url == "http://dotenv/v1"
    assert settings.model == "dotenv-model"
    assert settings.max_turns == 4


def test_repo_context_config_env_is_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)
    external = tmp_path / "external.yaml"
    external.write_text(
        """
model:
  base_url: "http://external/v1"
  model: "external-model"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("REPO_CONTEXT_CONFIG", str(external))

    settings = load_settings(repo_root=tmp_path)

    assert settings.base_url == ""
    assert settings.model == ""


def test_invalid_dotenv_line_raises_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text("not-an-assignment\n", encoding="utf-8")

    with pytest.raises(ExplorerError) as exc_info:
        load_settings(repo_root=tmp_path / "target")

    assert exc_info.value.code == "CONFIG_INVALID"


def test_invalid_integer_env_raises_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)
    monkeypatch.setenv("FASTCONTEXT_MAX_TURNS", "nope")

    with pytest.raises(ExplorerError) as exc_info:
        load_settings(repo_root=tmp_path)

    assert exc_info.value.code == "CONFIG_INVALID"


def test_max_parallel_tools_must_be_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch, tmp_path)
    monkeypatch.setenv("FASTCONTEXT_MAX_PARALLEL_TOOLS", "0")

    with pytest.raises(ExplorerError) as exc_info:
        load_settings(repo_root=tmp_path)

    assert exc_info.value.code == "CONFIG_INVALID"
    assert exc_info.value.details == {"max_parallel_tools": 0}
