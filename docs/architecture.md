# Architecture

```text
src/adt/cli.py                 Typer/Rich input and output adapter
src/adt/core/device_service.py Device parsing, selection, property queries
src/adt/core/adb_locator.py    Discovery and version validation
src/adt/core/adb_runner.py     Sole ADB subprocess boundary
src/adt/core/models.py         Shared typed results
src/adt/core/errors.py         Stable error categories/exit codes
tests/                        Isolated Mock ADB and real subprocess tests
.github/workflows/ci.yml       Windows/Ubuntu checks
```

Dependency direction: adapters → core services → runner → subprocess. Core imports
neither CLI nor future TUI. Services receive a runner; tests replace the subprocess
boundary with a deterministic fake. No device status cache, global selected target,
network request, persistent command log or arbitrary shell executor exists.

AdbRunner executes an argv tuple with shell=False and captures bytes before decoding
UTF-8 with replacement. CommandResult preserves argv, return code (None on timeout),
stdout/stderr and monotonic duration. Nonzero results raise typed exceptions retaining
the result. subprocess.run terminates and waits for the finite child on timeout; M1
does not introduce process trees or streaming commands. Keyboard interruption is
handled by Python/subprocess and Typer's standard CLI behavior, with no custom signal
handler that would assume POSIX signals on Windows.

DeviceService refreshes devices -l, refuses ambiguous/unavailable targets and locks
the selected serial into the subsequent getprop argv. A disconnect between discovery
and querying is a real failure, never grounds for silently targeting a different phone.
Missing individual properties are nullable; failed commands remain errors. Transport
is nullable rather than an assumption that all physical serials mean USB.

Future Textual workers must call these same services outside the UI thread. Future
destructive actions require confirmation, validated device-shell arguments and explicit
target selection. Do not add these commands before their milestone.

The convenience entrypoint is a line-based menu in the CLI adapter,
enabled only for no-argument invocations with terminal input/output. It reuses the
same command functions and core services. Selected targets are rechecked after user
input; no core module depends on prompts. Direct commands never enter the menu or
prompt, so machine-readable behavior and ambiguity failures remain stable.

install.ps1 is a Windows setup script, not an ADT runtime executor. It invokes uv
(and optionally WinGet after consent) to install dependencies, makes the executable
available in the current process and asks before persisting user PATH changes. It
does not run ADB, install it, alter system PATH or modify shell profiles/policies.
