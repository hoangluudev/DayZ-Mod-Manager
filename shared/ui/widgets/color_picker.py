"""
Color Picker Widget - Generic color selection widget.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QColorDialog,
    QFrame
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor


class ColorPicker(QWidget):
    """
    A full color picker with preview and custom color option.
    
    Features:
    - Color preview square
    - Button to open color dialog
    - Emits signal when color changes
    """
    
    color_changed = Signal(str)
    
    def __init__(self, current_color: str = "#43a047", parent=None):
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
