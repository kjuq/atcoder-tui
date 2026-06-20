"""lazygit 風の AtCoder TUI アプリ本体。"""

from __future__ import annotations

import asyncio
import webbrowser
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListView

from ..client import AtCoderClient, AtCoderError
from ..markdown import html_to_markdown
from ..models import Contest, Problem, ProblemSummary
from ..tester import TesterError, parse_time_limit, run_samples
from .modals import (
	REFRESH_CONTESTS,
	ConfirmScreen,
	ContestSearchScreen,
	CookieLoginScreen,
	FilePromptScreen,
	SubmitScreen,
)
from .widgets import ProblemItem, ProblemList, ResultsPanel, StatementPanel

_WELCOME = """\
# atcoder-tui

AtCoder の問題を閲覧・テスト・提出できる TUI です。

操作方法:

- `/` : コンテストを検索して選ぶ (例 abc100 で絞り込み)
- `Enter` : 問題一覧から問題を開く
- `t` : 選択中の問題をローカルのサンプルでテスト
- `s` : 選択中の問題にソースを提出 (確認あり)
- `S` : 自分の提出一覧を確認 / `r` : 問題をbrowserで開く
- `L` : ログイン
- `1` `2` `3` : 各パネルへフォーカス移動
- `h` `l` `Tab` : パネル間を移動 / `j` `k` : パネル内を上下移動
- `?` : このヘルプ / `q` : 終了

まずは `/` を押してコンテストを検索してください。
"""


