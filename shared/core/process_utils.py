"""Process detection helpers.

Currently used to detect if DayZ server is running before writing config files.
"""

from __future__ import annotations

import sys
import subprocess


DAYZ_SERVER_PROCESS_NAMES: tuple[str, ...] = (
    "DayZServer_x64.exe",
    "DayZServer.exe",
)


def is_process_running(process_name: str) -> bool:
    """Return True if a process with the given image name is running.

    Windows implementation uses `tasklist` to avoid extra dependencies.
    Non-Windows returns False.
    """

    if sys.platform != "win32":
        return False

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return False
        return process_name.lower() in (result.stdout or "").lower()
    except Exception:
        return False


def is_dayz_server_running() -> bool:
    """Return True if DayZ server process appears to be running."""

    return any(is_process_running(name) for name in DAYZ_SERVER_PROCESS_NAMES)
