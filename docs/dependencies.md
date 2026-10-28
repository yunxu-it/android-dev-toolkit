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
license notices in future bundled distributions. M1 distributes ADT source/wheels,
not vendored third-party binaries or Android SDK Platform-Tools. Textual and PyYAML
are not installed until their milestones need them.
