"""Discover official user-installed ADB; never download or modify the environment."""

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from adt.core.adb_runner import AdbRunner
from adt.core.errors import AdbCancelledError, AdbUnavailableError, AdtError
from adt.core.models import CommandResult

DOWNLOAD_URL = "https://developer.android.com/tools/releases/platform-tools"


@dataclass(frozen=True)
class AdbCandidate:
    source: str
    path: Path | None


@dataclass(frozen=True)
class AdbLocation:
    path: Path
    candidates: tuple[AdbCandidate, ...]
    version: CommandResult
    rejected: tuple[str, ...]


class AdbLocator:
    def __init__(
        self,
        explicit_path: Path | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        timeout: float = 10.0,
        cancel_event: Event | None = None,
    ) -> None:
        self.explicit_path = explicit_path
        self.environ = os.environ if environ is None else environ
        self.timeout = timeout
        self.cancel_event = cancel_event

    def candidates(self) -> tuple[AdbCandidate, ...]:
        executable = "adb.exe" if os.name == "nt" else "adb"
        candidates = [AdbCandidate("--adb-path", self.explicit_path)]
        for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
            root = self.environ.get(name)
            candidates.append(
                AdbCandidate(name, Path(root) / "platform-tools" / executable if root else None)
            )
        found = shutil.which(executable, path=self.environ.get("PATH", ""))
        candidates.append(AdbCandidate("PATH", Path(found) if found else None))
        return tuple(candidates)

    def locate(self) -> AdbLocation:
        candidates = self.candidates()
        rejected: list[str] = []
        for candidate in candidates:
            path = candidate.path
            if path is None:
                continue
            try:
                if not path.is_file() or not os.access(path, os.X_OK):
                    raise AdbUnavailableError("File is missing or not executable.")
                version = AdbRunner(
                    path.resolve(), timeout=self.timeout, cancel_event=self.cancel_event
                ).run(["version"])
                if "Android Debug Bridge version" not in version.stdout:
                    raise AdbUnavailableError(
                        "Executable did not identify itself as Android Debug Bridge."
                    )
            except AdbCancelledError:
                raise
            except (AdtError, OSError) as exc:
                rejected.append(f"{candidate.source}: {path}: {exc}")
                if isinstance(exc, AdtError) and exc.result is not None:
                    result = exc.result
                    rejected.append(
                        f"argv={result.argv!r}; exit={result.returncode}; "
                        f"duration={result.duration_ms:.1f} ms; "
                        f"stdout={result.stdout!r}; stderr={result.stderr!r}"
                    )
                # 显式路径出错必须暴露，不能悄悄切换到另一套 SDK。
                if candidate.source == "--adb-path":
                    break
                continue
            return AdbLocation(path.resolve(), candidates, version, tuple(rejected))
        searched = "\n".join(
            f"  {item.source}: {item.path or '(not set/found)'}" for item in candidates
        )
        details = "\n".join(rejected)
        raise AdbUnavailableError(
            f"No usable ADB. Searched:\n{searched}\n{details}\n"
            f"Install official Platform-Tools: {DOWNLOAD_URL}\n"
            "Use --adb-path PATH or set ANDROID_HOME for this terminal; "
            "no permanent change is needed."
        )
