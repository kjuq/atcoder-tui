"""atcoder-cli で扱うドメインモデル群。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class Sample:
	"""問題のサンプル入出力 1 ペア。"""

	index: int
	input: str
	output: str


@dataclass(frozen=True)
class ProblemSummary:
	"""コンテストの問題一覧に並ぶ 1 問分の概要。"""

	contest_id: str
	task_id: str
	index: str
	title: str
	url: str


@dataclass
class Problem:
	"""問題ページから抽出した詳細情報。"""

	contest_id: str
	task_id: str
	index: str
	title: str
	url: str
	time_limit: str | None = None
	memory_limit: str | None = None
	samples: list[Sample] = field(default_factory=list)
	# defuddle に渡すための、問題文部分の HTML (lang コンテナ)。
	statement_html: str | None = None
	# defuddle で変換済みの Markdown (遅延設定)。
	markdown: str | None = None


@dataclass(frozen=True)
class Language:
	"""提出言語。id は AtCoder の LanguageId、name は表示名。"""

	id: str
	name: str


@dataclass(frozen=True)
class Submission:
	"""提出一覧の 1 行。"""

	id: str
	task_id: str
	language: str
	status: str
	score: str | None = None
	exec_time: str | None = None
	memory: str | None = None
	submitted_at: str | None = None
	url: str | None = None


class TestStatus(str, Enum):
	"""ローカルサンプルテストの判定結果。"""

	AC = "AC"
	WA = "WA"
	RE = "RE"
	TLE = "TLE"
	CE = "CE"

	@property
	def label(self) -> str:
		return self.value


@dataclass
class TestResult:
	"""1 サンプルに対するローカル実行結果。"""

	index: int
	status: TestStatus
	input: str
	expected: str
	actual: str
	stderr: str = ""
	elapsed: float = 0.0
