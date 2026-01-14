"""
UI Package - User interface components and views
"""

from src.ui.icons import Icons, ACCENT_COLORS
from src.ui.theme_manager import ThemeManager
from src.ui.sidebar_widget import SidebarWidget
from src.ui.config_manager import ConfigChangeManager, ConfigSnapshot

__all__ = [
    'Icons',
    'ACCENT_COLORS',
    'ThemeManager',
    'SidebarWidget',
    'ConfigChangeManager',
    'ConfigSnapshot',
]
