"""設定値とローカル保存先パスの管理。"""

from __future__ import annotations

import os
from pathlib import Path

import platformdirs

from .models import Language

APP_NAME = "atcoder-tui"

# AtCoder へ送る User-Agent。問い合わせ先が分かる形にしておく。
USER_AGENT = "atcoder-tui (Textual TUI; +https://github.com/kjuq/atcoder-tui)"

# 連続リクエストの最小間隔 (秒)。サーバ負荷への配慮。
REQUEST_INTERVAL = 0.4

# defuddle 実行に使うコマンド (npx 経由)。
DEFUDDLE_COMMAND = ["npx", "-y", "defuddle", "parse", "--markdown"]


def config_dir() -> Path:
	"""設定/セッションを置くディレクトリ (なければ作成)。"""
	path = Path(platformdirs.user_config_dir(APP_NAME))
	path.mkdir(parents=True, exist_ok=True)
	return path


def session_path() -> Path:
	"""ログインセッション (cookie jar) の保存先。"""
	return state_dir() / "session.txt"


def contests_cache_path() -> Path:
	"""コンテスト一覧のキャッシュ (JSON) の保存先。"""
	return config_dir() / "contests.json"


def cache_dir() -> Path:
	"""問題文 Markdown などのキャッシュを置くディレクトリ。"""
	base = os.environ.get("XDG_CACHE_HOME")
	path = Path(base) if base else Path.home() / ".cache"
	path = path / APP_NAME
	path.mkdir(parents=True, exist_ok=True)
	return path


def state_dir() -> Path:
	"""Persistent application state directory following the XDG layout."""
	base = os.environ.get("XDG_STATE_HOME")
	path = Path(base) if base else Path.home() / ".local" / "state"
	path = path / APP_NAME
	path.mkdir(parents=True, exist_ok=True)
	return path


def problem_markdown_cache_path(contest_id: str, task_id: str) -> Path:
	"""問題文 Markdown キャッシュの保存先。"""
	path = cache_dir() / contest_id / f"{task_id}.md"
	path.parent.mkdir(parents=True, exist_ok=True)
	return path


def load_problem_markdown_cache(contest_id: str, task_id: str) -> str | None:
	"""問題文 Markdown をキャッシュから読み込む。"""
	try:
		return problem_markdown_cache_path(contest_id, task_id).read_text(
			encoding="utf-8"
		)
	except OSError:
		return None


def save_problem_markdown_cache(
	contest_id: str, task_id: str, markdown: str
) -> None:
	"""問題文 Markdown をキャッシュへ保存する。"""
	try:
		problem_markdown_cache_path(contest_id, task_id).write_text(
			markdown, encoding="utf-8"
		)
	except OSError:
		# キャッシュ保存に失敗しても、問題の表示自体は成功扱いにする。
		pass


def last_contest_path() -> Path:
	"""Path storing the last loaded contest ID."""
	return state_dir() / "last_contest"


def _legacy_last_contest_path() -> Path:
	"""旧設定ディレクトリに保存されたコンテスト ID のパス。"""
	return config_dir() / "last_contest"


def load_last_contest() -> str | None:
	"""Return the last loaded contest ID, migrating the old location if needed."""
	for path in (last_contest_path(), _legacy_last_contest_path()):
		try:
			contest_id = path.read_text(encoding="utf-8").strip()
		except OSError:
			continue
		if contest_id:
			if path != last_contest_path():
				save_last_contest(contest_id)
			return contest_id
	return None


def save_last_contest(contest_id: str) -> None:
	"""Save the last loaded contest ID."""
	try:
		path = last_contest_path()
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(f"{contest_id}\n", encoding="utf-8")
	except OSError:
		# 設定の保存に失敗しても、コンテストの読み込み自体は成功扱いにする。
		pass


def last_problem_path() -> Path:
	"""Path storing the last loaded problem."""
	return state_dir() / "last_problem"


def load_last_problem() -> tuple[str, str] | None:
	"""Return the last loaded ``(contest_id, task_id)`` pair."""
	try:
		lines = last_problem_path().read_text(encoding="utf-8").splitlines()
	except OSError:
		return None
	if len(lines) < 2 or not lines[0].strip() or not lines[1].strip():
		return None
	return lines[0].strip(), lines[1].strip()


def save_last_problem(contest_id: str, task_id: str) -> None:
	"""Save the last loaded problem."""
	try:
		path = last_problem_path()
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(
			f"{contest_id}\n{task_id}\n", encoding="utf-8"
		)
	except OSError:
		pass


def submission_language_path() -> Path:
	"""Path storing the selected submission language."""
	return state_dir() / "submission_language"


def load_submission_language() -> Language | None:
	"""Return the persisted submission language."""
	try:
		lines = submission_language_path().read_text(encoding="utf-8").splitlines()
	except OSError:
		return None
	if len(lines) < 2 or not lines[0].strip() or not lines[1].strip():
		return None
	return Language(lines[0].strip(), lines[1].strip())


def save_submission_language(language: Language) -> None:
	"""Persist the selected submission language."""
	try:
		path = submission_language_path()
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(
			f"{language.id}\n{language.name}\n", encoding="utf-8"
		)
	except OSError:
		pass
