import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from adt.core.adb_runner import AdbRunner
from adt.core.errors import (
    AdbCommandError,
    AdbTimeoutError,
    AdbUnavailableError,
    DeviceUnavailableError,
)


def test_argv_windows_path_unicode_serial_and_cwd(monkeypatch, tmp_path):
    process = Mock(return_value=subprocess.CompletedProcess([], 0, b"ok\xff", b"warning"))
    monkeypatch.setattr(subprocess, "run", process)
    path = Path("C:/SDK 中文 space/platform-tools/adb.exe")
    result = AdbRunner(path).run(["shell", "getprop"], serial="demo-serial", cwd=tmp_path)
    assert result.argv == (str(path), "-s", "demo-serial", "shell", "getprop")
    assert result.stdout == "ok\ufffd"
    assert result.stderr == "warning"
    assert result.returncode == 0 and result.duration_ms >= 0
    process.assert_called_once_with(
        result.argv, shell=False, capture_output=True, timeout=10.0, cwd=tmp_path
    )


@pytest.mark.parametrize(
    "marker",
    [
        "device unauthorized",
        "device offline",
        "device 'demo' not found",
        "no devices/emulators found",
        "more than one device/emulator",
        "multiple devices",
        "no permissions",
    ],
)
def test_actionable_device_errors(monkeypatch, marker):
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 1, b"", marker.encode())),
    )
    with pytest.raises(DeviceUnavailableError) as failure:
        AdbRunner(Path("adb")).run(["devices"])
    assert failure.value.result.returncode == 1


def test_nonzero_preserves_both_outputs(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 17, b"partial", b"protocol fault")),
    )
    with pytest.raises(AdbCommandError) as failure:
        AdbRunner(Path("adb")).run(["devices"])
    assert failure.value.result.returncode == 17
    assert failure.value.result.stdout == "partial"
    assert failure.value.result.stderr == "protocol fault"


def test_missing_or_nonexecutable_binary(monkeypatch):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=PermissionError("denied")))
    with pytest.raises(AdbUnavailableError, match="permissions"):
        AdbRunner(Path("adb")).run(["version"])


def test_timeout_preserves_partial_bytes(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(side_effect=subprocess.TimeoutExpired("adb", 1, b"partial\xff", b"busy")),
    )
    with pytest.raises(AdbTimeoutError) as failure:
        AdbRunner(Path("adb")).run(["devices"], timeout=1)
    assert failure.value.result.stdout == "partial\ufffd"
    assert failure.value.result.stderr == "busy"
    assert failure.value.result.returncode is None


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_timeouts(timeout):
    with pytest.raises(ValueError):
        AdbRunner(Path("adb"), timeout=timeout)
    with pytest.raises(ValueError):
        AdbRunner(Path("adb")).run(["version"], timeout=timeout)


def test_real_subprocess_bytes_and_nonzero(tmp_path):
    script = tmp_path / "fake_adb.py"
    script.write_text(
        "import sys\nsys.stdout.buffer.write(b'hello\\xff')\n"
        "sys.stderr.write('problem')\nsys.exit(7)\n",
        encoding="utf-8",
    )
    with pytest.raises(AdbCommandError) as failure:
        AdbRunner(Path(sys.executable)).run([str(script)], cwd=tmp_path)
    assert failure.value.result.returncode == 7
    assert failure.value.result.stdout == "hello\ufffd"
    assert failure.value.result.stderr == "problem"


def test_real_subprocess_timeout(tmp_path):
    script = tmp_path / "fake_adb.py"
    script.write_text(
        "import time\nprint('started', flush=True)\ntime.sleep(30)\n", encoding="utf-8"
    )
    with pytest.raises(AdbTimeoutError) as failure:
        AdbRunner(Path(sys.executable), timeout=1).run([str(script)])
    assert failure.value.result.returncode is None
    assert "started" in failure.value.result.stdout
