import os
import subprocess
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest

from adt.core.adb_locator import AdbLocator
from adt.core.errors import AdbCancelledError, AdbUnavailableError


def sdk(tmp_path, name):
    root = tmp_path / name
    executable = root / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    executable.parent.mkdir(parents=True)
    executable.touch()
    executable.chmod(0o755)
    return root, executable


def test_priority_and_all_candidates(fake_adb, tmp_path, monkeypatch):
    home, home_adb = sdk(tmp_path, "home")
    legacy, legacy_adb = sdk(tmp_path, "legacy")
    monkeypatch.setattr("shutil.which", lambda *args, **kwargs: str(legacy_adb))
    env = {"ANDROID_HOME": str(home), "ANDROID_SDK_ROOT": str(legacy), "PATH": "demo"}
    location = AdbLocator(fake_adb.path, environ=env).locate()
    assert location.path == fake_adb.path.resolve()
    assert [item.path for item in location.candidates] == [
        fake_adb.path,
        home_adb,
        legacy_adb,
        legacy_adb,
    ]
    assert len(fake_adb.calls) == 1
    assert AdbLocator(environ=env).locate().path == home_adb.resolve()
    assert (
        AdbLocator(environ={"ANDROID_SDK_ROOT": str(legacy)}).locate().path == legacy_adb.resolve()
    )
    assert AdbLocator(environ={"PATH": "demo"}).locate().path == legacy_adb.resolve()


def test_missing_adb_has_search_locations_and_download():
    with pytest.raises(AdbUnavailableError) as failure:
        AdbLocator(environ={}).locate()
    message = str(failure.value)
    for value in (
        "ANDROID_HOME",
        "ANDROID_SDK_ROOT",
        "PATH",
        "https://developer.android.com",
        "--adb-path",
    ):
        assert value in message


def test_explicit_invalid_does_not_fall_back(fake_adb):
    with pytest.raises(AdbUnavailableError):
        AdbLocator(Path("missing-adb"), environ={"PATH": str(fake_adb.path.parent)}).locate()
    assert fake_adb.calls == []


def test_explicit_relative_path_is_resolved_before_execution(fake_adb, monkeypatch):
    monkeypatch.chdir(fake_adb.path.parent)
    location = AdbLocator(Path(fake_adb.path.name), environ={}).locate()
    assert Path(location.version.argv[0]).is_absolute()
    assert location.path == fake_adb.path.resolve()


def test_bad_home_falls_back_and_records_reason(fake_adb, tmp_path):
    root, _ = sdk(tmp_path, "fallback")
    location = AdbLocator(
        environ={"ANDROID_HOME": str(tmp_path / "missing"), "ANDROID_SDK_ROOT": str(root)}
    ).locate()
    assert location.path.parent.parent == root
    assert "missing" in location.rejected[0]


@pytest.mark.parametrize("returncode,stdout", [(1, b""), (0, b"some unrelated executable")])
def test_failed_version_probe(fake_adb, monkeypatch, returncode, stdout):
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], returncode, stdout, b"bad version")),
    )
    with pytest.raises(AdbUnavailableError):
        AdbLocator(fake_adb.path, environ={}).locate()


def test_version_timeout(fake_adb, monkeypatch):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("adb", 1)))
    with pytest.raises(AdbUnavailableError, match="timed out"):
        AdbLocator(fake_adb.path, environ={}, timeout=1).locate()


def test_version_cancellation_is_not_reported_as_missing_adb(fake_adb):
    stop = Event()
    stop.set()
    with pytest.raises(AdbCancelledError):
        AdbLocator(fake_adb.path, environ={}, cancel_event=stop).locate()


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable permission bits")
def test_not_executable(tmp_path):
    file = tmp_path / "adb"
    file.touch()
    file.chmod(0o644)
    with pytest.raises(AdbUnavailableError, match="not executable"):
        AdbLocator(file, environ={}).locate()
