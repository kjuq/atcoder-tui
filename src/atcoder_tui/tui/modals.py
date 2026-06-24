"""TUI のモーダル画面群 (ログイン/ファイル入力/提出/確認)。"""

from __future__ import annotations

import webbrowser
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListView, Select, Static

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
			yield Label("ログイン (セッション Cookie)", classes="dialog-title")
			yield Static(
				"AtCoder のログインは CAPTCHA (Cloudflare Turnstile) で保護されて"
				"いるため、ブラウザでログインして Cookie を取り込みます。\n\n"
				"1. 「ブラウザを開く」で AtCoder にログイン\n"
				"2. 開発者ツール → Application/ストレージ → Cookies → "
				"https://atcoder.jp\n"
				"3. REVEL_SESSION の値をコピーして下に貼り付け",
			)
			yield Button("ブラウザを開く", id="login-open", classes="dialog-field")
			yield Input(
				placeholder="REVEL_SESSION の値",
				id="login-cookie",
				classes="dialog-field",
			)
			with Horizontal(classes="dialog-buttons"):
				yield Button("キャンセル", id="login-cancel")
				yield Button("ログイン", variant="primary", id="login-ok")

	def on_mount(self) -> None:
		self.query_one("#login-cookie", Input).focus()

	def on_button_pressed(self, event: Button.Pressed) -> None:
		if event.button.id == "login-open":
			webbrowser.open(_LOGIN_URL)
			self.notify("ブラウザで AtCoder にログインしてください")
		elif event.button.id == "login-ok":
			self._submit()
		else:
			self.dismiss(None)

	def on_input_submitted(self, event: Input.Submitted) -> None:
		self._submit()

	def _submit(self) -> None:
		value = self.query_one("#login-cookie", Input).value.strip()
		if not value:
			self.notify("REVEL_SESSION の値を入力してください", severity="warning")
			return
		self.dismiss(value)

	def action_cancel(self) -> None:
		self.dismiss(None)


class FilePromptScreen(ModalScreen[str | None]):
	"""1 行のテキスト (ファイルパス) を入力する画面。"""

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
				yield Button("キャンセル", id="prompt-cancel")
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
	"""過去コンテストを絞り込み検索して選ぶ画面。

	入力欄に "abc100" のような文字列を打つと、コンテスト id とタイトルに対して
	部分一致でフィルタする。Enter または一覧での選択で id を返す。
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
			yield Label("コンテストを選択", classes="dialog-title")
			yield Input(
				placeholder="abc100 などで検索 (id / タイトル)",
				id="contest-filter",
				# "/" で戻ったときに入力済みの文字列を選択状態にしない
				# (選択されていると次の入力で全置換されてしまうため)。
				select_on_focus=False,
			)
			yield ListView(id="contest-list")
			yield Static("", id="contest-count")
			yield Static(
				"↓: 一覧へ  /: 検索へ  Enter: 選択  Ctrl+R: 一覧を再取得  Esc: 閉じる",
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
		more = " (絞り込んでください)" if total > len(hits) else ""
		count.update(f"{len(hits)} / {total} 件{more}")

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
			self.notify("該当するコンテストがありません", severity="warning")

	def action_refresh(self) -> None:
		self.dismiss(REFRESH_CONTESTS)

	def action_cancel(self) -> None:
		self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
	"""はい/いいえの確認ダイアログ。提出前の最終確認に使う。"""

	BINDINGS = [("escape", "cancel", "Cancel")]

	def __init__(self, message: str, *, confirm_label: str = "実行") -> None:
		super().__init__()
		self._message = message
		self._confirm_label = confirm_label

	def compose(self) -> ComposeResult:
		with Vertical(id="confirm-dialog"):
			yield Label("確認", classes="dialog-title")
			yield Static(self._message)
			with Horizontal(classes="dialog-buttons"):
				yield Button("キャンセル", id="confirm-cancel")
				yield Button(self._confirm_label, variant="error", id="confirm-ok")

	def on_mount(self) -> None:
		self.query_one("#confirm-cancel", Button).focus()

	def on_button_pressed(self, event: Button.Pressed) -> None:
		self.dismiss(event.button.id == "confirm-ok")

	def action_cancel(self) -> None:
		self.dismiss(False)


class SubmitScreen(ModalScreen["tuple[Path, str, str] | None"]):
	"""提出するソースファイルと言語を選ぶ画面。

	dismiss する値は (ファイルパス, 言語ID, 言語名) のタプル。
	"""

	BINDINGS = [("escape", "cancel", "Cancel")]

	def __init__(
		self, problem: Problem, languages: list[Language], default_path: str
	) -> None:
		super().__init__()
		self._problem = problem
		self._languages = languages
		self._default_path = default_path

	def _default_language(self) -> str | None:
		for lang in self._languages:
			if "Python" in lang.name and "PyPy" not in lang.name:
				return lang.id
		return self._languages[0].id if self._languages else None

	def compose(self) -> ComposeResult:
		options = [(lang.name, lang.id) for lang in self._languages]
		with Vertical(id="submit-dialog"):
			yield Label(
				f"提出: {self._problem.index} - {self._problem.title}",
				classes="dialog-title",
			)
			yield Label("ソースファイル", classes="dialog-field")
			yield Input(
				value=self._default_path, id="submit-path", classes="dialog-field"
			)
			yield Label("言語", classes="dialog-field")
			yield Select(
				options,
				value=self._default_language(),
				allow_blank=True,
				id="submit-lang",
			)
			with VerticalScroll(id="submit-preview"):
				yield Static("", id="submit-preview-body")
			with Horizontal(classes="dialog-buttons"):
				yield Button("キャンセル", id="submit-cancel")
				yield Button("内容を確認して提出", variant="primary", id="submit-ok")

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
			body.update("[dim]ファイルが見つかりません[/dim]")
			return
		try:
			text = path.read_text(encoding="utf-8")
		except OSError as exc:
			body.update(f"[red]読み込みエラー: {exc}[/red]")
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
		lang_value = self.query_one("#submit-lang", Select).value
		if not raw:
			self.notify("ファイルパスを入力してください", severity="warning")
			return
		if lang_value is Select.BLANK or lang_value is None:
			self.notify("言語を選択してください", severity="warning")
			return
		lang_id = str(lang_value)
		lang_name = next(
			(lang.name for lang in self._languages if lang.id == lang_id), lang_id
		)
		self.dismiss((Path(raw), lang_id, lang_name))

	def action_cancel(self) -> None:
		self.dismiss(None)
