"""AtCoder と HTTP でやり取りするクライアント。

AtCoder には公開 API が無いため、ログイン済みセッションを使った
スクレイピングで問題取得・提出・提出一覧取得を行う。CSRF トークンと
セッション cookie の扱いは online-judge-tools の実装を参考にしている。
"""

from __future__ import annotations

import dataclasses
import http.cookiejar
import json
import time
from collections.abc import Callable
from pathlib import Path

import requests

from . import parser
from .config import (
	REQUEST_INTERVAL,
	USER_AGENT,
	contests_cache_path,
	session_path,
)
from .models import Contest, Language, Problem, ProblemSummary, Submission

BASE_URL = "https://atcoder.jp"

# AtCoder のログインセッションを表す Cookie 名 (Revel フレームワーク)。
SESSION_COOKIE = "REVEL_SESSION"


class AtCoderError(Exception):
	"""AtCoder クライアントの基底例外。"""


class LoginError(AtCoderError):
	"""ログインに失敗した。"""


class NotLoggedInError(AtCoderError):
	"""ログインが必要な操作をログインせずに実行しようとした。"""


class SubmissionError(AtCoderError):
	"""提出に失敗した。"""


class AtCoderClient:
	"""AtCoder へのアクセスをまとめたクライアント。"""

	def __init__(self, cookie_path: Path | None = None) -> None:
		self._cookie_path = cookie_path or session_path()
		self._session = requests.Session()
		self._session.headers["User-Agent"] = USER_AGENT
		self._cookies = http.cookiejar.LWPCookieJar(str(self._cookie_path))
		if self._cookie_path.exists():
			try:
				self._cookies.load(ignore_discard=True)
			except (http.cookiejar.LoadError, OSError):
				pass
		self._session.cookies = self._cookies  # type: ignore[assignment]
		self._last_request = 0.0

	# -- 低レベル HTTP -------------------------------------------------

	def _throttle(self) -> None:
		elapsed = time.monotonic() - self._last_request
		if elapsed < REQUEST_INTERVAL:
			time.sleep(REQUEST_INTERVAL - elapsed)
		self._last_request = time.monotonic()

	def _get(self, url: str, **kwargs: object) -> requests.Response:
		self._throttle()
		try:
			return self._session.get(url, **kwargs)  # type: ignore[arg-type]
		except requests.RequestException as exc:
			raise AtCoderError(f"GET に失敗しました: {url} ({exc})") from exc

	def _post(self, url: str, data: dict[str, str]) -> requests.Response:
		self._throttle()
		try:
			return self._session.post(url, data=data)
		except requests.RequestException as exc:
			raise AtCoderError(f"POST に失敗しました: {url} ({exc})") from exc

	def _save_cookies(self) -> None:
		self._cookie_path.parent.mkdir(parents=True, exist_ok=True)
		self._cookies.save(ignore_discard=True)

	# -- 認証 ----------------------------------------------------------

	def is_logged_in(self) -> bool:
		"""ログイン済みかどうか。/settings へのアクセスで判定する。"""
		resp = self._get(f"{BASE_URL}/settings", allow_redirects=False)
		return resp.status_code == 200

	def login_with_cookie(self, session_value: str) -> None:
		"""ブラウザで取得したセッション Cookie (REVEL_SESSION) でログインする。

		AtCoder のログインフォームは Cloudflare Turnstile で保護されており、
		requests だけではユーザ名/パスワードによるログインができない。そこで
		ユーザが自分のブラウザでログインして得た REVEL_SESSION を取り込む。
		"""
		value = session_value.strip()
		# "REVEL_SESSION=..." 形式で貼られても受け付ける。
		if value.startswith(f"{SESSION_COOKIE}="):
			value = value[len(SESSION_COOKIE) + 1 :]
		value = value.strip().strip('"')
		if not value:
			raise LoginError("セッション Cookie (REVEL_SESSION) を入力してください。")
		cookie = requests.cookies.create_cookie(
			name=SESSION_COOKIE, value=value, domain="atcoder.jp", path="/"
		)
		self._cookies.set_cookie(cookie)
		self._save_cookies()
		if not self.is_logged_in():
			raise LoginError(
				"セッションが無効です。ブラウザでログインし直し、"
				"REVEL_SESSION の値を確認してください。"
			)

	def logout(self) -> None:
		"""ローカルのセッションを破棄する。"""
		self._cookies.clear()
		if self._cookie_path.exists():
			self._cookie_path.unlink()

	# -- 取得系 --------------------------------------------------------

	def get_contests(
		self,
		*,
		force_refresh: bool = False,
		progress: Callable[[int, int], None] | None = None,
	) -> list[Contest]:
		"""過去コンテストの一覧を取得する。

		アーカイブは数十ページに渡るため、初回取得時にローカルへキャッシュし、
		以降はキャッシュを使う。force_refresh=True で再取得する。
		progress(現在ページ, 総ページ数) が指定されると進捗を通知する。
		"""
		cache = contests_cache_path()
		if not force_refresh and cache.exists():
			cached = self._load_contests_cache(cache)
			if cached:
				return cached
		contests = self._fetch_all_contests(progress)
		self._save_contests_cache(cache, contests)
		return contests

	@staticmethod
	def _load_contests_cache(cache: Path) -> list[Contest]:
		try:
			data = json.loads(cache.read_text(encoding="utf-8"))
			return [Contest(**item) for item in data["contests"]]
		except (json.JSONDecodeError, OSError, KeyError, TypeError):
			return []

	@staticmethod
	def _save_contests_cache(cache: Path, contests: list[Contest]) -> None:
		payload = {"contests": [dataclasses.asdict(c) for c in contests]}
		try:
			cache.write_text(
				json.dumps(payload, ensure_ascii=False), encoding="utf-8"
			)
		except OSError:
			pass

	def _fetch_all_contests(
		self, progress: Callable[[int, int], None] | None
	) -> list[Contest]:
		archive_url = f"{BASE_URL}/contests/archive"
		first = self._get(archive_url, params={"lang": "ja"})
		last_page = parser.parse_archive_last_page(first.text)
		contests = parser.parse_contest_archive(first.text)
		if progress:
			progress(1, last_page)
		for page in range(2, last_page + 1):
			resp = self._get(archive_url, params={"lang": "ja", "page": page})
			contests.extend(parser.parse_contest_archive(resp.text))
			if progress:
				progress(page, last_page)
		return contests

	def get_task_list(self, contest_id: str) -> list[ProblemSummary]:
		url = f"{BASE_URL}/contests/{contest_id}/tasks"
		resp = self._get(url)
		if resp.status_code == 404:
			raise AtCoderError(f"コンテストが見つかりません: {contest_id}")
		return parser.parse_task_list(resp.text, contest_id)

	def get_problem(
		self, contest_id: str, task_id: str, *, prefer_lang: str = "ja"
	) -> Problem:
		url = f"{BASE_URL}/contests/{contest_id}/tasks/{task_id}"
		resp = self._get(url)
		if resp.status_code == 404:
			raise AtCoderError(f"問題が見つかりません: {contest_id}/{task_id}")
		return parser.parse_problem(
			resp.text, contest_id, task_id, url, prefer_lang=prefer_lang
		)

	def get_languages(self, contest_id: str) -> list[Language]:
		"""提出フォームから利用可能な言語一覧を取得する (要ログイン)。"""
		url = f"{BASE_URL}/contests/{contest_id}/submit"
		resp = self._get(url, allow_redirects=False)
		if resp.status_code != 200:
			raise NotLoggedInError("提出フォームの取得にはログインが必要です。")
		return parser.parse_languages(resp.text)

	def get_my_submissions(self, contest_id: str) -> list[Submission]:
		"""自分の提出一覧を取得する (要ログイン)。"""
		url = f"{BASE_URL}/contests/{contest_id}/submissions/me"
		resp = self._get(url, allow_redirects=False)
		if resp.status_code != 200:
			raise NotLoggedInError("提出一覧の取得にはログインが必要です。")
		return parser.parse_submissions(resp.text, contest_id)

	# -- 提出 ----------------------------------------------------------

	def submit(
		self, contest_id: str, task_id: str, language_id: str, source: str
	) -> Submission | None:
		"""ソースコードを提出する (要ログイン)。直近の提出を返す。"""
		submit_url = f"{BASE_URL}/contests/{contest_id}/submit"
		page = self._get(submit_url, allow_redirects=False)
		if page.status_code != 200:
			raise NotLoggedInError("提出にはログインが必要です。")
		token = parser.parse_csrf_token(page.text)
		if token is None:
			raise SubmissionError("提出フォームから csrf_token を取得できませんでした。")
		resp = self._post(
			submit_url,
			data={
				"csrf_token": token,
				"data.TaskScreenName": task_id,
				"data.LanguageId": language_id,
				"sourceCode": source,
			},
		)
		self._save_cookies()
		# 提出成功時は submissions/me へリダイレクトされる。
		if "/submit" in resp.url and "submissions" not in resp.url:
			raise SubmissionError(
				"提出に失敗しました。言語IDやログイン状態を確認してください。"
			)
		submissions = self.get_my_submissions(contest_id)
		for sub in submissions:
			if sub.task_id == task_id:
				return sub
		return submissions[0] if submissions else None
