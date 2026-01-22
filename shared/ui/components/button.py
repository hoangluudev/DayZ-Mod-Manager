"""
Reusable Button Component.
"""

from typing import Optional, Callable
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from shared.ui.theme_manager import ThemeManager


class ReusableButton(QPushButton):
    """
    Reusable button with customizable text, icon, and callback.
    """

    clicked_signal = Signal()

    def __init__(self, text: str = "", icon: Optional[str] = None,
                 callback: Optional[Callable] = None, parent=None):
        super().__init__(text, parent)

        if icon:
            # TODO: Load icon from Icons system
            pass

        if callback:
            self.clicked.connect(callback)

        # Apply theme
        ThemeManager.apply_theme_to_widget(self)
