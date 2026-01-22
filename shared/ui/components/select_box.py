"""
Reusable Select Box (ComboBox) Component.
"""

from typing import List, Dict, Any, Optional, Callable
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Signal

from shared.ui.theme_manager import ThemeManager


class ReusableSelectBox(QComboBox):
    """
    Reusable select box with customizable options and callback.
    """

    selection_changed = Signal(str, Any)  # key, value

    def __init__(self, options: List[Dict[str, Any]], default_key: Optional[str] = None,
                 callback: Optional[Callable[[str, Any], None]] = None, parent=None):
        super().__init__(parent)

        self.options = options
        self._setup_options()

        if default_key:
            self.set_current_by_key(default_key)

        if callback:
            self.currentIndexChanged.connect(self._on_selection_changed)

        # Apply theme
        ThemeManager.apply_theme_to_widget(self)

    def _setup_options(self):
        """Setup combo box options."""
        for option in self.options:
            text = option.get('text', '')
            key = option.get('key', text)
            value = option.get('value', key)
            self.addItem(text, (key, value))

    def _on_selection_changed(self, index: int):
        """Handle selection change."""
        if 0 <= index < len(self.options):
            key, value = self.itemData(index)
            self.selection_changed.emit(key, value)

    def set_current_by_key(self, key: str):
        """Set current selection by key."""
        for i in range(self.count()):
            item_key, _ = self.itemData(i)
            if item_key == key:
                self.setCurrentIndex(i)
                break

    def get_current_key(self) -> Optional[str]:
        """Get current selected key."""
        index = self.currentIndex()
        if index >= 0:
            key, _ = self.itemData(index)
            return key
        return None

    def get_current_value(self) -> Any:
        """Get current selected value."""
        index = self.currentIndex()
        if index >= 0:
            _, value = self.itemData(index)
            return value
        return None
