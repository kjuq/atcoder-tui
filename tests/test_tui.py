"""Textual の run_test を使った TUI のヘッドレス動作確認。"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from textual.widgets import ListView, Markdown

from atcoder_tui.models import Contest, Problem, ProblemSummary, Sample
from atcoder_tui.tui.app import AtcoderApp
from atcoder_tui.tui.widgets import ProblemItem


class FakeClient:
	"""ネットワークに出ないテスト用クライアント。"""

	def is_logged_in(self) -> bool:
		return False

	def get_contests(self, *, force_refresh: bool = False, progress=None) -> list[Contest]:
		return [
			Contest("abc086", "AtCoder Beginner Contest 086", "2018-01-01", "~ 1999", "https://x/abc086"),
			Contest("abc100", "AtCoder Beginner Contest 100", "2018-06-01", "~ 1999", "https://x/abc100"),
			Contest("arc050", "AtCoder Regular Contest 050", "2016-01-01", "1200 ~", "https://x/arc050"),
		]

	def get_task_list(self, contest_id: str) -> list[ProblemSummary]:
		return [
			ProblemSummary(contest_id, "abc086_a", "A", "Product", "https://x/a"),
			ProblemSummary(contest_id, "abc086_b", "B", "1 21", "https://x/b"),
		]

	def get_problem(
		self, contest_id: str, task_id: str, *, prefer_lang: str = "ja"
	) -> Problem:
		return Problem(
			contest_id=contest_id,
			task_id=task_id,
			index="A",
			title="Product",
			url="https://x/a",
			time_limit="2 sec",
			memory_limit="256 MiB",
			samples=[Sample(1, "3 4\n", "Even\n")],
			statement_html="<h3>問題文</h3><p>テスト</p>",
		)


async def _wait_until(app: AtcoderApp, pilot, predicate, *, tries: int = 60) -> bool:
	for _ in range(tries):
		if predicate():
			return True
		await pilot.pause(0.05)
	return predicate()


def test_app_layout_and_flow() -> None:
	async def scenario() -> None:
		app = AtcoderApp(client=FakeClient())
		async with app.run_test() as pilot:
			# 3 パネルが構築されている。
			assert app.query_one("#problems-panel")
			assert app.query_one("#results-panel")
			assert app.query_one("#statement-panel")

			# 初期表示はウェルカム (ヘルプ)。
			md = app.query_one("#statement-md", Markdown)
			assert "atcoder-tui" in md.source

			# `/` でコンテスト検索を開き、id で絞り込んで選ぶ。
			await pilot.press("slash")
			assert await _wait_until(
				app, pilot, lambda: app.screen.__class__.__name__ == "ContestSearchScreen"
			)
			# "abc100" で絞り込むと候補が 1 件になる。
			await pilot.press(*"abc100")
			await pilot.pause(0.1)
			contest_list = app.screen.query_one("#contest-list", ListView)
			assert len(list(contest_list.query("ContestItem"))) == 1
			# Enter で選択 -> モーダルが閉じて問題が読み込まれる。
			await pilot.press("enter")
			assert await _wait_until(app, pilot, lambda: app.contest_id == "abc100")
			assert await _wait_until(app, pilot, lambda: len(app.problems) == 2)

			listview = app.query_one("#problem-list", ListView)
			items = list(listview.query(ProblemItem))
			assert len(items) == 2

			# 先頭の問題を開く。
			listview.focus()
			listview.index = 0
			await pilot.press("enter")
			assert await _wait_until(
				app, pilot, lambda: app.current_problem is not None
			)
			assert app.current_problem.title == "Product"
			assert "Product" in md.source

			# サンプルが結果パネルに反映される。
			assert app.results.row_count == 1

			# フォーカス系・ヘルプのアクションがクラッシュしない。
			await pilot.press("2")
			await pilot.press("3")
			await pilot.press("1")
			app.action_help()
			await pilot.pause()

			# j/k はパネル内移動: 問題一覧で上下に動く。
			listview.focus()
			listview.index = 0
			await pilot.press("j")
			assert listview.index == 1
			await pilot.press("k")
			assert listview.index == 0

			# h/l はパネル間移動 (lazygit 風)。
			results = app.query_one("#results-panel")
			statement = app.query_one("#statement-panel")
			listview.focus()
			await pilot.press("l")
			assert app.focused is results
			await pilot.press("l")
			assert app.focused is statement
			await pilot.press("l")
			assert app.focused is listview
			await pilot.press("h")
			assert app.focused is statement

			# Tab はパネルのみを巡回する。
			listview.focus()
			await pilot.press("tab")
			assert app.focused is results
			await pilot.press("tab")
			assert app.focused is statement
			await pilot.press("tab")
			assert app.focused is listview

			# r で現在の問題をブラウザで開く。
			with patch("webbrowser.open") as mock_open:
				listview.focus()
				await pilot.press("r")
				assert await _wait_until(app, pilot, lambda: mock_open.called)
				mock_open.assert_called_once_with("https://x/a")

			# L (大文字) でログイン画面 (Cookie 貼り付け) が開く。
			await pilot.press("L")
			assert await _wait_until(
				app, pilot, lambda: app.screen.__class__.__name__ == "CookieLoginScreen"
			)
			await pilot.press("escape")

	with patch(
		"atcoder_tui.tui.app.html_to_markdown", return_value="変換済み本文"
	):
		asyncio.run(scenario())


def test_contest_search_highlight_and_slash_focus() -> None:
	"""絞り込み直後は常に先頭が選択され、"/" で検索窓へ戻れること。"""

	async def scenario() -> None:
		app = AtcoderApp(client=FakeClient())
		async with app.run_test() as pilot:
			await pilot.press("slash")
			assert await _wait_until(
				app,
				pilot,
				lambda: app.screen.__class__.__name__ == "ContestSearchScreen",
			)
			screen = app.screen
			listview = screen.query_one("#contest-list", ListView)

			# 絞り込むたびに先頭 (index=0) が選択された状態になっている。
			for keys in ("abc", "0", "8"):
				await pilot.press(*keys)
				await pilot.pause(0.1)
				assert listview.index == 0
				assert listview.highlighted_child is not None

			# 一覧へフォーカスを移し、"/" で検索窓へ戻れる。
			await pilot.press("down")
			assert await _wait_until(
				app, pilot, lambda: app.focused is not None and app.focused.id == "contest-list"
			)
			await pilot.press("slash")
			assert await _wait_until(
				app,
				pilot,
				lambda: app.focused is not None and app.focused.id == "contest-filter",
			)
			filter_input = screen.query_one("#contest-filter")
			# "/" は検索文字列に紛れ込まない。
			assert "/" not in filter_input.value
			# 戻ったとき入力済み文字列は選択状態になっていない
			# (次の入力で全置換されないように)。
			assert filter_input.selected_text == ""
			await pilot.press("escape")

	asyncio.run(scenario())