class AtcoderApp(App[None]):
	"""AtCoder 問題ブラウザ TUI。"""

	CSS_PATH = "styles.tcss"
	TITLE = "atcoder-tui"

	BINDINGS = [
		Binding("slash", "pick_contest", "Contest"),
		Binding("c", "pick_contest", "Contest", show=False),
		Binding("t", "run_tests", "Test"),
		Binding("s", "submit", "Submit"),
		Binding("S", "submissions", "Submissions"),
		Binding("r", "open_browser", "Browser"),
		Binding("L", "login", "Login"),
		Binding("question_mark", "help", "Help"),
		Binding("q", "quit", "Quit"),
		Binding("1", "focus_problems", "Problems", show=False),
		Binding("2", "focus_results", "Results", show=False),
		Binding("3", "focus_statement", "Statement", show=False),
		Binding("l", "next_panel", "Next panel", show=False),
		Binding("h", "prev_panel", "Prev panel", show=False),
	]

	# h/l で巡回するパネル (lazygit 風のパネル間移動)。
	_PANELS = ("#problem-list", "#results-panel", "#statement-panel")

	def __init__(self, client: AtCoderClient | None = None) -> None:
		super().__init__()
		self.client = client or AtCoderClient()
		self.contest_id: str | None = None
		self.contests: list[Contest] | None = None
		self.problems: list[ProblemSummary] = []
		self.current_problem: Problem | None = None

	# -- レイアウト ----------------------------------------------------

	def compose(self) -> ComposeResult:
		yield Header()
		with Horizontal(id="body"):
			with Vertical(id="left"):
				with Container(id="problems-panel"):
					yield ProblemList(id="problem-list")
				yield ResultsPanel(id="results-panel")
			yield StatementPanel(id="statement-panel")
		yield Footer()

	def on_mount(self) -> None:
		self._set_panel_titles()
		self.statement.show_message(_WELCOME)
		self.refresh_login_status()

	def _set_panel_titles(self) -> None:
		self.query_one("#problems-panel").border_title = "1 Problems"
		self.query_one("#results-panel").border_title = "2 Samples / Tests"
		self.query_one("#statement-panel").border_title = "3 Statement"

	# -- ショートカット ------------------------------------------------

	@property
	def statement(self) -> StatementPanel:
		return self.query_one("#statement-panel", StatementPanel)

	@property
	def results(self) -> ResultsPanel:
		return self.query_one("#results-panel", ResultsPanel)

	# -- フォーカス操作 ------------------------------------------------

	def action_focus_problems(self) -> None:
		self.query_one("#problem-list", ListView).focus()

	def action_focus_results(self) -> None:
		self.results.focus()

	def action_focus_statement(self) -> None:
		self.statement.focus()

	def _cycle_panel(self, delta: int) -> None:
		panels = [self.query_one(sel) for sel in self._PANELS]
		current = next(
			(i for i, p in enumerate(panels) if self.focused is p), None
		)
		if current is None:
			target = panels[0] if delta > 0 else panels[-1]
		else:
			target = panels[(current + delta) % len(panels)]
		target.focus()

	def action_next_panel(self) -> None:
		self._cycle_panel(1)

	def action_prev_panel(self) -> None:
		self._cycle_panel(-1)

	# Tab / Shift+Tab もパネル間移動にする (検索ウィンドウはスキップ)。
	# モーダル内では従来通りフィールド間を移動する。
	def action_focus_next(self) -> None:
		if isinstance(self.screen, ModalScreen):
			super().action_focus_next()
		else:
			self._cycle_panel(1)

	def action_focus_previous(self) -> None:
		if isinstance(self.screen, ModalScreen):
			super().action_focus_previous()
		else:
			self._cycle_panel(-1)

	def action_help(self) -> None:
		self.statement.show_message(_WELCOME)

	# -- コンテスト/問題の読み込み ------------------------------------

	async def _ensure_contests(self, *, force: bool = False) -> list[Contest] | None:
		"""コンテスト一覧を (必要なら取得して) 返す。失敗時は None。"""
		if self.contests is not None and not force:
			return self.contests

		def report(page: int, total: int) -> None:
			self.call_from_thread(
				self.notify, f"コンテスト一覧を取得中... {page}/{total}"
			)

		self.notify("コンテスト一覧を取得中... (初回は数十秒かかります)")
		try:
			contests = await asyncio.to_thread(
				self.client.get_contests, force_refresh=force, progress=report
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return None
		self.contests = contests
		return contests

	@work(exclusive=True, group="pick-contest")
	async def action_pick_contest(self) -> None:
		force = False
		while True:
			contests = await self._ensure_contests(force=force)
			if not contests:
				return
			choice = await self.push_screen_wait(ContestSearchScreen(contests))
			if choice == REFRESH_CONTESTS:
				force = True
				continue
			if choice:
				self.load_contest(choice)
			return

	def on_list_view_selected(self, event: ListView.Selected) -> None:
		item = event.item
		if isinstance(item, ProblemItem):
			self.load_problem(item.summary)

	@work(exclusive=True, group="contest")
	async def load_contest(self, contest_id: str) -> None:
		self.notify(f"コンテスト {contest_id} を読み込み中...")
		try:
			problems = await asyncio.to_thread(self.client.get_task_list, contest_id)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		if not problems:
			self.notify("問題が見つかりませんでした", severity="warning")
			return
		self.contest_id = contest_id
		self.problems = problems
		self.query_one("#problems-panel").border_title = f"1 {contest_id}"
		await self._populate_problems(problems)
		self.notify(f"{len(problems)} 問を取得しました")

	async def _populate_problems(self, problems: list[ProblemSummary]) -> None:
		listview = self.query_one("#problem-list", ListView)
		await listview.clear()
		for summary in problems:
			await listview.append(ProblemItem(summary))
		listview.focus()
		if problems:
			listview.index = 0

	@work(exclusive=True, group="problem")
	async def load_problem(self, summary: ProblemSummary) -> None:
		self.statement.show_message(f"# {summary.index} - {summary.title}\n\n読み込み中...")
		try:
			problem = await asyncio.to_thread(
				self.client.get_problem, summary.contest_id, summary.task_id
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		self.results.show_samples(problem.samples)
		self.statement.show_message(
			f"# {problem.index} - {problem.title}\n\nMarkdown に変換中 (defuddle)..."
		)
		markdown = await asyncio.to_thread(
			html_to_markdown,
			problem.statement_html or "",
			title=f"{problem.index} - {problem.title}",
		)
		problem.markdown = markdown
		self.current_problem = problem
		self.statement.show_problem(problem)

	# -- ローカルテスト ------------------------------------------------

	@work(exclusive=True, group="test")
	async def action_run_tests(self) -> None:
		problem = self.current_problem
		if problem is None:
			self.notify("先に問題を選択してください", severity="warning")
			return
		if not problem.samples:
			self.notify("この問題にはサンプルがありません", severity="warning")
			return
		default = f"{problem.task_id}.py"
		raw = await self.push_screen_wait(
			FilePromptScreen("テストするソースファイル", default)
		)
		if not raw:
			return
		path = Path(raw)
		if not path.exists():
			self.notify(f"ファイルが見つかりません: {path}", severity="error")
			return
		self.notify("サンプルテストを実行中...")
		time_limit = parse_time_limit(problem.time_limit)
		try:
			results = await asyncio.to_thread(
				run_samples, path, problem.samples, time_limit=time_limit
			)
		except TesterError as exc:
			self.notify(str(exc), severity="error")
			return
		self.results.show_results(results)
		ac = sum(1 for r in results if r.status.value == "AC")
		self.notify(f"テスト完了: {ac}/{len(results)} AC")

	# -- ログイン ------------------------------------------------------

	def refresh_login_status(self) -> None:
		self._check_login()

	@work(exclusive=True, group="login-status")
	async def _check_login(self) -> None:
		try:
			logged_in = await asyncio.to_thread(self.client.is_logged_in)
		except AtCoderError:
			logged_in = False
		self.sub_title = "ログイン済み" if logged_in else "ゲスト"

	@work(exclusive=True, group="login")
	async def action_login(self) -> None:
		session_value = await self.push_screen_wait(CookieLoginScreen())
		if not session_value:
			return
		self.notify("セッションを検証中...")
		try:
			await asyncio.to_thread(self.client.login_with_cookie, session_value)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		self.sub_title = "ログイン済み"
		self.notify("ログインしました", severity="information")

	# -- 提出 ----------------------------------------------------------

	@work(exclusive=True, group="submit")
	async def action_submit(self) -> None:
		problem = self.current_problem
		if problem is None:
			self.notify("先に問題を選択してください", severity="warning")
			return
		if not await asyncio.to_thread(self.client.is_logged_in):
			self.notify("提出にはログインが必要です (l)", severity="warning")
			return
		try:
			languages = await asyncio.to_thread(
				self.client.get_languages, problem.contest_id
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		if not languages:
			self.notify("提出言語の一覧を取得できませんでした", severity="error")
			return
		choice = await self.push_screen_wait(
			SubmitScreen(problem, languages, f"{problem.task_id}.py")
		)
		if not choice:
			return
		path, lang_id, lang_name = choice
		if not path.exists():
			self.notify(f"ファイルが見つかりません: {path}", severity="error")
			return
		source = path.read_text(encoding="utf-8")
		confirmed = await self.push_screen_wait(
			ConfirmScreen(
				f"以下の内容で提出します。よろしいですか?\n\n"
				f"問題: {problem.index} - {problem.title}\n"
				f"言語: {lang_name}\n"
				f"ファイル: {path} ({len(source)} bytes)",
				confirm_label="提出する",
			)
		)
		if not confirmed:
			return
		self.notify("提出中...")
		try:
			submission = await asyncio.to_thread(
				self.client.submit, problem.contest_id, problem.task_id, lang_id, source
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		status = submission.status if submission else "送信完了"
		self.notify(
			f"提出しました (状態: {status or '判定中'})。r で結果を更新できます。",
			severity="information",
			timeout=8,
		)

	@work(exclusive=True, group="browser")
	async def action_open_browser(self) -> None:
		"""選択中の問題を既定のブラウザで開く。"""
		problem = self.current_problem
		if problem is None:
			self.notify("先に問題を選択してください", severity="warning")
			return
		await asyncio.to_thread(webbrowser.open, problem.url)
		self.notify(f"ブラウザで開きました: {problem.url}")

	@work(exclusive=True, group="submissions")
	async def action_submissions(self) -> None:
		if self.contest_id is None:
			self.notify("先にコンテストを読み込んでください", severity="warning")
			return
		try:
			submissions = await asyncio.to_thread(
				self.client.get_my_submissions, self.contest_id
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		if not submissions:
			self.notify("提出はまだありません")
			return
		latest = submissions[0]
		self.notify(
			f"最新の提出: {latest.task_id} / {latest.language} / "
			f"{latest.status or '判定中'}",
			timeout=8,
		)


def run() -> None:
	AtcoderApp().run()
