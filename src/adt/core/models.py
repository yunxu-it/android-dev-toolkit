"""Immutable values shared by command and future TUI adapters."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: float


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    model: str | None = None
    transport: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceInfo:
    device: Device
    manufacturer: str | None
    model: str | None
    android_version: str | None
    api_level: str | None
    commands: tuple[CommandResult, ...]
