"""Tests for repository-based source resolution and language matching."""

from pathlib import Path

import pytest

from atcoder_tui.languages import (
	DEFAULT_SUBMISSION_LANGUAGES,
	find_matching_language,
	language_extension,
)
from atcoder_tui.models import Language, Problem
from atcoder_tui.source import SourcePathError, resolve_source_path
from scripts.update_languages import extract_languages


def _problem() -> Problem:
	return Problem("abc471", "abc471_a", "A", "問題", "https://example.com")


def test_resolve_source_path_from_repo_base(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setenv("ATCODER_TUI_REPO_BASE", str(tmp_path))

	path = resolve_source_path(_problem(), Language("python", "Python (CPython 3.11.4)"))

	assert path == tmp_path / "abc471" / "a" / "main.py"


def test_resolve_source_path_requires_repo_base(monkeypatch) -> None:
	monkeypatch.delenv("ATCODER_TUI_REPO_BASE", raising=False)

	with pytest.raises(SourcePathError, match="ATCODER_TUI_REPO_BASE"):
		resolve_source_path(_problem(), Language("python", "Python"))


def test_language_family_matching_and_extensions() -> None:
	preferred = Language("cpp", "C++23 (GCC 12.2.0)")
	available = [
		Language("6017", "C++23 (GCC 15.2.0)"),
		Language("4006", "Python (CPython 3.11.4)"),
	]

	assert find_matching_language(preferred, available) == available[0]
	assert language_extension(preferred) == "cpp"
	assert language_extension(Language("pypy", "PyPy 3.10")) == "py"


def test_catalog_contains_current_atcoder_typescript_variants() -> None:
	names = [language.name for language in DEFAULT_SUBMISSION_LANGUAGES]

	assert "TypeScript 5.8 (Deno 2.4.5)" in names
	assert "TypeScript 5.9 (tsc 5.9.2 (Bun 1.2.21))" in names
	typescript = next(language for language in DEFAULT_SUBMISSION_LANGUAGES if language.id == "typescript")
	assert language_extension(typescript) == "ts"


def test_language_update_script_extracts_names_and_extensions() -> None:
	html = """
	<h2>C++23 (GCC 15.2.0)</h2>
	<table><tr><td>ファイル名</td><td><code>Main.cpp</code></td></tr></table>
	<h2>TypeScript 5.9 (tsc 5.9.2 (Node.js 22.19.0))</h2>
	<table><tr><td>ファイル名</td><td><code>Main.ts</code></td></tr></table>
	"""

	entries = extract_languages(html, minimum_entries=1)

	assert entries == [
		{
			"id": "cpp",
			"name": "C++23 (GCC 15.2.0)",
			"family": "cpp",
			"extension": "cpp",
		},
		{
			"id": "typescript",
			"name": "TypeScript 5.9 (tsc 5.9.2 (Node.js 22.19.0))",
			"family": "typescript",
			"extension": "ts",
		},
	]


def test_language_update_script_supports_non_table_language_blocks() -> None:
	html = """
	<p>C++23 (GCC 15.2.0)</p>
	<p>ファイル名 | <code>Main.cpp</code></p>
	"""

	entries = extract_languages(html, minimum_entries=1)

	assert entries[0]["name"] == "C++23 (GCC 15.2.0)"
	assert entries[0]["extension"] == "cpp"
