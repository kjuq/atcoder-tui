"""AtCoder のページ HTML をパースしてドメインモデルへ変換する。

構造は ABC/ARC/AGC の現行フォーマットを基準にしつつ、見出し文字列ベースの
フォールバックを併用して旧フォーマットにもある程度耐えるようにしている。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import Contest, Language, Problem, ProblemSummary, Sample, Submission

BASE_URL = "https://atcoder.jp"

_INPUT_MARKERS = ("入力例", "Sample Input")
_OUTPUT_MARKERS = ("出力例", "Sample Output")


def make_soup(html: str) -> BeautifulSoup:
	return BeautifulSoup(html, "lxml")


def parse_csrf_token(html: str) -> str | None:
	"""ページに埋め込まれた csrf_token を取り出す。"""
	soup = make_soup(html)
	tag = soup.find("input", attrs={"name": "csrf_token"})
	if isinstance(tag, Tag):
		value = tag.get("value")
		if isinstance(value, str) and value:
			return value
	return None


def parse_archive_last_page(html: str) -> int:
	"""コンテストアーカイブのページネーションから最終ページ番号を得る。

	ページリンクは ``...&amp;page=29`` のように現れるため、page=N を直接拾う。
	"""
	pages = [int(m) for m in re.findall(r"page=(\d+)", html)]
	return max(pages) if pages else 1


def _parse_contest_rows(table: Tag) -> list[Contest]:
	"""コンテスト一覧テーブル (開始時刻/名前/時間/Rated の 4 列) を解析する。

	アーカイブとメインページ (開催中/予定/デイリー) は同じ行構造のため共通化する。
	"""
	contests: list[Contest] = []
	body = table.find("tbody")
	rows = body.find_all("tr") if isinstance(body, Tag) else table.find_all("tr")
	for tr in rows:
		# コンテストへのリンク (timeanddate 等の外部リンクは除外)。
		link = None
		for a in tr.find_all("a"):
			href = a.get("href", "")
			if href.startswith("/contests/") and "/archive" not in href:
				link = a
				break
		if link is None:
			continue
		href = link.get("href", "")
		contest_id = href.rstrip("/").rsplit("/", 1)[-1]
		title = link.get_text(strip=True)
		tds = tr.find_all("td")
		time_el = tr.find("time")
		if isinstance(time_el, Tag):
			start = time_el.get_text(strip=True)
		else:
			start = tds[0].get_text(strip=True) if tds else ""
		rated = tds[3].get_text(strip=True) if len(tds) > 3 else ""
		contests.append(
			Contest(
				id=contest_id,
				title=title,
				start_time=start,
				rated=rated,
				url=urljoin(BASE_URL, href),
			)
		)
	return contests


def parse_contest_archive(html: str) -> list[Contest]:
	"""コンテストアーカイブ 1 ページ分から Contest のリストを作る。"""
	soup = make_soup(html)
	table = soup.find("table")
	if not isinstance(table, Tag):
		return []
	return _parse_contest_rows(table)


def parse_contest_list(html: str, section_ids: Iterable[str]) -> list[Contest]:
	"""メインの /contests/ ページから、指定セクションのコンテストを取り出す。

	section_ids には ``contest-table-action`` (開催中) などの ``<div>`` の id を
	渡す。アーカイブに含まれない開催中/予定/デイリーのコンテストを拾うために使う。
	存在しない/空のセクションは無視する。
	"""
	soup = make_soup(html)
	contests: list[Contest] = []
	for section_id in section_ids:
		section = soup.find(id=section_id)
		if not isinstance(section, Tag):
			continue
		table = section.find("table")
		if isinstance(table, Tag):
			contests.extend(_parse_contest_rows(table))
	return contests


def parse_task_list(html: str, contest_id: str) -> list[ProblemSummary]:
	"""コンテストの問題一覧ページから ProblemSummary のリストを作る。"""
	soup = make_soup(html)
	summaries: list[ProblemSummary] = []
	table = soup.find("table")
	if not isinstance(table, Tag):
		return summaries
	body = table.find("tbody")
	rows = body.find_all("tr") if isinstance(body, Tag) else table.find_all("tr")
	for tr in rows:
		links = [a for a in tr.find_all("a") if a.get("href", "").find("/tasks/") != -1]
		if len(links) < 2:
			continue
		index = links[0].get_text(strip=True)
		title = links[1].get_text(strip=True)
		href = links[0].get("href", "")
		task_id = href.rstrip("/").rsplit("/", 1)[-1]
		summaries.append(
			ProblemSummary(
				contest_id=contest_id,
				task_id=task_id,
				index=index,
				title=title,
				url=urljoin(BASE_URL, href),
			)
		)
	return summaries


def _statement_root(soup: BeautifulSoup) -> Tag | None:
	root = soup.find(id="task-statement")
	return root if isinstance(root, Tag) else None


def _language_container(soup: BeautifulSoup, prefer: str) -> Tag | None:
	"""prefer ("ja"/"en") に対応する言語コンテナ。なければ task-statement 全体。"""
	root = _statement_root(soup)
	if root is None:
		return None
	wanted = f"lang-{prefer}"
	span = root.find("span", class_=wanted)
	if isinstance(span, Tag):
		return span
	# 反対の言語しか無い場合や lang 分割が無い旧形式は root をそのまま使う。
	for fallback in ("lang-ja", "lang-en"):
		span = root.find("span", class_=fallback)
		if isinstance(span, Tag):
			return span
	return root


def _pre_for_heading(h3: Tag) -> Tag | None:
	"""見出し h3 に対応する pre を探す。"""
	part = h3.find_parent("div", class_="part")
	if isinstance(part, Tag):
		pre = part.find("pre")
		if isinstance(pre, Tag):
			return pre
	# div.part に包まれていない旧形式は文書順で次の pre を採用する。
	nxt = h3.find_next("pre")
	return nxt if isinstance(nxt, Tag) else None


def _extract_samples(container: Tag) -> list[Sample]:
	inputs: list[str] = []
	outputs: list[str] = []
	for h3 in container.find_all("h3"):
		text = h3.get_text(strip=True)
		pre = _pre_for_heading(h3)
		if pre is None:
			continue
		body = pre.get_text()
		if any(m in text for m in _INPUT_MARKERS):
			inputs.append(body)
		elif any(m in text for m in _OUTPUT_MARKERS):
			outputs.append(body)
	samples: list[Sample] = []
	for i, (inp, out) in enumerate(zip(inputs, outputs), start=1):
		samples.append(Sample(index=i, input=inp, output=out))
	return samples


def _parse_limits(soup: BeautifulSoup) -> tuple[str | None, str | None]:
	""""Time Limit: 2 sec / Memory Limit: 256 MiB" から両者を取り出す。"""
	text_node = soup.find(string=re.compile(r"Time Limit"))
	if not text_node:
		return None, None
	text = str(text_node)
	tl = re.search(r"Time Limit:\s*([^/]+)", text)
	ml = re.search(r"Memory Limit:\s*(.+)", text)
	tlv = tl.group(1).strip() if tl else None
	mlv = ml.group(1).strip() if ml else None
	return tlv, mlv


def _split_title(soup: BeautifulSoup, fallback_id: str) -> tuple[str, str]:
	"""ページタイトルから ("A", "Product") のように index と題名を分離する。"""
	# 問題ページ上部の見出し span.h2 を優先し、無ければ <title> を使う。
	# span.h2 直下には解説ボタン等のリンクが含まれるため、直下テキストノードだけを拾う。
	heading = soup.select_one("#main-container span.h2")
	raw = ""
	if isinstance(heading, Tag):
		raw = "".join(heading.find_all(string=True, recursive=False)).strip()
	if not raw:
		title_tag = soup.find("title")
		raw = title_tag.get_text(strip=True) if title_tag else ""
	# "A - Product - AtCoder ..." のような余分な後置を落とす。
	raw = raw.split(" - AtCoder")[0].strip()
	if " - " in raw:
		index, title = raw.split(" - ", 1)
		return index.strip(), title.strip()
	return fallback_id, raw or fallback_id


def parse_problem(
	html: str,
	contest_id: str,
	task_id: str,
	url: str,
	*,
	prefer_lang: str = "ja",
) -> Problem:
	"""問題ページの HTML から Problem を構築する。"""
	soup = make_soup(html)
	container = _language_container(soup, prefer_lang)
	samples = _extract_samples(container) if container is not None else []
	tl, ml = _parse_limits(soup)
	index, title = _split_title(soup, task_id)
	statement_html = str(container) if container is not None else None
	return Problem(
		contest_id=contest_id,
		task_id=task_id,
		index=index,
		title=title,
		url=url,
		time_limit=tl,
		memory_limit=ml,
		samples=samples,
		statement_html=statement_html,
	)


def parse_languages(html: str) -> list[Language]:
	"""提出ページの言語 select から Language の一覧を作る (重複排除)。"""
	soup = make_soup(html)
	seen: dict[str, str] = {}
	for select in soup.find_all("select", attrs={"name": "data.LanguageId"}):
		for option in select.find_all("option"):
			value = option.get("value")
			name = option.get_text(strip=True)
			if value and name and value not in seen:
				seen[value] = name
	return [Language(id=v, name=n) for v, n in seen.items()]


def parse_submissions(html: str, contest_id: str) -> list[Submission]:
	"""自分の提出一覧ページから Submission のリストを作る。"""
	soup = make_soup(html)
	results: list[Submission] = []
	table = soup.find("table")
	if not isinstance(table, Tag):
		return results
	body = table.find("tbody")
	rows = body.find_all("tr") if isinstance(body, Tag) else []
	for tr in rows:
		task_link = tr.find("a", href=re.compile(r"/tasks/"))
		detail_link = tr.find("a", href=re.compile(r"/submissions/\d+"))
		if not isinstance(task_link, Tag):
			continue
		task_href = task_link.get("href", "")
		task_id = task_href.rstrip("/").rsplit("/", 1)[-1]
		status_node = tr.find(attrs={"data-status": True})
		if isinstance(status_node, Tag):
			status = status_node.get("data-status", "").strip() or status_node.get_text(strip=True)
		else:
			status = ""
		time_node = tr.find("time")
		submitted_at = time_node.get_text(strip=True) if isinstance(time_node, Tag) else None
		sub_id = ""
		sub_url = None
		if isinstance(detail_link, Tag):
			href = detail_link.get("href", "")
			sub_id = href.rstrip("/").rsplit("/", 1)[-1]
			sub_url = urljoin(BASE_URL, href)
		tds = tr.find_all("td")
		# 言語/得点/実行時間/メモリは列位置が変動しうるので緩く拾う。
		language = tds[3].get_text(strip=True) if len(tds) > 3 else ""
		results.append(
			Submission(
				id=sub_id,
				task_id=task_id,
				language=language,
				status=status,
				submitted_at=submitted_at,
				url=sub_url,
			)
		)
	return results
