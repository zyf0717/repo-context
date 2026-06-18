from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from repo_context import mcp_server
from repo_context.config import Settings
from repo_context.mcp_server import explore_repository_handler
from repo_context.types import Citation, ExploreRequest, ExploreResult


def test_mcp_handler_delegates_to_core(tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    settings = Settings(base_url="http://test/v1", model="test-model")

    def fake_core(request: ExploreRequest, core_settings: Settings) -> ExploreResult:
        captured["request"] = request
        captured["settings"] = core_settings
        return ExploreResult(
            query=request.query,
            repo_root=str(tmp_path),
            answer="src/api/validation.py:1",
            citations=[Citation("src/api/validation.py", 1, 1)],
            turns_used=1,
        )

    result = explore_repository_handler(
        query="Find validation",
        repo_root=str(tmp_path),
        max_turns=2,
        citation=True,
        settings=settings,
        core=fake_core,
    )

    request = captured["request"]
    assert isinstance(request, ExploreRequest)
    assert request.max_turns == 2
    assert result["citations"] == [
        {
            "path": "src/api/validation.py",
            "start_line": 1,
            "end_line": 1,
            "reason": None,
        }
    ]


def test_mcp_handler_returns_structured_error_for_invalid_root(tmp_path: Path) -> None:
    settings = Settings(base_url="http://test/v1", model="test-model")

    result = explore_repository_handler(
        query="Find validation",
        repo_root=str(tmp_path / "missing"),
        settings=settings,
    )

    assert result["error"]["code"] == "REPO_NOT_FOUND"  # type: ignore[index]


def test_mcp_server_registers_explore_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeServer:
        def __init__(self, name: str) -> None:
            self.name = name
            self.tools: dict[str, Callable[..., object]] = {}

        def tool(self) -> Callable[[Callable[..., object]], Callable[..., object]]:
            def decorator(func: Callable[..., object]) -> Callable[..., object]:
                self.tools[func.__name__] = func
                return func

            return decorator

    monkeypatch.setattr(
        mcp_server,
        "import_module",
        lambda name: SimpleNamespace(FastMCP=FakeServer),
    )

    server = mcp_server.create_server()

    assert server.name == "repo-context"
    assert "explore_repository" in server.tools
