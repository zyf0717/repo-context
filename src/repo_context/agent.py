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
SOURCE_LINES_RE = re.compile(
    r"`?(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)`?"
    r",?\s+lines?\s+"
    r"(?P<start>[1-9][0-9]*)"
    r"(?:\s*[-\u2013\u2014]\s*(?P<end>[1-9][0-9]*))?",
    re.IGNORECASE,
)
LINES_OF_SOURCE_RE = re.compile(
    r"lines?\s+"
    r"(?P<start>[1-9][0-9]*)"
    r"(?:\s*[-\u2013\u2014]\s*(?P<end>[1-9][0-9]*))?"
    r"\s+of\s+"
    r"`?(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)`?",
    re.IGNORECASE,
)
MARKDOWN_FILE_LINES_RE = re.compile(
    r"File\**\s*:\s*`?"
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)`?"
    r".{0,120}?"
    r"Lines\**\s*:\s*"
    r"(?P<start>[1-9][0-9]*)"
    r"(?:\s*[-\u2013\u2014]\s*(?P<end>[1-9][0-9]*))?",
    re.IGNORECASE | re.DOTALL,
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
    file_sample = repo_glob(
        repo_root=repo_root,
        pattern="**/*",
        max_results=settings.max_grep_results,
        ignore=settings.ignore,
    )
    messages = _initial_messages(request, file_sample)
    tools = tool_schemas()
    truncated = False
    warnings: list[str] = []
    last_content = ""
    read_observations: list[ToolObservation] = []

    try:
        for turn in range(1, effective_max_turns + 1):
            response = chat_client.chat_completion(messages=messages, tools=tools)
            message = _extract_message(response)
            recorder.record_model_turn(turn, message)
            content_text = str(message.get("content") or "").strip()
            if content_text:
                last_content = content_text
            tool_calls = _extract_tool_calls(message)
            if not tool_calls:
                answer = content_text
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
                if observation.ok and observation.path and observation.line_range:
                    read_observations.append(observation)
                recorder.record_observation(turn, tool_call.name, observation)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": json.dumps(
                            _model_observation_payload(observation),
                            sort_keys=True,
                        ),
                    }
                )
        if last_content:
            citations = extract_citations(last_content) or _citations_from_observations(
                last_content, read_observations
            )
            warnings.append("max turns exceeded after partial answer")
            if request.citation and not citations:
                warnings.append("partial answer did not include parseable citations")
            result = ExploreResult(
                query=request.query,
                repo_root=str(repo_root),
                answer=last_content,
                citations=citations,
                turns_used=effective_max_turns,
                truncated=truncated,
                warnings=warnings,
            )
            recorder.finish(result=result)
            return result
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
                        "path": {
                            "type": "string",
                            "description": (
                                "Repository-relative file path with no leading "
                                "slash, e.g. src/repo_context/types.py."
                            ),
                        },
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
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": (
                                "Repository-relative glob with no leading "
                                "slash, e.g. src/**/*.py."
                            ),
                        }
                    },
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
                        "glob": {
                            "type": "string",
                            "description": (
                                "Optional repository-relative glob with no "
                                "leading slash, e.g. src/**/*.py."
                            ),
                        },
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
    for regex in (
        CITATION_RE,
        SOURCE_LINES_RE,
        LINES_OF_SOURCE_RE,
        MARKDOWN_FILE_LINES_RE,
    ):
        for match in regex.finditer(answer):
            citation = _citation_from_match(match)
            key = (citation.path, citation.start_line or 0, citation.end_line)
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
    return citations


def _citation_from_match(match: re.Match[str]) -> Citation:
        path = match.group("path")
        start = int(match.group("start"))
        end_text = match.group("end")
        end = int(end_text) if end_text is not None else start
        return Citation(path=path, start_line=start, end_line=end)


def _citations_from_observations(
    answer: str,
    observations: list[ToolObservation],
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, int | None, int | None]] = set()
    for observation in observations:
        if observation.path is None or observation.line_range is None:
            continue
        if observation.path not in answer and Path(observation.path).name not in answer:
            continue
        start, end = _parse_line_range(observation.line_range)
        key = (observation.path, start, end)
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(observation.path, start, end))
    return citations[:5]


def _parse_line_range(line_range: str) -> tuple[int | None, int | None]:
    start_text, _, end_text = line_range.partition("-")
    try:
        start = int(start_text)
    except ValueError:
        return None, None
    if not end_text:
        return start, start
    try:
        end = int(end_text)
    except ValueError:
        return start, start
    return start, end


def _initial_messages(
    request: ExploreRequest,
    file_sample: ToolObservation,
) -> list[dict[str, Any]]:
    files = "\n".join(f"- {path}" for path in file_sample.matches)
    if not files:
        files = "- <no safe files listed>"
    truncated_note = (
        "\nThe file list is truncated; use repo_glob/repo_grep for more paths."
        if file_sample.truncated
        else ""
    )
    output_contract = (
        "Final answer format is strict: return only 1-5 lines of "
        "path:start-end citations. Do not include prose, Markdown, code "
        "blocks, bullets, or explanations. If no citation is supported, "
        "return exactly NO_CITATIONS_FOUND."
        if request.citation
        else "Final answer may include concise prose with file-line citations."
    )
    return [
        {
            "role": "system",
            "content": (
                "You answer focused questions about a local repository. "
                "Use only the provided read-only tools. Return compact "
                "repository-relative citations as path:start-end. Use the "
                "listed repository paths as grounding and do not invent paths. "
                "Tool path arguments must be repository-relative with no "
                "leading slash and must not include the repository directory "
                "name as a prefix. Example: use src/app.py, not "
                "/repo/src/app.py or repo/src/app.py. "
                "If a read returns PATH_NOT_FOUND, INVALID_TOOL_ARGUMENTS, or "
                "PATH_OUTSIDE_ROOT, correct the path once using the known file "
                "list or broaden search; do not repeat the same failing call. "
                f"{output_contract}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"{request.query}\n\n"
                f"Known safe repository files:\n{files}{truncated_note}"
            ),
        },
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


def _model_observation_payload(observation: ToolObservation) -> dict[str, object]:
    payload = observation.to_dict()
    if (
        observation.ok
        and observation.content is not None
        and observation.line_range is not None
    ):
        payload["content"] = _with_line_numbers(
            observation.content,
            observation.line_range,
        )
    return payload


def _with_line_numbers(content: str, line_range: str) -> str:
    start, _ = _parse_line_range(line_range)
    line_number = start or 1
    lines: list[str] = []
    for offset, line in enumerate(content.splitlines(), start=0):
        lines.append(f"{line_number + offset}: {line}")
    if content.endswith("\n"):
        return "\n".join(lines) + "\n"
    return "\n".join(lines)


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
