"""tester モジュールのテスト (Python ソースを対象に各判定を検証)。"""

from __future__ import annotations

import textwrap
from pathlib import Path

from atcoder_tui.models import Sample, TestStatus
from atcoder_tui.tester import parse_time_limit, run_samples


def _write(tmp_path: Path, code: str) -> Path:
	path = tmp_path / "sol.py"
	path.write_text(textwrap.dedent(code), encoding="utf-8")
	return path


def test_parse_time_limit() -> None:
	assert parse_time_limit("2 sec") == 2.0
	assert parse_time_limit("1.5 sec") == 1.5
	assert parse_time_limit(None) == 2.0


def test_all_accepted(tmp_path: Path) -> None:
	src = _write(
		tmp_path,
		"""
		a, b = map(int, input().split())
		print("Even" if a * b % 2 == 0 else "Odd")
		""",
	)
	samples = [Sample(1, "3 4\n", "Even\n"), Sample(2, "1 21\n", "Odd\n")]
	results = run_samples(src, samples)
	assert [r.status for r in results] == [TestStatus.AC, TestStatus.AC]


def test_wrong_answer(tmp_path: Path) -> None:
	src = _write(tmp_path, "print('Odd')")
	results = run_samples(src, [Sample(1, "3 4\n", "Even\n")])
	assert results[0].status == TestStatus.WA
	assert results[0].actual.strip() == "Odd"


def test_runtime_error(tmp_path: Path) -> None:
	src = _write(tmp_path, "raise ValueError('boom')")
	results = run_samples(src, [Sample(1, "", "")])
	assert results[0].status == TestStatus.RE
	assert "ValueError" in results[0].stderr


def test_time_limit_exceeded(tmp_path: Path) -> None:
	src = _write(tmp_path, "while True:\n\tpass")
	results = run_samples(src, [Sample(1, "", "")], time_limit=0.5)
	assert results[0].status == TestStatus.TLE


def test_trailing_whitespace_is_ignored(tmp_path: Path) -> None:
	# 末尾の空白や改行差は AC とみなす。
	src = _write(tmp_path, "print('Even ')")
	results = run_samples(src, [Sample(1, "3 4\n", "Even")])
	assert results[0].status == TestStatus.AC
