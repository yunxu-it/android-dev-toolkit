import subprocess

import pytest

from adt.core.adb_runner import AdbRunner
from adt.core.device_service import DeviceService, parse_devices
from adt.core.errors import DeviceUnavailableError


def test_parse_states_missing_fields_and_transport():
    output = (
        "List of devices attached\r\n"
        "demo-usb device usb:1-2 model:Demo_Phone transport_id:1\r\n"
        "demo-off offline\n"
        "demo-auth unauthorized usb:2-1\n"
        "emulator-5554 device product:sdk\n"
        "192.0.2.1:5555 device model:Demo\n"
        "demo-unknown recovery\n"
        "demo-noperm no permissions (check udev rules)\n"
        "* daemon started successfully\n"
    )
    devices = parse_devices(output)
    assert [item.state for item in devices] == [
        "device",
        "offline",
        "unauthorized",
        "device",
        "device",
        "recovery",
        "no permissions",
    ]
    assert devices[0].model == "Demo_Phone"
    assert devices[1].model is None and devices[1].transport is None
    assert [devices[index].transport for index in (0, 3, 4)] == ["usb", "emulator", "network"]
    assert parse_devices("List of devices attached\n\n") == []


@pytest.mark.parametrize(
    "serial,transport",
    [
        ("[2001:db8::1]:5555", "network"),
        ("adb-demo._adb-tls-connect._tcp", "network"),
        ("unknown:123", None),
        ("demo", None),
    ],
)
def test_transport_is_only_inferred_when_reliable(serial, transport):
    assert parse_devices(f"{serial} device")[0].transport == transport


def test_info_uses_unique_online_device_and_getprop(fake_adb):
    fake_adb.listing = b"List of devices attached\ndemo-off offline\ndemo-online device\n"
    info = DeviceService(AdbRunner(fake_adb.path)).info()
    assert info.device.serial == "demo-online"
    assert info.manufacturer == "Example" and info.model == "Demo Phone"
    assert info.android_version == "15" and info.api_level == "35"
    assert fake_adb.calls[-1][1:] == ("-s", "demo-online", "shell", "getprop")
    assert len(info.commands) == 2


def test_missing_properties_are_none(fake_adb):
    fake_adb.listing = b"demo-online device model:Demo\n"
    fake_adb.properties = b"[ro.product.model]: []\n"
    info = DeviceService(AdbRunner(fake_adb.path)).info()
    assert info.model == "Demo"
    assert info.android_version is None and info.api_level is None


@pytest.mark.parametrize(
    "listing,serial,message",
    [
        (b"", None, "No online"),
        (b"demo-a device\ndemo-b device\n", None, "Multiple online"),
        (b"demo-a offline\n", "demo-a", "Reconnect"),
        (b"demo-a unauthorized\n", "demo-a", "RSA"),
        (b"demo-a no permissions\n", "demo-a", "USB permissions"),
        (b"demo-a recovery\n", "demo-a", "recovery"),
        (b"demo-other device\n", "demo-missing", "not found"),
    ],
)
def test_unavailable_or_ambiguous_never_queries_properties(fake_adb, listing, serial, message):
    fake_adb.listing = listing
    with pytest.raises(DeviceUnavailableError, match=message):
        DeviceService(AdbRunner(fake_adb.path)).info(serial)
    assert len(fake_adb.calls) == 1


def test_override_and_disconnect_do_not_select_another_device(fake_adb):
    fake_adb.listing = b"demo-a device\ndemo-b device\n"
    service = DeviceService(AdbRunner(fake_adb.path))
    assert service.info("demo-b").device.serial == "demo-b"
    fake_adb.listing = b"demo-a device\n"
    with pytest.raises(DeviceUnavailableError, match="not found"):
        service.info("demo-b")
    assert fake_adb.calls[-1][1:] == ("devices", "-l")


def test_disconnect_between_list_and_getprop(fake_adb, monkeypatch):
    fake_adb.listing = b"demo-a device\n"
    original = fake_adb.run

    def disconnected(argv, **kwargs):
        if "getprop" in argv:
            return subprocess.CompletedProcess(argv, 1, b"", b"error: device 'demo-a' not found")
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", disconnected)
    with pytest.raises(DeviceUnavailableError, match="disappeared"):
        DeviceService(AdbRunner(fake_adb.path)).info("demo-a")
