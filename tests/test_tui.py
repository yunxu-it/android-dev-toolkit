"""Pilot exercises actual screens against a deterministic ADB boundary."""

import asyncio
import subprocess
from threading import Event

import pytest
from textual.widgets import ContentSwitcher, DataTable, Input, Static

from adt.core.adb_runner import AdbRunner
from adt.core.errors import AdbCancelledError
from adt.tui.app import AdtApp


@pytest.fixture
def tui_adb(fake_adb, monkeypatch):
    def execute(runner, argv, limit, cwd, start):
        return fake_adb.run(argv, shell=False, capture_output=True, timeout=limit, cwd=cwd)

    monkeypatch.setattr(AdbRunner, "_run_cancellable", execute)
    return fake_adb


async def settled(app, pilot):
    await pilot.pause()
    # 刷新可合法取消旧 worker；未处理的程序错误仍由 run_test 在退出时抛出。
    await asyncio.gather(*(worker.wait() for worker in app.workers), return_exceptions=True)
    await pilot.pause()


def content(app, selector):
    return str(app.query_one(selector, Static).content)


@pytest.mark.parametrize("size", [(100, 30), (80, 24)])
def test_navigation_empty_state_and_keyboard_exit(tui_adb, size):
    async def scenario():
        app = AdtApp(tui_adb.path)
        async with app.run_test(size=size) as pilot:
            await settled(app, pilot)
            assert "0 online" in content(app, "#summary")
            await pilot.press("2")
            assert app.query_one("#pages", ContentSwitcher).current == "devices"
            assert "No devices" in content(app, "#empty-state")
            assert app.query_one("#device-table", DataTable).has_focus
            await pilot.press("escape")
            assert app.query_one("#pages", ContentSwitcher).current == "dashboard"
            await pilot.press("down", "down", "enter")
            assert app.query_one("#pages", ContentSwitcher).current == "diagnostics"
            assert "Effective ADB" in content(app, "#diagnostic-output")
            await pilot.press("q")

    asyncio.run(scenario())


def test_selects_explicit_device_and_returns_to_list(tui_adb):
    tui_adb.listing = b"demo-a device model:Demo_A\ndemo-b device model:Demo_B\n"

    async def scenario():
        app = AdtApp(tui_adb.path)
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await pilot.press("2", "down", "enter")
            await settled(app, pilot)
            assert app.query_one("#pages", ContentSwitcher).current == "details"
            assert "Demo Phone" in content(app, "#device-details")
            assert "35" in content(app, "#device-details")
            assert app.selected_serial == "demo-b"
            assert tui_adb.calls[-1][1:] == ("-s", "demo-b", "shell", "getprop")
            await pilot.press("escape")
            assert app.query_one("#pages", ContentSwitcher).current == "devices"

    asyncio.run(scenario())


@pytest.mark.parametrize("state,hint", [("offline", "Reconnect"), ("unauthorized", "RSA")])
def test_unavailable_device_shows_reason_without_properties(tui_adb, state, hint):
    tui_adb.listing = f"demo-a {state}\n".encode()

    async def scenario():
        app = AdtApp(tui_adb.path)
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await pilot.press("2", "enter")
            await settled(app, pilot)
            assert hint in content(app, "#device-details")
            assert app.selected_serial is None
            assert not any("getprop" in call for call in tui_adb.calls)

    asyncio.run(scenario())


def test_missing_adb_still_opens_and_accepts_session_path(tui_adb):
    async def scenario():
        app = AdtApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await settled(app, pilot)
            assert "ADB unavailable" in content(app, "#status")
            await pilot.press("3")
            assert "Platform-Tools" in content(app, "#diagnostic-output")
            app.query_one("#adb-path", Input).value = str(tui_adb.path)
            await pilot.click("#apply-path")
            await settled(app, pilot)
            assert "Ready" in content(app, "#status")
            assert app.adb_path == tui_adb.path

    asyncio.run(scenario())


