"""
Theme Manager - Dark/Light/System theme support
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


DARK_STYLESHEET = """
/* Main Window */
QMainWindow {
    background-color: #1e1e1e;
}

/* Central Widget */
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
}

/* Sidebar Navigation */
QListWidget#sidebar {
    background-color: #252526;
    border: none;
    border-right: 1px solid #3c3c3c;
    padding: 8px 0;
    font-size: 13px;
}

QListWidget#sidebar::item {
    padding: 12px 20px;
    border-radius: 0;
    margin: 2px 0;
    color: #b0b0b0;
}

QListWidget#sidebar::item:hover {
    background-color: #2d2d30;
    color: #ffffff;
}

QListWidget#sidebar::item:selected {
    background-color: #094771;
    color: #ffffff;
    border-left: 3px solid #0078d4;
}

/* Group Boxes */
QGroupBox {
    font-weight: bold;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: #252526;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    color: #0078d4;
}

/* Buttons */
QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 16px;
    color: #e0e0e0;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #4a4a4a;
    border-color: #0078d4;
}

QPushButton:pressed {
    background-color: #094771;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #666666;
}

QPushButton#primary {
    background-color: #0078d4;
    border-color: #0078d4;
    color: white;
}

QPushButton#primary:hover {
    background-color: #1e90ff;
}

QPushButton#danger {
    background-color: #c42b1c;
    border-color: #c42b1c;
    color: white;
}

QPushButton#danger:hover {
    background-color: #e74c3c;
}

/* Tables */
QTableWidget {
    background-color: #1e1e1e;
    alternate-background-color: #252526;
    gridline-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    selection-background-color: #094771;
}

QTableWidget::item {
    padding: 4px 8px;
    color: #e0e0e0;
}

QTableWidget::item:selected {
    background-color: #094771;
}

QHeaderView::section {
    background-color: #2d2d30;
    color: #e0e0e0;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #3c3c3c;
    border-right: 1px solid #3c3c3c;
    font-weight: bold;
}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
    selection-background-color: #094771;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #0078d4;
}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background-color: #2d2d2d;
    color: #666666;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #e0e0e0;
}

QComboBox QAbstractItemView {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    selection-background-color: #094771;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #e0e0e0;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #555555;
    background-color: #3c3c3c;
}

QCheckBox::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}

QCheckBox::indicator:hover {
    border-color: #0078d4;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #666666;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #555555;
    border-radius: 4px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #666666;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Progress Bar */
QProgressBar {
    background-color: #3c3c3c;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 4px;
}

/* Tabs (sub-tabs) */
QTabWidget::pane {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    background-color: #252526;
}

QTabBar::tab {
    background-color: #2d2d30;
    border: 1px solid #3c3c3c;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #b0b0b0;
}

QTabBar::tab:selected {
    background-color: #252526;
    color: #ffffff;
    border-bottom: 2px solid #0078d4;
}

QTabBar::tab:hover:!selected {
    background-color: #3c3c3c;
}

/* Splitter */
QSplitter::handle {
    background-color: #3c3c3c;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* Status Bar */
QStatusBar {
    background-color: #007acc;
    color: white;
    padding: 4px;
}

/* Menu Bar */
QMenuBar {
    background-color: #2d2d30;
    color: #e0e0e0;
    border-bottom: 1px solid #3c3c3c;
}

QMenuBar::item {
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #094771;
}

QMenu {
    background-color: #2d2d30;
    border: 1px solid #3c3c3c;
    padding: 4px 0;
}

QMenu::item {
    padding: 6px 20px;
    color: #e0e0e0;
}

QMenu::item:selected {
    background-color: #094771;
}

QMenu::separator {
    height: 1px;
    background-color: #3c3c3c;
    margin: 4px 10px;
}

/* Labels */
QLabel {
    color: #e0e0e0;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#subtitle {
    font-size: 12px;
    color: #888888;
}

/* Message Boxes */
QMessageBox {
    background-color: #2d2d30;
}

/* Tool Tips */
QToolTip {
    background-color: #2d2d30;
    color: #e0e0e0;
    border: 1px solid #555555;
    padding: 4px 8px;
}
"""


LIGHT_STYLESHEET = """
/* Main Window */
QMainWindow {
    background-color: #f5f5f5;
}

/* Central Widget */
QWidget {
    background-color: #f5f5f5;
    color: #1e1e1e;
}

/* Sidebar Navigation */
QListWidget#sidebar {
    background-color: #ffffff;
    border: none;
    border-right: 1px solid #e0e0e0;
    padding: 8px 0;
    font-size: 13px;
}

QListWidget#sidebar::item {
    padding: 12px 20px;
    border-radius: 0;
    margin: 2px 0;
    color: #555555;
}

