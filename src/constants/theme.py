"""
Theme Constants
Defines theme modes, accent colors, and theme-related configuration.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class ThemeMode(str, Enum):
    """
    Application theme modes.
    
    Inherits from str to allow direct comparison with string values.
    """
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"
    
    @classmethod
    def from_string(cls, value: str) -> "ThemeMode":
        """Convert string to ThemeMode, defaulting to DARK."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.DARK


@dataclass(frozen=True)
class ThemeOption:
    """
    Represents a theme option for UI display.
    
    Attributes:
        mode: The theme mode
        translation_key: Key for localized name
        icon: Icon/emoji for the option
    """
    mode: ThemeMode
    translation_key: str
    icon: str


# Theme options for menus/dropdowns
THEME_OPTIONS: List[ThemeOption] = [
    ThemeOption(ThemeMode.SYSTEM, "theme.system", "🖥️"),
    ThemeOption(ThemeMode.DARK, "theme.dark", "🌙"),
    ThemeOption(ThemeMode.LIGHT, "theme.light", "☀️"),
]


# ============================================================================
# ACCENT COLORS
# ============================================================================

DEFAULT_ACCENT_COLOR = "#43a047"  # Default green

@dataclass(frozen=True)
class AccentPreset:
    """Preset accent color."""
    name: str
    color: str
    translation_key: str


# Preset accent colors for quick selection
ACCENT_PRESETS: List[AccentPreset] = [
    AccentPreset("blue", "#0078d4", "accent.blue"),
    AccentPreset("green", "#107c10", "accent.green"),
    AccentPreset("red", "#e81123", "accent.red"),
    AccentPreset("purple", "#881798", "accent.purple"),
    AccentPreset("orange", "#ff8c00", "accent.orange"),
    AccentPreset("teal", "#00b7c3", "accent.teal"),
    AccentPreset("pink", "#e3008c", "accent.pink"),
    AccentPreset("gold", "#ffb900", "accent.gold"),
]


# ============================================================================
# COLOR CONSTANTS
# ============================================================================

class Colors:
    """Common color constants used throughout the app."""
    
    # Background colors (dark theme)
    DARK_BG_PRIMARY = "#1e1e1e"
    DARK_BG_SECONDARY = "#252526"
    DARK_BG_TERTIARY = "#2d2d30"
    DARK_BORDER = "#3e3e42"
    
    # Background colors (light theme)
    LIGHT_BG_PRIMARY = "#ffffff"
    LIGHT_BG_SECONDARY = "#f3f3f3"
    LIGHT_BG_TERTIARY = "#e5e5e5"
    LIGHT_BORDER = "#d1d1d1"
    
    # Text colors
    DARK_TEXT_PRIMARY = "#ffffff"
    DARK_TEXT_SECONDARY = "#cccccc"
    DARK_TEXT_MUTED = "#888888"
    
    LIGHT_TEXT_PRIMARY = "#1e1e1e"
    LIGHT_TEXT_SECONDARY = "#3e3e3e"
    LIGHT_TEXT_MUTED = "#666666"
    
    # Status colors
    SUCCESS = "#4caf50"
    WARNING = "#ff9800"
    ERROR = "#f44336"
    INFO = "#4caf50"
    
    # Overlay colors
    OVERLAY_LIGHT = "rgba(255, 255, 255, 0.06)"
    OVERLAY_DARK = "rgba(0, 0, 0, 0.06)"
