# ADR 0001 — M1 scope and persistent selection

Status: accepted for M0/M1, 2026-10-28.

M1 provides discovery, diagnostics, device lists and read-only details. Persistent
selection requires configuration schemas, OS-specific user directories and atomic
writes. These responsibilities belong to M3 alongside project management.

Decision: M1 has no persisted selection and no inactive device use command. Explicit
--serial wins; otherwise exactly one online device is required. M3 adds storage and
must preserve the rule that a disconnected saved target never falls back to another.

Similarly, explicit ADB configuration is supplied by the global --adb-path option
until TOML is introduced. Invalid explicit paths fail rather than silently switching
SDKs; invalid environment candidates can fall through with diagnostic reasons.

No-argument adt opens a line-based CLI menu when attached to a terminal. Windows
install.ps1 provides one-time setup; redirected invocations still show help.
Textual, its dependency and full-screen entrypoint remain M2. No TUI scaffolding or
persistent ADB/device configuration is introduced.
