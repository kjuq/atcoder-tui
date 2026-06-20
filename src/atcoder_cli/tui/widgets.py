"""TUI を構成するカスタムウィジェット群。"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Label, ListItem, ListView, Markdown

from ..models import Problem, ProblemSummary, Sample, TestResult, TestStatus

# 判定ごとの表示色。
_STATUS_COLOR: dict[TestStatus, str] = {
	TestStatus.AC: "green",
	TestStatus.WA: "red",
	TestStatus.RE: "yellow",
	TestStatus.TLE: "magenta",
	TestStatus.CE: "red",
}


class ProblemItem(ListItem):
	"""問題一覧の 1 行。元の ProblemSummary を保持する。"""

	def __init__(self, summary: ProblemSummary) -> None:
		super().__init__(Label(f"{summary.index}  {summary.title}"))
		self.summary = summary


class ProblemList(ListView):
	"""問題一覧。矢印キーに加えて j/k で上下移動できる。"""

	BINDINGS = [
		Binding("j", "cursor_down", "Down", show=False),
		Binding("k", "cursor_up", "Up", show=False),
	]


class ResultsPanel(DataTable):
	"""サンプル一覧とローカルテスト結果を表示するテーブル。"""

	# パネル内の上下移動は j/k でも行える (h/l はパネル間移動に使う)。
	BINDINGS = [
		Binding("j", "cursor_down", "Down", show=False),
		Binding("k", "cursor_up", "Up", show=False),
	]

	def on_mount(self) -> None:
		self.cursor_type = "row"
		self.zebra_stripes = True
		self.add_columns("#", "結果", "時間")

	def show_samples(self, samples: list[Sample]) -> None:
		"""テスト前のサンプル一覧 (結果は未実行)。"""
		self.clear()
		for sample in samples:
			self.add_row(str(sample.index), Text("未実行", style="dim"), "")

	def show_results(self, results: list[TestResult]) -> None:
		"""ローカルテストの結果を反映する。"""
		self.clear()
		for result in results:
			color = _STATUS_COLOR.get(result.status, "white")
			status = Text(result.status.value, style=f"bold {color}")
			elapsed = f"{result.elapsed:.2f}s" if result.elapsed else ""
			label = str(result.index) if result.index else "-"
			self.add_row(label, status, elapsed)


class StatementPanel(VerticalScroll):
	"""問題文を Markdown で表示するスクロール領域。"""

	# 上下スクロールは j/k でも行える (h/l はパネル間移動に使う)。
	BINDINGS = [
		Binding("j", "scroll_down", "Down", show=False),
		Binding("k", "scroll_up", "Up", show=False),
	]

	def compose(self) -> ComposeResult:
		yield Markdown(id="statement-md")

	def show_message(self, message: str) -> None:
		self.query_one("#statement-md", Markdown).update(message)

	def show_problem(self, problem: Problem) -> None:
		limits = f"Time Limit: {problem.time_limit} / Memory Limit: {problem.memory_limit}"
		header = (
			f"# {problem.index} - {problem.title}\n\n"
			f"{limits}\n\n"
			f"{problem.url}\n\n---\n\n"
		)
		body = problem.markdown or "(本文を変換できませんでした)"
		self.query_one("#statement-md", Markdown).update(header + body)
		self.scroll_home(animate=False)
