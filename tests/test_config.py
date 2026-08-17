"""設定値の保存・読み込みのテスト。"""

from __future__ import annotations

from pathlib import Path

from atcoder_tui import config


def test_last_contest_round_trip(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
	monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "legacy")

	assert config.load_last_contest() is None
	config.save_last_contest("abc100")

	assert config.load_last_contest() == "abc100"
	assert config.last_contest_path().read_text(encoding="utf-8") == "abc100\n"


def test_load_last_contest_ignores_blank_file(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
	monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "legacy")
	config.last_contest_path().write_text("  \n", encoding="utf-8")

	assert config.load_last_contest() is None


def test_last_contest_migrates_from_legacy_config_dir(
	tmp_path: Path, monkeypatch
) -> None:
	state = tmp_path / "state"
	legacy = tmp_path / "legacy"
	monkeypatch.setattr(config, "state_dir", lambda: state)
	monkeypatch.setattr(config, "config_dir", lambda: legacy)
	legacy.mkdir()
	(config.config_dir() / "last_contest").write_text("abc100\n", encoding="utf-8")

	assert config.load_last_contest() == "abc100"
	assert config.last_contest_path().read_text(encoding="utf-8") == "abc100\n"


def test_last_problem_round_trip(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setattr(config, "state_dir", lambda: tmp_path)

	assert config.load_last_problem() is None
	config.save_last_problem("abc100", "abc100_a")

	assert config.load_last_problem() == ("abc100", "abc100_a")


def test_submission_language_round_trip(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
	language = config.Language("python", "Python (CPython 3.11.4)")

	assert config.load_submission_language() is None
	config.save_submission_language(language)

	assert config.load_submission_language() == language


def test_problem_markdown_cache_uses_xdg_cache_home(
	tmp_path: Path, monkeypatch
) -> None:
	cache_home = tmp_path / "cache"
	monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))

	path = config.problem_markdown_cache_path("abc100", "abc100_a")
	assert path == cache_home / "atcoder-tui" / "abc100" / "abc100_a.md"

	config.save_problem_markdown_cache("abc100", "abc100_a", "# Cached")
	assert config.load_problem_markdown_cache("abc100", "abc100_a") == "# Cached"


def test_problem_markdown_cache_returns_none_when_missing(
	tmp_path: Path, monkeypatch
) -> None:
	monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

	assert config.load_problem_markdown_cache("abc100", "abc100_a") is None
