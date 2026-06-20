"""問題本文の HTML を Markdown へ変換する。

主経路は defuddle (Node 製) を npx 経由の subprocess で呼ぶ。defuddle や
Node が使えない環境のために、BeautifulSoup による簡易フォールバックも持つ。
"""

from __future__ import annotations

import subprocess

from bs4 import BeautifulSoup

from .config import DEFUDDLE_COMMAND
from .mathtext import preprocess_math

_DEFUDDLE_TIMEOUT = 60


def _wrap_document(html: str, title: str) -> str:
	"""defuddle が本文抽出しやすいよう、完全な HTML ドキュメントに包む。"""
	return (
		"<!DOCTYPE html><html><head>"
		'<meta charset="utf-8">'
		f"<title>{title}</title>"
		f"</head><body><article>{html}</article></body></html>"
	)


def defuddle_available() -> bool:
	"""defuddle を起動できるか (npx 経由) を確認する。"""
	try:
		proc = subprocess.run(
			["npx", "-y", "defuddle", "--version"],
			capture_output=True,
			text=True,
			timeout=_DEFUDDLE_TIMEOUT,
		)
	except (FileNotFoundError, subprocess.TimeoutExpired):
		return False
	return proc.returncode == 0


def html_to_markdown(html: str, *, title: str = "") -> str:
	"""HTML を Markdown に変換する。defuddle が使えない場合はフォールバック。

	変換前に LaTeX (KaTeX) を Unicode へ前処理しておく。
	"""
	html = preprocess_math(html)
	document = _wrap_document(html, title)
	try:
		proc = subprocess.run(
			DEFUDDLE_COMMAND,
			input=document,
			capture_output=True,
			text=True,
			timeout=_DEFUDDLE_TIMEOUT,
		)
	except (FileNotFoundError, subprocess.TimeoutExpired):
		return fallback_markdown(html)
	if proc.returncode != 0 or not proc.stdout.strip():
		return fallback_markdown(html)
	return proc.stdout.strip()


def fallback_markdown(html: str) -> str:
	"""defuddle を使えない時の簡易 HTML→Markdown 変換。"""
	soup = BeautifulSoup(html, "lxml")
	blocks: list[str] = []
	for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "pre", "li"]):
		name = el.name
		text = el.get_text()
		if name.startswith("h") and len(name) == 2 and name[1].isdigit():
			level = int(name[1])
			heading = text.strip()
			if heading:
				blocks.append("#" * level + " " + heading)
		elif name == "pre":
			blocks.append("```\n" + text.rstrip("\n") + "\n```")
		elif name == "li":
			item = text.strip()
			if item:
				blocks.append("- " + item)
		else:
			paragraph = text.strip()
			if paragraph:
				blocks.append(paragraph)
	return "\n\n".join(blocks)
