"""設定値の保存・読み込みのテスト。"""

from __future__ import annotations

from pathlib import Path

from atcoder_tui import config


def test_last_contest_round_trip(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setattr(config, "config_dir", lambda: tmp_path)

	assert config.load_last_contest() is None
	config.save_last_contest("abc100")

	assert config.load_last_contest() == "abc100"
	assert config.last_contest_path().read_text(encoding="utf-8") == "abc100\n"


def test_load_last_contest_ignores_blank_file(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
	config.last_contest_path().write_text("  \n", encoding="utf-8")

	assert config.load_last_contest() is None
