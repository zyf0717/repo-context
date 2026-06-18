from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from repo_context.agent import explore
from repo_context.config import Settings
from repo_context.llm import ChatClient
from repo_context.types import ExploreRequest, ExplorerError


def test_mock_endpoint_drives_glob_grep_read_loop(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "api").mkdir(parents=True)
    (repo / "src" / "api" / "validation.py").write_text(
        "def validate_request(payload):\n    return bool(payload)\n",
        encoding="utf-8",
    )
    responses: Iterator[dict[str, object]] = iter(
        [
            _tool_response("call_1", "repo_glob", {"pattern": "src/**/*.py"}),
            _tool_response(
                "call_2",
                "repo_grep",
                {"pattern": "validate_request", "glob": "src/**/*.py"},
            ),
            _tool_response(
                "call_3",
                "read_file",
                {"path": "src/api/validation.py", "start_line": 1, "end_line": 2},
            ),
            _message_response("src/api/validation.py:1-2\nValidation entrypoint."),
        ]
    )
    seen_payloads: list[dict[str, object]] = []
    settings = Settings(base_url="http://test/v1", model="test-model")
    client = ChatClient(settings, transport=_mock_transport(responses, seen_payloads))

    result = explore(
        ExploreRequest(query="Find validation", repo_root=repo),
        settings,
        client=client,
    )

    assert result.citations[0].path == "src/api/validation.py"
    assert result.citations[0].start_line == 1
    assert result.turns_used == 4
    assert any(
        message.get("role") == "tool"
        for payload in seen_payloads[1:]
        for message in cast(list[dict[str, Any]], payload["messages"])
    )


def test_unsupported_tool_call_is_fatal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    settings = Settings(base_url="http://test/v1", model="test-model")
    responses: Iterator[dict[str, object]] = iter(
        [_tool_response("call_1", "write_file", {"path": "x"})]
    )
    client = ChatClient(settings, transport=_mock_transport(responses, []))

    with pytest.raises(ExplorerError) as exc_info:
        explore(ExploreRequest(query="write", repo_root=repo), settings, client=client)

    assert exc_info.value.code == "UNSUPPORTED_TOOL_CALL"


def test_trajectory_log_omits_denied_file_content(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("SECRET_TOKEN=abc", encoding="utf-8")
    traj_dir = tmp_path / "traj"
    settings = Settings(
        base_url="http://test/v1",
        model="test-model",
        traj_dir=traj_dir,
    )
    responses: Iterator[dict[str, object]] = iter(
        [
            _tool_response("call_1", "read_file", {"path": ".env"}),
            _message_response("No accessible citation."),
        ]
    )
    client = ChatClient(settings, transport=_mock_transport(responses, []))

    explore(ExploreRequest(query="read env", repo_root=repo), settings, client=client)

    logs = list(traj_dir.glob("*.json"))
    assert len(logs) == 1
    assert "SECRET_TOKEN" not in logs[0].read_text(encoding="utf-8")


def _mock_transport(
    responses: Iterator[dict[str, object]],
    seen_payloads: list[dict[str, object]],
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=next(responses))

    return httpx.MockTransport(handler)


def _tool_response(
    call_id: str,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ]
    }


def _message_response(content: str) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }
