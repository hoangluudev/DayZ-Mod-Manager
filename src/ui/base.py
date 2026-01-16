"""
Base Widget Classes
Common base classes for UI widgets with shared functionality.
"""

from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QPushButton, QMessageBox
)
from PySide6.QtCore import Signal, Qt

from src.utils.locale_manager import tr


class BaseTab(QWidget):
    """
    Base class for main content tabs.
    
    Provides:
    - Consistent layout structure with header
    - Language update handling
    - Optional scroll area
    - Status signals
    - Common dialog helpers
    """
    
    # Common signals
    status_message = Signal(str)  # For status bar updates
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        scrollable: bool = True,
        title_key: Optional[str] = None,
    ):
        super().__init__(parent)
        self._scrollable = scrollable
        self._title_key = title_key
        self._header_buttons: List[QWidget] = []
        self._setup_base_layout()
    
    def _setup_base_layout(self) -> None:
        """Setup the base layout structure."""
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(16, 16, 16, 16)
        self._outer_layout.setSpacing(12)
        
        # Header with title and action buttons
        self._header_layout = QHBoxLayout()
        self._header_layout.setSpacing(8)
        
        self._title_label = QLabel()
        if self._title_key:
            self._title_label.setText(f"<h2>{tr(self._title_key)}</h2>")
        self._header_layout.addWidget(self._title_label)
        self._header_layout.addStretch()
        
        # Placeholder for header buttons (added by subclasses)
        self._header_buttons_layout = QHBoxLayout()
        self._header_buttons_layout.setSpacing(8)
        self._header_layout.addLayout(self._header_buttons_layout)
        
        self._outer_layout.addLayout(self._header_layout)
        
        if self._scrollable:
            # Create scroll area for content
            self._scroll_area = QScrollArea()
            self._scroll_area.setWidgetResizable(True)
            self._scroll_area.setFrameShape(QFrame.NoFrame)
            
            # Content container inside scroll area
            self._content_widget = QWidget()
            self._content_layout = QVBoxLayout(self._content_widget)
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            self._content_layout.setSpacing(12)
            
            self._scroll_area.setWidget(self._content_widget)
            self._outer_layout.addWidget(self._scroll_area, stretch=1)
        else:
            # Direct content layout
            self._content_layout = QVBoxLayout()
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            self._content_layout.setSpacing(12)
            self._outer_layout.addLayout(self._content_layout, stretch=1)
    
    @property
    def content_layout(self) -> QVBoxLayout:
        """Get the content layout for adding widgets."""
        return self._content_layout
    
    @property
    def header_layout(self) -> QHBoxLayout:
        """Get the header layout."""
        return self._header_layout
    
    def set_title(self, text: str) -> None:
        """Set the tab title."""
        self._title_label.setText(f"<h2>{text}</h2>")
    
    def add_header_button(self, button: QWidget) -> None:
        """Add a button to the header area."""
        self._header_buttons_layout.addWidget(button)
        self._header_buttons.append(button)
    
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget, stretch)
    
    def add_layout(self, layout, stretch: int = 0) -> None:
        """Add a layout to the content area."""
        self._content_layout.addLayout(layout, stretch)
    
    def add_stretch(self, stretch: int = 1) -> None:
        """Add stretch to the content area."""
        self._content_layout.addStretch(stretch)
    
    def clear_content(self) -> None:
        """Clear all widgets from content area."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
    
    def _clear_layout(self, layout) -> None:
        """Recursively clear a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
    
    def update_texts(self) -> None:
        """
        Update all UI texts for language change.
        
        Subclasses should override this to update all translatable strings.
        """
        if self._title_key:
            self._title_label.setText(f"<h2>{tr(self._title_key)}</h2>")
    
    def set_status(self, message: str) -> None:
        """Emit a status message."""
        self.status_message.emit(message)
    
    # =========================================================================
    # Dialog Helpers
    # =========================================================================
    
    def confirm_dialog(
        self,
        message: str,
        title: Optional[str] = None,
    ) -> bool:
        """
        Show a confirmation dialog.
        
        Returns:
            True if user clicked Yes, False otherwise
        """
        reply = QMessageBox.question(
            self,
            title or tr("common.confirm"),
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes
    
    def info_dialog(self, message: str, title: Optional[str] = None) -> None:
        """Show an information dialog."""
        QMessageBox.information(
            self,
            title or tr("common.info"),
            message
        )
    
    def error_dialog(self, message: str, title: Optional[str] = None) -> None:
        """Show an error dialog."""
        QMessageBox.critical(
            self,
            title or tr("common.error"),
            message
        )
    
    def warning_dialog(self, message: str, title: Optional[str] = None) -> None:
        """Show a warning dialog."""
        QMessageBox.warning(
            self,
            title or tr("common.warning"),
            message
        )


class BaseSubTab(QWidget):
    """
    Base class for sub-tabs within a tab widget.
    
    Lighter weight than BaseTab, no header/scroll by default.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_layout()
    
    def _setup_layout(self) -> None:
        """Setup the base layout."""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(16)
    
    @property
    def layout(self) -> QVBoxLayout:
        """Get the main layout."""
        return self._layout
    
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Add a widget."""
        self._layout.addWidget(widget, stretch)
    
    def add_stretch(self, stretch: int = 1) -> None:
        """Add stretch."""
        self._layout.addStretch(stretch)
    
    def update_texts(self) -> None:
        """Update all UI texts for language change."""
        pass


class BaseDialog:
    """
    Mixin for dialog classes with common functionality.
    
    Provides:
    - Consistent result handling
    - Language update support
    """
    
    def update_texts(self) -> None:
        """Update all UI texts for language change."""
        pass
    
    def get_result(self):
        """
        Get the dialog result data.
        
        Returns:
            Dictionary with result data, or None if cancelled
        """
        return None


class ObservableMixin:
    """
    Mixin class providing observer pattern functionality.
    
    Usage:
        class MyClass(ObservableMixin):
            def __init__(self):
                super().__init__()
                self._init_observable()
            
            def some_action(self):
                self._notify_observers("action_happened", data)
    """
    
    def _init_observable(self) -> None:
        """Initialize the observer list."""
        self._observers: list = []
    
    def add_observer(self, callback: Callable) -> None:
        """Add an observer callback."""
        if callback not in self._observers:
            self._observers.append(callback)
    
    def remove_observer(self, callback: Callable) -> None:
        """Remove an observer callback."""
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self, *args, **kwargs) -> None:
        """Notify all observers."""
        for observer in self._observers:
            try:
                observer(*args, **kwargs)
            except Exception as e:
                print(f"Error notifying observer: {e}")


