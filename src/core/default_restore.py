"""Default Restore Utilities

Provides functions to restore server files and app settings to their defaults.

- Server restore: copies template `start.bat` and `serverDZ.cfg` into a selected server folder.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import shutil

from src.core.storage_paths import get_defaults_path


@dataclass(frozen=True)
class RestoreResult:
    server_path: Path
    start_bat_written: bool
    server_cfg_written: bool
    start_bat_path: Path
    server_cfg_path: Path


def defaults_dir() -> Path:
    return get_defaults_path()


def default_start_bat_template() -> Path:
    return defaults_dir() / "start.bat"


def default_server_cfg_template() -> Path:
    return defaults_dir() / "serverDZ.cfg"


def restore_server_defaults(
    server_path: str | Path,
    overwrite: bool = True,
) -> RestoreResult:
    """Restore `start.bat` and `serverDZ.cfg` into the given server folder.

    Args:
        server_path: DayZ server folder (destination)
        overwrite: If True, overwrite existing files.

    Returns:
        RestoreResult describing what was written.

    Raises:
        FileNotFoundError: if template files are missing.
        NotADirectoryError: if server_path is not a directory.
    """
    server_dir = Path(server_path)
    if not server_dir.exists() or not server_dir.is_dir():
        raise NotADirectoryError(f"Invalid server folder: {server_dir}")

    start_tpl = default_start_bat_template()
    cfg_tpl = default_server_cfg_template()

    if not start_tpl.exists():
        raise FileNotFoundError(f"Missing default template: {start_tpl}")
    if not cfg_tpl.exists():
        raise FileNotFoundError(f"Missing default template: {cfg_tpl}")

    dest_start = server_dir / "start.bat"
    dest_cfg = server_dir / "serverDZ.cfg"

    start_written = False
    cfg_written = False

    if overwrite or not dest_start.exists():
        shutil.copy2(start_tpl, dest_start)
        start_written = True

    if overwrite or not dest_cfg.exists():
        shutil.copy2(cfg_tpl, dest_cfg)
        cfg_written = True

    return RestoreResult(
        server_path=server_dir,
        start_bat_written=start_written,
        server_cfg_written=cfg_written,
        start_bat_path=dest_start,
        server_cfg_path=dest_cfg,
    )
