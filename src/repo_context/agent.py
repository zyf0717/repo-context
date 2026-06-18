from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, cast

from repo_context.config import Settings
from repo_context.llm import ChatClient
from repo_context.logging import TrajectoryRecorder
from repo_context.tools import read_file, repo_glob, repo_grep
from repo_context.types import (
    Citation,
    ExploreRequest,
    ExplorerError,
    ExploreResult,
    ToolCall,
    ToolObservation,
)

ToolName = Literal["read_file", "repo_glob", "repo_grep"]

ALLOWED_TOOLS: set[ToolName] = {"read_file", "repo_glob", "repo_grep"}
CITATION_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+)"
    r":(?P<start>[1-9][0-9]*)(?:-(?P<end>[1-9][0-9]*))?"
)


def explore(
    request: ExploreRequest,
    settings: Settings,
    *,
    client: ChatClient | None = None,
) -> ExploreResult:
    request.validate()
    settings.require_endpoint()
    repo_root = request.repo_root.resolve()
    effective_max_turns = min(request.max_turns, settings.max_turns)
    recorder = TrajectoryRecorder(settings.traj_dir, request)
    owns_client = client is None
    chat_client = client or ChatClient(settings)
    messages = _initial_messages(request)
    tools = tool_schemas()
    truncated = False
    warnings: list[str] = []

    try:
        for turn in range(1, effective_max_turns + 1):
            response = chat_client.chat_completion(messages=messages, tools=tools)
            message = _extract_message(response)
            recorder.record_model_turn(turn, message)
            tool_calls = _extract_tool_calls(message)
            if not tool_calls:
                answer = str(message.get("content") or "").strip()
                citations = extract_citations(answer)
                if request.citation and not citations:
                    warnings.append("final answer did not include parseable citations")
                result = ExploreResult(
                    query=request.query,
                    repo_root=str(repo_root),
                    answer=answer,
                    citations=citations,
                    turns_used=turn,
                    truncated=truncated,
                    warnings=warnings,
                )
                recorder.finish(result=result)
                return result

            messages.append(_assistant_tool_message(message))
            for tool_call in tool_calls:
                observation = _execute_tool_call(
                    tool_call,
                    repo_root=repo_root,
                    settings=settings,
                )
                observation.tool_call_id = tool_call.id
                truncated = truncated or observation.truncated
                recorder.record_observation(turn, tool_call.name, observation)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": json.dumps(observation.to_dict(), sort_keys=True),
                    }
                )
        error = ExplorerError(
            "MAX_TURNS_EXCEEDED",
            "Exploration exceeded the configured maximum turns",
            details={"max_turns": effective_max_turns},
        )
        raise error
    except ExplorerError as exc:
        recorder.finish(error=exc)
        raise
    finally:
        if owns_client:
            chat_client.close()


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a bounded line range from a repository file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer", "minimum": 1},
                        "end_line": {"type": "integer", "minimum": 1},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "repo_glob",
                "description": "List repository files matching a glob pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "repo_grep",
                "description": (
                    "Search repository text files with a regular expression."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "glob": {"type": "string"},
                        "max_results": {"type": "integer", "minimum": 1},
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def format_text_result(result: ExploreResult, *, citation: bool) -> str:
    if not citation or not result.citations:
        return result.answer
    citation_lines = [citation_item.label() for citation_item in result.citations]
    answer_lines = [
        line.strip()
        for line in result.answer.splitlines()
        if line.strip() and line.strip() not in citation_lines
    ]
    if not answer_lines:
        return "\n".join(citation_lines)
    return "\n".join([*citation_lines, "", *answer_lines])


def extract_citations(answer: str) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, int, int | None]] = set()
    for match in CITATION_RE.finditer(answer):
        path = match.group("path")
        start = int(match.group("start"))
        end_text = match.group("end")
        end = int(end_text) if end_text is not None else start
        key = (path, start, end)
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(path=path, start_line=start, end_line=end))
    return citations


def _initial_messages(request: ExploreRequest) -> list[dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": (
                "You answer focused questions about a local repository. "
                "Use only the provided read-only tools. Return compact "
                "repository-relative citations as path:start-end."
            ),
        },
        {"role": "user", "content": request.query},
    ]


