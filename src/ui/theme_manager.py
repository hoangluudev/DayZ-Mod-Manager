"""
Theme Manager - Dark/Light/System theme support with accent color customization
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, Signal, QObject

from src.ui.icons import ACCENT_COLORS


def get_dark_stylesheet(accent: str = "#0078d4") -> str:
    """Generate dark theme stylesheet with custom accent color."""
    accent_hover = _lighten_color(accent, 15)
    accent_light = _rgba_color(accent, 0.1)
    accent_border = _rgba_color(accent, 0.3)
    
    return f"""
/* Main Window */
QMainWindow {{
    background-color: #1e1e1e;
}}

/* Central Widget */
QWidget {{
    background-color: #1e1e1e;
    color: #e0e0e0;
}}

/* Prevent solid blocks under text */
QLabel, QAbstractButton, QCheckBox, QRadioButton {{
    background-color: transparent;
}}

QFrame {{
    background-color: transparent;
}}

/* Sidebar Navigation */
QListWidget#sidebar {{
    background-color: #252526;
    border: none;
    border-right: 1px solid #3c3c3c;
    padding: 8px 0;
    font-size: 13px;
}}

QListWidget#sidebar::item {{
    padding: 12px 20px;
    border-radius: 0;
    margin: 2px 0;
    color: #b0b0b0;
}}

QListWidget#sidebar::item:hover {{
    background-color: #2d2d30;
    color: #ffffff;
}}

QListWidget#sidebar::item:selected {{
    background-color: {accent_light};
    color: #ffffff;
    border-left: 3px solid {accent};
}}

/* Group Boxes */
QGroupBox {{
    font-weight: bold;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: #252526;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    color: {accent};
}}

/* Buttons */
QPushButton {{
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 16px;
    color: #e0e0e0;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #4a4a4a;
    border-color: {accent};
}}

QPushButton:pressed {{
    background-color: {accent_light};
}}

QPushButton:disabled {{
    background-color: #2d2d2d;
    color: #666666;
}}

QPushButton#primary {{
    background-color: {accent};
    border-color: {accent};
    color: white;
}}

QPushButton#primary:hover {{
    background-color: {accent_hover};
}}

QPushButton#danger {{
    background-color: #c42b1c;
    border-color: #c42b1c;
    color: white;
}}

QPushButton#danger:hover {{
    background-color: #e74c3c;
}}

/* Tables */
QTableWidget {{
    background-color: #1e1e1e;
    alternate-background-color: #252526;
    gridline-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    selection-background-color: {accent_light};
}}

QTableWidget::item {{
    padding: 4px 8px;
    color: #e0e0e0;
}}

QTableWidget::item:selected {{
    background-color: {accent_light};
}}

QHeaderView::section {{
    background-color: #2d2d30;
    color: #e0e0e0;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #3c3c3c;
    border-right: 1px solid #3c3c3c;
    font-weight: bold;
}}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
    selection-background-color: {accent_light};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {accent};
}}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: #2d2d2d;
    color: #666666;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: #3c3c3c;
    border: 1px solid #555555;
    selection-background-color: {accent_light};
}}

/* Checkboxes */
QCheckBox {{
    spacing: 8px;
    color: #e0e0e0;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #555555;
    background-color: #3c3c3c;
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

QCheckBox::indicator:hover {{
    border-color: {accent};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background-color: #1e1e1e;
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #555555;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #666666;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: #1e1e1e;
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: #555555;
    border-radius: 4px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #666666;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Progress Bar */
QProgressBar {{
    background-color: #3c3c3c;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 4px;
}}

/* Tabs (sub-tabs) */
QTabWidget::pane {{
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    background-color: #252526;
}}

QTabBar::tab {{
    background-color: #2d2d30;
    border: 1px solid #3c3c3c;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #b0b0b0;
}}

QTabBar::tab:selected {{
    background-color: #252526;
    color: #ffffff;
    border-bottom: 2px solid {accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: #3c3c3c;
}}

/* Splitter */
QSplitter::handle {{
    background-color: #3c3c3c;
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {accent};
    color: white;
    padding: 4px;
}}

/* Menu Bar */
QMenuBar {{
    background-color: #2d2d30;
    color: #e0e0e0;
    border-bottom: 1px solid #3c3c3c;
}}

QMenuBar::item {{
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {accent_light};
}}

QMenu {{
    background-color: #2d2d30;
    border: 1px solid #3c3c3c;
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 20px;
    color: #e0e0e0;
}}

QMenu::item:selected {{
    background-color: {accent_light};
}}

QMenu::separator {{
    height: 1px;
    background-color: #3c3c3c;
    margin: 4px 10px;
}}

/* Labels */
QLabel {{
    color: #e0e0e0;
}}

QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}}

QLabel#subtitle {{
    font-size: 12px;
    color: #888888;
}}

/* Message Boxes */
QMessageBox {{
    background-color: #2d2d30;
}}

/* Tool Tips */
QToolTip {{
    background-color: #2d2d30;
    color: #e0e0e0;
    border: 1px solid #555555;
    padding: 4px 8px;
}}

/* Profile Bar */
QFrame#profileBar {{
    background-color: {accent_light};
    border-bottom: 1px solid {accent_border};
}}

