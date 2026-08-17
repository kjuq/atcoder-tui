"""Tests for repository-based source resolution and language matching."""

from pathlib import Path

import pytest

from atcoder_tui.languages import find_matching_language, language_extension
from atcoder_tui.models import Language, Problem
from atcoder_tui.source import SourcePathError, resolve_source_path


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
