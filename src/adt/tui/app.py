"""Device dashboard with cancellable queries and no persistent user state."""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Header,
    Input,
    LoadingIndicator,
    OptionList,
    Static,
)
from textual.worker import Worker

from adt.core.adb_locator import AdbLocation, AdbLocator
from adt.core.adb_runner import AdbRunner
from adt.core.device_service import DeviceService, parse_devices
from adt.core.errors import AdbUnavailableError, AdtError
from adt.core.models import CommandResult, Device, DeviceInfo


@dataclass(frozen=True)
class _Snapshot:
    location: AdbLocation
    devices: list[Device]
    commands: tuple[CommandResult, ...]
    info: DeviceInfo | None


class AdtApp(App[None]):
    """共享 core 服务的全屏入口；所有 ADB 查询都在后台线程中执行。"""

    TITLE = "ADT — Android Dev Toolkit"
    CSS_PATH = "app.tcss"
    ENABLE_COMMAND_PALETTE = False
    POLL_INTERVAL = 3.0
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("1", "navigate('dashboard')", "Home"),
        Binding("2", "navigate('devices')", "Devices"),
        Binding("3", "navigate('diagnostics')", "Diagnostics"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "back", "Back / cancel"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
    ]

    def __init__(self, adb_path: Path | None = None, *, timeout: float = 10.0) -> None:
        super().__init__()
        self.adb_path = adb_path
        self.timeout = timeout
        self.selected_serial: str | None = None
        self._devices: list[Device] = []
        self._query_id = 0
        self._active_stop: Event | None = None
        self._worker: Worker[None] | None = None
        self._pending: set[asyncio.Task[_Snapshot]] = set()
        self._busy = False
        self._query_closing = False
        self._pause_polling = False
        self._discovery_failed = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                yield Static("WORKSPACE", classes="section-title")
                yield OptionList("Dashboard", "Devices", "Diagnostics", id="navigation")
                yield Static("Tab: change focus\nEnter: open device", id="keyboard-help")
            with Vertical(id="main"):
                yield Static("Dashboard", id="page-title")
                yield Static("No device selected", id="device-context", markup=False)
                with Horizontal(id="toolbar"):
                    yield Button("Refresh", id="refresh", variant="primary")
                    yield Button("Cancel", id="cancel", disabled=True)
                    yield LoadingIndicator(id="loading")
                yield Static("Starting…", id="status", markup=False)
                with ContentSwitcher(initial="dashboard", id="pages"):
                    with VerticalScroll(id="dashboard"):
                        yield Static("Connected devices", classes="section-title")
                        yield Static("Checking ADB…", id="summary", markup=False)
                        yield Static(
                            "Choose Devices, then use ↑/↓ and Enter to inspect a target.\n"
                            "Unavailable devices remain visible. Nothing is saved or uploaded.",
                            classes="hint",
                            markup=False,
                        )
                        yield Button("View devices", id="view-devices")
                    with Vertical(id="devices"):
                        yield Static("Checking devices…", id="empty-state", markup=False)
                        yield DataTable(id="device-table", cursor_type="row", zebra_stripes=True)
                    with VerticalScroll(id="details"):
                        yield Static(
                            "Select a device to view its details.",
                            id="device-details",
                            markup=False,
                        )
                        yield Button("Back to devices", id="back-devices")
                    with VerticalScroll(id="diagnostics"):
                        yield Static("ADB executable (optional, this session only)")
                        yield Input(
                            value=str(self.adb_path or ""),
                            placeholder="Path to adb / adb.exe",
                            id="adb-path",
                        )
                        yield Button("Apply path and refresh", id="apply-path")
                        yield Static("Checking environment…", id="diagnostic-output", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#device-table", DataTable).add_columns(
            "Serial", "State", "Model", "Transport"
        )
        self.query_one("#loading").display = False
        self.query_one("#navigation", OptionList).focus()
        self.set_interval(self.POLL_INTERVAL, self._poll)
        self.action_refresh()

    def action_navigate(self, page: str) -> None:
        """切换已有页面；设备选择保持在会话内，不触发隐式切换目标。"""
        self.query_one("#pages", ContentSwitcher).current = page
        self.query_one("#page-title", Static).update(
            {
                "dashboard": "Dashboard",
                "devices": "Devices",
                "details": "Device details",
                "diagnostics": "Diagnostics",
            }[page]
        )
        self.query_one("#navigation", OptionList).highlighted = {
            "dashboard": 0,
            "devices": 1,
            "details": 1,
            "diagnostics": 2,
        }[page]
        if page == "devices":
            self.query_one("#device-table", DataTable).focus()
        elif page == "details":
            self.query_one("#details", VerticalScroll).focus()
        else:
            self.query_one("#navigation", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.action_navigate(("dashboard", "devices", "diagnostics")[event.option_index])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        serial = event.row_key.value
        if serial is not None:
            self.selected_serial = serial
            self.sub_title = f"Device: {serial}"
            self.query_one("#device-context", Static).update(f"Selected: {serial}")
            self.action_navigate("details")
            self._start_query(serial)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "refresh":
                self.action_refresh()
            case "cancel":
                self.action_cancel()
            case "view-devices" | "back-devices":
                self.action_navigate("devices")
            case "apply-path":
                self._apply_path()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "adb-path":
            self._apply_path()

    def _apply_path(self) -> None:
        value = self.query_one("#adb-path", Input).value.strip().strip('"')
        self.adb_path = Path(value).expanduser() if value else None
        self._invalidate_selection("ADB path changed. Select a device again.")
        self.action_refresh()

    def _poll(self) -> None:
        if not (self._busy or self._pause_polling or self._discovery_failed or self._query_closing):
            self._start_query(background=True)

    def action_refresh(self) -> None:
        self._pause_polling = False
        current = self.query_one("#pages", ContentSwitcher).current
        self._start_query(self.selected_serial if current == "details" else None)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.query_one("#loading").display = busy
        self.query_one("#cancel", Button).disabled = not busy

    def _start_query(self, serial: str | None = None, *, background: bool = False) -> None:
        if self._active_stop is not None:
            self._active_stop.set()
        self._query_id += 1
        stop = self._active_stop = Event()
        self._set_busy(True)
        if not background:
            self._pause_polling = False
            self._set_status("Loading… Esc to cancel.")
        if serial is not None:
            self.query_one("#device-details", Static).update("Loading device properties…")
        # exclusive 取消过期 worker；Event 同时终止其线程内正在执行的子进程。
        self._worker = self.run_worker(
            self._query(self._query_id, stop, serial),
            group="adb",
            exclusive=True,
        )

    def _load(self, stop: Event, serial: str | None) -> _Snapshot:
        location = AdbLocator(self.adb_path, timeout=self.timeout, cancel_event=stop).locate()
        service = DeviceService(AdbRunner(location.path, timeout=self.timeout, cancel_event=stop))
        if serial is None:
            devices, listing = service.list_devices()
            info = None
            commands: tuple[CommandResult, ...] = (location.version, listing)
        else:
            info = service.info(serial)
            devices = parse_devices(info.commands[0].stdout)
            commands = (location.version, *info.commands)
        return _Snapshot(location, devices, commands, info)

    async def _query(self, query_id: int, stop: Event, serial: str | None) -> None:
        task = asyncio.create_task(asyncio.to_thread(self._load, stop, serial))
        self._pending.add(task)
        try:
            snapshot = await asyncio.shield(task)
            if query_id == self._query_id and not self._query_closing:
                self._apply_snapshot(snapshot)
        except asyncio.CancelledError:
            stop.set()
            # 结果已失效，只等待线程/子进程清理，不再把它写入界面。
            await asyncio.gather(task, return_exceptions=True)
            raise
        except AdtError as exc:
            if query_id == self._query_id and not self._query_closing:
                self._discovery_failed = isinstance(exc, AdbUnavailableError)
                self._devices = []
                self.query_one("#device-table", DataTable).clear()
                self.query_one("#summary", Static).update("Device state could not be confirmed.")
                self.query_one("#empty-state", Static).update(
                    "Query failed. See Diagnostics or refresh."
                )
                self.query_one("#empty-state").display = True
                self._invalidate_selection(str(exc))
                self._set_status(
                    "ADB unavailable. Open Diagnostics to set its path."
                    if self._discovery_failed
                    else str(exc),
                    error=True,
                )
                diagnostic = str(exc)
                if exc.result is not None:
                    diagnostic += "\n\n" + self._format_commands((exc.result,))
                self.query_one("#diagnostic-output", Static).update(diagnostic)
        finally:
            stop.set()
            self._pending.discard(task)
            if query_id == self._query_id and not self._query_closing:
                self._set_busy(False)

    def _apply_snapshot(self, snapshot: _Snapshot) -> None:
        self._discovery_failed = False
        table = self.query_one("#device-table", DataTable)
        if snapshot.devices != self._devices:
            cursor = table.cursor_row
            table.clear()
            for device in snapshot.devices:
                style = (
                    "green"
                    if device.state == "device"
                    else "yellow"
                    if device.state == "unauthorized"
                    else "red"
                )
                table.add_row(
                    Text(device.serial),
                    Text(device.state, style=style),
                    Text(device.model or "N/A"),
                    Text(device.transport or "N/A"),
                    key=device.serial,
                )
            if snapshot.devices:
                table.move_cursor(row=min(cursor, len(snapshot.devices) - 1))
        self._devices = snapshot.devices
        online = sum(device.state == "device" for device in snapshot.devices)
        self.query_one("#summary", Static).update(
            f"{online} online / {len(snapshot.devices)} connected\n\n"
            "Select a device explicitly to read its properties."
        )
        empty = self.query_one("#empty-state", Static)
        empty.display = not snapshot.devices
        empty.update("No devices. Connect one, enable USB debugging and accept its RSA prompt.")
        if self.selected_serial is not None and not any(
            device.serial == self.selected_serial and device.state == "device"
            for device in snapshot.devices
        ):
            self._invalidate_selection(
                "Selected device disconnected or became unavailable.\n"
                "Return to Devices and select an online target."
            )
            self._set_status(
                "Selected device is unavailable. No other device was selected.", error=True
            )
        else:
            self._set_status(f"Ready · {online} online · auto-refresh every 3 seconds")
        if snapshot.info is not None:
            info = snapshot.info
            details = Text()
            for label, value in (
                ("Serial", info.device.serial),
                ("State", info.device.state),
                ("Transport", info.device.transport),
                ("Manufacturer", info.manufacturer),
                ("Model", info.model),
                ("Android", info.android_version),
                ("API level", info.api_level),
            ):
                details.append(f"{label:14}", style="bold cyan")
                details.append(f"{value or 'N/A'}\n")
            self.query_one("#device-details", Static).update(details)
        candidates = "\n".join(
            f"{item.source}: {item.path or '(not set/found)'}"
            for item in snapshot.location.candidates
        )
        self.query_one("#diagnostic-output", Static).update(
            f"Effective ADB: {snapshot.location.path}\n{candidates}\n"
            + "\n".join(snapshot.location.rejected)
            + "\n\n"
            + self._format_commands(snapshot.commands)
        )

    @staticmethod
    def _format_commands(commands: tuple[CommandResult, ...]) -> str:
        return "\n\n".join(
            f"argv: {json.dumps(item.argv, ensure_ascii=True)}\n"
            f"exit: {item.returncode}; duration: {item.duration_ms:.1f} ms\n"
            f"stdout: {item.stdout.rstrip()}\nstderr: {item.stderr.rstrip()}"
            for item in commands
        )

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(message)
        status.set_class(error, "error")

    def _invalidate_selection(self, message: str) -> None:
        self.selected_serial = None
        self.sub_title = ""
        self.query_one("#device-context", Static).update("No device selected")
        self.query_one("#device-details", Static).update(message)

    def action_cancel(self) -> None:
        """暂停自动轮询并取消当前查询，直到用户主动刷新或选择设备。"""
        self._pause_polling = True
        if self._active_stop is not None:
            self._active_stop.set()
        if self._worker is not None:
            self._worker.cancel()
        self._query_id += 1
        self._set_busy(False)
        self._invalidate_selection("Query cancelled. Refresh or choose a device to retry.")
        self._set_status("Query cancelled. Press r to refresh.")

    async def action_back(self) -> None:
        if self._busy:
            self.action_cancel()
        elif self.query_one("#pages", ContentSwitcher).current == "details":
            self.action_navigate("devices")
        else:
            self.action_navigate("dashboard")
            self.query_one("#navigation", OptionList).focus()

    async def _close_queries(self) -> None:
        self._query_closing = True
        if self._active_stop is not None:
            self._active_stop.set()
        self.workers.cancel_all()
        await asyncio.gather(*tuple(self._pending), return_exceptions=True)

    async def action_quit(self) -> None:
        await self._close_queries()
        self.exit()

    async def on_unmount(self) -> None:
        await self._close_queries()
