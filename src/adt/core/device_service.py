"""Device parsing, explicit target selection and read-only property queries."""

import ipaddress
import re

from adt.core.adb_runner import AdbRunner
from adt.core.errors import DeviceUnavailableError
from adt.core.models import CommandResult, Device, DeviceInfo


def _transport(serial: str, attributes: dict[str, str]) -> str | None:
    if "usb" in attributes:
        return "usb"
    if re.fullmatch(r"emulator-\d+", serial):
        return "emulator"
    if serial.endswith("._adb-tls-connect._tcp"):
        return "network"
    host, separator, port = serial.rpartition(":")
    if separator and port.isdigit():
        try:
            ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            return None
        return "network"
    return None


def parse_devices(output: str) -> list[Device]:
    """解析 devices -l；未知状态保留，但只有 device 状态可被选择。"""
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith(("List of devices attached", "*")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state, *fields = parts
        if state == "no" and fields[:1] == ["permissions"]:
            state = "no permissions"
        attributes = dict(field.split(":", 1) for field in fields if ":" in field)
        devices.append(
            Device(
                serial, state, attributes.get("model"), _transport(serial, attributes), attributes
            )
        )
    return devices


class DeviceService:
    def __init__(self, runner: AdbRunner) -> None:
        self.runner = runner

    def list_devices(self) -> tuple[list[Device], CommandResult]:
        result = self.runner.run(["devices", "-l"])
        return parse_devices(result.stdout), result

    def info(self, serial: str | None = None) -> DeviceInfo:
        devices, listing = self.list_devices()
        if serial is not None:
            matches = [device for device in devices if device.serial == serial]
            if not matches:
                raise DeviceUnavailableError(
                    f"Device {serial!r} not found. Reconnect it and run adt devices.",
                    result=listing,
                )
            device = matches[0]
            if device.state != "device":
                hints = {
                    "unauthorized": "Unlock the device and accept the USB debugging RSA prompt.",
                    "offline": "Reconnect the device and check USB debugging.",
                    "no permissions": "Check Android USB permissions for your operating system.",
                }
                raise DeviceUnavailableError(
                    f"Device {serial!r} is {device.state}. "
                    + hints.get(device.state, "Run adt devices and choose an online device."),
                    result=listing,
                )
        else:
            online = [device for device in devices if device.state == "device"]
            if len(online) != 1:
                raise DeviceUnavailableError(
                    "Multiple online devices. Pass --serial SERIAL explicitly."
                    if online
                    else "No online device. Connect a device, enable USB debugging, accept its RSA "
                    "prompt, and run adt devices; offline devices need reconnection.",
                    result=listing,
                )
            device = online[0]
        properties = self.runner.run(["shell", "getprop"], serial=device.serial)
        values = dict(re.findall(r"^\[([^\]]+)\]: \[(.*)\]\r?$", properties.stdout, re.MULTILINE))
        return DeviceInfo(
            device,
            values.get("ro.product.manufacturer") or None,
            values.get("ro.product.model") or device.model,
            values.get("ro.build.version.release") or None,
            values.get("ro.build.version.sdk") or None,
            (listing, properties),
        )
