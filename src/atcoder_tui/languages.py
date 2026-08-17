"""Submission language catalog and matching helpers."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Language

# IDs in this fallback catalog are stable internal keys.  The actual AtCoder
# language ID is resolved from the authenticated problem page before submit.
DEFAULT_SUBMISSION_LANGUAGES: tuple[Language, ...] = (
	Language("python", "Python (CPython 3.11.4)"),
	Language("pypy", "PyPy 3.10"),
	Language("cpp", "C++23 (GCC 12.2.0)"),
	Language("c", "C (GCC 12.2.0)"),
	Language("rust", "Rust 1.70.0"),
	Language("go", "Go 1.20.6"),
	Language("javascript", "JavaScript (Node.js 18.16.1)"),
	Language("java", "Java (OpenJDK 17)"),
	Language("csharp", "C# 11.0"),
	Language("kotlin", "Kotlin 1.8.20"),
	Language("ruby", "Ruby 3.0.1"),
	Language("php", "PHP 8.2.8"),
)

_EXTENSIONS: dict[str, str] = {
	"python": "py",
	"pypy": "py",
	"cpp": "cpp",
	"c": "c",
	"rust": "rs",
	"go": "go",
	"javascript": "js",
	"java": "java",
	"csharp": "cs",
	"kotlin": "kt",
	"ruby": "rb",
	"php": "php",
}


def language_key(name: str) -> str:
	"""Return a stable family key for an AtCoder language name."""
	normalized = name.casefold()
	if "pypy" in normalized:
		return "pypy"
	if "python" in normalized:
		return "python"
	if "c++" in normalized or "gnu++" in normalized:
		return "cpp"
	if "c#" in normalized or "csharp" in normalized:
		return "csharp"
	if "javascript" in normalized or "node.js" in normalized:
		return "javascript"
	if "kotlin" in normalized:
		return "kotlin"
	if "swift" in normalized:
		return "swift"
	if "rust" in normalized:
		return "rust"
	if "golang" in normalized or normalized.startswith("go "):
		return "go"
	if "java" in normalized:
		return "java"
	if "ruby" in normalized:
		return "ruby"
	if "php" in normalized:
		return "php"
	if normalized == "c" or normalized.startswith("c "):
		return "c"
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
