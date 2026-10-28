# Changelog

## Unreleased

- Add a one-command Windows installer with automatic runtime setup and opt-in user PATH update.
- Start a line-based menu with `adt` in a terminal; prompt for missing ADB paths and device selection.
- Keep routine menu results compact; color headings/device states and retain plain text accessibility.
- Keep direct commands/JSON noninteractive, revalidate devices after selection and recover to the menu.
- Preserve the M1 boundary: no Textual dependency, full-screen TUI or persisted device/config state.
- Consolidate development artifacts under .adt-local and add a public documentation index.

## 0.1.0 — 2026-10-28

- M0: src-layout package, uv lock, MIT license, bilingual documentation, development rules
  and Windows/Ubuntu CI configuration.
- M1: validated ADB discovery, doctor, timeout-aware argv execution, structured errors,
  device listing/JSON, safe device selection and read-only Android properties.
- Automated tests for missing ADB, discovery priority, Unicode paths, decoding, device states,
  multiple targets, disconnection, nonzero exits and real subprocess timeouts.
- No TUI or M2+ placeholder commands. Saved default selection is deferred to M3 by ADR.