/* Sidebar Header */
QFrame#sidebarHeader {{
    background-color: {accent};
    padding: 16px;
}}

/* Profile Card */
ProfileCard {{
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 8px;
    padding: 10px;
}}

ProfileCard:hover {{
    background-color: #454545;
    border-color: {accent};
}}
"""


def get_light_stylesheet(accent: str = "#1967d2") -> str:
    """Generate light theme stylesheet with custom accent color."""
    accent_hover = _darken_color(accent, 10)
    accent_light = _rgba_color(accent, 0.08)
    accent_border = _rgba_color(accent, 0.2)
    
    return f"""
/* Main Window */
QMainWindow {{
    background-color: #fafafa;
}}

/* Central Widget - Remove background for text clarity */
QWidget {{
    background-color: transparent;
    color: #1a1a1a;
}}

/* Specific container backgrounds */
QMainWindow > QWidget {{
    background-color: #fafafa;
}}

/* Sidebar Navigation */
QListWidget#sidebar {{
    background-color: #ffffff;
    border: none;
    border-right: 1px solid #e5e5e5;
    padding: 8px 0;
    font-size: 13px;
}}

QListWidget#sidebar::item {{
    padding: 12px 20px;
    border-radius: 0;
    margin: 2px 0;
    color: #333333;
    background-color: transparent;
}}

QListWidget#sidebar::item:hover {{
    background-color: #f5f5f5;
    color: #1a1a1a;
}}

QListWidget#sidebar::item:selected {{
    background-color: {accent_light};
    color: {accent};
    border-left: 3px solid {accent};
}}

/* Group Boxes - Clean background */
QGroupBox {{
    font-weight: bold;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: #ffffff;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    color: {accent};
    background-color: #ffffff;
}}

/* Buttons */
QPushButton {{
    background-color: #ffffff;
    border: 1px solid #d5d5d5;
    border-radius: 4px;
    padding: 6px 16px;
    color: #1a1a1a;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #f5f5f5;
    border-color: {accent};
}}

QPushButton:pressed {{
    background-color: {accent_light};
}}

QPushButton:disabled {{
    background-color: #f0f0f0;
    color: #999999;
    border-color: #e0e0e0;
}}

QPushButton#primary {{
    background-color: {accent};
    border-color: {accent};
    color: white;
}}

QPushButton#primary:hover {{
    background-color: {accent_hover};
}}

QPushButton#danger {{
    background-color: #d93025;
    border-color: #d93025;
    color: white;
}}

QPushButton#danger:hover {{
    background-color: #ea4335;
}}

/* Tables - Clear text contrast */
QTableWidget {{
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    gridline-color: #e5e5e5;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    selection-background-color: {accent_light};
}}

QTableWidget::item {{
    padding: 4px 8px;
    color: #1a1a1a;
    background-color: transparent;
}}

QTableWidget::item:selected {{
    background-color: {accent_light};
    color: {accent};
}}

QHeaderView::section {{
    background-color: #f5f5f5;
    color: #1a1a1a;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #e5e5e5;
    border-right: 1px solid #e5e5e5;
    font-weight: bold;
}}

/* Input Fields - Proper contrast */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: #ffffff;
    border: 1px solid #d5d5d5;
    border-radius: 4px;
    padding: 6px 10px;
    color: #1a1a1a;
    selection-background-color: {accent_light};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {accent};
}}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: #f5f5f5;
    color: #888888;
    border-color: #e0e0e0;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: #ffffff;
    border: 1px solid #d5d5d5;
    selection-background-color: {accent_light};
    color: #1a1a1a;
}}

/* Checkboxes - Clear text */
QCheckBox {{
    spacing: 8px;
    color: #1a1a1a;
    background-color: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #d5d5d5;
    background-color: #ffffff;
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

QCheckBox::indicator:hover {{
    border-color: {accent};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background-color: #f5f5f5;
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #c0c0c0;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #a0a0a0;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: #f5f5f5;
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: #c0c0c0;
    border-radius: 4px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #a0a0a0;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Progress Bar */
QProgressBar {{
    background-color: #e0e0e0;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 4px;
}}

/* Tabs (sub-tabs) - Clean backgrounds */
QTabWidget::pane {{
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    background-color: #ffffff;
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar::tab {{
    background-color: #f5f5f5;
    border: 1px solid #e5e5e5;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #333333;
}}

QTabBar::tab:selected {{
    background-color: #ffffff;
    color: {accent};
    border-bottom: 2px solid {accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: #eeeeee;
    color: #1a1a1a;
}}

/* Splitter */
QSplitter::handle {{
    background-color: #e0e0e0;
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {accent};
    color: white;
    padding: 4px;
}}

/* Menu Bar */
QMenuBar {{
    background-color: #ffffff;
    color: #1e1e1e;
    border-bottom: 1px solid #e0e0e0;
}}

QMenuBar::item {{
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {accent_light};
}}

QMenu {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 20px;
    color: #1e1e1e;
}}

QMenu::item:selected {{
    background-color: {accent_light};
}}

QMenu::separator {{
    height: 1px;
    background-color: #e0e0e0;
    margin: 4px 10px;
}}

/* Labels - Clear text with transparent background */
QLabel {{
    color: #1a1a1a;
    background-color: transparent;
}}

QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: #1a1a1a;
}}

QLabel#subtitle {{
    font-size: 12px;
    color: #555555;
}}

/* Form Labels */
QFormLayout QLabel {{
    color: #1a1a1a;
    background-color: transparent;
}}

/* Message Boxes */
QMessageBox {{
    background-color: #ffffff;
}}

/* Tool Tips */
QToolTip {{
    background-color: #ffffff;
    color: #1e1e1e;
    border: 1px solid #d0d0d0;
    padding: 4px 8px;
}}

/* Profile Bar */
QFrame#profileBar {{
    background-color: {accent_light};
    border-bottom: 1px solid {accent_border};
}}

