"""client モジュールのテスト (ネットワークに出ない範囲)。"""

from __future__ import annotations

from pathlib import Path

import pytest

from atcoder_cli.client import SESSION_COOKIE, AtCoderClient, LoginError


def _client(tmp_path: Path) -> AtCoderClient:
	return AtCoderClient(cookie_path=tmp_path / "session.txt")


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
