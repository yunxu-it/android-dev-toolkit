"""Entrypoint routing; full-screen flows are exercised by Textual Pilot tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console
from typer.testing import CliRunner

from adt.cli import app

runner = CliRunner()


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(True, True), (False, True), (True, False)])
def test_tui_only_starts_for_terminal_input_and_output(monkeypatch, stdin_tty, stdout_tty):
    monkeypatch.setattr(
        "adt.cli.sys",
        SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: stdin_tty),
            stdout=SimpleNamespace(isatty=lambda: stdout_tty),
        ),
    )
    run = Mock()
    monkeypatch.setattr("adt.tui.app.AdtApp.run", run)
    result = runner.invoke(app, ["--adb-path", "demo-adb", "--timeout", "5"])
    assert result.exit_code == 0
    assert run.call_count == int(stdin_tty and stdout_tty)
    if not (stdin_tty and stdout_tty):
        assert "Usage:" in result.stdout


@pytest.mark.parametrize("args", [["--help"], ["--version"], ["devices", "--json"]])
def test_explicit_commands_never_start_tui(monkeypatch, args):
    monkeypatch.setattr(
        "adt.cli.sys",
        SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: True),
            stdout=SimpleNamespace(isatty=lambda: True),
        ),
    )
    run = Mock()
    monkeypatch.setattr("adt.tui.app.AdtApp.run", run)
    runner.invoke(app, args)
    run.assert_not_called()


@pytest.mark.parametrize("no_color", [False, True])
def test_cli_color_is_optional_and_states_remain_readable(fake_adb, monkeypatch, no_color):
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("adt.cli.console", Console(force_terminal=True, color_system="standard"))
    fake_adb.listing = b"demo-a device\ndemo-b offline\ndemo-c unauthorized\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path), "devices"], color=True)
    assert result.exit_code == 0
    for state in ("device", "offline", "unauthorized"):
        assert state in result.stdout
    for code in ("\x1b[32m", "\x1b[33m", "\x1b[31m"):
        assert (code in result.stdout) is not no_color
