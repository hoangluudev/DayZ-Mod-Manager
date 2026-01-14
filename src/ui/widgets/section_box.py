"""
Section Box Widget - A styled group box for organizing settings.
"""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class SectionBox(QGroupBox):
    """
    A styled section box for organizing related content.
    
    Features:
    - Consistent styling across the app
    - Optional collapsible behavior
    - Clean, modern appearance
    """
    
    def __init__(self, title: str = "", parent=None):
        """
        Initialize SectionBox.
        
        Args:
            title: Section title
            parent: Parent widget
        """
        super().__init__(title, parent)
        
        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(12, 16, 12, 12)
        self._content_layout.setSpacing(8)
    
    def add_widget(self, widget: QWidget):
        """Add a widget to the section."""
        self._content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """Add a layout to the section."""
        self._content_layout.addLayout(layout)
    
    def add_stretch(self, stretch: int = 1):
        """Add stretch to the section."""
        self._content_layout.addStretch(stretch)
    
    def content_layout(self):
        """Get the content layout for manual management."""
        return self._content_layout
    
    def set_spacing(self, spacing: int):
        """Set the spacing between items."""
        self._content_layout.setSpacing(spacing)
    
    def set_margins(self, left: int, top: int, right: int, bottom: int):
        """Set content margins."""
        self._content_layout.setContentsMargins(left, top, right, bottom)
