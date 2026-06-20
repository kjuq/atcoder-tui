"""parser モジュールのテスト。

fixture は AtCoder の DOM 構造を模した自作のサンプル HTML を使う
(実際の問題文は著作物のため同梱しない)。
"""

from __future__ import annotations

from pathlib import Path

from atcoder_tui import parser

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
	return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_csrf_token() -> None:
	token = parser.parse_csrf_token(_read("sample_task.html"))
	assert token is not None
	assert len(token) > 0


def test_parse_contest_archive() -> None:
	html = _read("sample_archive.html")
	contests = parser.parse_contest_archive(html)
	assert len(contests) == 4
	ids = [c.id for c in contests]
	assert ids == ["demo102", "demo101", "demo100", "demoreg050"]
	first = contests[0]
	assert first.title == "Demo Beginner Contest 102"
	assert first.rated == "~ 1999"
	assert first.start_time == "2024-06-01 21:00:00+0900"
	assert first.url.endswith("/contests/demo102")


def test_parse_archive_last_page() -> None:
	html = _read("sample_archive.html")
	assert parser.parse_archive_last_page(html) == 3


def test_parse_task_list() -> None:
	summaries = parser.parse_task_list(_read("sample_tasks.html"), "demo")
	assert len(summaries) == 4
	first = summaries[0]
	assert first.index == "A"
	assert first.title == "Sum Parity"
	assert first.task_id == "demo_a"
	assert first.url.endswith("/contests/demo/tasks/demo_a")
	# C 問題は別コンテストとの共通問題を想定し、task_id が異なる。
	assert summaries[2].task_id == "shared_c"


def test_parse_problem_samples() -> None:
	problem = parser.parse_problem(
		_read("sample_task.html"),
		contest_id="demo",
		task_id="demo_a",
		url="https://atcoder.jp/contests/demo/tasks/demo_a",
	)
	assert problem.index == "A"
	assert problem.title == "Sum Parity"
	assert problem.time_limit == "2 sec"
	assert problem.memory_limit == "256 MiB"
	assert len(problem.samples) == 2
	assert problem.samples[0].input == "2 3\n"
	assert problem.samples[0].output == "Odd\n"
	assert problem.samples[1].input == "4 6\n"
	assert problem.samples[1].output == "Even\n"
	assert problem.statement_html is not None
	assert "問題文" in problem.statement_html


def test_parse_problem_prefer_en() -> None:
	problem = parser.parse_problem(
		_read("sample_task.html"),
		contest_id="demo",
		task_id="demo_a",
		url="https://atcoder.jp/contests/demo/tasks/demo_a",
		prefer_lang="en",
	)
	# 英語コンテナでも同じサンプルが取れる。
	assert len(problem.samples) == 2
	assert problem.samples[0].input == "2 3\n"
	assert problem.statement_html is not None
	assert "Problem Statement" in problem.statement_html
