# Configuration (M2)

The ADT runtime reads no persistent configuration and writes no user files.
The optional Windows installer installs the tool and, with confirmation, updates
user PATH. Global CLI options:

- `--adb-path PATH`: exact ADB executable, not its containing directory; quote spaces.
- `--timeout SECONDS`: finite positive float, default 10 per ADB subprocess.
- `--version`: print package version without probing ADB.

Global options precede the command. `device info --serial SERIAL` is a per-call
override and does not save a default. Without a serial only one online device is
eligible in direct commands. The full-screen TUI uses explicit device-row selection
and accepts an ADB path in Diagnostics for this session. ANDROID_SERIAL is deliberately not used:
ADT passes the selected -s serial
explicitly. Discovery checks ANDROID_HOME, legacy ANDROID_SDK_ROOT and PATH after
the explicit path; doctor describes search results and the official download URL.

TOML config, schema_version, atomic writes, OS-standard user directories and saved
device/project selection belong to M3. No example user configuration is activated
silently in M2. See the scope ADR. The TUI polls device states every three seconds,
pauses after cancellation and clears old details when the selected target disappears.

For a restricted Windows environment with an unwritable uv cache, set a temporary
session cache under the ignored local directory before installation:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.adt-local/uv-cache'
uv sync --locked
```

This setting affects uv, not ADT or system ADB discovery. Do not commit local caches.
The Windows install.ps1 entrypoint already supplies a local cache automatically;
ordinary users do not need to set this variable or run uv sync.
