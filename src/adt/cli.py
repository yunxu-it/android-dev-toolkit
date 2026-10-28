"""Typer adapter; all ADB behavior lives in core."""

import json
import math
import platform
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Annotated, NoReturn, cast

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from adt import __version__
from adt.core.adb_locator import AdbLocation, AdbLocator
from adt.core.adb_runner import AdbRunner
from adt.core.device_service import DeviceService
from adt.core.errors import AdbUnavailableError, AdtError, DeviceUnavailableError
from adt.core.models import CommandResult

app = typer.Typer(help="Android Dev Toolkit: local, explicit, read-only device diagnostics.")
device_app = typer.Typer(help="Inspect an explicitly selected or uniquely online device.")
app.add_typer(device_app, name="device")
console = Console(markup=False, highlight=False)
errors = Console(stderr=True, markup=False, highlight=False)


@dataclass(frozen=True)
class Options:
    adb_path: Path | None
    timeout: float
    interactive: bool = False


def _version(value: bool) -> None:
    if value:
        typer.echo(f"adt {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    adb_path: Annotated[Path | None, typer.Option(help="Official adb executable path.")] = None,
    timeout: Annotated[float, typer.Option(help="ADB command timeout in seconds.")] = 10.0,
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    if not math.isfinite(timeout) or timeout <= 0:
        raise typer.BadParameter("Must be a finite positive number.", param_hint="--timeout")
    ctx.obj = Options(adb_path, timeout)
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty() and sys.stdout.isatty():
            ctx.obj = replace(ctx.obj, interactive=True)
            _interactive(ctx)
        else:
            typer.echo(ctx.get_help())


def _trace(result: CommandResult, target: Console = console) -> None:
    target.print(f"argv: {json.dumps(result.argv, ensure_ascii=True)}")
    target.print(f"exit: {result.returncode}; duration: {result.duration_ms:.1f} ms")
    if result.stdout.strip():
        target.print("stdout: " + result.stdout.rstrip())
    if result.stderr.strip():
        target.print("stderr: " + result.stderr.rstrip())


def _fail(exc: AdtError, *, concise: bool = False) -> NoReturn:
    errors.print(str(exc), style="bold red")
    if exc.result is not None:
        if concise:
            output = (exc.result.stderr or exc.result.stdout).strip()
            if output:
                errors.print(output)
        else:
            _trace(exc.result, errors)
    raise typer.Exit(exc.exit_code)


def _state(state: str) -> Text:
    style = "green" if state == "device" else "yellow" if state == "unauthorized" else "red"
    return Text(state, style=style)


def _locate(ctx: typer.Context) -> AdbLocation:
    """仅菜单允许补充 ADB 路径；脚本调用始终立即返回明确错误。"""
    while True:
        options = cast(Options, ctx.obj)
        try:
            return AdbLocator(options.adb_path, timeout=options.timeout).locate()
        except AdbUnavailableError as exc:
            if not options.interactive:
                raise
            errors.print(str(exc), style="bold red")
            path = (
                typer.prompt(
                    "ADB executable path (Enter to return to menu)", default="", show_default=False
                )
                .strip()
                .strip('"')
            )
            if not path:
                raise typer.Exit() from exc
            ctx.obj = replace(options, adb_path=Path(path).expanduser())


def _service(ctx: typer.Context) -> DeviceService:
    location = _locate(ctx)
    options = cast(Options, ctx.obj)
    return DeviceService(AdbRunner(location.path, timeout=options.timeout))


def _interactive(ctx: typer.Context) -> None:
    """轻量逐行菜单复用现有命令；操作失败后保留会话供用户重试。"""
    console.print("\nADT — Android Dev Toolkit", style="bold cyan")
    console.print("1. Devices   2. Device details   3. Check environment   0. Quit", style="dim")
    while True:
        choice = typer.prompt("Choose", default=1, type=int)
        if choice == 0:
            return
        try:
            if choice == 1:
                console.print("\nDevices", style="bold cyan")
                devices(ctx)
            elif choice == 2:
                console.print("\nDevice details", style="bold cyan")
                device_info(ctx)
            elif choice == 3:
                console.print("\nEnvironment", style="bold cyan")
                doctor(ctx)
            else:
                console.print("Choose 0, 1, 2 or 3.", style="yellow")
        except typer.Exit:
            # 命令已展示具体错误；菜单继续，Ctrl+C/EOF 仍由 Typer 正常中止。
            pass
        console.print()


@app.command()
def doctor(ctx: typer.Context) -> None:
    """Check ADB discovery, Python, OS and terminal; no device is required."""
    console.print(f"Python: {platform.python_version()}; OS: {platform.system()}")
    console.print(f"Terminal: {'TTY' if sys.stdout.isatty() else 'redirected'}")
    try:
        location = _locate(ctx)
    except AdtError as exc:
        _fail(exc, concise=cast(Options, ctx.obj).interactive)
    for candidate in location.candidates:
        console.print(f"Candidate ({candidate.source}): {candidate.path or '(not set/found)'}")
    for rejected in location.rejected:
        console.print(f"Rejected: {rejected}")
    console.print(f"Effective ADB: {location.path}")
    console.print("Lower-priority candidates are listed but are not probed after success.")
    _trace(location.version)


@app.command()
def devices(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Write a JSON object to stdout.")] = False,
) -> None:
    """List connected devices, including unavailable devices."""
    try:
        items, command = _service(ctx).list_devices()
    except AdtError as exc:
        _fail(exc, concise=cast(Options, ctx.obj).interactive)
    if as_json:
        typer.echo(
            json.dumps(
                {"devices": [asdict(item) for item in items], "commands": [asdict(command)]},
                ensure_ascii=True,
            )
        )
        return
    table = Table(
        "Serial",
        "State",
        "Model",
        "Transport",
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
        border_style="dim",
    )
    for item in items:
        table.add_row(item.serial, _state(item.state), item.model or "N/A", item.transport or "N/A")
    console.print(table)
    if not items:
        console.print(
            "No devices. Connect a device and enable USB debugging, then accept its RSA prompt."
        )
    if not cast(Options, ctx.obj).interactive:
        _trace(command)
    elif command.stderr.strip():
        console.print(command.stderr.rstrip(), style="yellow")


@device_app.command("info")
def device_info(
    ctx: typer.Context,
    serial: Annotated[
        str | None, typer.Option(help="Override the target for this call only.")
    ] = None,
) -> None:
    """Read Android properties; refuse to guess between multiple online devices."""
    if serial is not None and (
        not serial
        or serial.startswith("-")
        or any(char.isspace() or ord(char) < 32 for char in serial)
    ):
        raise typer.BadParameter("Supply a nonempty device serial without whitespace or controls.")
    try:
        service = _service(ctx)
        if serial is None and cast(Options, ctx.obj).interactive:
            items, listing = service.list_devices()
            online = [item for item in items if item.state == "device"]
            if not online:
                raise DeviceUnavailableError(
                    "No online device. Enable USB debugging, accept the RSA prompt, "
                    "or reconnect offline devices. Choose Devices to inspect their states.",
                    result=listing,
                )
            if len(online) == 1:
                serial = online[0].serial
            else:
                for index, item in enumerate(online, 1):
                    console.print(f"{index}. {item.model or 'N/A'} ({item.serial})")
                while True:
                    index = typer.prompt("Device number (0 to return to menu)", type=int)
                    if index == 0:
                        return
                    if 1 <= index <= len(online):
                        serial = online[index - 1].serial
                        break
                    console.print(f"Choose a number from 1 to {len(online)}, or 0.")
        # 交互选择后重新查询状态，防止等待输入期间断线时误用其它设备。
        info = service.info(serial)
    except AdtError as exc:
        _fail(exc, concise=cast(Options, ctx.obj).interactive)
    table = Table(
        "Property", "Value", box=box.SIMPLE_HEAD, header_style="bold cyan", border_style="dim"
    )
    for key, value in (
        ("Serial", info.device.serial),
        ("State", info.device.state),
        ("Transport", info.device.transport),
        ("Manufacturer", info.manufacturer),
        ("Model", info.model),
        ("Android", info.android_version),
        ("API level", info.api_level),
    ):
        table.add_row(key, _state(value) if key == "State" and value else value or "N/A")
    console.print(table)
    for command in info.commands:
        if not cast(Options, ctx.obj).interactive:
            _trace(command)
        elif command.stderr.strip():
            console.print(command.stderr.rstrip(), style="yellow")
