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
    version: str = "1.0.0"
    name: str = "DayZ Mod Manager"
    description: str = "DayZ Mod Manager & Server Controller"
    author: str = "Your Name"
    license: str = "GPL-3.0"
    repository: str = ""
    homepage: str = ""


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
            # Default: app.json in configs directory
            self._config_path = Path(__file__).parent.parent.parent / "configs" / "app.json"
        
        self._config = AppConfig()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Update config with loaded values
                    for key, value in data.items():
                        if hasattr(self._config, key):
                            setattr(self._config, key, value)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading app config: {e}")
        else:
            # Create default config file if it doesn't exist
            self._save_config()
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': self._config.version,
                    'name': self._config.name,
                    'description': self._config.description,
                    'author': self._config.author,
                    'license': self._config.license,
                    'repository': self._config.repository,
                    'homepage': self._config.homepage
                }, f, indent=2)
        except IOError as e:
            print(f"Error saving app config: {e}")
    
    @property
    def version(self) -> str:
        """Get application version."""
        return self._config.version
    
    @property
    def name(self) -> str:
        """Get application name."""
        return self._config.name
    
    @property
    def description(self) -> str:
        """Get application description."""
        return self._config.description
    
    @property
    def author(self) -> str:
        """Get application author."""
        return self._config.author
    
    @property
    def license(self) -> str:
        """Get application license."""
        return self._config.license
    
    @property
    def repository(self) -> str:
        """Get repository URL."""
        return self._config.repository
    
    @property
    def homepage(self) -> str:
        """Get homepage URL."""
        return self._config.homepage
    
    def set_version(self, version: str) -> None:
        """Set application version."""
        self._config.version = version
        self._save_config()
    
    def set_name(self, name: str) -> None:
        """Set application name."""
        self._config.name = name
        self._save_config()
    
    def set_description(self, description: str) -> None:
        """Set application description."""
        self._config.description = description
        self._save_config()
    
    def set_author(self, author: str) -> None:
        """Set application author."""
        self._config.author = author
        self._save_config()
    
    def set_license(self, license: str) -> None:
        """Set application license."""
        self._config.license = license
        self._save_config()
    
    def set_repository(self, repository: str) -> None:
        """Set repository URL."""
        self._config.repository = repository
        self._save_config()
    
    def set_homepage(self, homepage: str) -> None:
        """Set homepage URL."""
        self._config.homepage = homepage
        self._save_config()
    
    def get_config(self) -> AppConfig:
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
