from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pytest

from repo_context.agent import NO_CITATIONS_FOUND, explore, format_text_result
from repo_context.config import SettingsOverrides, load_settings
from repo_context.types import Citation, ExploreRequest, ExplorerError

pytestmark = pytest.mark.e2e

RUN_E2E_ENV = "REPO_CONTEXT_RUN_E2E"


@dataclass(frozen=True, slots=True)
class PromptCase:
    name: str
    query: str
    expected_path: str
    expected_text: str


PROMPT_CASES = (
    PromptCase(
        name="config observation cap",
        query=(
            "In src/repo_context/config.py, find where the Settings model defines "
            "`max_observation_chars`. Return citations only."
        ),
        expected_path="src/repo_context/config.py",
        expected_text="max_observation_chars",
    ),
    PromptCase(
        name="llm completion limits",
        query=(
            "In src/repo_context/llm.py, find where chat completion payloads set "
            "`max_tokens`. Return citations only."
        ),
        expected_path="src/repo_context/llm.py",
        expected_text="max_tokens",
    ),
    PromptCase(
        name="path safety class",
        query=(
            "In src/repo_context/tools/safety.py, find the definition of "
            "`PathSafety`. Return citations only."
        ),
        expected_path="src/repo_context/tools/safety.py",
        expected_text="class PathSafety",
    ),
    PromptCase(
        name="read tool entrypoint",
        query=(
            "In src/repo_context/tools/read.py, find the `read_file` function "
            "definition. Return citations only."
        ),
        expected_path="src/repo_context/tools/read.py",
        expected_text="def read_file",
    ),
    PromptCase(
        name="mcp handler",
        query=(
            "In src/repo_context/mcp_server.py, find the "
            "`explore_repository_handler` function definition. Return citations only."
        ),
        expected_path="src/repo_context/mcp_server.py",
        expected_text="def explore_repository_handler",
    ),
)


def test_current_repo_multi_prompt_timing_e2e() -> None:
    if os.environ.get(RUN_E2E_ENV) != "1":
        pytest.skip(f"set {RUN_E2E_ENV}=1 to run endpoint-backed e2e tests")

    repo_root = Path(__file__).resolve().parents[2]
    settings = load_settings(
        repo_root=repo_root,
        overrides=SettingsOverrides(max_turns=6, traj_dir=None),
    )
    try:
        settings.require_endpoint()
    except ExplorerError as exc:
        pytest.skip(f"FastContext endpoint config missing: {exc.code}")

    timings: list[tuple[PromptCase, float, str, int, list[str]]] = []
    total_start = perf_counter()
    for case in PROMPT_CASES:
        started = perf_counter()
        result = explore(
            ExploreRequest(
                query=case.query,
                repo_root=repo_root,
                max_turns=settings.max_turns,
                citation=True,
            ),
            settings,
        )
        elapsed = perf_counter() - started
        rendered = format_text_result(result, citation=True)
        timings.append(
            (case, elapsed, rendered, result.turns_used, list(result.warnings))
        )

        assert result.answer != NO_CITATIONS_FOUND, case.name
        assert result.citations, case.name
        assert rendered == result.answer
        assert result.answer == "\n".join(
            citation.label() for citation in result.citations
        )
        assert any(
            citation.path == case.expected_path for citation in result.citations
        ), case.name
        cited_text = _read_cited_text(
            repo_root=repo_root,
            citations=result.citations,
            expected_path=case.expected_path,
        )
        assert case.expected_text in cited_text, case.name

    total_elapsed = perf_counter() - total_start
    _print_timing_summary(timings, total_elapsed)


def _read_cited_text(
    *,
    repo_root: Path,
    citations: list[Citation],
    expected_path: str,
) -> str:
    chunks: list[str] = []
    for citation in citations:
        if (
            citation.path != expected_path
            or citation.start_line is None
            or citation.end_line is None
        ):
            continue
        lines = (repo_root / citation.path).read_text(encoding="utf-8").splitlines()
        chunks.append("\n".join(lines[citation.start_line - 1 : citation.end_line]))
    return "\n".join(chunks)


def _print_timing_summary(
    timings: list[tuple[PromptCase, float, str, int, list[str]]],
    total_elapsed: float,
) -> None:
    print("\ncurrent-repo multi-prompt e2e timings:")
    for case, elapsed, rendered, turns_used, warnings in timings:
        warning_text = ", ".join(warnings) if warnings else "-"
        print(
            f"- {case.name}: {elapsed:.2f}s, turns={turns_used}, "
            f"citations={rendered}, warnings={warning_text}"
        )
    print(f"total: {total_elapsed:.2f}s")
