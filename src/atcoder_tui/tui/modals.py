"""Modal screens used by the TUI."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListView, Select, Static
from textual.widgets._select import SelectCurrent, SelectOverlay

from ..models import Contest, Language, Problem
from .widgets import ContestItem

_LOGIN_URL = "https://atcoder.jp/login"

# コンテスト検索で「一覧を再取得する」ことを表す番兵値。
REFRESH_CONTESTS = "\x00refresh\x00"


class CookieLoginScreen(ModalScreen["str | None"]):
	"""セッション Cookie (REVEL_SESSION) を貼り付けてログインする画面。

	AtCoder のログインは Cloudflare Turnstile で保護されているため、ユーザに
	自分のブラウザでログインしてもらい、その REVEL_SESSION を取り込む。
	"""

	BINDINGS = [("escape", "cancel", "Cancel")]

	def compose(self) -> ComposeResult:
		with Vertical(id="login-dialog"):
			yield Label("Log in (session cookie)", classes="dialog-title")
			yield Static(
				"AtCoder login is protected by CAPTCHA (Cloudflare Turnstile), "
				"so log in through a browser and import the cookie.\n\n"
				"1. Log in to AtCoder with `Open browser`\n"
				"2. Open Developer Tools → Application/Storage → Cookies → "
				"https://atcoder.jp\n"
				"3. Copy the REVEL_SESSION value and paste it below",
			)
			yield Button("Open browser", id="login-open", classes="dialog-field")
			yield Input(
				placeholder="REVEL_SESSION value",
				id="login-cookie",
				classes="dialog-field",
			)
			with Horizontal(classes="dialog-buttons"):
				yield Button("Cancel", id="login-cancel")
				yield Button("Log in", variant="primary", id="login-ok")

	def on_mount(self) -> None:
		self.query_one("#login-cookie", Input).focus()

	def on_button_pressed(self, event: Button.Pressed) -> None:
		if event.button.id == "login-open":
			webbrowser.open(_LOGIN_URL)
			self.notify("Log in to AtCoder in the browser.")
		elif event.button.id == "login-ok":
			self._submit()
		else:
			self.dismiss(None)

	def on_input_submitted(self, event: Input.Submitted) -> None:
		self._submit()

	def _submit(self) -> None:
		value = self.query_one("#login-cookie", Input).value.strip()
		if not value:
			self.notify("Enter the REVEL_SESSION value.", severity="warning")
			return
		self.dismiss(value)

	def action_cancel(self) -> None:
		self.dismiss(None)


class FilePromptScreen(ModalScreen[str | None]):
	"""Screen for entering a one-line text value, such as a file path."""

	BINDINGS = [("escape", "cancel", "Cancel")]

	def __init__(self, title: str, default: str = "") -> None:
		super().__init__()
		self._title = title
		self._default = default

	def compose(self) -> ComposeResult:
		with Vertical(id="prompt-dialog"):
			yield Label(self._title, classes="dialog-title")
			yield Input(value=self._default, id="prompt-input", classes="dialog-field")
			with Horizontal(classes="dialog-buttons"):
				yield Button("Cancel", id="prompt-cancel")
				yield Button("OK", variant="primary", id="prompt-ok")

	def on_mount(self) -> None:
		inp = self.query_one("#prompt-input", Input)
		inp.focus()
		inp.cursor_position = len(inp.value)

	def on_button_pressed(self, event: Button.Pressed) -> None:
		if event.button.id == "prompt-ok":
			self._submit()
		else:
			self.dismiss(None)

	def on_input_submitted(self, event: Input.Submitted) -> None:
		self._submit()

	def _submit(self) -> None:
		value = self.query_one("#prompt-input", Input).value.strip()
		if not value:
			self.dismiss(None)
			return
		self.dismiss(value)

	def action_cancel(self) -> None:
		self.dismiss(None)


class ContestSearchScreen(ModalScreen["str | None"]):
	"""Screen for filtering and selecting an archived contest.

	Type text such as "abc100" to filter contest IDs and titles by substring.
	Press Enter or select an item to return its ID.
	"""

	BINDINGS = [
		("escape", "cancel", "Cancel"),
		("ctrl+r", "refresh", "Refresh"),
	]

	# 一度に表示する最大件数 (打ち込むほど絞られる)。
	_LIMIT = 100

	def __init__(self, contests: list[Contest]) -> None:
		super().__init__()
		self._contests = contests

	def compose(self) -> ComposeResult:
		with Vertical(id="contest-dialog"):
			yield Label("Select a contest", classes="dialog-title")
			yield Input(
				placeholder="Search by ID or title, e.g. abc100",
				id="contest-filter",
				# "/" で戻ったときに入力済みの文字列を選択状態にしない
				# (選択されていると次の入力で全置換されてしまうため)。
				select_on_focus=False,
			)
			yield ListView(id="contest-list")
			yield Static("", id="contest-count")
			yield Static(
				"Down: list  /: search  Enter: select  Ctrl+R: refresh  Esc: close",
				id="contest-hint",
			)

	async def on_mount(self) -> None:
		await self._refilter("")
		self.query_one("#contest-filter", Input).focus()

	def _filtered(self, query: str) -> tuple[list[Contest], int]:
		q = query.strip().lower()
		if not q:
			hits = self._contests
		else:
			hits = [
				c
				for c in self._contests
				if q in c.id.lower() or q in c.title.lower()
			]
		return hits[: self._LIMIT], len(hits)

	async def _refilter(self, query: str) -> None:
		hits, total = self._filtered(query)
		listview = self.query_one("#contest-list", ListView)
		# clear()/extend() は非同期に DOM を更新する。await せずに index を
		# 設定すると、古い項目の削除や新項目のマウントが終わる前に index が
		# 確定してしまい、絞り込み直後に先頭が選択されない瞬間が生じる。
		# 必ず DOM 更新を待ってから先頭をハイライトする。
		await listview.clear()
		if hits:
			await listview.extend(ContestItem(contest) for contest in hits)
			listview.index = 0
		count = self.query_one("#contest-count", Static)
		more = " (type to filter)" if total > len(hits) else ""
		count.update(f"{len(hits)} / {total} results{more}")

	async def on_input_changed(self, event: Input.Changed) -> None:
		if event.input.id == "contest-filter":
			await self._refilter(event.value)

	def on_input_submitted(self, event: Input.Submitted) -> None:
		self._pick_highlighted()

	def on_key(self, event: events.Key) -> None:
		focused = self.focused
		# 入力欄で下矢印を押したら一覧へフォーカスを移す。
		if event.key == "down" and focused is not None and focused.id == "contest-filter":
			self.query_one("#contest-list", ListView).focus()
			event.stop()
		# 一覧側にいるときに "/" を押したら検索窓へフォーカスを戻す。
		# (入力欄にフォーカスがある間は Input が "/" を文字として消費するため
		#  ここには来ない。)
		elif event.key == "slash" and (
			focused is None or focused.id != "contest-filter"
		):
			self.query_one("#contest-filter", Input).focus()
			event.stop()
			event.prevent_default()

	def on_list_view_selected(self, event: ListView.Selected) -> None:
		if isinstance(event.item, ContestItem):
			self.dismiss(event.item.contest.id)

	def _pick_highlighted(self) -> None:
		listview = self.query_one("#contest-list", ListView)
		item = listview.highlighted_child
		if isinstance(item, ContestItem):
			self.dismiss(item.contest.id)
		else:
			self.notify("No matching contests.", severity="warning")

	def action_refresh(self) -> None:
		self.dismiss(REFRESH_CONTESTS)

	def action_cancel(self) -> None:
		self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
	"""Yes/no confirmation dialog used before submission."""

	BINDINGS = [("escape", "cancel", "Cancel")]

	def __init__(self, message: str, *, confirm_label: str = "Run") -> None:
		super().__init__()
		self._message = message
		self._confirm_label = confirm_label

	def compose(self) -> ComposeResult:
		with Vertical(id="confirm-dialog"):
			yield Label("Confirm", classes="dialog-title")
			yield Static(self._message)
			with Horizontal(classes="dialog-buttons"):
				yield Button("Cancel", id="confirm-cancel")
				yield Button(self._confirm_label, variant="error", id="confirm-ok")

	def on_mount(self) -> None:
		self.query_one("#confirm-cancel", Button).focus()

	def on_button_pressed(self, event: Button.Pressed) -> None:
		self.dismiss(event.button.id == "confirm-ok")

	def action_cancel(self) -> None:
		self.dismiss(False)


class LanguageSearchChanged(Message):
	"""Message posted when the language filter changes."""

	def __init__(self, query: str) -> None:
		super().__init__()
		self.query = query


class LanguageSelectOverlay(SelectOverlay):
	"""Language-selection overlay with type-to-filter support."""

	def __init__(self) -> None:
		super().__init__(type_to_search=False)

	async def _on_key(self, event: events.Key) -> None:
		parent = self.parent
		query = getattr(parent, "_filter_query", "")
		new_query: str | None = None
		if event.key == "backspace":
			new_query = query[:-1]
		elif event.key == "ctrl+w":
			trimmed = query.rstrip()
			separator = trimmed.rfind(" ")
			new_query = trimmed[:separator] if separator >= 0 else ""
		elif event.key == "ctrl+u":
			new_query = ""
		elif event.character is not None and event.is_printable:
			new_query = query + event.character

		if new_query is not None:
			event.stop()
			event.prevent_default()
			self.post_message(LanguageSearchChanged(new_query))


class LanguageSelect(Select[str]):
	"""Select widget that filters language options while typing."""

	def __init__(self, options: list[tuple[str, str]], **kwargs: object) -> None:
		self._all_options = options
		self._filter_query = ""
		super().__init__(options, **kwargs)

	def compose(self) -> ComposeResult:
		yield SelectCurrent(self.prompt)
		yield LanguageSelectOverlay().data_bind(compact=Select.compact)

	def action_show_overlay(self) -> None:
		# Esc で閉じた後に前回の検索文字列を持ち越さない。
		self._filter_query = ""
		self._apply_filter()
		super().action_show_overlay()

	def _filtered_options(self) -> list[tuple[str, str]]:
		query = self._filter_query.casefold()
		return [
			option
			for option in self._all_options
			if not query or query in option[0].casefold()
		]

	def _apply_filter(self) -> None:
		selected = self.value
		options = self._filtered_options()
		option_ids = {language_id for _, language_id in options}
		super().set_options(options)
		self.value = selected if selected in option_ids else Select.NULL
		self._update_search_display()

	def _update_search_display(self) -> None:
		"""検索中は入力文字列を Select の現在値表示に出す。"""
		try:
			current = self.query_one(SelectCurrent)
		except NoMatches:
			# compose 前は SelectCurrent がまだ存在しない。
			return
		if self._filter_query:
			current.update(f"Filter: {self._filter_query}")
			return
		if self.value == self.NULL:
			current.update(self.NULL)
			return
		for prompt, value in self._options:
			if value == self.value:
				current.update(prompt)
				return

	def _update_selection(self, event: SelectOverlay.UpdateSelection) -> None:
		"""Restore the selected language name after selection."""
		super()._update_selection(event)
		self._filter_query = ""
		self._update_search_display()

	def on_language_search_changed(self, event: LanguageSearchChanged) -> None:
		event.stop()
		self._filter_query = event.query
		self._apply_filter()


class SubmitScreen(ModalScreen["tuple[Path, str, str] | None"]):
	"""Screen for selecting a source file and submission language.

	 dismiss returns a tuple of (file path, language ID, language name).
	"""

	BINDINGS = [("escape", "cancel", "Cancel")]

	def __init__(
		self, problem: Problem, languages: list[Language], default_path: str
	) -> None:
		super().__init__()
		self._problem = problem
		self._languages = languages
		self._default_path = default_path
		self._selected_language_id = self._default_language()

	def _default_language(self) -> str | None:
		for lang in self._languages:
			if "Python" in lang.name and "PyPy" not in lang.name:
				return lang.id
		return self._languages[0].id if self._languages else None

	def compose(self) -> ComposeResult:
		with Vertical(id="submit-dialog"):
			yield Label(
				f"Submit: {self._problem.index} - {self._problem.title}",
				classes="dialog-title",
			)
			yield Label("Source file", classes="dialog-field")
			yield Input(
				value=self._default_path, id="submit-path", classes="dialog-field"
			)
			yield Label("Language", classes="dialog-field")
			yield LanguageSelect(
				[(lang.name, lang.id) for lang in self._languages],
				prompt="Select a language (type to filter)",
				value=self._selected_language_id,
				allow_blank=True,
				id="submit-lang",
			)
			with VerticalScroll(id="submit-preview"):
				yield Static("", id="submit-preview-body")
			with Horizontal(classes="dialog-buttons"):
				yield Button("Cancel", id="submit-cancel")
				yield Button("Review and submit", variant="primary", id="submit-ok")

	def on_mount(self) -> None:
		self.query_one("#submit-path", Input).focus()
		self._refresh_preview()

	def on_input_changed(self, event: Input.Changed) -> None:
		if event.input.id == "submit-path":
			self._refresh_preview()

	def on_input_submitted(self, event: Input.Submitted) -> None:
		self._submit()

	def _refresh_preview(self) -> None:
		body = self.query_one("#submit-preview-body", Static)
		raw = self.query_one("#submit-path", Input).value.strip()
		path = Path(raw) if raw else None
		if path is None or not path.exists():
			body.update("[dim]File not found[/dim]")
			return
		try:
			text = path.read_text(encoding="utf-8")
		except OSError as exc:
			body.update(f"[red]Read error: {exc}[/red]")
			return
		preview = "\n".join(text.splitlines()[:12])
		body.update(f"[dim]{len(text)} bytes[/dim]\n{preview}")

	def on_button_pressed(self, event: Button.Pressed) -> None:
		if event.button.id == "submit-ok":
			self._submit()
		else:
			self.dismiss(None)

	def _submit(self) -> None:
		raw = self.query_one("#submit-path", Input).value.strip()
		lang_value = self.query_one("#submit-lang", LanguageSelect).value
		if not raw:
			self.notify("Enter a file path.", severity="warning")
			return
		if lang_value is Select.NULL or lang_value is None:
			self.notify("Select a language.", severity="warning")
			return
		lang_id = str(lang_value)
		lang_name = next(
			(lang.name for lang in self._languages if lang.id == lang_id), lang_id
		)
		self.dismiss((Path(raw), lang_id, lang_name))

	def action_cancel(self) -> None:
		self.dismiss(None)
