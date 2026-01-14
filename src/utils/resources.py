"""Resource path helpers.

Keeps access to bundled files consistent between dev runs and PyInstaller builds.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable


def _dev_project_root() -> Path:
    # src/utils/resources.py -> src/utils -> src -> project root
    return Path(__file__).resolve().parents[3]


def _frozen_base_dir() -> Path:
    # For PyInstaller onedir, sys.executable is in dist/<app>/
    # For onefile, bundled files are extracted to sys._MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return Path(sys.executable).resolve().parent


def app_base_dir() -> Path:
    """Return base directory used to resolve bundled resources."""
    if getattr(sys, "frozen", False):
        return _frozen_base_dir()
    return _dev_project_root()


def asset_path(*parts: str) -> Path:
    """Resolve a path under the app's assets directory."""
    return app_base_dir() / "assets" / Path(*parts)


def first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None
