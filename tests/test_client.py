"""client モジュールのテスト (ネットワークに出ない範囲)。"""

from __future__ import annotations

from pathlib import Path

import pytest

from atcoder_tui.client import (
	_EXTRA_ARCHIVE_CATEGORIES,
	SESSION_COOKIE,
	AtCoderClient,
	LoginError,
)


def _client(tmp_path: Path) -> AtCoderClient:
	return AtCoderClient(cookie_path=tmp_path / "session.txt")


class _FakeResponse:
	def __init__(self, text: str, status_code: int = 200) -> None:
		self.text = text
		self.status_code = status_code


def _rows_html(rows: list[tuple[str, str]]) -> str:
	return "".join(
		f'<tr><td><time>2020-01-01 00:00:00+0900</time></td>'
		f'<td><a href="/contests/{cid}">{title}</a></td>'
		f"<td>00:40</td><td>-</td></tr>"
		for cid, title in rows
	)


def _archive_html(rows: list[tuple[str, str]]) -> str:
	"""contest_id/title の行からアーカイブ 1 ページ分の最小 HTML を作る。"""
	return f"<table><tbody>{_rows_html(rows)}</tbody></table>"


def _live_html(rows: list[tuple[str, str]]) -> str:
	"""開催中セクション 1 つだけを持つメインページ風の最小 HTML を作る。"""
	return (
		'<div id="contest-table-action">'
		f"<table><tbody>{_rows_html(rows)}</tbody></table></div>"
	)


def test_login_with_cookie_stores_session(tmp_path: Path, monkeypatch) -> None:
	client = _client(tmp_path)
	monkeypatch.setattr(client, "is_logged_in", lambda: True)
	client.login_with_cookie("abc123")
	stored = {c.name: c.value for c in client._cookies}
	assert stored[SESSION_COOKIE] == "abc123"
	# 保存ファイルが作られる。
	assert (tmp_path / "session.txt").exists()


def test_login_with_cookie_accepts_name_prefix(tmp_path: Path, monkeypatch) -> None:
	client = _client(tmp_path)
	monkeypatch.setattr(client, "is_logged_in", lambda: True)
	# "REVEL_SESSION=..." 形式や引用符付きでも値だけを取り出す。
	client.login_with_cookie('  REVEL_SESSION="xyz789"  ')
	stored = {c.name: c.value for c in client._cookies}
	assert stored[SESSION_COOKIE] == "xyz789"


def test_login_with_cookie_invalid_raises(tmp_path: Path, monkeypatch) -> None:
	client = _client(tmp_path)
	monkeypatch.setattr(client, "is_logged_in", lambda: False)
	with pytest.raises(LoginError):
		client.login_with_cookie("badtoken")


def test_login_with_cookie_empty_raises(tmp_path: Path) -> None:
	client = _client(tmp_path)
	with pytest.raises(LoginError):
		client.login_with_cookie("   ")


def test_get_languages_reads_problem_page(tmp_path: Path, monkeypatch) -> None:
	client = _client(tmp_path)
	seen: list[str] = []

	def fake_get(url: str, **kwargs: object) -> _FakeResponse:
		seen.append(url)
		return _FakeResponse(
			'<form action="/contests/demo/submit">'
			'<select name="data.LanguageId">'
			'<option value="4006">Python</option>'
			"</select></form>"
		)

	monkeypatch.setattr(client, "_get", fake_get)
	languages = client.get_languages("demo", "demo_a")

	assert [(lang.id, lang.name) for lang in languages] == [("4006", "Python")]
	assert seen == ["https://atcoder.jp/contests/demo/tasks/demo_a"]


