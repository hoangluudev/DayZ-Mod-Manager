"""
Settings Manager
Handles application settings persistence with JSON storage.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class Theme(Enum):
    """Application theme options."""
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


@dataclass
class AppSettings:
    """Application settings data structure."""
    # Appearance
    theme: str = "dark"
    language: str = "en"
    
    # Paths
    steamcmd_path: str = ""
    workshop_path: str = ""
    last_server_path: str = ""
    default_workshop_path: str = ""
    default_server_path: str = ""
    
    # Startup
    start_minimized: bool = False
    check_updates_on_startup: bool = True
    
    # Behavior
    auto_backup: bool = True
    confirm_actions: bool = True
    auto_copy_bikeys: bool = True
    
    # Window state
    window_width: int = 1200
    window_height: int = 800
    window_maximized: bool = False
    
    # Last used profile
    last_profile: str = ""


class SettingsManager:
    """
    Manages application settings with automatic persistence.
    
    Features:
    - Load/save settings from JSON file
    - Default values for missing settings
    - Type-safe access to settings
    - Auto-save on change (optional)
    
    Usage:
        settings = SettingsManager()
        settings.set("theme", "light")
        theme = settings.get("theme")
        settings.save()
    """
    
    _instance: Optional['SettingsManager'] = None
    
    def __new__(cls, *args, **kwargs) -> 'SettingsManager':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, settings_path: Optional[str] = None, auto_save: bool = True):
        """
        Initialize SettingsManager.
        
        Args:
            settings_path: Path to settings JSON file
            auto_save: Automatically save when settings change
        """
        if self._initialized:
            return
            
        self._initialized = True
        
        if settings_path:
            self._settings_path = Path(settings_path)
        else:
            # Default: settings.json in app config directory
            self._settings_path = Path(__file__).parent.parent.parent / "configs" / "settings.json"
        
        self._auto_save = auto_save
        self._settings = AppSettings()
        
        self._load()
    
    def _load(self) -> None:
        """Load settings from file."""
        if self._settings_path.exists():
            try:
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Update settings with loaded values
                    for key, value in data.items():
                        if hasattr(self._settings, key):
                            setattr(self._settings, key, value)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading settings: {e}")
    
    def save(self) -> bool:
        """
        Save settings to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._settings), f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return getattr(self._settings, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        if hasattr(self._settings, key):
            setattr(self._settings, key, value)
            if self._auto_save:
                self.save()
    
    @property
    def settings(self) -> AppSettings:
        """Get the settings object."""
        return self._settings
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = AppSettings()
        if self._auto_save:
            self.save()
