"""The only layer allowed to start ADB subprocesses."""

import math
import subprocess
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter

from adt.core.errors import (
    AdbCommandError,
    AdbTimeoutError,
    AdbUnavailableError,
    DeviceUnavailableError,
)
from adt.core.models import CommandResult


def decode_output(value: bytes | str | None) -> str:
    """保留可读 UTF-8 输出，异常字节使用替换字符而不使命令崩溃。"""
    if value is None:
        return ""
    return value if isinstance(value, str) else value.decode("utf-8", errors="replace")


class AdbRunner:
    def __init__(self, adb_path: Path, *, timeout: float = 10.0) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be a finite positive number.")
        self.adb_path = adb_path
        self.timeout = timeout

    def run(
        self,
        args: Sequence[str],
        *,
        serial: str | None = None,
        timeout: float | None = None,
        cwd: Path | None = None,
    ) -> CommandResult:
        """执行有限时 ADB 调用，失败和超时均保留命令与已捕获的输出。"""
        limit = self.timeout if timeout is None else timeout
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("Timeout must be a finite positive number.")
        argv = (str(self.adb_path), *(("-s", serial) if serial is not None else ()), *args)
        start = perf_counter()
        try:
            completed = subprocess.run(
                argv, shell=False, capture_output=True, timeout=limit, cwd=cwd
            )
        except subprocess.TimeoutExpired as exc:
            result = CommandResult(
                argv,
                None,
                decode_output(exc.stdout),
                decode_output(exc.stderr),
                (perf_counter() - start) * 1000,
            )
            raise AdbTimeoutError(
                f"ADB timed out after {limit:g}s. Check the connection or increase --timeout.",
                result=result,
            ) from exc
        except OSError as exc:
            raise AdbUnavailableError(
                f"Cannot execute ADB at {self.adb_path}: {exc}. Check --adb-path and permissions."
            ) from exc
        result = CommandResult(
            argv,
            completed.returncode,
            decode_output(completed.stdout),
            decode_output(completed.stderr),
            (perf_counter() - start) * 1000,
        )
        if result.returncode != 0:
            output = (result.stderr + "\n" + result.stdout).lower()
            hints = (
                ("unauthorized", "Unlock the device and accept the USB debugging RSA prompt."),
                ("offline", "Reconnect the device and check USB debugging; the device is offline."),
                ("not found", "The target device disappeared. Reconnect it and run adt devices."),
                ("no devices", "Connect a device, enable USB debugging, and run adt devices."),
                ("more than one", "Multiple devices found. Pass --serial SERIAL explicitly."),
                ("multiple devices", "Multiple devices found. Pass --serial SERIAL explicitly."),
                ("no permissions", "Check USB permissions and the platform's Android USB setup."),
            )
            for marker, hint in hints:
                if marker in output:
                    raise DeviceUnavailableError(hint, result=result)
            raise AdbCommandError(
                f"ADB failed with exit code {result.returncode}. Inspect the command output.",
                result=result,
            )
        return result
