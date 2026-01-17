"""
Storage Paths Manager
Handles storage location logic for app data, profiles, and configs.
Supports different paths for development vs production environments.
"""

import os
import sys
import shutil
import json
from pathlib import Path
from typing import Optional
from enum import Enum


class StorageLocation(str, Enum):
    """Storage location modes."""
    APP_FOLDER = "app_folder"       # Store in app installation folder
    PROGRAM_DATA = "program_data"   # Store in C:\ProgramData\AppName
    CUSTOM = "custom"               # User-defined custom path


def is_frozen() -> bool:
    """Check if running as compiled executable (PyInstaller)."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_app_name() -> str:
    """Get the application name for folder creation."""
    return "DayZModManager"


def get_base_path() -> Path:
    """
    Get the base path for the application.
    
    - If frozen (built executable): Returns the directory containing the exe
    - If running as script: Returns the project root directory
    """
    if is_frozen():
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script - project root (where main.py is)
        return Path(__file__).parent.parent.parent


def get_resource_base_path() -> Path:
    """Return the base directory for bundled, read-only resources.

    Dev: project root
    Frozen (PyInstaller): sys._MEIPASS (fallback to exe dir)
    """
    if is_frozen():
        exe_dir = Path(sys.executable).parent
        # In onedir builds, data folders usually live next to the exe.
        if (exe_dir / "locales").exists() or (exe_dir / "assets").exists() or (exe_dir / "configs").exists():
            return exe_dir

        # In onefile builds, data lives under _MEIPASS.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass)
            if p.exists():
                return p
        return exe_dir
    return Path(__file__).parent.parent.parent


def get_default_storage_path() -> Path:
    """
    Get the default storage path based on environment.
    
    All modes:
        - Use per-user writable storage under %APPDATA% (Roaming)
        - This avoids writing into Program Files or other protected folders
    """
    appdata = os.environ.get('APPDATA')
    if appdata:
        base = Path(appdata)
    else:
        # Fallback for environments where APPDATA isn't set
        base = Path.home() / 'AppData' / 'Roaming'
    storage_path = base / get_app_name()
    try:
        storage_path.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        print(f"Warning: Could not create APPDATA storage directory at {storage_path}: {e}")
    return storage_path


def get_configs_path(custom_path: Optional[str] = None) -> Path:
    """
    Get the path for configuration files.
    
    Args:
        custom_path: Optional custom storage path from settings
    
    Returns:
        Path to configs directory
    """
    if custom_path and Path(custom_path).exists():
        base = Path(custom_path)
    else:
        base = get_default_storage_path()
    
    configs_path = base / "configs"
    configs_path.mkdir(parents=True, exist_ok=True)
    return configs_path


def get_profiles_path(custom_path: Optional[str] = None) -> Path:
    """
    Get the path for profile files.
    
    Args:
        custom_path: Optional custom profiles path from settings
    
    Returns:
        Path to profiles directory
    """
    if custom_path and Path(custom_path).exists():
        base = Path(custom_path)
        profiles_path = base if base.name == "profiles" else base / "profiles"
    else:
        profiles_path = get_default_storage_path() / "profiles"
    
    profiles_path.mkdir(parents=True, exist_ok=True)
    return profiles_path


def get_settings_file_path() -> Path:
    """
    Get the path for the settings.json file.
    
    Returns:
        Path to settings.json
    """
    return get_configs_path() / "settings.json"


def get_app_config_file_path() -> Path:
    """
    Get the path for the app.json config file.
    
    Always use the bundled/resource config - this is read-only app metadata.
    
    Returns:
        Path to app.json in resource directory
    """
    return get_resource_base_path() / "configs" / "app.json"


def get_defaults_path() -> Path:
    """
    Get the path for default config templates.
    Always from app installation/project folder.
    
    Returns:
        Path to defaults directory
    """
    return get_resource_base_path() / "configs" / "defaults"


def get_resource_configs_path() -> Path:
    """Return the bundled configs directory (read-only)."""
    return get_resource_base_path() / "configs"


def get_locales_path() -> Path:
    """
    Get the path for locale files.
    Always from app installation/project folder.
    
    Returns:
        Path to locales directory
    """
    return get_resource_base_path() / "locales"


def get_assets_path() -> Path:
    """
    Get the path for asset files (icons, themes, etc.).
    Always from app installation/project folder.
    
    Returns:
        Path to assets directory
    """
    return get_resource_base_path() / "assets"


def ensure_storage_structure() -> dict:
    """
    Ensure all required storage directories exist.
    
    Returns:
        Dictionary with paths to all storage locations
    """
    paths = {
        # Writable
        'base': get_default_storage_path(),
        'configs': get_configs_path(),
        'profiles': get_profiles_path(),
        # Read-only bundled resources
        'defaults': get_defaults_path(),
        'locales': get_locales_path(),
        'assets': get_assets_path(),
    }
    
    # Ensure writable directories exist
    for name in ("base", "configs", "profiles"):
        path = paths[name]
        try:
            path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not create {name} directory at {path}: {e}")
    
    return paths


def bootstrap_first_run() -> None:
    """Ensure first-run files exist in the writable storage folder.

    This is especially important for frozen builds where the bundled configs/locales
    live under sys._MEIPASS (read-only) and user-writable configs must be created
    under %APPDATA%.
    """
    ensure_storage_structure()

    configs_dir = get_configs_path()
    bundled_configs = get_resource_configs_path()

    # app.json is resource-only. If an older version wrote it into user storage,
    # remove it to avoid confusion.
    try:
        stale_app_json = configs_dir / "app.json"
        if stale_app_json.exists():
            stale_app_json.unlink()
    except Exception as e:
        print(f"Warning: Could not remove stale app.json: {e}")

    # settings.json
    settings_dst = configs_dir / "settings.json"
    if not settings_dst.exists():
        settings_src = bundled_configs / "settings.json"
        try:
            if settings_src.exists():
                shutil.copyfile(settings_src, settings_dst)
            else:
                from dataclasses import asdict
                from src.core.settings_manager import AppSettings

                settings_dst.write_text(
                    json.dumps(asdict(AppSettings()), indent=2) + "\n",
                    encoding="utf-8",
                )
        except Exception as e:
            print(f"Warning: Could not bootstrap settings.json: {e}")

    # NOTE: app.json is app metadata and must remain read-only.
    # It is bundled with the application and should never be copied into user storage.


def get_storage_info() -> dict:
    """
    Get information about current storage configuration.
    
    Returns:
        Dictionary with storage information for display
    """
    return {
        'is_production': is_frozen(),
        'base_path': str(get_default_storage_path()),
        'configs_path': str(get_configs_path()),
        'profiles_path': str(get_profiles_path()),
        'app_path': str(get_base_path()),
    }


# Initialize storage on module load
if __name__ != "__main__":
    ensure_storage_structure()
