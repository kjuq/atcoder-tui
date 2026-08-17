"""The main AtCoder TUI application."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime

from textual import constants, work
from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Header, Label, ListView

# Textual defaults to a 100 ms delay to distinguish Esc from an escape
# sequence. atcoder-tui doesn't need that much delay for its TUI controls.
constants.ESCAPE_DELAY = 0.01

from ..client import AtCoderClient, AtCoderError
from ..config import (
	load_last_contest,
	load_last_problem,
	load_problem_markdown_cache,
	load_submission_language,
	save_last_contest,
	save_last_problem,
	save_problem_markdown_cache,
	save_submission_language,
)
from ..markdown import html_to_markdown
from ..languages import DEFAULT_SUBMISSION_LANGUAGES
from ..models import Contest, Problem, ProblemSummary
from ..source import SourcePathError, resolve_source_path
from ..tester import TesterError, parse_time_limit, run_samples
from .modals import (
	REFRESH_CONTESTS,
	ConfirmScreen,
	ContestSearchScreen,
	CookieLoginScreen,
	EventLogScreen,
	LanguageSelectScreen,
)
from .widgets import ProblemItem, ProblemList, ResultsPanel, StatementPanel

_WELCOME = """\
# atcoder-tui

Browse, test, and submit AtCoder problems from this TUI.

Key bindings:

- `/` : Search and select a contest (type `abc100` to filter)
- `Enter` : Open a problem from the problem list
- `t` : Test the selected problem with local samples
- `e` : Edit the selected problem's source with `$EDITOR`
- `s` : Open the selected problem for submission (with confirmation)
- `S` : View your submissions / `r` : Open the problem in a browser
- `L` : Log in
- `w` : Change the submission language
- `E` : Show the event log
- `1` `2` `3` : Focus each panel
- `h` `l` `Tab` : Move between panels / `j` `k` : Move within a panel
- `PageUp` `PageDown` : Scroll the statement by 3 lines
- `?` : Show this help / `q` : Quit