class CardWidget(QFrame):
    """
    Base class for card-style widgets.
    
    Provides consistent styling and click behavior.
    """
    
    clicked = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None, clickable: bool = True):
        super().__init__(parent)
        self._clickable = clickable
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
    
    @property
    def card_layout(self) -> QVBoxLayout:
        """Get the card's layout."""
        return self._layout
    
    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class EmptyStateWidget(QWidget):
    """
    Widget shown when a list/container is empty.
    """
    
    action_clicked = Signal()
    
    def __init__(
        self,
        message: str,
        icon_name: Optional[str] = None,
        action_text: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._message = message
        self._icon_name = icon_name
        self._action_text = action_text
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)
        
        # Icon (if provided)
        if self._icon_name:
            from src.ui.icons import Icons
            icon_label = QLabel()
            icon_label.setPixmap(Icons.get_pixmap(self._icon_name, size=48, color="#666"))
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
        
        # Message
        self._label = QLabel(self._message)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: gray; font-size: 14px;")
        layout.addWidget(self._label)
        
        # Action button (if provided)
        if self._action_text:
            self._action_btn = QPushButton(self._action_text)
            self._action_btn.clicked.connect(self.action_clicked.emit)
            layout.addWidget(self._action_btn, alignment=Qt.AlignCenter)
    
    def set_message(self, message: str) -> None:
        """Update the message text."""
        self._message = message
        self._label.setText(message)
    
    def set_action_text(self, text: str) -> None:
        """Update the action button text."""
        if hasattr(self, '_action_btn'):
            self._action_text = text
            self._action_btn.setText(text)
