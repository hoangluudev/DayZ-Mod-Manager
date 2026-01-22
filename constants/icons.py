"""
Icons Constants
Defines icon names and mappings for consistent icon usage.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class IconNames:
    """
    Centralized icon name constants.
    
    Use these instead of raw strings to prevent typos
    and enable IDE autocompletion.
    """
    # Navigation
    FOLDER = "folder"
    PUZZLE = "puzzle"
    ROCKET = "rocket"
    COG = "cog"
    SETTINGS = "settings"
    
    # Actions
    PLUS = "plus"
    EDIT = "edit"
    DELETE = "delete"
    TRASH = "trash"
    SAVE = "save"
    REFRESH = "refresh"
    BROWSE = "browse"
    CHECK = "check"
    CLOSE = "close"
    COPY = "copy"
    
    # Status
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    
    # Theme
    SUN = "sun"
    MOON = "moon"
    
    # Chevrons
    CHEVRON_LEFT = "chevron_left"
    CHEVRON_RIGHT = "chevron_right"
    CHEVRON_DOWN = "chevron_down"
    CHEVRON_UP = "chevron_up"
    
    # Server/Game
    PLAY = "play"
    STOP = "stop"
    SERVER = "server"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    
    # Files
    FILE = "file"
    FILE_CODE = "file_code"
    LINK = "link"
    EXTERNAL_LINK = "external_link"
    KEY = "key"


# Mapping of menu items to their icons
MENU_ICONS: Dict[str, str] = {
    "profiles": IconNames.FOLDER,
    "mods": IconNames.PUZZLE,
    "config": IconNames.COG,
    "settings": IconNames.SETTINGS,
    "launcher": IconNames.ROCKET,
}


# Default accent colors for theme customization
ACCENT_COLOR_PRESETS: List[Dict[str, str]] = [
    {"name": "blue", "color": "#0078d4"},
    {"name": "green", "color": "#107c10"},
    {"name": "red", "color": "#e81123"},
    {"name": "purple", "color": "#881798"},
    {"name": "orange", "color": "#ff8c00"},
    {"name": "teal", "color": "#00b7c3"},
    {"name": "pink", "color": "#e3008c"},
    {"name": "gold", "color": "#ffb900"},
]
