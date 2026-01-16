"""
Application Constants
Core application configuration and metadata constants.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class LanguageCode(str, Enum):
    """Supported language codes."""
    ENGLISH = "en"
    VIETNAMESE = "vi"
    
    @classmethod
    def from_string(cls, value: str) -> "LanguageCode":
        """Convert string to LanguageCode, defaulting to ENGLISH."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.ENGLISH


@dataclass(frozen=True)
class LanguageInfo:
    """Language metadata."""
    code: LanguageCode
    name: str
    native_name: str
    flag_emoji: str


SUPPORTED_LANGUAGES: Dict[str, LanguageInfo] = {
    "en": LanguageInfo(LanguageCode.ENGLISH, "English", "English", "🇬🇧"),
    "vi": LanguageInfo(LanguageCode.VIETNAMESE, "Vietnamese", "Tiếng Việt", "🇻🇳"),
}


@dataclass(frozen=True)
class AppDefaults:
    """Default application values."""
    
    # Appearance
    THEME: str = "dark"
    LANGUAGE: str = "en"
    ACCENT_COLOR: str = "#43a047"
    
    # Window
    WINDOW_WIDTH: int = 1200
    WINDOW_HEIGHT: int = 800
    
    # Behavior
    AUTO_BACKUP: bool = True
    CONFIRM_ACTIONS: bool = True
    CHECK_UPDATES: bool = True
    START_MINIMIZED: bool = False
    AUTO_COPY_BIKEYS: bool = True
    
    # App metadata
    APP_NAME: str = "DayZ Mod Manager"
    ORGANIZATION: str = "DayzModManager"
    
    # File names
    SETTINGS_FILE: str = "settings.json"
    APP_CONFIG_FILE: str = "app.json"
    DEFAULT_LOGO: str = "new_logo.png"


APP_DEFAULTS = AppDefaults()


# ============================================================================
# FILE PATHS (relative to project root)
# ============================================================================

class Paths:
    """Standard paths relative to project root."""
    
    CONFIGS_DIR = "configs"
    LOCALES_DIR = "locales"
    PROFILES_DIR = "profiles"
    ASSETS_DIR = "assets"
    ICONS_DIR = "assets/icons"
    THEMES_DIR = "assets/themes"
    
    # Default files
    DEFAULT_SERVER_CFG = "configs/defaults/serverDZ.cfg"
    DEFAULT_START_BAT = "configs/defaults/start.bat"


# ============================================================================
# MENU STRUCTURE (for reference/documentation)
# ============================================================================
# File Menu:
#   - Exit
#
# View Menu:
#   - Theme submenu (System, Dark, Light)
#   - Language submenu (English, Vietnamese)
#
# Help Menu:
#   - About
# ============================================================================
