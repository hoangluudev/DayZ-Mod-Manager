"""
Application Configuration Manager
Centralized configuration for app metadata and version.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application configuration data."""
    version: str
    name: str
    description: str
    author: str
    license: str
    repository: str
    homepage: str


class AppConfigManager:
    """
    Manages application configuration with centralized version control.
    
    Features:
    - Load config from JSON file
    - Provide app metadata (version, name, etc.)
    - Singleton pattern for app-wide access
    """
    
    _instance: Optional['AppConfigManager'] = None
    
    def __new__(cls, *args, **kwargs) -> 'AppConfigManager':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize AppConfigManager.
        
        Args:
            config_path: Path to app config JSON file
        """
        if self._initialized:
            return
            
        self._initialized = True
        
        if config_path:
            self._config_path = Path(config_path)
        else:
            # Use storage_paths module for proper path resolution
            from shared.core.storage_paths import get_app_config_file_path
            self._config_path = get_app_config_file_path()
        
        self._config = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        # In frozen builds, app metadata must be embedded (not shipped as a plain JSON file).
        try:
            from shared.core.storage_paths import is_frozen
            if is_frozen():
                from constants.app_embedded import APP_CONFIG  # type: ignore
                if isinstance(APP_CONFIG, dict) and APP_CONFIG:
                    self._config = APP_CONFIG
                    return
        except Exception:
            # Fall back to file loading below
            pass

        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._config = data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading app config: {e}")
                self._config = self._get_default_config()
        else:
            # Use default config if file doesn't exist (shouldn't happen in production)
            print(f"Warning: app.json not found at {self._config_path}, using defaults")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'version': '1.0.0',
            'name': 'DayZ Mod Manager',
            'description': 'DayZ Mod Manager & Server Controller',
            'author': 'Your Name',
            'license': 'GPL-3.0',
            'repository': '',
            'homepage': ''
        }
    
    @property
    def version(self) -> str:
        """Get application version."""
        return self._config.get('version', '1.0.0')
    
    @property
    def name(self) -> str:
        """Get application name."""
        return self._config.get('name', 'DayZ Mod Manager')
    
    @property
    def description(self) -> str:
        """Get application description."""
        return self._config.get('description', 'DayZ Mod Manager & Server Controller')
    
    @property
    def author(self) -> str:
        """Get application author."""
        return self._config.get('author', 'Your Name')
    
    @property
    def license(self) -> str:
        """Get application license."""
        return self._config.get('license', 'GPL-3.0')
    
    @property
    def repository(self) -> str:
        """Get repository URL."""
        return self._config.get('repository', '')
    
    @property
    def homepage(self) -> str:
        """Get homepage URL."""
        return self._config.get('homepage', '')
    
    def get_config(self) -> Dict[str, Any]:
        """Get the complete configuration object."""
        return self._config.copy()
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()


# Convenience functions
def get_version() -> str:
    """Get application version."""
    return AppConfigManager().version

def get_app_name() -> str:
    """Get application name."""
    return AppConfigManager().name

def get_app_description() -> str:
    """Get application description."""
    return AppConfigManager().description

def get_app_author() -> str:
    """Get application author."""
    return AppConfigManager().author

def get_app_license() -> str:
    """Get application license."""
    return AppConfigManager().license

def get_app_repository() -> str:
    """Get repository URL."""
    return AppConfigManager().repository

def get_app_homepage() -> str:
    """Get homepage URL."""
    return AppConfigManager().homepage