/* Sidebar Header */
QFrame#sidebarHeader {{
    background-color: {accent};
    padding: 16px;
}}

/* Profile Card - Clear styling */
ProfileCard {{
    background-color: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    padding: 10px;
}}

ProfileCard:hover {{
    background-color: #fafafa;
    border-color: {accent};
}}

/* Scroll Areas - Transparent content */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* List Widgets - Clear styling */
QListWidget {{
    background-color: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    color: #1a1a1a;
}}

QListWidget::item {{
    padding: 8px;
    color: #1a1a1a;
    background-color: transparent;
}}

QListWidget::item:selected {{
    background-color: {accent_light};
    color: {accent};
}}

QListWidget::item:hover:!selected {{
    background-color: #f5f5f5;
}}

/* Specific frame backgrounds */
QFrame {{
    background-color: transparent;
}}

QFrame#profileBar {{
    background-color: {accent_light};
    border-bottom: 1px solid {accent_border};
}}

QFrame#sidebarHeader {{
    background-color: {accent};
    padding: 16px;
}}
"""


def _lighten_color(hex_color: str, percent: int) -> str:
    """Lighten a hex color by a percentage."""
    color = QColor(hex_color)
    h, s, l, a = color.getHslF()
    l = min(1.0, l + (percent / 100))
    color.setHslF(h, s, l, a)
    return color.name()


def _darken_color(hex_color: str, percent: int) -> str:
    """Darken a hex color by a percentage."""
    color = QColor(hex_color)
    h, s, l, a = color.getHslF()
    l = max(0.0, l - (percent / 100))
    color.setHslF(h, s, l, a)
    return color.name()


def _rgba_color(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba with alpha."""
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


class ThemeManager:
    """Manages application themes (Dark/Light/System) with accent colors."""
    
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"
    
    _current_theme = DARK
    _current_accent = "#0078d4"
    _observers = []
    
    @classmethod
    def apply_theme(cls, theme: str = None, accent: str = None, app: QApplication = None):
        """Apply a theme to the application."""
        if app is None:
            app = QApplication.instance()
        
        if not app:
            return
        
        if theme:
            cls._current_theme = theme
        if accent:
            cls._current_accent = accent
        
        effective_theme = cls._current_theme
        
        if effective_theme == cls.SYSTEM:
            # Detect system theme (Windows)
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                effective_theme = cls.LIGHT if value else cls.DARK
            except Exception:
                effective_theme = cls.DARK
        
        if effective_theme == cls.DARK:
            app.setStyleSheet(get_dark_stylesheet(cls._current_accent))
        else:
            app.setStyleSheet(get_light_stylesheet(cls._current_accent))
        
        # Clear icon cache when theme changes
        try:
            from src.ui.icons import Icons
            Icons.clear_cache()
        except:
            pass
        
        # Notify observers
        for observer in cls._observers:
            try:
                observer(cls._current_theme, cls._current_accent)
            except:
                pass
    
    @classmethod
    def get_current_theme(cls) -> str:
        """Get the current theme setting."""
        return cls._current_theme
    
    @classmethod
    def get_current_accent(cls) -> str:
        """Get the current accent color."""
        return cls._current_accent
    
    @classmethod
    def set_accent_color(cls, accent: str, app: QApplication = None):
        """Set and apply a new accent color."""
        cls._current_accent = accent
        cls.apply_theme(app=app)
    
    @classmethod
    def toggle_theme(cls, app: QApplication = None):
        """Toggle between dark and light themes."""
        if cls._current_theme == cls.DARK:
            cls.apply_theme(cls.LIGHT, app=app)
        else:
            cls.apply_theme(cls.DARK, app=app)
    
    @classmethod
    def is_dark_theme(cls) -> bool:
        """Check if current theme is dark."""
        if cls._current_theme == cls.SYSTEM:
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return not value
            except:
                return True
        return cls._current_theme == cls.DARK
    
    @classmethod
    def add_observer(cls, callback):
        """Add an observer to be notified when theme changes."""
        cls._observers.append(callback)
    
    @classmethod
    def remove_observer(cls, callback):
        """Remove a theme change observer."""
        if callback in cls._observers:
            cls._observers.remove(callback)
