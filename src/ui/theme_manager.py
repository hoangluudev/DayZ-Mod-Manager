"""
Theme Manager - Simplified theme management using Theme Packs.
Manages application theming with a scalable, maintainable approach.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from typing import Optional, Callable, List

from src.ui.themes import ThemeRegistry, ThemePack


class ThemeManager:
    """
    Manages application themes using the Theme Pack system.
    
    This is a simplified theme manager that:
    - Uses predefined theme packs instead of customizable colors
    - Removes light/system mode complexity
    - Provides easy theme switching via theme pack IDs
    - Notifies observers when theme changes
    
    Usage:
        # Apply default theme
        ThemeManager.apply_theme()
        
        # Apply specific theme
        ThemeManager.apply_theme("midnight")
        
        # Get current theme info
        theme = ThemeManager.get_current_theme()
    """
    
    _current_theme_id: str = "default"
    _observers: List[Callable[[str, ThemePack], None]] = []
    
    @classmethod
    def apply_theme(cls, theme_id: str = None, app: QApplication = None) -> bool:
        """
        Apply a theme pack to the application.
        
        Args:
            theme_id: Theme pack ID to apply. If None, uses current theme.
            app: QApplication instance. If None, uses current instance.
            
        Returns:
            True if theme was applied successfully, False otherwise.
        """
        if app is None:
            app = QApplication.instance()
        
        if not app:
            return False
        
        # Get theme pack
        if theme_id:
            cls._current_theme_id = theme_id
        
        theme = ThemeRegistry.get(cls._current_theme_id)
        if not theme:
            theme = ThemeRegistry.get_default()
            cls._current_theme_id = theme.id
        
        # Apply stylesheet
        app.setStyleSheet(theme.get_stylesheet())
        
        # Clear icon cache when theme changes
        try:
            from src.ui.icons import Icons
            Icons.clear_cache()
        except Exception:
            pass
        
        # Notify observers
        for observer in cls._observers:
            try:
                observer(cls._current_theme_id, theme)
            except Exception:
                pass
        
        return True
    
    @classmethod
    def get_current_theme_id(cls) -> str:
        """Get the current theme pack ID."""
        return cls._current_theme_id
    
    @classmethod
    def get_current_theme(cls) -> ThemePack:
        """Get the current theme pack."""
        theme = ThemeRegistry.get(cls._current_theme_id)
        return theme if theme else ThemeRegistry.get_default()
    
    @classmethod
    def get_accent_color(cls) -> str:
        """Get the current theme's accent color."""
        return cls.get_current_theme().colors.accent

    @classmethod
    def get_current_accent(cls) -> str:
        """Backward-compatible alias for the current accent color."""
        return cls.get_accent_color()
    
    @classmethod
    def get_text_color(cls) -> str:
        """Get the current theme's primary text color."""
        return cls.get_current_theme().colors.text_primary
    
    @classmethod
    def is_dark_theme(cls) -> bool:
        """Check if current theme is a dark theme."""
        return cls.get_current_theme().is_dark
    
    @classmethod
    def get_available_themes(cls) -> list:
        """
        Get list of available themes for UI dropdowns.
        
        Returns:
            List of (theme_id, theme_name) tuples
        """
        return ThemeRegistry.get_theme_list()
    
    @classmethod
    def add_observer(cls, callback: Callable[[str, ThemePack], None]) -> None:
        """
        Add an observer to be notified when theme changes.
        
        Args:
            callback: Function that takes (theme_id, theme_pack) arguments
        """
        if callback not in cls._observers:
            cls._observers.append(callback)
    
    @classmethod
    def remove_observer(cls, callback: Callable) -> None:
        """Remove a theme change observer."""
        if callback in cls._observers:
            cls._observers.remove(callback)


# Legacy compatibility - these can be removed once all code is updated
def get_dark_stylesheet(accent: str = "#43a047") -> str:
    """Legacy function - returns default theme stylesheet."""
    return ThemeRegistry.get_default().get_stylesheet()


def _lighten_color(hex_color: str, percent: int) -> str:
    """Lighten a hex color by a percentage."""
    color = QColor(hex_color)
    h, s, l, a = color.getHslF()
    l = min(1.0, l + (percent / 100))
    color.setHslF(h, s, l, a)
    return color.name()


def _darken_color(hex_color: str, percent: int) -> str:
    """Darken a hex color by a percentage."""
    color = QColor(hex_color)
    h, s, l, a = color.getHslF()
    l = max(0.0, l - (percent / 100))
    color.setHslF(h, s, l, a)
    return color.name()


def _rgba_color(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba with alpha."""
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"
