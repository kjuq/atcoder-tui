"""提出画面のロジックのテスト。"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult

from atcoder_tui.models import Language
from atcoder_tui.tui.modals import LanguageSelect, LanguageSelectScreen


def test_language_select_filters_by_name() -> None:
	select = LanguageSelect(
		[
			("Python (CPython 3.11.4)", "4006"),
			("C++23 (GCC 12.2.0)", "5010"),
			("Rust 1.70.0", "5001"),
		],
		allow_blank=True,
	)

	select._filter_query = "python"
	assert select._filtered_options() == [
		("Python (CPython 3.11.4)", "4006")
	]
	select._filter_query = "GCC"
	assert select._filtered_options() == [("C++23 (GCC 12.2.0)", "5010")]
	select._filter_query = ""
	assert select._filtered_options() == [
		("Python (CPython 3.11.4)", "4006"),
		("C++23 (GCC 12.2.0)", "5010"),
		("Rust 1.70.0", "5001"),
	]


def test_language_select_screen_keeps_selected_language() -> None:
	languages = [Language("python", "Python"), Language("cpp", "C++")]
	screen = LanguageSelectScreen(languages, languages[1])

	assert screen._selected_id == "cpp"


class _LanguageSearchApp(App[None]):
	def compose(self) -> ComposeResult:
		yield LanguageSelect(
			[("Python", "py"), ("C++", "cpp"), ("Rust", "rs")],
			id="lang",
			value="py",
			allow_blank=True,
		)


def test_language_select_keeps_typed_query_and_supports_editing() -> None:
	async def scenario() -> None:
		app = _LanguageSearchApp()
		async with app.run_test() as pilot:
			select = app.query_one("#lang", LanguageSelect)
			select.focus()
			await pilot.press("enter")
			await pilot.press(*"python")
			await pilot.pause()
			assert select._filter_query == "python"

			await pilot.press("ctrl+w")
			await pilot.pause()
			assert select._filter_query == ""

			await pilot.press(*"c++")
			await pilot.press("ctrl+u")
			await pilot.pause()
			assert select._filter_query == ""

	asyncio.run(scenario())
