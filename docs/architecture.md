# Architecture

```text
src/adt/cli.py                 Typer/Rich input and output adapter
src/adt/tui/app.py             Textual screens, query workers and ephemeral UI state
src/adt/tui/app.tcss           Full-screen layout
src/adt/core/device_service.py Device parsing, selection, property queries
src/adt/core/adb_locator.py    Discovery and version validation
src/adt/core/adb_runner.py     Sole ADB subprocess boundary
src/adt/core/models.py         Shared typed results
src/adt/core/errors.py         Stable error categories/exit codes
tests/                        Isolated Mock ADB and real subprocess tests
.github/workflows/ci.yml       Windows/Ubuntu checks
```

Dependency direction: adapters → core services → runner → subprocess. Core imports
neither CLI nor TUI. Services receive a runner; tests replace the subprocess
boundary with a deterministic fake. No persistent device cache, global selected target,
network request, persistent command log or arbitrary shell executor exists.

AdbRunner executes an argv tuple with shell=False and captures bytes before decoding
UTF-8 with replacement. CommandResult preserves argv, return code (None on timeout),
stdout/stderr and monotonic duration. Nonzero results raise typed exceptions retaining
the result. CLI uses subprocess.run; TUI supplies a cancellation Event and uses the
runner's Popen/communicate path, which kills and reaps the child on cancel/timeout.
No process trees or streaming commands are introduced. Keyboard interruption is
handled by Python/subprocess and Typer's standard CLI behavior, with no custom signal
handler that would assume POSIX signals on Windows.

DeviceService refreshes devices -l, refuses ambiguous/unavailable targets and locks
the selected serial into the subsequent getprop argv. A disconnect between discovery
and querying is a real failure, never grounds for silently targeting a different phone.
Missing individual properties are nullable; failed commands remain errors. Transport
is nullable rather than an assumption that all physical serials mean USB.

Textual workers call these same services outside the UI thread. Future
destructive actions require confirmation, validated device-shell arguments and explicit
target selection. Do not add these commands before their milestone.

The full-screen entrypoint is enabled only for no-argument invocations with terminal
input/output. It shares core services with the CLI. Selected targets are rechecked after user
input; no core module depends on widgets. Direct commands never enter the TUI or
prompt, so machine-readable behavior and ambiguity failures remain stable.

The UI has Dashboard, Devices, Device details and Diagnostics views, with loading,
empty and error states. A three-second poll refreshes device availability and clears
disconnected targets without selecting another device. Queries have exclusive workers,
cancellation events and generation IDs: obsolete results never update widgets. The
worker shields its thread task, signals cancellation and waits for cleanup; exit also
waits for pending query cleanup. Failed queries discard old details rather than leave
stale success visible. Choosing a device and entering an ADB path affect only the session.

install.ps1 is a Windows setup script, not an ADT runtime executor. It invokes uv
(and optionally WinGet after consent) to install dependencies, makes the executable
available in the current process and asks before persisting user PATH changes. It
does not run ADB, install it, alter system PATH or modify shell profiles/policies.
