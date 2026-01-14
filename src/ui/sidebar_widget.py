"""
Sidebar Navigation Widget - Vortex-style sidebar navigation
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QFrame, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon

from src.ui.icons import Icons
from src.ui.theme_manager import ThemeManager


class SidebarWidget(QWidget):
    """Vortex-style sidebar navigation widget."""
    
    item_selected = Signal(int)  # Emits index of selected item
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        # Icon size used for sidebar items (width, height)
        # Reverted to original small size for menu icons
        self._sidebar_icon_size = 20
        # Logo size in pixels (used for app branding in the sidebar header)
        # This should be slightly smaller than the sidebar width minus header margins
        self._logo_size = 164
        self._items = []  # Store item data (icon_name, text)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # App branding header (logo beside app title)
        self.header = QFrame()
        self.header.setObjectName("sidebarHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(8)

        # Logo on the left (scaled to fill most of the header width)
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedSize(self._logo_size, self._logo_size)
        self.logo_label.setPixmap(Icons.get_app_logo_pixmap(size=self._logo_size, variant="auto"))
        header_layout.addWidget(self.logo_label)

        # Title column on the right
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)

        self.app_title = QLabel("DayZ")
        self.app_title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        self.app_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_col.addWidget(self.app_title)

        self.app_subtitle = QLabel("Mod Manager")
        self.app_subtitle.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 11px;")
        self.app_subtitle.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title_col.addWidget(self.app_subtitle)

        header_layout.addLayout(title_col, stretch=1)

        layout.addWidget(self.header)

        # Keep the logo updated when the theme changes.
        try:
            ThemeManager.add_observer(lambda *_: self._refresh_logo())
        except Exception:
            pass
        
        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("sidebar")
        self.nav_list.setSpacing(2)
        self.nav_list.setFocusPolicy(Qt.NoFocus)
        # Keep sidebar menu icons at the original small size
        self.nav_list.setIconSize(QSize(self._sidebar_icon_size, self._sidebar_icon_size))
        self.nav_list.currentRowChanged.connect(self._on_row_changed)
        
        layout.addWidget(self.nav_list, stretch=1)
        
        # Footer
        self.footer = QLabel()
        self.footer.setStyleSheet("color: #666; font-size: 10px; padding: 8px 16px;")
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)
    
    def add_item(self, icon_name: str, text: str):
        """Add a navigation item with SVG icon."""
        item = QListWidgetItem(text)
        # Keep the original item height for menu items
        item.setSizeHint(QSize(0, 44))

        # Set icon from Icons module (small menu icon)
        icon = Icons.get_icon(icon_name, size=self._sidebar_icon_size)
        item.setIcon(icon)
        
        font = QFont()
        font.setPointSize(11)
        item.setFont(font)
        item.setTextAlignment(Qt.AlignVCenter)
        
        self.nav_list.addItem(item)
        self._items.append((icon_name, text))
    
    def set_current_index(self, index: int):
        """Set the current selected index."""
        self.nav_list.setCurrentRow(index)
    
    def get_current_index(self) -> int:
        """Get current selected index."""
        return self.nav_list.currentRow()
    
    def update_item_text(self, index: int, icon_name: str, text: str):
        """Update text and icon of an item at index."""
        item = self.nav_list.item(index)
        if item:
            item.setText(text)
            icon = Icons.get_icon(icon_name, size=self._sidebar_icon_size)
            item.setIcon(icon)
            
            # Update stored data
            if index < len(self._items):
                self._items[index] = (icon_name, text)
    
    def refresh_icons(self):
        """Refresh all icons (call after theme change)."""
        for i, (icon_name, text) in enumerate(self._items):
            item = self.nav_list.item(i)
            if item:
                icon = Icons.get_icon(icon_name, size=self._sidebar_icon_size)
                item.setIcon(icon)

        self._refresh_logo()

    def _refresh_logo(self):
        try:
            self.logo_label.setPixmap(Icons.get_app_logo_pixmap(size=self._logo_size, variant="auto"))
        except Exception:
            pass
    
    def set_footer_text(self, text: str):
        """Set footer text (e.g., version info)."""
        self.footer.setText(text)
    
    def _on_row_changed(self, row: int):
        """Handle row selection change."""
        if row >= 0:
            self.item_selected.emit(row)