def _extract_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ExplorerError("ENDPOINT_BAD_RESPONSE", "Endpoint response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ExplorerError(
            "ENDPOINT_BAD_RESPONSE", "Endpoint choice must be an object"
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise ExplorerError(
            "ENDPOINT_BAD_RESPONSE", "Endpoint message must be an object"
        )
    return cast(dict[str, Any], message)


def _extract_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    raw_calls = message.get("tool_calls")
    if raw_calls is None:
        return []
    if not isinstance(raw_calls, list):
        raise ExplorerError("ENDPOINT_BAD_RESPONSE", "tool_calls must be a list")
    calls: list[ToolCall] = []
    for raw_call in raw_calls:
        calls.append(_parse_tool_call(raw_call))
    return calls


def _parse_tool_call(raw_call: object) -> ToolCall:
    if not isinstance(raw_call, dict):
        raise ExplorerError("ENDPOINT_BAD_RESPONSE", "tool call must be an object")
    call_id = raw_call.get("id")
    function = raw_call.get("function")
    if not isinstance(call_id, str) or not isinstance(function, dict):
        raise ExplorerError("ENDPOINT_BAD_RESPONSE", "tool call is missing id/function")
    name = function.get("name")
    if not isinstance(name, str) or name not in ALLOWED_TOOLS:
        raise ExplorerError(
            "UNSUPPORTED_TOOL_CALL",
            "Endpoint requested an unsupported tool",
            details={"tool": name or "<missing>"},
        )
    raw_arguments = function.get("arguments", "{}")
    if not isinstance(raw_arguments, str):
        raise ExplorerError("ENDPOINT_BAD_RESPONSE", "tool arguments must be JSON text")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ExplorerError(
            "ENDPOINT_BAD_RESPONSE",
            "tool arguments must be valid JSON",
        ) from exc
    if not isinstance(arguments, dict):
        raise ExplorerError("ENDPOINT_BAD_RESPONSE", "tool arguments must be an object")
    return ToolCall(
        id=call_id,
        name=name,
        arguments=cast(dict[str, object], arguments),
    )


def _assistant_tool_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls"),
    }


def _execute_tool_call(
    tool_call: ToolCall,
    *,
    repo_root: Path,
    settings: Settings,
) -> ToolObservation:
    try:
        if tool_call.name == "read_file":
            return read_file(
                repo_root=repo_root,
                path=_required_str(tool_call.arguments, "path"),
                start_line=_optional_int(tool_call.arguments, "start_line"),
                end_line=_optional_int(tool_call.arguments, "end_line"),
                max_bytes=settings.max_read_bytes,
                ignore=settings.ignore,
            )
        if tool_call.name == "repo_glob":
            return repo_glob(
                repo_root=repo_root,
                pattern=_required_str(tool_call.arguments, "pattern"),
                max_results=settings.max_grep_results,
                ignore=settings.ignore,
            )
        if tool_call.name == "repo_grep":
            requested_max = _optional_int(tool_call.arguments, "max_results")
            return repo_grep(
                repo_root=repo_root,
                pattern=_required_str(tool_call.arguments, "pattern"),
                glob=_optional_str(tool_call.arguments, "glob") or "**/*",
                max_results=requested_max or settings.max_grep_results,
                configured_max_results=settings.max_grep_results,
                ignore=settings.ignore,
            )
    except ExplorerError as exc:
        return ToolObservation.from_error(exc, tool_call_id=tool_call.id)
    raise AssertionError(f"unhandled tool: {tool_call.name}")


def _required_str(arguments: dict[str, object], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ExplorerError("INVALID_TOOL_ARGUMENTS", f"{key} is required")
    return value


def _optional_str(arguments: dict[str, object], key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ExplorerError("INVALID_TOOL_ARGUMENTS", f"{key} must be a string")
    return value


def _optional_int(arguments: dict[str, object], key: str) -> int | None:
    value = arguments.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExplorerError("INVALID_TOOL_ARGUMENTS", f"{key} must be an integer")
    return value
