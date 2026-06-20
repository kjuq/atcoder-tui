"""ローカルでサンプル入力に対してソースを実行し、合否を判定する。

言語は拡張子から推定する。必要ならコンパイルし、各サンプルを stdin で与えて
標準出力を期待値と比較する。判定は AC / WA / RE / TLE / CE。
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Sample, TestResult, TestStatus

# コンパイルに課す上限 (秒)。
_BUILD_TIMEOUT = 60.0


@dataclass(frozen=True)
class RunnerConfig:
	"""言語ごとの実行方法。コマンド内の {file}/{dir}/{exe} を実行時に展開する。"""

	name: str
	run: list[str]
	build: list[str] | None = None


# 拡張子 -> 実行設定。
_RUNNERS: dict[str, RunnerConfig] = {
	".py": RunnerConfig(name="Python", run=["python3", "{file}"]),
	".cpp": RunnerConfig(
		name="C++",
		build=["g++", "-O2", "-std=gnu++20", "-o", "{exe}", "{file}"],
		run=["{exe}"],
	),
	".cc": RunnerConfig(
		name="C++",
		build=["g++", "-O2", "-std=gnu++20", "-o", "{exe}", "{file}"],
		run=["{exe}"],
	),
	".c": RunnerConfig(
		name="C",
		build=["gcc", "-O2", "-o", "{exe}", "{file}"],
		run=["{exe}"],
	),
	".rs": RunnerConfig(
		name="Rust",
		build=["rustc", "-O", "-o", "{exe}", "{file}"],
		run=["{exe}"],
	),
	".go": RunnerConfig(name="Go", run=["go", "run", "{file}"]),
	".js": RunnerConfig(name="JavaScript", run=["node", "{file}"]),
}


class TesterError(Exception):
	"""テスト実行の前提を満たさない場合の例外。"""


def detect_runner(source_path: Path) -> RunnerConfig:
	"""拡張子から実行設定を選ぶ。未対応なら TesterError。"""
	suffix = source_path.suffix.lower()
	runner = _RUNNERS.get(suffix)
	if runner is None:
		raise TesterError(f"未対応の拡張子です: {suffix or '(なし)'}")
	return runner


def parse_time_limit(time_limit: str | None, *, default: float = 2.0) -> float:
	"""'2 sec' のような文字列から秒数を取り出す。"""
	if not time_limit:
		return default
	match = re.search(r"([\d.]+)", time_limit)
	return float(match.group(1)) if match else default


def _normalize(text: str) -> str:
	"""比較用に行末空白と末尾の空行を取り除く。"""
	lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
	while lines and lines[-1] == "":
		lines.pop()
	return "\n".join(lines)


def _expand(template: list[str], *, file: Path, workdir: Path, exe: Path) -> list[str]:
	mapping = {"file": str(file), "dir": str(workdir), "exe": str(exe)}
	return [part.format(**mapping) for part in template]


def run_samples(
	source_path: Path,
	samples: list[Sample],
	*,
	runner: RunnerConfig | None = None,
	time_limit: float = 2.0,
) -> list[TestResult]:
	"""ソースを各サンプルで実行し、TestResult のリストを返す。

	コンパイルに失敗した場合は CE を 1 件だけ返す。
	"""
	source_path = Path(source_path)
	if not source_path.exists():
		raise TesterError(f"ソースファイルが見つかりません: {source_path}")
	runner = runner or detect_runner(source_path)

	with tempfile.TemporaryDirectory(prefix="atcoder-cli-") as tmp:
		workdir = Path(tmp)
		exe = workdir / "a.out"

		if runner.build:
			build_cmd = _expand(runner.build, file=source_path, workdir=workdir, exe=exe)
			try:
				proc = subprocess.run(
					build_cmd,
					capture_output=True,
					text=True,
					timeout=_BUILD_TIMEOUT,
				)
			except FileNotFoundError as exc:
				raise TesterError(f"コンパイラが見つかりません: {build_cmd[0]}") from exc
			except subprocess.TimeoutExpired:
				return [
					TestResult(
						index=0,
						status=TestStatus.CE,
						input="",
						expected="",
						actual="",
						stderr="コンパイルがタイムアウトしました。",
					)
				]
			if proc.returncode != 0:
				return [
					TestResult(
						index=0,
						status=TestStatus.CE,
						input="",
						expected="",
						actual="",
						stderr=proc.stderr,
					)
				]

		run_cmd = _expand(runner.run, file=source_path, workdir=workdir, exe=exe)
		results: list[TestResult] = []
		for sample in samples:
			results.append(
				_run_one(run_cmd, sample, time_limit=time_limit)
			)
		return results


def _run_one(
	run_cmd: list[str], sample: Sample, *, time_limit: float
) -> TestResult:
	start = time.monotonic()
	try:
		proc = subprocess.run(
			run_cmd,
			input=sample.input,
			capture_output=True,
			text=True,
			timeout=time_limit,
		)
	except FileNotFoundError as exc:
		raise TesterError(f"実行コマンドが見つかりません: {run_cmd[0]}") from exc
	except subprocess.TimeoutExpired:
		return TestResult(
			index=sample.index,
			status=TestStatus.TLE,
			input=sample.input,
			expected=sample.output,
			actual="",
			elapsed=time_limit,
		)
	elapsed = time.monotonic() - start
	actual = proc.stdout
	if proc.returncode != 0:
		status = TestStatus.RE
	elif _normalize(actual) == _normalize(sample.output):
		status = TestStatus.AC
	else:
		status = TestStatus.WA
	return TestResult(
		index=sample.index,
		status=status,
		input=sample.input,
		expected=sample.output,
		actual=actual,
		stderr=proc.stderr,
		elapsed=elapsed,
	)