Press `/` to search for a contest.
"""


def copy_to_clipboard(text: str) -> str | None:
	"""Copy text using a locally available native clipboard command."""
	if sys.platform == "darwin":
		commands = (["pbcopy"],)
	elif sys.platform.startswith("win"):
		commands = (["clip.exe"],)
	else:
		commands = (
			["wl-copy"],
			["xsel", "--clipboard", "--input"],
			["xclip", "-selection", "clipboard"],
		)
	for command in commands:
		if shutil.which(command[0]) is None:
			continue
		try:
			subprocess.run(
				command,
				input=text,
				text=True,
				check=True,
				timeout=5,
			)
		except (OSError, subprocess.SubprocessError):
			continue
		return command[0]
	return None


class AtcoderApp(App[None]):
	"""A TUI for browsing AtCoder problems."""

	CSS_PATH = "styles.tcss"
	TITLE = "atcoder-tui"
	ENABLE_COMMAND_PALETTE = False

	BINDINGS = [
		Binding("slash", "pick_contest", "Contest"),
		Binding("c", "pick_contest", "Contest", show=False),
		Binding("t", "run_tests", "Test"),
		Binding("e", "edit_source", "Edit"),
		Binding("s", "submit", "Submit"),
		Binding("S", "submissions", "Submissions"),
		Binding("r", "open_browser", "Browser"),
		Binding("L", "login", "Login"),
		Binding("w", "select_language", "Language"),
		Binding("E", "show_event_log", "Event log"),
		Binding("question_mark", "help", "Help"),
		Binding("escape", "quit", "Quit", show=False),
		Binding("q", "quit", "Quit"),
		Binding("1", "focus_problems", "Problems", show=False),
		Binding("2", "focus_results", "Results", show=False),
		Binding("3", "focus_statement", "Statement", show=False),
		Binding(
			"pageup",
			"scroll_statement_up",
			"Statement page up",
			show=False,
			priority=True,
		),
		Binding(
			"pagedown",
			"scroll_statement_down",
			"Statement page down",
			show=False,
			priority=True,
		),
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
		self._event_log: list[str] = []
		self.submission_language = (
			load_submission_language()
			or next(
				language
				for language in DEFAULT_SUBMISSION_LANGUAGES
				if language.id == "python"
			)
		)

	# -- レイアウト ----------------------------------------------------

	def notify(
		self,
		message: str,
		*,
		title: str = "",
		severity: str = "information",
		timeout: float | None = None,
		markup: bool = True,
	) -> None:
		"""Record an event without displaying a transient notification."""
		severity_value = getattr(severity, "value", severity)
		prefix = f"{title}: " if title else ""
		entry = (
			f"[{datetime.now().strftime('%H:%M:%S')}] "
			f"{str(severity_value).upper()}: {prefix}{message}"
		)
		self._event_log.append(entry)
		# Keep a long-running session from growing without bound.
		if len(self._event_log) > 500:
			del self._event_log[:-500]

	def action_show_event_log(self) -> None:
		self.push_screen(EventLogScreen(self._event_log))

	def compose(self) -> ComposeResult:
		yield Header()
		with Horizontal(id="body"):
			with Vertical(id="left"):
				with Container(id="problems-panel"):
					yield ProblemList(id="problem-list")
				yield ResultsPanel(id="results-panel")
			yield StatementPanel(id="statement-panel")
		with Horizontal(id="status-bar"):
			yield Label(id="language-status")

	def on_mount(self) -> None:
		self._set_panel_titles()
		self._update_language_status()
		self.statement.show_message(_WELCOME)
		self.refresh_login_status()
		last_contest = load_last_contest()
		if last_contest:
			self.load_contest(last_contest)

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

	def _update_language_status(self) -> None:
		self.query_one("#language-status", Label).update(
			f"Language: {self.submission_language.name}"
		)

	@work(exclusive=True, group="language")
	async def action_select_language(self) -> None:
		languages = list(DEFAULT_SUBMISSION_LANGUAGES)
		if all(language.id != self.submission_language.id for language in languages):
			languages.append(self.submission_language)
		selected = await self.push_screen_wait(
			LanguageSelectScreen(languages, self.submission_language)
		)
		if selected is None:
			return
		self.submission_language = selected
		save_submission_language(selected)
		self._update_language_status()
		self.notify(f"Submission language set to {selected.name}.")

	@work(exclusive=True, group="edit")
	async def action_edit_source(self) -> None:
		"""Open the selected problem's source in the user's terminal editor."""
		problem = self.current_problem
		if problem is None:
			self.notify("Select a problem first.", severity="warning")
			return
		try:
			path = resolve_source_path(problem, self.submission_language)
		except SourcePathError as exc:
			self.notify(str(exc), severity="error")
			return

		editor = os.environ.get("EDITOR", "").strip()
		if not editor:
			self.notify("Set $EDITOR to edit source files.", severity="warning")
			return
		try:
			command = shlex.split(editor)
		except ValueError as exc:
			self.notify(f"Invalid $EDITOR value: {exc}", severity="error")
			return
		if not command:
			self.notify("Set $EDITOR to edit source files.", severity="warning")
			return
		command.append(str(path))

		try:
			with self.suspend():
				completed = await asyncio.to_thread(
					subprocess.run, command, check=False
				)
		except (OSError, SuspendNotSupported) as exc:
			# SuspendNotSupported is an environment-specific exception, while
			# OSError covers a missing editor executable. Keep both as a log event.
			self.notify(f"Could not open editor: {exc}", severity="error")
			return
		if completed.returncode != 0:
			self.notify(
				f"Editor exited with status {completed.returncode}.", severity="error"
			)

	# -- フォーカス操作 ------------------------------------------------

	def action_focus_problems(self) -> None:
		self.query_one("#problem-list", ListView).focus()

	def action_focus_results(self) -> None:
		self.results.focus()

	def action_focus_statement(self) -> None:
		self.statement.focus()

	def action_scroll_statement_up(self) -> None:
		"""Scroll the statement three lines up regardless of focus."""
		if not isinstance(self.screen, ModalScreen):
			self.statement.scroll_to(y=self.statement.scroll_target_y - 3, animate=False)

	def action_scroll_statement_down(self) -> None:
		"""Scroll the statement three lines down regardless of focus."""
		if not isinstance(self.screen, ModalScreen):
			self.statement.scroll_to(y=self.statement.scroll_target_y + 3, animate=False)

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
		"""Return the contest list, fetching it when necessary."""
		if self.contests is not None and not force:
			return self.contests

		def report(page: int, total: int) -> None:
			self.call_from_thread(
				self.notify, f"Loading contest list... {page}/{total}"
			)

		self.notify("Loading contest list... (the first load may take several seconds)")
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

	def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
		if event.data_table is self.results:
			self._show_test_details(event.cursor_row)

	def _show_test_details(self, row: int) -> None:
		problem = self.current_problem
		test = self.results.test_at(row)
		if problem is not None and test is not None:
			self.statement.show_test_case(problem, test)

	@work(exclusive=True, group="contest")
	async def load_contest(self, contest_id: str) -> None:
		self.notify(f"Loading contest {contest_id}...")
		try:
			problems = await asyncio.to_thread(self.client.get_task_list, contest_id)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		if not problems:
			self.notify("No problems found.", severity="warning")
			return
		self.contest_id = contest_id
		self.problems = problems
		save_last_contest(contest_id)
		self.query_one("#problems-panel").border_title = f"1 {contest_id}"
		await self._populate_problems(problems)
		last_problem = load_last_problem()
		if last_problem and last_problem[0] == contest_id:
			last_summary = next(
				(summary for summary in problems if summary.task_id == last_problem[1]),
				None,
			)
			if last_summary is not None:
				self.load_problem(last_summary)
		self.notify(f"Loaded {len(problems)} problems.")

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
		self.statement.show_message(f"# {summary.index} - {summary.title}\n\nLoading...")
		try:
			problem = await asyncio.to_thread(
				self.client.get_problem, summary.contest_id, summary.task_id
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		self.results.show_samples(problem.samples)
		markdown = await asyncio.to_thread(
			load_problem_markdown_cache, problem.contest_id, problem.task_id
		)
		if markdown is None:
			self.statement.show_message(
				f"# {problem.index} - {problem.title}\n\n"
				"Converting to Markdown (defuddle)..."
			)
			markdown = await asyncio.to_thread(
				html_to_markdown,
				problem.statement_html or "",
				title=f"{problem.index} - {problem.title}",
			)
			await asyncio.to_thread(
				save_problem_markdown_cache,
				problem.contest_id,
				problem.task_id,
				markdown,
			)
		else:
			self.statement.show_message(
				f"# {problem.index} - {problem.title}\n\n"
				"Loaded Markdown from cache."
			)
		problem.markdown = markdown
		self.current_problem = problem
		save_last_problem(problem.contest_id, problem.task_id)
		self.statement.show_problem(problem)

	# -- ローカルテスト ------------------------------------------------

	@work(exclusive=True, group="test")
	async def action_run_tests(self) -> None:
		problem = self.current_problem
		if problem is None:
			self.notify("Select a problem first.", severity="warning")
			return
		if not problem.samples:
			self.notify("This problem has no samples.", severity="warning")
			return
		try:
			path = resolve_source_path(problem, self.submission_language)
		except SourcePathError as exc:
			self.notify(str(exc), severity="error")
			return
		if not path.is_file():
			self.notify(f"File not found: {path}", severity="error")
			return
		self.notify("Running sample tests...")
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
		self.notify(f"Testing complete: {ac}/{len(results)} AC")

	# -- ログイン ------------------------------------------------------

	def refresh_login_status(self) -> None:
		self._check_login()

	@work(exclusive=True, group="login-status")
	async def _check_login(self) -> None:
		try:
			logged_in = await asyncio.to_thread(self.client.is_logged_in)
		except AtCoderError:
			logged_in = False
		self.sub_title = "Logged in" if logged_in else "Guest"

	@work(exclusive=True, group="login")
	async def action_login(self) -> None:
		session_value = await self.push_screen_wait(CookieLoginScreen())
		if not session_value:
			return
		self.notify("Validating session...")
		try:
			await asyncio.to_thread(self.client.login_with_cookie, session_value)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		self.sub_title = "Logged in"
		self.notify("Logged in.", severity="information")

	# -- 提出 ----------------------------------------------------------

	@work(exclusive=True, group="submit")
	async def action_submit(self) -> None:
		problem = self.current_problem
		if problem is None:
			self.notify("Select a problem first.", severity="warning")
			return
		try:
			path = resolve_source_path(problem, self.submission_language)
		except SourcePathError as exc:
			self.notify(str(exc), severity="error")
			return
		if not path.is_file():
			self.notify(f"File not found: {path}", severity="error")
			return
		try:
			source = path.read_text(encoding="utf-8")
		except (OSError, UnicodeError) as exc:
			self.notify(f"Could not read source file: {exc}", severity="error")
			return
		confirmed = await self.push_screen_wait(
			ConfirmScreen(
				f"Open the problem page for submission?\n\n"
				f"Problem: {problem.index} - {problem.title}\n"
				f"Language: {self.submission_language.name}\n"
				f"File: {path} ({len(source)} bytes)",
				confirm_label="Open in browser",
			)
		)
		if not confirmed:
			return
		clipboard_command = await asyncio.to_thread(copy_to_clipboard, source)
		browser_url = f"{problem.url}#submit"
		await asyncio.to_thread(webbrowser.open, browser_url)
		clipboard_status = (
			f"Copied the source to the clipboard with {clipboard_command}. "
			if clipboard_command
			else "Could not copy the source to the clipboard. "
		)
		self.notify(
			f"{clipboard_status}Opened {browser_url}. Select {self.submission_language.name} "
			"and submit in the browser.",
			severity="information",
			timeout=8,
		)

	@work(exclusive=True, group="browser")
	async def action_open_browser(self) -> None:
		"""選択中の問題を既定のブラウザで開く。"""
		problem = self.current_problem
		if problem is None:
			self.notify("Select a problem first.", severity="warning")
			return
		await asyncio.to_thread(webbrowser.open, problem.url)
		self.notify(f"Opened in browser: {problem.url}")

	@work(exclusive=True, group="submissions")
	async def action_submissions(self) -> None:
		if self.contest_id is None:
			self.notify("Load a contest first.", severity="warning")
			return
		try:
			submissions = await asyncio.to_thread(
				self.client.get_my_submissions, self.contest_id
			)
		except AtCoderError as exc:
			self.notify(str(exc), severity="error")
			return
		if not submissions:
			self.notify("No submissions yet.")
			return
		latest = submissions[0]
		self.notify(
			f"Latest submission: {latest.task_id} / {latest.language} / "
			f"{latest.status or 'Judging'}",
			timeout=8,
		)


def run() -> None:
	AtcoderApp().run()
