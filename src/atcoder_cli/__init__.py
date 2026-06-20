"""atcoder-cli: AtCoder の問題を閲覧・テスト・提出する lazygit 風 TUI。"""

from __future__ import annotations


def main() -> None:
	"""コンソールスクリプトのエントリポイント。TUI を起動する。"""
	from .tui.app import run

	run()