QListWidget#sidebar::item:hover {
    background-color: #f0f0f0;
    color: #1e1e1e;
}

QListWidget#sidebar::item:selected {
    background-color: #e8f0fe;
    color: #1967d2;
    border-left: 3px solid #1967d2;
}

/* Group Boxes */
QGroupBox {
    font-weight: bold;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    color: #1967d2;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 6px 16px;
    color: #1e1e1e;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #f0f0f0;
    border-color: #1967d2;
}

QPushButton:pressed {
    background-color: #e8f0fe;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    color: #999999;
}

QPushButton#primary {
    background-color: #1967d2;
    border-color: #1967d2;
    color: white;
}

QPushButton#primary:hover {
    background-color: #1a73e8;
}

QPushButton#danger {
    background-color: #d93025;
    border-color: #d93025;
    color: white;
}

QPushButton#danger:hover {
    background-color: #ea4335;
}

/* Tables */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    gridline-color: #e0e0e0;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    selection-background-color: #e8f0fe;
}

QTableWidget::item {
    padding: 4px 8px;
    color: #1e1e1e;
}

QTableWidget::item:selected {
    background-color: #e8f0fe;
    color: #1967d2;
}

QHeaderView::section {
    background-color: #fafafa;
    color: #1e1e1e;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    border-right: 1px solid #e0e0e0;
    font-weight: bold;
}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 6px 10px;
    color: #1e1e1e;
    selection-background-color: #e8f0fe;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #1967d2;
}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background-color: #f5f5f5;
    color: #999999;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #666666;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    selection-background-color: #e8f0fe;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #1e1e1e;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #d0d0d0;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #1967d2;
    border-color: #1967d2;
}

QCheckBox::indicator:hover {
    border-color: #1967d2;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #f5f5f5;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #f5f5f5;
    height: 12px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #c0c0c0;
    border-radius: 4px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a0a0a0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Progress Bar */
QProgressBar {
    background-color: #e0e0e0;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #1967d2;
    border-radius: 4px;
}

/* Tabs (sub-tabs) */
QTabWidget::pane {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #fafafa;
    border: 1px solid #e0e0e0;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #555555;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1967d2;
    border-bottom: 2px solid #1967d2;
}

QTabBar::tab:hover:!selected {
    background-color: #f0f0f0;
}

/* Splitter */
QSplitter::handle {
    background-color: #e0e0e0;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* Status Bar */
QStatusBar {
    background-color: #1967d2;
    color: white;
    padding: 4px;
}

/* Menu Bar */
QMenuBar {
    background-color: #ffffff;
    color: #1e1e1e;
    border-bottom: 1px solid #e0e0e0;
}

QMenuBar::item {
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #e8f0fe;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    padding: 4px 0;
}

QMenu::item {
    padding: 6px 20px;
    color: #1e1e1e;
}

QMenu::item:selected {
    background-color: #e8f0fe;
}

QMenu::separator {
    height: 1px;
    background-color: #e0e0e0;
    margin: 4px 10px;
}

/* Labels */
QLabel {
    color: #1e1e1e;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #1e1e1e;
}

QLabel#subtitle {
    font-size: 12px;
    color: #666666;
}

/* Message Boxes */
QMessageBox {
    background-color: #ffffff;
}

/* Tool Tips */
QToolTip {
    background-color: #ffffff;
    color: #1e1e1e;
    border: 1px solid #d0d0d0;
    padding: 4px 8px;
}
"""


class ThemeManager:
    """Manages application themes (Dark/Light/System)."""
    
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"
    
    _current_theme = SYSTEM
    
    @classmethod
    def apply_theme(cls, theme: str, app: QApplication = None):
        """Apply a theme to the application."""
        if app is None:
            app = QApplication.instance()
        
        if not app:
            return
        
        cls._current_theme = theme
        
        if theme == cls.SYSTEM:
            # Detect system theme (Windows)
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                theme = cls.LIGHT if value else cls.DARK
            except Exception:
                theme = cls.DARK  # Default to dark if detection fails
        
        if theme == cls.DARK:
            app.setStyleSheet(DARK_STYLESHEET)
        else:
            app.setStyleSheet(LIGHT_STYLESHEET)
    
    @classmethod
    def get_current_theme(cls) -> str:
        """Get the current theme setting."""
        return cls._current_theme
    
    @classmethod
    def toggle_theme(cls, app: QApplication = None):
        """Toggle between dark and light themes."""
        if cls._current_theme == cls.DARK:
            cls.apply_theme(cls.LIGHT, app)
        else:
            cls.apply_theme(cls.DARK, app)
