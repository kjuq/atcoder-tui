"""Resolve source files from the user's solution repository."""

from __future__ import annotations

import os
from pathlib import Path

from .languages import language_extension
from .models import Language, Problem

REPO_BASE_ENV = "ATCODER_TUI_REPO_BASE"


class SourcePathError(ValueError):
	"""The configured repository path cannot be resolved."""


def resolve_source_path(problem: Problem, language: Language) -> Path:
	"""Resolve ``main.<extension>`` for a problem and language."""
	base = os.environ.get(REPO_BASE_ENV)
	if not base:
		raise SourcePathError(f"{REPO_BASE_ENV} is not set.")
	extension = language_extension(language)
	if extension is None:
		raise SourcePathError(
			f"No source-file extension is configured for {language.name}."
		)
	return (
		Path(base).expanduser()
		/ problem.contest_id
		/ problem.index.lower()
		/ f"main.{extension}"
	)
