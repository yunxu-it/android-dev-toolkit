import json
import subprocess

import pytest
from typer.testing import CliRunner

from adt.cli import app

runner = CliRunner()


@pytest.mark.parametrize("args", [[], ["--help"], ["--version"]])
def test_entrypoints_without_adb(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert "adt" in result.stdout.lower() or "Android Dev Toolkit" in result.stdout


def test_doctor_missing_adb():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3
    assert "ANDROID_HOME" in result.stderr and "https://developer.android.com" in result.stderr
    assert "Traceback" not in result.output


def test_doctor_reports_effective_path(fake_adb):
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path), "doctor"])
    assert result.exit_code == 0
    assert "Effective ADB" in result.stdout
    assert "Candidate (PATH)" in result.stdout
    assert "1.0.41" in result.stdout


def test_empty_devices_is_success(fake_adb):
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path), "devices"])
    assert result.exit_code == 0
    assert "No devices" in result.stdout


def test_json_stdout_is_clean_even_with_daemon_stderr(fake_adb):
    fake_adb.listing = b"demo-a device model:Demo\ndemo-b unauthorized\n"
    fake_adb.stderr = b"* daemon started successfully\n"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path), "devices", "--json"], color=True)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["devices"]) == 2
    assert payload["devices"][1]["state"] == "unauthorized"
    assert payload["commands"][0]["stderr"].startswith("* daemon")
    assert "\x1b" not in result.stdout


def test_json_failure_writes_only_stderr():
    result = runner.invoke(app, ["devices", "--json"])
    assert result.exit_code == 3
    assert result.stdout == ""
    assert "No usable ADB" in result.stderr


def test_info_and_explicit_serial(fake_adb):
    fake_adb.listing = b"demo-a device\ndemo-b device\n"
    base = ["--adb-path", str(fake_adb.path), "device", "info"]
    ambiguous = runner.invoke(app, base)
    assert ambiguous.exit_code == 4
    assert "--serial" in ambiguous.stderr
    chosen = runner.invoke(app, [*base, "--serial", "demo-b"])
    assert chosen.exit_code == 0
    assert "Demo Phone" in chosen.stdout and "35" in chosen.stdout
    assert fake_adb.calls[-1][2] == "demo-b"


@pytest.mark.parametrize("state", ["offline", "unauthorized"])
def test_cli_rejects_unavailable_devices(fake_adb, state):
    fake_adb.listing = f"demo-a {state}\n".encode()
    result = runner.invoke(
        app, ["--adb-path", str(fake_adb.path), "device", "info", "--serial", "demo-a"]
    )
    assert result.exit_code == 4
    assert state in result.stderr


def test_cli_timeout_exit_code(fake_adb, monkeypatch):
    original = fake_adb.run

    def timed_out(argv, **kwargs):
        if "devices" in argv:
            raise subprocess.TimeoutExpired(argv, 1, b"partial", b"busy")
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", timed_out)
    result = runner.invoke(
        app, ["--adb-path", str(fake_adb.path), "--timeout", "1", "devices", "--json"]
    )
    assert result.exit_code == 5
    assert result.stdout == ""
    assert "partial" in result.stderr and "busy" in result.stderr


def test_general_command_error_exit_code(fake_adb):
    fake_adb.returncode = 17
    fake_adb.stderr = b"protocol fault"
    result = runner.invoke(app, ["--adb-path", str(fake_adb.path), "devices", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "protocol fault" in result.stderr and "17" in result.stderr


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_invalid_timeout_exit_code(value):
    assert runner.invoke(app, ["--timeout", value, "devices"]).exit_code == 2


@pytest.mark.parametrize("serial", ["", "bad serial", "-option", "bad\nserial"])
def test_invalid_serial_exit_code(serial):
    result = runner.invoke(app, ["device", "info", "--serial", serial])
    assert result.exit_code == 2
