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
	def __init__(self, text: str) -> None:
		self.text = text


def _archive_html(rows: list[tuple[str, str]]) -> str:
	"""contest_id/title の行からアーカイブ 1 ページ分の最小 HTML を作る。"""
	trs = "".join(
		f'<tr><td><time>2020-01-01 00:00:00+0900</time></td>'
		f'<td><a href="/contests/{cid}">{title}</a></td>'
		f"<td>00:40</td><td>-</td></tr>"
		for cid, title in rows
	)
	return f"<table><tbody>{trs}</tbody></table>"


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
