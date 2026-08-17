"""設定値とローカル保存先パスの管理。"""

from __future__ import annotations

from pathlib import Path

import platformdirs

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
	return config_dir() / "session.txt"


def contests_cache_path() -> Path:
	"""コンテスト一覧のキャッシュ (JSON) の保存先。"""
	return config_dir() / "contests.json"


def last_contest_path() -> Path:
	"""最後に読み込んだコンテスト ID の保存先。"""
	return config_dir() / "last_contest"


def load_last_contest() -> str | None:
	"""最後に読み込んだコンテスト ID を返す。保存されていなければ None。"""
	try:
		contest_id = last_contest_path().read_text(encoding="utf-8").strip()
	except OSError:
		return None
	return contest_id or None


def save_last_contest(contest_id: str) -> None:
	"""最後に読み込んだコンテスト ID を保存する。"""
	try:
		last_contest_path().write_text(f"{contest_id}\n", encoding="utf-8")
	except OSError:
		# 設定の保存に失敗しても、コンテストの読み込み自体は成功扱いにする。
		pass
