from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_context import cli
from repo_context.config import Settings
from repo_context.types import Citation, ExploreRequest, ExploreResult


def test_cli_text_output_is_citation_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_explore(request: ExploreRequest, settings: Settings) -> ExploreResult:
        assert request.query == "Find validation"
        assert settings.max_turns == 6
        return ExploreResult(
            query=request.query,
            repo_root=str(repo),
            answer="src/api/validation.py:1-2\nValidation entrypoint.",
            citations=[Citation("src/api/validation.py", 1, 2)],
            turns_used=1,
        )

    monkeypatch.setattr(cli, "explore", fake_explore)

    code = cli.main(["explore", "--query", "Find validation", "--repo", str(repo)])

    assert code == 0
    assert capsys.readouterr().out.splitlines()[0] == "src/api/validation.py:1-2"


def test_cli_json_output_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_explore(request: ExploreRequest, settings: Settings) -> ExploreResult:
        return ExploreResult(
            query=request.query,
            repo_root=str(repo),
            answer="src/api/validation.py:1",
            citations=[Citation("src/api/validation.py", 1, 1)],
            turns_used=1,
        )

    monkeypatch.setattr(cli, "explore", fake_explore)

    code = cli.main(
        [
            "explore",
            "--query",
            "Find validation",
            "--repo",
            str(repo),
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["query"] == "Find validation"
    assert payload["citations"][0]["path"] == "src/api/validation.py"


def test_cli_missing_endpoint_is_configuration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key in ("FASTCONTEXT_BASE_URL", "FASTCONTEXT_MODEL"):
        monkeypatch.delenv(key, raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()

    code = cli.main(["explore", "--query", "Find validation", "--repo", str(repo)])

    captured = capsys.readouterr()
    assert code == 3
    assert "CONFIG_MISSING_ENDPOINT" in captured.err

