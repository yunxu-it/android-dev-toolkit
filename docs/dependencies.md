# Dependency review

Initial version bounds were checked against PyPI's official JSON metadata on
2026-10-28. Python minimums: Typer 0.27.3 (3.10), Rich 15.0.0 (3.9), pytest 9.2.0
(3.10), Ruff 0.17.3 (3.7), mypy 2.4.0 (3.10), Hatchling 1.33.0 (3.10).
All are compatible with this project's Python >=3.12 requirement according to metadata.
uv.lock records resolved direct and transitive versions with hashes, from public PyPI.

Official metadata sources: https://pypi.org/pypi/typer/json,
https://pypi.org/pypi/rich/json, https://pypi.org/pypi/pytest/json,
https://pypi.org/pypi/ruff/json, https://pypi.org/pypi/mypy/json,
https://pypi.org/pypi/hatchling/json.

All direct packages declare MIT licenses in official metadata. Runtime transitive
dependencies declare MIT, BSD-2-Clause/BSD and ISC licenses. Development dependencies
also include Apache-2.0/BSD, MPL-2.0 and PSF-2.0 declarations. A metadata review is not
a substitute for preserving dependency
license notices in future bundled distributions. ADT distributes source/wheels,
not vendored third-party binaries or Android SDK Platform-Tools.

M2 adds Textual >=8.2.8,<9, verified against official PyPI metadata on 2026-10-30:
https://pypi.org/pypi/textual/json. Its Python requirement is >=3.9,<4 and Rich
requirement >=14.2, compatible with this project. It declares MIT; its new transitive
packages (linkify-it-py, mdit-py-plugins and platformdirs) also declare permissive
licenses. No syntax extras or test-only plugins are installed. Pilot is included in
Textual; async tests use asyncio.run with existing pytest. PyYAML remains deferred to M4.
