"""Observable prompt flows; the same core calls serve scripts and the menu."""

import subprocess
from types import SimpleNamespace

import pytest
from rich.console import Console
from typer.testing import CliRunner

from adt.cli import app

runner = CliRunner()


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setattr(
        "adt.cli.sys",
        SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: True),
            stdout=SimpleNamespace(isatty=lambda: True),
        ),
    )


def test_quit_does_not_require_adb(terminal):
    result = runner.invoke(app, input="0\n")
    assert result.exit_code == 0
    assert "1. Devices" in result.stdout
    assert "No usable ADB" not in result.output


def test_default_action_and_one_device_details(fake_adb, terminal):
    fake_adb.listing = b"demo-a device model:Demo\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="\n2\n0\n")
    assert result.exit_code == 0
    assert "demo-a" in result.stdout and "Demo Phone" in result.stdout
    assert "Device number" not in result.stdout
    assert "[ro.product" not in result.stdout
    assert "argv:" not in result.stdout and "duration:" not in result.stdout
    assert result.stdout.count("1. Devices") == 1
    assert fake_adb.calls[-1][1:] == ("-s", "demo-a", "shell", "getprop")


def test_multiple_devices_prompt_without_selecting_unavailable(fake_adb, terminal):
    fake_adb.listing = b"demo-off offline\ndemo-a device\ndemo-b device\ndemo-auth unauthorized\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="2\n9\n2\n0\n")
    assert result.exit_code == 0
    assert "1. N/A (demo-a)" in result.stdout
    assert "2. N/A (demo-b)" in result.stdout
    assert "Choose a number" in result.stdout
    assert fake_adb.calls[-1][1:] == ("-s", "demo-b", "shell", "getprop")


def test_cancel_device_selection_does_not_query_properties(fake_adb, terminal):
    fake_adb.listing = b"demo-a device\ndemo-b device\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="2\n0\n0\n")
    assert result.exit_code == 0
    assert not any("getprop" in call for call in fake_adb.calls)


def test_missing_adb_prompt_and_session_reuse(fake_adb, terminal):
    result = runner.invoke(app, input=f'1\n"{fake_adb.path}"\n1\n0\n')
    assert result.exit_code == 0
    assert result.stdout.count("ADB executable path") == 1
    assert sum(call[1:] == ("devices", "-l") for call in fake_adb.calls) == 2


def test_invalid_adb_path_can_be_corrected(fake_adb, terminal):
    result = runner.invoke(app, input=f"1\nmissing-adb\n{fake_adb.path}\n0\n")
    assert result.exit_code == 0
    assert result.stdout.count("ADB executable path") == 2


def test_cancel_missing_adb_returns_to_menu(terminal):
    result = runner.invoke(app, input="1\n\n0\n")
    assert result.exit_code == 0
    assert result.stdout.count("Choose [1]") == 2


def test_unavailable_device_does_not_end_session(fake_adb, terminal):
    fake_adb.listing = b"demo-auth unauthorized\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="2\n1\n0\n")
    assert result.exit_code == 0
    assert "RSA" in result.stderr
    assert "unauthorized" in result.stdout
    assert result.stdout.count("Choose [1]") == 3


def test_failed_query_returns_to_menu(fake_adb, terminal):
    fake_adb.returncode = 1
    fake_adb.stderr = b"protocol fault"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="1\n0\n")
    assert result.exit_code == 0
    assert "protocol fault" in result.stderr
    assert result.stdout.count("Choose [1]") == 2
    assert "argv:" not in result.stderr


def test_disconnect_while_choosing_never_falls_back(fake_adb, terminal, monkeypatch):
    original = fake_adb.run
    listings = 0

    def disconnect(argv, **kwargs):
        nonlocal listings
        if list(argv[1:]) == ["devices", "-l"]:
            listings += 1
            fake_adb.listing = (
                b"demo-a device\ndemo-b device\n" if listings == 1 else b"demo-a device\n"
            )
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", disconnect)
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="2\n2\n0\n")
    assert result.exit_code == 0
    assert "not found" in result.stderr
    assert not any("getprop" in call for call in fake_adb.calls)


def test_invalid_menu_input_and_eof(terminal):
    invalid = runner.invoke(app, input="9\nabc\n0\n")
    assert invalid.exit_code == 0
    assert "Choose 0, 1, 2 or 3" in invalid.stdout
    eof = runner.invoke(app, input="")
    assert eof.exit_code == 1
    assert "Aborted" in eof.output


def test_help_and_machine_output_never_prompt(fake_adb, terminal):
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "Choose" not in help_result.stdout
    fake_adb.listing = b"demo-a device\ndemo-b device\n"
    info = runner.invoke(app, ["--adb-path", str(fake_adb.path), "device", "info"])
    assert info.exit_code == 4
    assert "Device number" not in info.stdout


def test_environment_keeps_command_diagnostics(fake_adb, terminal):
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="3\n0\n")
    assert result.exit_code == 0
    assert "argv:" in result.stdout and "duration:" in result.stdout
    assert result.stdout.count("1. Devices") == 1


@pytest.mark.parametrize("no_color", [False, True])
def test_color_is_optional_and_states_remain_readable(fake_adb, terminal, monkeypatch, no_color):
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("adt.cli.console", Console(force_terminal=True, color_system="standard"))
    fake_adb.listing = b"demo-a device\ndemo-b offline\ndemo-c unauthorized\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path)], input="1\n0\n", color=True)
    assert result.exit_code == 0
    for state in ("device", "offline", "unauthorized"):
        assert state in result.stdout
    if no_color:
        assert "\x1b[32m" not in result.stdout
        assert "\x1b[33m" not in result.stdout
        assert "\x1b[31m" not in result.stdout
    else:
        assert "\x1b[32m" in result.stdout
        assert "\x1b[33m" in result.stdout
        assert "\x1b[31m" in result.stdout
