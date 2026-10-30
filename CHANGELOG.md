# Changelog

## Unreleased

- M2: replace the line-based menu with a full-screen Textual dashboard, device list,
  device details and diagnostics with a session-only ADB path field.
- Add keyboard navigation, three-second state refresh, loading/error/empty states,
  stale-selection invalidation and cancellable background queries with child cleanup.
- Preserve direct CLI/JSON commands and add Pilot coverage for full-screen interaction.
- Add a one-command Windows installer with automatic runtime setup and opt-in user PATH update.
- Keep routine device results compact, with colored states and readable status text.
- Keep direct commands/JSON noninteractive and revalidate explicitly selected device targets.
- Keep device/config persistence and project/app/script operations deferred to M3+.
- Consolidate development artifacts under .adt-local and add a public documentation index.

## 0.1.0 — 2026-10-28

- M0: src-layout package, uv lock, MIT license, bilingual documentation, development rules
  and Windows/Ubuntu CI configuration.
- M1: validated ADB discovery, doctor, timeout-aware argv execution, structured errors,
  device listing/JSON, safe device selection and read-only Android properties.
- Automated tests for missing ADB, discovery priority, Unicode paths, decoding, device states,
  multiple targets, disconnection, nonzero exits and real subprocess timeouts.
- No TUI or M2+ placeholder commands. Saved default selection is deferred to M3 by ADR.
