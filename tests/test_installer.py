"""Validate the real PowerShell setup boundary without installing into user directories."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "install.ps1"
POWERSHELLS = [path for name in ("pwsh", "powershell") if (path := shutil.which(name))]


@pytest.mark.parametrize("powershell", POWERSHELLS or [None])
def test_installer_parses_in_available_powershell_versions(powershell):
    if powershell is None:
        pytest.skip("PowerShell is not installed")
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$tokens = $null; $parseErrors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            "$env:ADT_TEST_INSTALLER, [ref]$tokens, [ref]$parseErrors) > $null; "
            "if ($parseErrors.Count) { $parseErrors | Out-String | Write-Error; exit 1 }",
        ],
        env={**os.environ, "ADT_TEST_INSTALLER": str(INSTALLER)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd executable stub")
def test_failed_tool_install_does_not_claim_success_or_change_path(tmp_path):
    if not POWERSHELLS:
        pytest.skip("PowerShell is not installed")
    (tmp_path / "uv.cmd").write_bytes(b"@echo off\r\nexit /b 23\r\n")
    second = tmp_path / "second-uv"
    second.mkdir()
    (second / "uv.cmd").write_bytes(b"@echo off\r\nexit /b 99\r\n")
    result = subprocess.run(
        [POWERSHELLS[0], "-NoProfile", "-NonInteractive", "-File", str(INSTALLER)],
        env={**os.environ, "PATH": os.pathsep.join((str(tmp_path), str(second)))},
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    assert result.returncode != 0
    assert "exit 23" in result.stderr
    assert "Ready." not in result.stdout
    assert "Make adt available" not in result.stdout
