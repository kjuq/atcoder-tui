"""Clipboard integration helpers."""

from __future__ import annotations

import subprocess

from atcoder_tui.tui.app import copy_to_clipboard


def test_copy_to_clipboard_uses_first_available_linux_command(monkeypatch) -> None:
	monkeypatch.setattr("sys.platform", "linux")
	available = {"wl-copy"}
	seen: dict[str, object] = {}

	def fake_which(command: str) -> str | None:
		return command if command in available else None

	def fake_run(command, **kwargs):
		seen["command"] = command
		seen.update(kwargs)

	monkeypatch.setattr("atcoder_tui.tui.app.shutil.which", fake_which)
	monkeypatch.setattr("atcoder_tui.tui.app.subprocess.run", fake_run)

	assert copy_to_clipboard("print(1)\n") == "wl-copy"
	assert seen["command"] == ["wl-copy"]
	assert seen["input"] == "print(1)\n"
	assert seen["check"] is True


def test_copy_to_clipboard_falls_back_when_command_fails(monkeypatch) -> None:
	monkeypatch.setattr("sys.platform", "linux")
	commands = {"wl-copy", "xsel"}
	seen: list[list[str]] = []

	monkeypatch.setattr(
		"atcoder_tui.tui.app.shutil.which",
		lambda command: command if command in commands else None,
	)

	def fake_run(command, **kwargs):
		seen.append(command)
		if command == ["wl-copy"]:
			raise subprocess.CalledProcessError(1, command)

	monkeypatch.setattr("atcoder_tui.tui.app.subprocess.run", fake_run)

	assert copy_to_clipboard("code") == "xsel"
	assert seen == [["wl-copy"], ["xsel", "--clipboard", "--input"]]
