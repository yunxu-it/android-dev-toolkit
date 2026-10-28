"""Deterministic ADB process double; never touch the host SDK or a phone."""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class FakeAdb:
    path: Path
    listing: bytes = b"List of devices attached\n"
    properties: bytes = (
        b"[ro.product.manufacturer]: [Example]\n"
        b"[ro.product.model]: [Demo Phone]\n"
        b"[ro.build.version.release]: [15]\n"
        b"[ro.build.version.sdk]: [35]\n"
    )
    returncode: int = 0
    stderr: bytes = b""
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def run(self, argv, **kwargs):
        assert kwargs["shell"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] > 0
        self.calls.append(tuple(argv))
        args = list(argv[1:])
        if args == ["version"]:
            return subprocess.CompletedProcess(
                argv, 0, b"Android Debug Bridge version 1.0.41\n", b""
            )
        if args == ["devices", "-l"]:
            return subprocess.CompletedProcess(argv, self.returncode, self.listing, self.stderr)
        assert args[:1] == ["-s"]
        assert args[2:] == ["shell", "getprop"]
        return subprocess.CompletedProcess(argv, self.returncode, self.properties, self.stderr)


@pytest.fixture(autouse=True)
def isolate_adb_environment(monkeypatch):
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT", "ANDROID_SERIAL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PATH", "")


@pytest.fixture
def fake_adb(tmp_path, monkeypatch):
    path = tmp_path / "SDK 中文 space" / ("adb.exe" if os.name == "nt" else "adb")
    path.parent.mkdir()
    path.touch()
    path.chmod(0o755)
    fake = FakeAdb(path)
    monkeypatch.setattr(subprocess, "run", fake.run)
    return fake