def test_fetch_all_contests_includes_special_categories(
	tmp_path: Path, monkeypatch
) -> None:
	client = _client(tmp_path)
	# デフォルトスコープには abc001、Weekday カテゴリー (category=20) には awc0001
	# を返すようにし、両方が結果に含まれること、重複が排除されることを確かめる。
	pages = {
		None: _archive_html([("abc001", "AtCoder Beginner Contest 001")]),
		"20": _archive_html(
			[
				("awc0001", "AtCoder Weekday Contest 0001 Beta"),
				# デフォルトと重複する ID。1 件にまとめられるべき。
				("abc001", "AtCoder Beginner Contest 001"),
			]
		),
	}

	def fake_get(url: str, **kwargs: object) -> _FakeResponse:
		params = kwargs.get("params", {})
		assert isinstance(params, dict)
		category = params.get("category")
		return _FakeResponse(pages.get(category, "<table><tbody></tbody></table>"))

	monkeypatch.setattr(client, "_get", fake_get)
	contests = client._fetch_all_contests(progress=None)

	ids = [c.id for c in contests]
	assert "abc001" in ids
	assert "awc0001" in ids
	# 重複 ID は 1 件だけ。
	assert ids.count("abc001") == 1


def test_fetch_all_contests_queries_every_special_category(
	tmp_path: Path, monkeypatch
) -> None:
	client = _client(tmp_path)
	seen: list[object] = []

	def fake_get(url: str, **kwargs: object) -> _FakeResponse:
		params = kwargs.get("params", {})
		assert isinstance(params, dict)
		seen.append(params.get("category"))
		return _FakeResponse("<table><tbody></tbody></table>")

	monkeypatch.setattr(client, "_get", fake_get)
	client._fetch_all_contests(progress=None)

	# デフォルト (None) と全ての特殊カテゴリーが少なくとも 1 回は問い合わせられる。
	assert None in seen
	for category in _EXTRA_ARCHIVE_CATEGORIES:
		assert category in seen


def _patch_cache(monkeypatch, tmp_path: Path) -> None:
	# get_contests がユーザーの実キャッシュに触らないよう、tmp に向ける。
	monkeypatch.setattr(
		"atcoder_tui.client.contests_cache_path",
		lambda: tmp_path / "contests.json",
	)


def test_get_contests_merges_live_and_dedups(tmp_path: Path, monkeypatch) -> None:
	client = _client(tmp_path)
	_patch_cache(monkeypatch, tmp_path)

	def fake_get(url: str, **kwargs: object):
		if url.endswith("/contests/archive"):
			# 終了済み: abc001 と、ライブと重複する awc0098。
			return _FakeResponse(
				_archive_html(
					[
						("abc001", "AtCoder Beginner Contest 001"),
						("awc0098", "AtCoder Weekday Contest 0098 Beta"),
					]
				)
			)
		# メインページ (開催中): awc0098。
		return _FakeResponse(
			_live_html([("awc0098", "AtCoder Weekday Contest 0098 Beta")])
		)

	monkeypatch.setattr(client, "_get", fake_get)
	contests = client.get_contests(force_refresh=True)

	ids = [c.id for c in contests]
	assert "awc0098" in ids
	assert "abc001" in ids
	# アーカイブとライブの重複は 1 件に。
	assert ids.count("awc0098") == 1
	# ライブが先頭に来る。
	assert ids[0] == "awc0098"


def test_get_contests_survives_live_fetch_failure(
	tmp_path: Path, monkeypatch
) -> None:
	from atcoder_tui.client import AtCoderError

	client = _client(tmp_path)
	_patch_cache(monkeypatch, tmp_path)

	def fake_get(url: str, **kwargs: object):
		if url.endswith("/contests/archive"):
			return _FakeResponse(
				_archive_html([("abc001", "AtCoder Beginner Contest 001")])
			)
		raise AtCoderError("ネットワークエラー")

	monkeypatch.setattr(client, "_get", fake_get)
	contests = client.get_contests(force_refresh=True)

	# ライブ取得が失敗してもアーカイブだけは返る。
	assert [c.id for c in contests] == ["abc001"]