def test_auto_refresh_invalidates_disconnected_device(tui_adb):
    tui_adb.listing = b"demo-a device\n"

    async def scenario():
        app = AdtApp(tui_adb.path)
        app.POLL_INTERVAL = 0.1
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await pilot.press("2", "enter")
            await settled(app, pilot)
            assert "Demo Phone" in content(app, "#device-details")
            tui_adb.listing = b"demo-other device\n"
            for _ in range(50):
                if app.selected_serial is None:
                    break
                await asyncio.sleep(0.02)
            assert app.selected_serial is None
            assert "Demo Phone" not in content(app, "#device-details")
            assert "disconnected" in content(app, "#device-details")
            assert not any(call[1:3] == ("-s", "demo-other") for call in tui_adb.calls)

    asyncio.run(scenario())


def test_query_error_clears_stale_details_and_refresh_recovers(tui_adb):
    tui_adb.listing = b"demo-a device\n"

    async def scenario():
        app = AdtApp(tui_adb.path)
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await pilot.press("2", "enter")
            await settled(app, pilot)
            tui_adb.returncode = 1
            tui_adb.stderr = b"device offline"
            await pilot.press("r")
            await settled(app, pilot)
            assert app.selected_serial is None
            assert "Demo Phone" not in content(app, "#device-details")
            assert "offline" in content(app, "#status")
            tui_adb.returncode = 0
            tui_adb.stderr = b""
            await pilot.press("escape", "r")
            await settled(app, pilot)
            assert "Ready" in content(app, "#status")
            assert app.query_one("#device-table", DataTable).row_count == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("quit_during_query", [False, True])
def test_slow_query_does_not_block_navigation_and_cancels(tui_adb, monkeypatch, quit_during_query):
    started, stopped = Event(), Event()
    original = AdbRunner._run_cancellable
    block = True

    def execute(runner, argv, limit, cwd, start):
        nonlocal block
        if argv[1:] == ("devices", "-l") and block:
            block = False
            started.set()
            assert runner.cancel_event.wait(3), "UI did not cancel its ADB query"
            stopped.set()
            raise AdbCancelledError("ADB query cancelled.")
        return original(runner, argv, limit, cwd, start)

    monkeypatch.setattr(AdbRunner, "_run_cancellable", execute)

    async def scenario():
        app = AdtApp(tui_adb.path)
        async with app.run_test() as pilot:
            assert await asyncio.to_thread(started.wait, 2)
            await pilot.press("3")
            assert app.query_one("#pages", ContentSwitcher).current == "diagnostics"
            if quit_during_query:
                await pilot.press("q")
                assert stopped.is_set()
            else:
                await pilot.press("escape")
                await pilot.pause()
                assert stopped.is_set()
                assert "cancelled" in content(app, "#status")
                await pilot.press("r")
                await settled(app, pilot)
                assert "Ready" in content(app, "#status")

    asyncio.run(scenario())


def test_obsolete_query_cannot_replace_newer_results(tui_adb, monkeypatch):
    started, release = Event(), Event()
    original = AdbRunner._run_cancellable
    first = True

    def execute(runner, argv, limit, cwd, start):
        nonlocal first
        if argv[1:] == ("devices", "-l") and first:
            first = False
            started.set()
            release.wait(3)
            return subprocess.CompletedProcess(argv, 0, b"demo-stale device\n", b"")
        return original(runner, argv, limit, cwd, start)

    monkeypatch.setattr(AdbRunner, "_run_cancellable", execute)
    tui_adb.listing = b"demo-fresh device\n"

    async def scenario():
        app = AdtApp(tui_adb.path)
        async with app.run_test() as pilot:
            try:
                assert await asyncio.to_thread(started.wait, 2)
                await pilot.press("r")
                await pilot.pause()
            finally:
                release.set()
            await settled(app, pilot)
            assert str(app.query_one("#device-table", DataTable).get_row_at(0)[0]) == "demo-fresh"

    asyncio.run(scenario())
