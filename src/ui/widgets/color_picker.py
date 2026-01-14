"""
Color Picker Widget - Color selection for accent colors.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QColorDialog,
    QFrame, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from src.ui.icons import ACCENT_COLORS


class ColorButton(QPushButton):
    """A colored button for selecting a color."""
    
    clicked_color = Signal(str)
    
    def __init__(self, color: str, name: str = "", size: int = 32, parent=None):
        super().__init__(parent)
        self._color = color
        self._name = name
        
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(name.capitalize() if name else color)
        self._update_style(False)
        
        self.clicked.connect(lambda: self.clicked_color.emit(self._color))
    
    def _update_style(self, selected: bool):
        border = "3px solid white" if selected else "2px solid transparent"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                border: {border};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid rgba(255, 255, 255, 0.5);
            }}
        """)
    
    def set_selected(self, selected: bool):
        self._update_style(selected)
    
    @property
    def color(self) -> str:
        return self._color


class AccentColorSelector(QWidget):
    """
    A widget for selecting an accent color from predefined colors.
    
    Features:
    - Grid of predefined accent colors
    - Shows selected color indicator
    - Emits signal when color changes
    """
    
    color_changed = Signal(str)
    
    def __init__(self, current_color: str = "#0078d4", parent=None):
        super().__init__(parent)
        
        self._current_color = current_color
        self._buttons = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        row = 0
        col = 0
        max_cols = 4
        
        for name, color in ACCENT_COLORS.items():
            btn = ColorButton(color, name, size=36)
            btn.clicked_color.connect(self._on_color_clicked)
            btn.set_selected(color.lower() == self._current_color.lower())
            
            self._buttons.append(btn)
            layout.addWidget(btn, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def _on_color_clicked(self, color: str):
        self._current_color = color
        
        # Update button states
        for btn in self._buttons:
            btn.set_selected(btn.color.lower() == color.lower())
        
        self.color_changed.emit(color)
    
    def get_color(self) -> str:
        return self._current_color
    
    def set_color(self, color: str):
        self._current_color = color
        for btn in self._buttons:
            btn.set_selected(btn.color.lower() == color.lower())


class ColorPicker(QWidget):
    """
    A full color picker with preview and custom color option.
    
    Features:
    - Color preview square
    - Button to open color dialog
    - Emits signal when color changes
    """
    
    color_changed = Signal(str)
    
    def __init__(self, current_color: str = "#0078d4", parent=None):
        super().__init__(parent)
        
        self._color = current_color
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Color preview
        self.preview = QFrame()
        self.preview.setFixedSize(32, 32)
        self.preview.setStyleSheet(f"""
            QFrame {{
                background-color: {self._color};
                border: 1px solid gray;
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.preview)
        
        # Color value label
        self.lbl_value = QLabel(self._color)
        layout.addWidget(self.lbl_value)
        
        layout.addStretch()
        
        # Pick color button
        self.btn_pick = QPushButton("...")
        self.btn_pick.setFixedSize(32, 32)
        self.btn_pick.setCursor(Qt.PointingHandCursor)
        self.btn_pick.clicked.connect(self._pick_color)
        layout.addWidget(self.btn_pick)
    
    def _pick_color(self):
        color = QColorDialog.getColor(
            QColor(self._color),
            self,
            "Select Color"
        )
        
        if color.isValid():
            self._color = color.name()
            self._update_display()
            self.color_changed.emit(self._color)
    
    def _update_display(self):
        self.preview.setStyleSheet(f"""
            QFrame {{
                background-color: {self._color};
                border: 1px solid gray;
                border-radius: 4px;
            }}
        """)
        self.lbl_value.setText(self._color)
    
    def get_color(self) -> str:
        return self._color
    
    def set_color(self, color: str):
        self._color = color
        self._update_display()
