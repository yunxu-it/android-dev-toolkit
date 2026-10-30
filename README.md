# ADT — Android Dev Toolkit

[简体中文](README.zh-CN.md) · MIT · Python 3.12+

A local Android debugging CLI, designed for Windows PowerShell / Windows Terminal
and compatible by design with macOS/Linux. **M0–M2**: working ADB discovery,
diagnostics, device listing and read-only device properties. No account, telemetry,
log uploads or private services. `adt` opens a full-screen Textual interface with a
dashboard, device list, device details and diagnostics. Direct CLI commands remain available.

## Install

On Windows, open PowerShell in this source checkout. First-time setup is one command:

```powershell
.\install.ps1
```

The script installs ADT in an isolated uv tool environment, obtains Python 3.12 if
needed, and uses a local cache automatically. If uv is absent, it asks before using
WinGet to install it. Without WinGet, it points to the official uv install guide.
ADT becomes available in the current terminal immediately. The script asks before
adding the tool folder to your **user PATH** for future terminals; system PATH and
PowerShell profiles/execution policy are untouched. Rerun the script to update ADT.
If PowerShell blocks local scripts, use the process-only alternative:
`powershell -ExecutionPolicy Bypass -File .\install.ps1`, then open a new terminal
if you accepted the user PATH update.

After setup, from any directory:

```powershell
adt
```

Use the sidebar with ↑/↓ and Enter, or `1` for Dashboard, `2` for Devices and `3` for
Diagnostics. In Devices, select a row and press Enter for details. `r` refreshes,
Esc cancels a pending query or returns to the previous view, and `q` / Ctrl+C quits.
Tab changes focus; buttons are also available. Normal full-screen mode is used on
Windows; no inline mode is required.

Device states refresh every three seconds without blocking navigation. A disconnected
or unavailable selected target clears its old details and never selects another phone.
Cancel pauses automatic refresh until a manual refresh or new selection. Exit terminates
and reaps pending ADB queries. Missing ADB does not prevent opening the interface: use
Diagnostics to supply its executable path and apply it for this session only.

Install official [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)
separately if missing. ADT never downloads ADB. Enable USB debugging on the phone,
connect it, unlock it and accept the debugging RSA authorization prompt.

On macOS/Linux, install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install .
uv tool update-shell
# Open a new terminal after updating the shell path.
adt
```

For direct commands, use `adt --help`, `adt doctor`, `adt devices`,
`adt devices --json`, or `adt device info --serial demo-device` (fictitious serial).
Developers can still use `uv sync --locked` and `uv run adt` from the checkout.
These installation commands may download dependencies/Python; daily use is offline.
The distribution name is provisional; PyPI name availability is not yet verified.

## Select ADB and a device

Discovery order: global `--adb-path`, `ANDROID_HOME/platform-tools/adb[.exe]`,
`ANDROID_SDK_ROOT/platform-tools/adb[.exe]`, then PATH. Candidates must be executable
files and pass `adb version`. `doctor` reports the effective path, candidate paths,
rejected candidates, Python/OS and whether stdout is a terminal. Lower-priority
candidates are listed without executing them after a successful match. An invalid
explicit path fails rather than silently selecting another SDK.

```powershell
uv run adt --adb-path "C:\Android SDK\platform-tools\adb.exe" doctor
uv run adt --timeout 20 device info --serial demo-device
```

Global options go **before** the command; `--serial` goes after `device info`.
Only a unique online (`device`) target is selected automatically. Multiple online
devices require `--serial` in direct commands; the TUI uses explicit row selection.
Offline, unauthorized and missing targets fail with
actionable messages, and an explicit missing target never falls back to another
device. Every call refreshes the list. `device use` and persisted configuration
are deferred to M3 ([ADR](docs/decisions/0001-m1-scope.md)).

Device details use `adb -s SERIAL shell getprop` and display manufacturer/model,
Android version, API level, state and transport. Missing properties are `N/A`;
transport is only inferred from a USB descriptor, emulator serial or reliable
network endpoint. Failure is reported with its cause. Human output includes the
actual argv, exit code, duration and captured output. The TUI keeps routine results compact;
command output and candidate ADB paths are available in Diagnostics. CLI colors honor
`NO_COLOR`, and device states remain readable as text. Invalid UTF-8 bytes are
replaced with U+FFFD so diagnostics do not crash.

`devices --json` writes exactly one JSON object to stdout:

```json
{"devices": [], "commands": [{"argv": ["adb", "devices", "-l"], "returncode": 0, "stdout": "List of devices attached\n", "stderr": "", "duration_ms": 1.0}]}
```

Each device has `serial`, `state`, nullable `model`/`transport`, and `attributes`.
On failure stdout is empty; diagnostics go to stderr. Command output may contain
device identifiers: review it before sharing. ADT does not save or upload it.

| Exit code | Meaning |
| --- | --- |
| 0 | Success, including an empty device list |
| 1 | General ADB command failure |
| 2 | Invalid CLI input |
| 3 | ADB missing, not executable or unsuccessful version probe |
| 4 | Device unavailable or ambiguous target |
| 5 | Device/list operation timeout |

Queries default to a finite 10-second timeout per subprocess, configurable by
`--timeout`. Version probe failures, including probe timeouts, mean ADB is unusable
and return 3. Ctrl+C uses the CLI's standard interruption behavior. There are no
streaming subprocesses. Redirected no-argument invocations print help rather
than prompting. Direct commands never prompt, including when attached to a terminal.

## Develop and contribute

```powershell
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests isolate the host SDK and phone, mock ADB responses, and also run real Python
subprocesses to verify output decoding, nonzero exits, timeout and cancellation cleanup.
Textual Pilot tests cover navigation, empty/error states, refresh, selection, stale
results and responsive cancellation/exit without requiring a real phone.
GitHub Actions covers Windows/Ubuntu with Python 3.12 and 3.14. CI results on the
remote service must be checked after publication; local checks do not prove them.
macOS is not yet in CI. Hardware states such as authorization, disconnection and
multiple devices are covered by isolated tests; CI does not require a phone.

Read [AGENTS.md](AGENTS.md), [architecture](docs/architecture.md),
[configuration](docs/configuration.md) and [roadmap](docs/roadmap.md) before changes.
Keep CLI/TUI adapters thin;
put shared behavior in core and subprocess calls only in `AdbRunner`. Use typed
APIs, argv arrays, `shell=False`, bounded timeouts and fictitious fixtures. Never
commit credentials, business identifiers or real serials. Avoid unrelated changes,
new dependencies without agreement, and speculative abstractions. Add tests for
observable behavior and update both READMEs/CHANGELOG for public changes.

MIT applies to ADT. Runtime dependencies are Typer, Rich and Textual.
Development/build dependencies include pytest, Ruff, mypy and Hatchling.
See [dependency review](docs/dependencies.md) for metadata and license review.

See the [documentation index](docs/README.md) for the project layout and all guides.
Generated caches and local acceptance installs belong in `.adt-local/`; `.git`,
`.github` and `.venv` retain their standard locations.

## Scope

M2 provides the device TUI. M3: projects, TOML, saved device selection and app/GA commands.
M4: structured YAML workflows. M5: packaging and release polish. None of those
features is exposed as an inactive command or page in this version.
