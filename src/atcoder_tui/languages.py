"""Submission language catalog and matching helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from importlib.resources import files
from typing import Any

from .models import Language


def _load_payload() -> dict[str, Any]:
	return json.loads(
		files("atcoder_tui.data").joinpath("languages.json").read_text(
			encoding="utf-8"
		)
	)


_catalog_payload = _load_payload()


def _load_catalog(payload: dict[str, Any]) -> tuple[Language, ...]:
	return tuple(
		Language(str(item["id"]), str(item["name"]))
		for item in payload["languages"]
    )


# IDs in the bundled catalog are stable internal keys.  The actual AtCoder
# language ID is resolved from the authenticated problem page before submit.
DEFAULT_SUBMISSION_LANGUAGES = _load_catalog(_catalog_payload)
_EXTENSIONS = {
    str(item["family"]): str(item["extension"])
    for item in _catalog_payload["languages"]
    if item.get("extension")
}


def language_key(name: str) -> str:
	"""Return a stable family key for an AtCoder language name."""
	normalized = name.casefold()
	prefixes = (
		("><>", "fishr"),
		("apl ", "apl"),
		("awk ", "awk"),
		("ada ", "ada"),
		("assembly mips", "asm-mips"),
		("assembly x64", "asm-x64"),
		("a言語", "a-lang"),
		("basic ", "basic"),
		("bash ", "bash"),
		("befunge", "befunge"),
		("brainfuck", "brainfuck"),
		("c3 ", "c3"),
		("cobol ", "cobol"),
		("carp", "carp"),
		("crystal ", "crystal"),
		("cyber ", "cyber"),
		("d (", "d"),
		("dart ", "dart"),
		("eclipse ", "eclipse"),
		("eiffel ", "eiffel"),
		("elixir ", "elixir"),
		("emojicode", "emojicode"),
		("erlang ", "erlang"),
		("factor ", "factor"),
		("fish ", "fish"),
		("fix ", "fix"),
		("forth ", "forth"),
		("gleam ", "gleam"),
		("haskell ", "haskell"),
		("haxe/", "haxe"),
		("islisp ", "islisp"),
		("jule ", "jule"),
		("julia ", "julia"),
		("koka ", "koka"),
		("kuin ", "kuin"),
		("llvm ir", "llvm"),
		("lean ", "lean"),
		("lua (", "lua"),
		("mercury ", "mercury"),
		("ocaml ", "ocaml"),
		("octave ", "octave"),
		("pascal ", "pascal"),
		("perl ", "perl"),
		("piet ", "piet"),
		("pony ", "pony"),
		("powershell ", "powershell"),
		("prolog ", "prolog"),
		("r (", "r"),
		("reasonml ", "reasonml"),
		("sagemath ", "sagemath"),
		("scala ", "scala"),
		("scheme ", "scheme"),
		("seed7 ", "seed7"),
		("sql ", "sql"),
		("tcl ", "tcl"),
		("tex ", "tex"),
		("terra ", "terra"),
		("text ", "text"),
		("uiua ", "uiua"),
		("unison ", "unison"),
		("vala ", "vala"),
		("verilog ", "verilog"),
		("veryl ", "veryl"),
		("webassembly ", "webassembly"),
		("whitespace ", "whitespace"),
		("zig ", "zig"),
		("bc ", "bc"),
		("dc ", "dc"),
		("clay ", "clay"),
		("なでしこ ", "なでしこ"),
		("プロデル ", "プロデル"),
	)
	for prefix, key in prefixes:
		if normalized.startswith(prefix):
			return key
	if "pypy" in normalized:
		return "pypy"
	if "typescript" in normalized:
		return "typescript"
	if "python" in normalized:
		return "python"
	if "clojurescript" in normalized:
		return "clojurescript"
	if "c#" in normalized or "csharp" in normalized:
		return "csharp"
	if "c++" in normalized or "gnu++" in normalized:
		return "cpp"
	if normalized.startswith("c23") or normalized == "c" or normalized.startswith("c "):
		return "c"
	if "javascript" in normalized or "node.js" in normalized:
		return "javascript"
	if normalized.startswith("go ") or normalized.startswith("go("):
		return "go"
	if normalized.startswith("f#"):
		return "f#"
	if "fortran77" in normalized:
		return "fortran77"
	if "fortran2018" in normalized:
		return "fortran2018"
	if "fortran2023" in normalized:
		return "fortran2023"
	if "common lisp" in normalized:
		return "common lisp"
	if "reasonml" in normalized:
		return "reasonml"
	if "webassembly" in normalized:
		return "webassembly"
	if "emacs lisp" in normalized:
		return "emacs lisp"
	if "lazy k" in normalized:
		return "lazy k"
	if "clojure" in normalized:
		return "clojure"
	if normalized.startswith("ruby"):
		return "ruby"
	if normalized.startswith("nim"):
		return "nim"
	if "kotlin" in normalized:
		return "kotlin"
	if "swift" in normalized:
		return "swift"
	if "rust" in normalized:
		return "rust"
	if "golang" in normalized:
		return "go"
	if "java" in normalized:
		return "java"
	if "ruby" in normalized:
		return "ruby"
	if "php" in normalized:
		return "php"
	if "clay" in normalized:
		return "clay"
	if normalized.startswith("v ("):
		return "v"
	return normalized


def language_extension(language: Language) -> str | None:
	"""Return the source-file extension for a submission language."""
	return _EXTENSIONS.get(language_key(language.name))


def find_matching_language(
	preferred: Language, available: Iterable[Language]
) -> Language | None:
	"""Match a configured language against the current contest's languages."""
	available_list = list(available)
	for language in available_list:
		if language.name.casefold() == preferred.name.casefold():
			return language
	preferred_key = language_key(preferred.name)
	return next(
		(language for language in available_list if language_key(language.name) == preferred_key),
		None,
	)
