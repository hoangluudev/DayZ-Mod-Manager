"""
Icon Button Widget - A button with an SVG icon that follows theme colors.
"""

import weakref

from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from shared.ui.icons import Icons
from shared.ui.theme_manager import ThemeManager


class IconButton(QPushButton):
    """
    A button with an SVG icon that adapts to theme colors.
    
    Features:
    - Uses theme-aware SVG icons
    - Supports text + icon or icon-only modes
    - Customizable size and colors
    """
    
    def __init__(
        self, 
        icon_name: str = None,
        text: str = "",
        color: str = None,
        size: int = 24,
        icon_only: bool = False,
        object_name: str = None,
        parent=None
    ):
        """
        Initialize IconButton.
        
        Args:
            icon_name: Name of the icon from Icons module
            text: Button text (optional)
            color: Icon color (optional, uses theme color if None)
            size: Icon size in pixels
            icon_only: If True, show only icon without text
            object_name: Qt object name for styling
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._icon_name = icon_name
        self._icon_color = color
        self._icon_size = size

        # Auto-refresh icons when theme/accent changes.
        self_ref = weakref.ref(self)

        def _on_theme_change(_theme: str, _accent: str):
            btn = self_ref()
            if btn is None:
                try:
                    ThemeManager.remove_observer(_on_theme_change)
                except Exception:
                    pass
                return
            btn.refresh_icon()

        ThemeManager.add_observer(_on_theme_change)
        
        if icon_name:
            self.setIcon(Icons.get_icon(icon_name, color, size))
            self.setIconSize(QSize(size, size))
        
        if text and not icon_only:
            self.setText(text)
        
        if icon_only:
            # Let the button size itself but provide sensible minimums
            self.setMinimumSize(size + 4, size + 4)
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # Remove extra padding so icon is vertically centered
            self.setStyleSheet("""
                QPushButton {
                    padding: 0px;
                    border-radius: 3px;
                }
            """)
            # ensure icon rendered at requested size
            self.setIconSize(QSize(size, size))

        # Avoid drawing focus rectangle for small icon buttons used inside tables
        self.setFocusPolicy(Qt.NoFocus)
        
        if object_name:
            self.setObjectName(object_name)
        
        self.setCursor(Qt.PointingHandCursor)
    
    def set_icon(self, icon_name: str, color: str = None):
        """Update the button icon."""
        self._icon_name = icon_name
        self._icon_color = color
        self.setIcon(Icons.get_icon(icon_name, color, self._icon_size))
    
    def refresh_icon(self):
        """Refresh the icon with current theme colors."""
        if self._icon_name:
            self.setIcon(Icons.get_icon(self._icon_name, self._icon_color, self._icon_size))
    
    @property
    def icon_name(self) -> str:
        """Get the current icon name."""
        return self._icon_name
