"""The only layer allowed to start ADB subprocesses."""

import math
import subprocess
from collections.abc import Sequence
from pathlib import Path
from threading import Event
from time import perf_counter
from typing import cast

from adt.core.errors import (
    AdbCancelledError,
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
    def __init__(
        self, adb_path: Path, *, timeout: float = 10.0, cancel_event: Event | None = None
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be a finite positive number.")
        self.adb_path = adb_path
        self.timeout = timeout
        self.cancel_event = cancel_event

    def _run_cancellable(
        self, argv: tuple[str, ...], limit: float, cwd: Path | None, start: float
    ) -> subprocess.CompletedProcess[bytes]:
        """可取消路径轮询 communicate，取消或超时后终止并回收子进程。"""
        assert self.cancel_event is not None
        if self.cancel_event.is_set():
            raise AdbCancelledError("ADB query cancelled.")
        with subprocess.Popen(
            argv, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd
        ) as process:
            while True:
                cancelled = self.cancel_event.is_set()
                remaining = limit - (perf_counter() - start)
                if cancelled or remaining <= 0:
                    process.kill()
                    stdout, stderr = process.communicate()
                    if cancelled:
                        raise AdbCancelledError(
                            "ADB query cancelled.",
                            result=CommandResult(
                                argv,
                                None,
                                decode_output(stdout),
                                decode_output(stderr),
                                (perf_counter() - start) * 1000,
                            ),
                        )
                    raise subprocess.TimeoutExpired(argv, limit, stdout, stderr)
                try:
                    stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                except subprocess.TimeoutExpired:
                    continue
                # communicate 已等待子进程结束，returncode 此时必为 int。
                return subprocess.CompletedProcess(
                    argv, cast(int, process.returncode), stdout, stderr
                )

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
            if self.cancel_event is None:
                completed = subprocess.run(
                    argv, shell=False, capture_output=True, timeout=limit, cwd=cwd
                )
            else:
                completed = self._run_cancellable(argv, limit, cwd, start)
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
