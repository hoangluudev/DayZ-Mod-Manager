"""
Icons Module - Centralized icon management with theme-aware SVG icons.
Provides consistent icons across the application that adapt to theme colors.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QImage
from PySide6.QtCore import Qt, QSize
from PySide6.QtSvg import QSvgRenderer
from typing import Dict, Optional
import io

from src.utils.resources import asset_path
from src.utils.assets import get_app_logo_path


class Icons:
    """
    Centralized icon management with SVG icons that follow text/accent colors.
    Icons are rendered dynamically to match the current theme.
    """
    
    # SVG icon definitions (simple, clean designs)
    _SVG_ICONS: Dict[str, str] = {
        # Navigation icons
        "folder": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>''',
        "puzzle": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M20.5 11H19V7c0-1.1-.9-2-2-2h-4V3.5C13 2.12 11.88 1 10.5 1S8 2.12 8 3.5V5H4c-1.1 0-2 .9-2 2v3.8h1.5c1.38 0 2.5 1.12 2.5 2.5S4.88 15.8 3.5 15.8H2V19c0 1.1.9 2 2 2h3.8v-1.5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5V21H17c1.1 0 2-.9 2-2v-4h1.5c1.38 0 2.5-1.12 2.5-2.5S21.88 11 20.5 11z"/></svg>''',
        "rocket": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 2C9 2 6.5 4.5 6 8c-1.5 0-3 1.5-3 3.5 0 1 .5 2 1 2.5l2 10h12l2-10c.5-.5 1-1.5 1-2.5 0-2-1.5-3.5-3-3.5-.5-3.5-3-6-6-6zm0 3c.5 0 1 .5 1 1s-.5 1-1 1-1-.5-1-1 .5-1 1-1zm-2 3h4v2h-4V8z"/></svg>''',
        "cog": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>''',
        "settings": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z"/></svg>''',
        
        # Action icons
        "plus": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>''',
        "edit": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>''',
        "delete": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>''',
        "trash": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM8 9h8v10H8V9zm7.5-5l-1-1h-5l-1 1H5v2h14V4h-3.5z"/></svg>''',
        "save": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M17 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/></svg>''',
        "refresh": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>''',
        "browse": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V6h5.17l2 2H20v10zm-8-4h2v2h-2v-2zm0-6h2v5h-2V8z"/></svg>''',
        "check": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>''',
        "close": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>''',
        
        # Status icons
        "success": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>''',
        "warning": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>''',
        "error": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>''',
        "info": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>''',
        
        # Theme icons
        "sun": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z"/></svg>''',
        "moon": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M9 2c-1.05 0-2.05.16-3 .46 4.06 1.27 7 5.06 7 9.54 0 4.48-2.94 8.27-7 9.54.95.3 1.95.46 3 .46 5.52 0 10-4.48 10-10S14.52 2 9 2z"/></svg>''',
        
        # Misc icons
        "server": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M20 2H4c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 6H4V4h16v4zm0 4H4c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-4c0-1.1-.9-2-2-2zm0 6H4v-4h16v4zM6 7h2V5H6v2zm0 8h2v-2H6v2z"/></svg>''',
        "play": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M8 5v14l11-7z"/></svg>''',
        "stop": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M6 6h12v12H6z"/></svg>''',
        "palette": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 2C6.49 2 2 6.49 2 12s4.49 10 10 10c1.38 0 2.5-1.12 2.5-2.5 0-.61-.23-1.2-.64-1.67-.08-.1-.13-.21-.13-.33 0-.28.22-.5.5-.5H16c3.31 0 6-2.69 6-6 0-4.96-4.49-9-10-9zm-5.5 9c-.83 0-1.5-.67-1.5-1.5S5.67 8 6.5 8 8 8.67 8 9.5 7.33 11 6.5 11zm3-4C8.67 7 8 6.33 8 5.5S8.67 4 9.5 4s1.5.67 1.5 1.5S10.33 7 9.5 7zm5 0c-.83 0-1.5-.67-1.5-1.5S13.67 4 14.5 4s1.5.67 1.5 1.5S15.33 7 14.5 7zm3 4c-.83 0-1.5-.67-1.5-1.5S16.67 8 17.5 8s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>''',
        "language": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2s.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.91-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2s.07-1.35.16-2h4.68c.09.65.16 1.32.16 2s-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2s-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z"/></svg>''',
        "about": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/></svg>''',
        "restore": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/></svg>''',
        "undo": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12.5 8c-2.65 0-5.05 1-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/></svg>''',
        "arrow_up": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>''',
        "arrow_down": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>''',
        "chevron_left": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>''',
        "chevron_right": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M8.59 16.59 10 18l6-6-6-6-1.41 1.41L13.17 12z"/></svg>''',
        "download": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>''',
        "upload": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>''',
        "copy": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>''',
        "fullscreen": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M7 14H5v5h5v-2H7v-3zm0-4h3V7h3V5H5v5h2zm10 7h-3v2h5v-5h-2v3zm-3-12v2h3v3h2V5h-5z"/></svg>''',
        "fullscreen_exit": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>''',
        "key": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/></svg>''',
        "sort": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z"/></svg>''',
        "search": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>''',
        "filter": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/></svg>''',
        "storage": '''<svg viewBox="0 0 24 24"><path fill="{color}" d="M2 20h20v-4H2v4zm2-3h2v2H4v-2zM2 4v4h20V4H2zm4 3H4V5h2v2zm-4 7h20v-4H2v4zm2-3h2v2H4v-2z"/></svg>''',
    }
    
    # Cache for rendered icons
    _icon_cache: Dict[str, QIcon] = {}
    
    @classmethod
    def get_icon(cls, name: str, color: Optional[str] = None, size: int = 24) -> QIcon:
        """
        Get a QIcon for the given icon name.
        
        Args:
            name: Icon name from the available icons
            color: Color to render the icon (hex or Qt color name). If None, uses text color.
            size: Icon size in pixels
            
        Returns:
            QIcon rendered with the specified color
        """
        if color is None:
            color = cls.get_text_color()
        
        cache_key = f"{name}_{color}_{size}"
        if cache_key in cls._icon_cache:
            return cls._icon_cache[cache_key]
        
        svg_template = cls._SVG_ICONS.get(name)
        if not svg_template:
            return QIcon()
        
        svg_data = svg_template.format(color=color)
        
        # Render SVG to pixmap
        renderer = QSvgRenderer(svg_data.encode('utf-8'))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        icon = QIcon(pixmap)
        cls._icon_cache[cache_key] = icon
        return icon
    
    @classmethod
    def get_pixmap(cls, name: str, color: Optional[str] = None, size: int = 24) -> QPixmap:
        """
        Get a QPixmap for the given icon name.
        
        Args:
            name: Icon name from the available icons
            color: Color to render the icon
            size: Icon size in pixels
            
        Returns:
            QPixmap rendered with the specified color
        """
        if color is None:
            color = cls.get_text_color()
            
        svg_template = cls._SVG_ICONS.get(name)
        if not svg_template:
            return QPixmap()
        
        svg_data = svg_template.format(color=color)
        
        renderer = QSvgRenderer(svg_data.encode('utf-8'))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        return pixmap
    
    @classmethod
    def clear_cache(cls):
        """Clear the icon cache. Call this when theme changes."""
        cls._icon_cache.clear()
    
    @classmethod
    def get_text_color(cls) -> str:
        """Get current text color based on theme."""
        try:
            from src.ui.theme_manager import ThemeManager
            return ThemeManager.get_text_color()
        except Exception:
            return "#e0e0e0"  # Default dark theme text color
    
    @classmethod
    def get_accent_color(cls) -> str:
        """Get current accent color from theme."""
        try:
            from src.ui.theme_manager import ThemeManager
            return ThemeManager.get_accent_color()
        except Exception:
            return "#43a047"  # Default green accent
    
    @classmethod
    def available_icons(cls) -> list:
        """Get list of available icon names."""
        return list(cls._SVG_ICONS.keys())

    @classmethod
    def get_app_logo_path(cls, variant: str = "auto"):
        """Return path to the app logo image.

        variant:
            - 'auto': monochrome on dark theme, color on light theme
            - 'color': force color logo
            - 'mono': force monochrome logo
        """
        # Prefer a configurable filename from settings so swapping is easy.
        return get_app_logo_path()

    @classmethod
    def get_app_logo_pixmap(cls, size: int = 96, variant: str = "auto") -> QPixmap:
        """Load and scale the app logo as a QPixmap.

        On dark themes, the default ('auto') variant is rendered as a monochrome
        mark using the current theme text color so it always matches the theme.
        """
        path = cls.get_app_logo_path(variant=variant)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QPixmap()

        # Resolve variant behavior.
        effective_variant = (variant or "auto").lower()
        if effective_variant == "auto":
            try:
                from src.ui.theme_manager import ThemeManager
                effective_variant = "mono" if ThemeManager.is_dark_theme() else "color"
            except Exception:
                effective_variant = "mono"

        if effective_variant == "mono":
            try:
                from src.ui.theme_manager import ThemeManager
                mono_color = ThemeManager.get_text_color()
            except Exception:
                mono_color = "#e0e0e0"

            img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
            tinted = QImage(img.size(), QImage.Format_ARGB32)
            tinted.fill(Qt.transparent)
            p = QPainter(tinted)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.drawImage(0, 0, img)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(tinted.rect(), QColor(mono_color))
            p.end()
            pixmap = QPixmap.fromImage(tinted)

        if size and size > 0:
            return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pixmap

    @classmethod
    def get_app_icon(cls) -> QIcon:
        """Return the QIcon used for window/taskbar (prefers color logo)."""
        # Cache under a fixed key; Qt will pick best size.
        cache_key = "__app_icon__"
        if cache_key in cls._icon_cache:
            return cls._icon_cache[cache_key]

        pixmap = cls.get_app_logo_pixmap(size=256, variant="color")
        icon = QIcon(pixmap) if not pixmap.isNull() else QIcon()
        cls._icon_cache[cache_key] = icon
        return icon
