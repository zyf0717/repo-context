from __future__ import annotations

from repo_context.agent import extract_citations


def test_extract_colon_range_citation() -> None:
    citations = extract_citations("src/repo_context/types.py:129-158")

    assert citations[0].path == "src/repo_context/types.py"
    assert citations[0].start_line == 129
    assert citations[0].end_line == 158


def test_extract_source_lines_citation_with_en_dash() -> None:
    citations = extract_citations(
        "Source: `src/repo_context/types.py`, lines 140\u2013166."
    )

    assert citations[0].path == "src/repo_context/types.py"
    assert citations[0].start_line == 140
    assert citations[0].end_line == 166


def test_extract_lines_of_source_citation() -> None:
    citations = extract_citations(
        "It is located at lines 135-159 of `src/repo_context/types.py`."
    )

    assert citations[0].path == "src/repo_context/types.py"
    assert citations[0].start_line == 135
    assert citations[0].end_line == 159


def test_extract_markdown_file_lines_citation() -> None:
    citations = extract_citations(
        "- **File**: `src/repo_context/types.py`\n"
        "- **Lines**: 125\u2013140"
    )

    assert citations[0].path == "src/repo_context/types.py"
    assert citations[0].start_line == 125
    assert citations[0].end_line == 140
