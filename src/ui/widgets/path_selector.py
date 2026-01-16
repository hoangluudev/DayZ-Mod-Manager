"""
Path Selector Widget - A text field with browse button for path selection.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QLabel, QFileDialog
)
from PySide6.QtCore import Signal

from src.ui.widgets.icon_button import IconButton
from src.utils.locale_manager import tr


class PathSelector(QWidget):
    """
    A path selector widget with text display and browse button.
    
    Features:
    - Shows current path (truncated if needed)
    - Browse button with folder icon
    - Emits signal when path changes
    """
    
    path_changed = Signal(str)
    
    def __init__(
        self, 
        label: str = "",
        path: str = "",
        placeholder: str = None,
        file_mode: bool = False,
        file_filter: str = "",
        parent=None
    ):
        """
        Initialize PathSelector.
        
        Args:
            label: Label text (optional)
            path: Initial path
            placeholder: Placeholder text when empty
            file_mode: If True, select files instead of folders
            file_filter: File filter for file mode (e.g., "Text Files (*.txt)")
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._path = path
        self._file_mode = file_mode
        self._file_filter = file_filter
        self._placeholder = placeholder or tr("settings.not_set")
        
        self._setup_ui()
        self._update_display()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Path display label
        self.lbl_path = QLabel()
        self.lbl_path.setStyleSheet("color: gray;")
        self.lbl_path.setWordWrap(False)
        layout.addWidget(self.lbl_path, stretch=1)
        
        # Browse button
        self.btn_browse = IconButton(
            icon_name="browse",
            text=tr("common.browse"),
            size=16
        )
        self.btn_browse.clicked.connect(self._browse)
        layout.addWidget(self.btn_browse)
    
    def _update_display(self):
        """Update the path display."""
        if self._path:
            # Truncate long paths
            display_path = self._path
            if len(display_path) > 50:
                display_path = "..." + display_path[-47:]
            self.lbl_path.setText(display_path)
            self.lbl_path.setToolTip(self._path)
            # Clear local styling so the global theme stylesheet applies.
            self.lbl_path.setStyleSheet("")
        else:
            self.lbl_path.setText(self._placeholder)
            self.lbl_path.setToolTip("")
            self.lbl_path.setStyleSheet("color: gray;")
    
    def _browse(self):
        """Open folder/file browser dialog."""
        if self._file_mode:
            path, _ = QFileDialog.getOpenFileName(
                self,
                tr("common.select"),
                self._path or "",
                self._file_filter
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                tr("common.select"),
                self._path or ""
            )
        
        if path:
            self._path = path
            self._update_display()
            self.path_changed.emit(path)
    
    def get_path(self) -> str:
        """Get the current path."""
        return self._path
    
    def set_path(self, path: str):
        """Set the path."""
        self._path = path
        self._update_display()
    
    def set_enabled(self, enabled: bool):
        """Enable or disable the widget."""
        self.btn_browse.setEnabled(enabled)
        self.lbl_path.setEnabled(enabled)
    
    def set_placeholder(self, text: str):
        """Set placeholder text."""
        self._placeholder = text
        self._update_display()
