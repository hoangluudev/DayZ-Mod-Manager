"""Resource path helpers.

Keeps access to bundled files consistent between dev runs and PyInstaller builds.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

from src.core.storage_paths import get_resource_base_path, get_assets_path


def app_base_dir() -> Path:
    """Return base directory used to resolve bundled resources."""
    return get_resource_base_path()


def asset_path(*parts: str) -> Path:
    """Resolve a path under the app's assets directory."""
    return get_assets_path() / Path(*parts)


def first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None
