"""Actionable errors and stable CLI exit codes."""

from adt.core.models import CommandResult


class AdtError(Exception):
    exit_code = 1

    def __init__(self, message: str, *, result: CommandResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class AdbUnavailableError(AdtError):
    exit_code = 3


class DeviceUnavailableError(AdtError):
    exit_code = 4


class AdbTimeoutError(AdtError):
    exit_code = 5


class AdbCancelledError(AdtError):
    """A user cancelled a finite ADB query after its child process was reaped."""

    exit_code = 130


class AdbCommandError(AdtError):
    """ADB executed but returned an unsuccessful status."""
