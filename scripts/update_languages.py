#!/usr/bin/env python3
"""Update the bundled AtCoder submission-language catalog.

The AtCoder language-list page is the source of truth.  This script extracts
the language headings and their file names, then writes the JSON consumed by
the TUI.  It intentionally does not try to copy AtCoder's build commands:
local sample runners are maintained separately in ``atcoder_tui.tester``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "src/atcoder_tui/data/languages.json"
DEFAULT_URL = "https://img.atcoder.jp/file/language-update/2025-10/language-list.html"


def _language_key(name: str) -> str:
	"""Import the application's family matcher without requiring installation."""
	src_root = str(PROJECT_ROOT / "src")
	if src_root not in sys.path:
		sys.path.insert(0, src_root)
	from atcoder_tui.languages import language_key

	return language_key(name)


def _stable_id(name: str, family: str, occurrences: dict[str, int]) -> str:
	"""Return a readable ID that survives version-only language updates."""
	normalized = name.casefold()
	base = family
	variants = (
		("csharp", "native aot", "csharp-aot"),
		("csharp", ".net", "csharp-dotnet"),
		("cpp", "ioi", "cpp-ioi"),
		("cpp", "clang", "cpp-clang"),
		("c", "clang", "c-clang"),
		("clojure", "aot", "clojure-aot"),
		("clojurescript", "", "clojurescript"),
		("clojure", "babashka", "babashka"),
		("d", "dmd", "d-dmd"),
		("d", "gdc", "d-gdc"),
		("d", "ldc", "d-ldc"),
		("eiffel", "gobo", "eiffel-gobo"),
		("eiffel", "liberty", "eiffel-liberty"),
		("fortran77", "", "fortran77"),
		("fortran2018", "", "fortran2018"),
		("fortran2023", "", "fortran2023"),
		("go", "gccgo", "go-gccgo"),
		("javascript", "bun", "javascript-bun"),
		("javascript", "deno", "javascript-deno"),
		("lua", "luajit", "luajit"),
		("nim", "1.", "nim-1"),
		("nim", "2.", "nim-2"),
		("python", "codon", "python-codon"),
		("pypy", "", "pypy"),
		("ruby", "truffle", "ruby-truffle"),
		("scala", "native", "scala-native"),
		("scheme", "chez", "scheme-chez"),
		("scheme", "gauche", "scheme-gauche"),
		("typescript", "deno", "typescript-deno"),
		("typescript", "bun", "typescript-bun"),
	)
	for variant_family, marker, variant_id in variants:
		if family == variant_family and (not marker or marker in normalized):
			base = variant_id
			break

	occurrences[base] += 1
	return base if occurrences[base] == 1 else f"{base}-{occurrences[base]}"


def _file_extension(table: Tag) -> str | None:
	for row in table.find_all("tr"):
		cells = row.find_all(["th", "td"])
		if len(cells) < 2:
			continue
		label = cells[0].get_text(" ", strip=True)
		if "ファイル名" not in label and label.casefold() != "filename":
			continue
		value = cells[1].find("code") or cells[1]
		path = value.get_text(" ", strip=True).replace("\\", "/")
		filename = path.rsplit("/", 1)[-1]
		if "." not in filename:
			return None
		return filename.rsplit(".", 1)[1]
	return None


def _append_entry(
	entries: list[dict[str, str]],
	occurrences: defaultdict[str, int], name: str, extension: str
) -> None:
	family = _language_key(name)
	entries.append(
		{
			"id": _stable_id(name, family, occurrences),
			"name": name,
			"family": family,
			"extension": extension,
		}
	)


def _extract_from_text(
	soup: BeautifulSoup,
	entries: list[dict[str, str]],
	occurrences: defaultdict[str, int],
) -> None:
	"""Parse the same page when its language blocks are not HTML tables."""
	lines = [
		re.sub(r"\s+", " ", line).strip(" `")
		for line in soup.get_text("\n").splitlines()
		if line.strip()
	]
	for index, line in enumerate(lines):
		if "ファイル名" not in line and line.casefold() != "filename":
			continue
		filename = line.split("|", 1)[-1].strip(" `")
		if "." not in filename and index + 1 < len(lines):
			filename = lines[index + 1].strip(" `")
		filename = filename.rsplit("/", 1)[-1].split()[0]
		if "." not in filename:
			continue
		name = lines[index - 1] if index else ""
		if not name or name.startswith(("#", "ファイル名", "実行", "コンパイル")):
			continue
		extension = filename.rsplit(".", 1)[1]
		_append_entry(entries, occurrences, name, extension)


def extract_languages(html: str, *, minimum_entries: int = 50) -> list[dict[str, str]]:
	"""Extract language metadata from an AtCoder language-list HTML page."""
	soup = BeautifulSoup(html, "html.parser")
	entries: list[dict[str, str]] = []
	occurrences: defaultdict[str, int] = defaultdict(int)
	heading_names = ["h1", "h2", "h3", "h4", "h5", "h6"]

	# The current official page uses <details><summary>...</summary><table>...</table>
	# rather than heading elements.
	for details in soup.find_all("details"):
		summary = details.find("summary")
		table = details.find("table")
		if not isinstance(summary, Tag) or not isinstance(table, Tag):
			continue
		name = re.sub(r"\s+", " ", summary.get_text(" ", strip=True))
		extension = _file_extension(table)
		if name and extension is not None:
			_append_entry(entries, occurrences, name, extension)

	if len(entries) < minimum_entries:
		entries.clear()
		occurrences.clear()
		for heading in soup.find_all(heading_names):
			name = re.sub(r"\s+", " ", heading.get_text(" ", strip=True))
			if not name or name == "使用できる言語とライブラリの一覧":
				continue

			table: Tag | None = None
			for node in heading.find_all_next(["table", *heading_names]):
				if node.name in heading_names:
					break
				table = node
				break
			if table is None:
				continue

			extension = _file_extension(table)
			if extension is not None:
				_append_entry(entries, occurrences, name, extension)

	if len(entries) < minimum_entries:
		entries.clear()
		occurrences.clear()
		_extract_from_text(soup, entries, occurrences)

	if len(entries) < minimum_entries:
		raise ValueError(
			f"Only extracted {len(entries)} languages; refusing to overwrite the catalog."
		)
	return entries


def _fetch(url: str) -> str:
	response = requests.get(
		url,
		headers={"User-Agent": "atcoder-tui-language-updater/1.0"},
		timeout=30,
	)
	response.raise_for_status()
	# The page declares no charset in Content-Type.  Requests otherwise uses
	# ISO-8859-1 for the response and corrupts the Japanese row labels.
	response.encoding = response.apparent_encoding or "utf-8"
	return response.text


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--url",
		default=DEFAULT_URL,
		help="AtCoder language-list HTML URL",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=DEFAULT_OUTPUT,
		help="Output JSON path",
	)
	parser.add_argument(
		"--check",
		action="store_true",
		help="Check whether the catalog is up to date without writing it",
	)
	args = parser.parse_args()

	entries = extract_languages(_fetch(args.url))
	payload: dict[str, Any] = {
		"source_url": args.url,
		"languages": entries,
	}
	serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

	if args.check:
		current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
		if current != serialized:
			print(f"Language catalog is out of date: {args.output}")
			return 1
		print("Language catalog is up to date.")
		return 0

	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(serialized, encoding="utf-8")
	print(f"Wrote {len(entries)} languages to {args.output}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
