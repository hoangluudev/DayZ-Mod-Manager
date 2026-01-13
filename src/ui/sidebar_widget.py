"""
Sidebar Navigation Widget - Vortex-style sidebar navigation
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class SidebarWidget(QWidget):
    """Vortex-style sidebar navigation widget."""
    
    item_selected = Signal(int)  # Emits index of selected item
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # App branding header
        self.header = QFrame()
        self.header.setObjectName("sidebarHeader")
        self.header.setStyleSheet("""
            QFrame#sidebarHeader {
                background-color: #0d47a1;
                padding: 16px;
            }
        """)
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(16, 16, 16, 16)
        
        self.app_title = QLabel("DayZ")
        self.app_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        header_layout.addWidget(self.app_title)
        
        self.app_subtitle = QLabel("Mod Manager")
        self.app_subtitle.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        header_layout.addWidget(self.app_subtitle)
        
        layout.addWidget(self.header)
        
        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("sidebar")
        self.nav_list.setSpacing(2)
        self.nav_list.setFocusPolicy(Qt.NoFocus)
        self.nav_list.currentRowChanged.connect(self._on_row_changed)
        
        layout.addWidget(self.nav_list, stretch=1)
        
        # Footer
        self.footer = QLabel()
        self.footer.setStyleSheet("color: #666; font-size: 10px; padding: 8px 16px;")
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)
    
    def add_item(self, icon: str, text: str):
        """Add a navigation item."""
        item = QListWidgetItem(f"{icon}  {text}")
        item.setSizeHint(item.sizeHint())
        font = QFont()
        font.setPointSize(11)
        item.setFont(font)
        self.nav_list.addItem(item)
    
    def set_current_index(self, index: int):
        """Set the current selected index."""
        self.nav_list.setCurrentRow(index)
    
    def get_current_index(self) -> int:
        """Get current selected index."""
        return self.nav_list.currentRow()
    
    def update_item_text(self, index: int, icon: str, text: str):
        """Update text of an item at index."""
        item = self.nav_list.item(index)
        if item:
            item.setText(f"{icon}  {text}")
    
    def set_footer_text(self, text: str):
        """Set footer text (e.g., version info)."""
        self.footer.setText(text)
    
    def _on_row_changed(self, row: int):
        """Handle row selection change."""
        if row >= 0:
            self.item_selected.emit(row)
