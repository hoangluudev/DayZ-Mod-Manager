"""
Theme Pack System
CurseForge-style theme packs for scalable theming.
Each theme is a self-contained pack with all colors and styles defined.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


@dataclass
class ThemeColors:
    """Color definitions for a theme."""
    # Base colors
    background: str = "#1e1e1e"
    background_secondary: str = "#252526"
    background_tertiary: str = "#2d2d30"
    surface: str = "#3c3c3c"
    
    # Text colors
    text_primary: str = "#e0e0e0"
    text_secondary: str = "#b0b0b0"
    text_muted: str = "#888888"
    text_disabled: str = "#666666"
    
    # Accent/Brand color
    accent: str = "#43a047"  # Green
    accent_hover: str = "#4caf50"
    accent_light: str = "rgba(67, 160, 71, 0.1)"
    accent_border: str = "rgba(67, 160, 71, 0.3)"
    
    # Borders
    border: str = "#3c3c3c"
    border_light: str = "#555555"
    
    # Status colors
    success: str = "#4caf50"
    warning: str = "#ff9800"
    error: str = "#f44336"
    info: str = "#4caf50"
    
    # Special
    danger: str = "#c42b1c"
    danger_hover: str = "#e74c3c"


@dataclass
class ThemePack:
    """
    A complete theme pack definition.
    
    Theme packs are self-contained and include all styling information.
    This makes it easy to add new themes without modifying core code.
    """
    id: str                          # Unique identifier (e.g., "default", "midnight")
    name: str                        # Display name (e.g., "Default", "Midnight Blue")
    description: str = ""            # Optional description
    colors: ThemeColors = field(default_factory=ThemeColors)
    is_dark: bool = True             # For system integration hints
    
    def get_stylesheet(self) -> str:
        """Generate the complete QSS stylesheet for this theme."""
        c = self.colors
        
        return f"""
/* ==================== MAIN WINDOW ==================== */
QMainWindow {{
    background-color: {c.background};
}}

/* ==================== BASE WIDGET ==================== */
QWidget {{
    background-color: {c.background};
    color: {c.text_primary};
}}

/* Prevent solid blocks under text */
QLabel, QAbstractButton, QCheckBox, QRadioButton {{
    background-color: transparent;
}}

QFrame {{
    background-color: transparent;
}}

/* ==================== SIDEBAR NAVIGATION ==================== */
QListWidget#sidebar {{
    background-color: {c.background_secondary};
    border: none;
    border-right: 1px solid {c.border};
    padding: 10px 0;
    font-size: 13px;
}}

QPushButton#sidebarCollapseBtn {{
    background-color: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 10px;
    padding: 8px;
}}

QPushButton#sidebarCollapseBtn:hover {{
    background-color: rgba(255, 255, 255, 0.20);
    border-color: rgba(255, 255, 255, 0.34);
}}

QListWidget#sidebar::item {{
    padding: 12px 16px;
    margin: 4px 10px;
    border-radius: 10px;
    color: {c.text_secondary};
}}

QListWidget#sidebar::item:hover {{
    background-color: rgba(255, 255, 255, 0.06);
    color: #ffffff;
}}

QListWidget#sidebar::item:selected {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                stop: 0 {c.accent_light},
                                stop: 1 rgba(255, 255, 255, 0.04));
    color: #ffffff;
    border-left: 3px solid {c.accent};
}}

/* ==================== THEME SELECTOR (CARDS) ==================== */
QFrame#themeCard {{
    background-color: {c.background_secondary};
    border: 1px solid {c.border};
    border-radius: 12px;
}}

QFrame#themeCard:hover {{
    background-color: {c.background_tertiary};
    border-color: {c.accent_border};
}}

QFrame#themeCard[selected="true"] {{
    border: 2px solid {c.accent};
}}

QLabel#themeCardName {{
    color: {c.text_primary};
    font-weight: 600;
}}

QLabel#themeCardDesc {{
    color: {c.text_muted};
}}

QLabel#themeCardBadge {{
    color: {c.text_primary};
}}

QLabel#themeCheck {{
    background-color: rgba(0, 0, 0, 0.0);
}}

QFrame#themeCardPreview {{
    background-color: {c.background_tertiary};
    border: 1px solid {c.border_light};
    border-radius: 12px;
}}

QFrame#themeCardSkeleton {{
    background-color: {c.surface};
    border-radius: 6px;
}}

/* ==================== GROUP BOXES ==================== */
QGroupBox {{
    font-weight: bold;
    border: 1px solid {c.border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: {c.background_secondary};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    color: {c.accent};
}}

/* ==================== BUTTONS ==================== */
QPushButton {{
    background-color: {c.surface};
    border: 1px solid {c.border_light};
    border-radius: 4px;
    padding: 6px 16px;
    color: {c.text_primary};
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #4a4a4a;
    border-color: {c.accent};
}}

QPushButton:pressed {{
    background-color: {c.accent_light};
}}

QPushButton:disabled {{
    background-color: {c.background_tertiary};
    color: {c.text_disabled};
}}

QPushButton#primary {{
    background-color: {c.accent};
    border-color: {c.accent};
    color: white;
}}

QPushButton#primary:hover {{
    background-color: {c.accent_hover};
}}

QPushButton#danger {{
    background-color: {c.danger};
    border-color: {c.danger};
    color: white;
}}

QPushButton#danger:hover {{
    background-color: {c.danger_hover};
}}

/* ==================== TABLES ==================== */
QTableWidget {{
    background-color: {c.background};
    alternate-background-color: {c.background_secondary};
    gridline-color: {c.border};
    border: 1px solid {c.border};
    border-radius: 4px;
    selection-background-color: {c.accent_light};
}}

QTableWidget::item {{
    padding: 4px 8px;
    color: {c.text_primary};
}}

QTableWidget::item:selected {{
    background-color: {c.accent_light};
}}

QHeaderView::section {{
    background-color: {c.background_tertiary};
    color: {c.text_primary};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {c.border};
    border-right: 1px solid {c.border};
    font-weight: bold;
}}

/* ==================== INPUT FIELDS ==================== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: {c.surface};
    border: 1px solid {c.border_light};
    border-radius: 4px;
    padding: 6px 10px;
    color: {c.text_primary};
    selection-background-color: {c.accent_light};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {c.accent};
}}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: {c.background_tertiary};
    color: {c.text_disabled};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.surface};
    border: 1px solid {c.border_light};
    selection-background-color: {c.accent_light};
}}

/* ==================== CHECKBOXES ==================== */
QCheckBox {{
    spacing: 8px;
    color: {c.text_primary};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {c.border_light};
    background-color: {c.surface};
}}

QCheckBox::indicator:checked {{
    background-color: {c.accent};
    border-color: {c.accent};
}}

QCheckBox::indicator:hover {{
    border-color: {c.accent};
}}

/* ==================== SCROLLBARS ==================== */
QScrollBar:vertical {{
    background-color: {c.background};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {c.border_light};
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
    background-color: {c.background};
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {c.border_light};
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

/* ==================== PROGRESS BAR ==================== */
QProgressBar {{
    background-color: {c.surface};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {c.accent};
    border-radius: 4px;
}}

/* ==================== TABS ==================== */
QTabWidget::pane {{
    border: 1px solid {c.border};
    border-radius: 4px;
    background-color: {c.background_secondary};
}}

QTabBar::tab {{
    background-color: {c.background_tertiary};
    border: 1px solid {c.border};
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: {c.text_secondary};
}}

QTabBar::tab:selected {{
    background-color: {c.background_secondary};
    color: #ffffff;
    border-bottom: 2px solid {c.accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: {c.surface};
}}

/* ==================== SPLITTER ==================== */
QSplitter::handle {{
    background-color: {c.border};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* ==================== STATUS BAR ==================== */
QStatusBar {{
    background-color: {c.accent};
    color: white;
    padding: 4px;
}}

/* ==================== MENU BAR ==================== */
QMenuBar {{
    background-color: {c.background_tertiary};
    color: {c.text_primary};
    border-bottom: 1px solid {c.border};
}}

QMenuBar::item {{
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {c.accent_light};
}}

QMenu {{
    background-color: {c.background_tertiary};
    border: 1px solid {c.border};
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 20px;
    color: {c.text_primary};
}}

QMenu::item:selected {{
    background-color: {c.accent_light};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c.border};
    margin: 4px 10px;
}}

/* ==================== LABELS ==================== */
QLabel {{
    color: {c.text_primary};
}}

QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}}

QLabel#subtitle {{
    font-size: 12px;
    color: {c.text_muted};
}}

/* ==================== MESSAGE BOXES ==================== */
QMessageBox {{
    background-color: {c.background_tertiary};
}}

/* ==================== TOOLTIPS ==================== */
QToolTip {{
    background-color: {c.background_tertiary};
    color: {c.text_primary};
    border: 1px solid {c.border_light};
    padding: 4px 8px;
}}

/* ==================== SPECIAL FRAMES ==================== */
QFrame#profileBar {{
    background-color: {c.accent_light};
    border-bottom: 1px solid {c.accent_border};
}}

QFrame#sidebarHeader {{
    background-color: transparent;
    border-bottom: 1px solid rgba(0, 0, 0, 0.25);
}}

QFrame#sidebarLogoBadge {{
    background: qradialgradient(cx: 0.3, cy: 0.2, radius: 1.2,
                                stop: 0 rgba(255, 255, 255, 0.18),
                                stop: 1 rgba(255, 255, 255, 0.08));
    border: 1px solid rgba(255, 255, 255, 0.26);
    border-radius: 18px;
}}

QLabel#sidebarLogo {{
    background-color: transparent;
}}

/* ==================== PROFILE CARD ==================== */
ProfileCard {{
    background-color: {c.surface};
    border: 1px solid {c.border_light};
    border-radius: 8px;
    padding: 10px;
}}

ProfileCard:hover {{
    background-color: #454545;
    border-color: {c.accent};
}}

/* ==================== LIST WIDGETS ==================== */
QListWidget {{
    background-color: {c.background};
    border: 1px solid {c.border};
    border-radius: 4px;
    color: {c.text_primary};
}}

QListWidget::item {{
    padding: 8px;
    color: {c.text_primary};
    background-color: transparent;
}}

QListWidget::item:selected {{
    background-color: {c.accent_light};
}}

QListWidget::item:hover:!selected {{
    background-color: rgba(255, 255, 255, 0.06);
}}

/* ==================== SCROLL AREAS ==================== */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
"""


class ThemeRegistry:
    """
    Registry of all available theme packs.
    
    To add a new theme:
    1. Create a ThemePack instance with unique id
    2. Register it using ThemeRegistry.register()
    """
    
    _themes: Dict[str, ThemePack] = {}
    _default_theme_id: str = "default"
    
    @classmethod
    def register(cls, theme: ThemePack) -> None:
        """Register a new theme pack."""
        cls._themes[theme.id] = theme
    
    @classmethod
    def get(cls, theme_id: str) -> Optional[ThemePack]:
        """Get a theme pack by ID."""
        return cls._themes.get(theme_id)
    
    @classmethod
    def get_default(cls) -> ThemePack:
        """Get the default theme pack."""
        return cls._themes.get(cls._default_theme_id, _create_default_theme())
    
    @classmethod
    def get_all(cls) -> Dict[str, ThemePack]:
        """Get all registered themes."""
        return cls._themes.copy()
    
    @classmethod
    def get_theme_list(cls) -> list:
        """Get list of (id, name) tuples for UI dropdowns."""
        return [(t.id, t.name) for t in cls._themes.values()]
    
    @classmethod
    def set_default(cls, theme_id: str) -> None:
        """Set the default theme ID."""
        if theme_id in cls._themes:
            cls._default_theme_id = theme_id


def _create_default_theme() -> ThemePack:
    """Create the default dark green theme."""
    return ThemePack(
        id="default",
        name="Default",
        description="Dark theme with green accent - inspired by CurseForge",
        colors=ThemeColors(
            # Base dark colors
            background="#1e1e1e",
            background_secondary="#252526",
            background_tertiary="#2d2d30",
            surface="#3c3c3c",
            
            # Text
            text_primary="#e0e0e0",
            text_secondary="#b0b0b0",
            text_muted="#888888",
            text_disabled="#666666",
            
            # Green accent (main brand color)
            accent="#43a047",
            accent_hover="#4caf50",
            accent_light="rgba(67, 160, 71, 0.1)",
            accent_border="rgba(67, 160, 71, 0.3)",
            
            # Borders
            border="#3c3c3c",
            border_light="#555555",
            
            # Status
            success="#4caf50",
            warning="#ff9800",
            error="#f44336",
            info="#4caf50",
            
            # Danger
            danger="#c42b1c",
            danger_hover="#e74c3c",
        ),
        is_dark=True
    )


# Register built-in themes
ThemeRegistry.register(_create_default_theme())


# Future themes can be added like this:
# ThemeRegistry.register(ThemePack(
#     id="midnight",
#     name="Midnight Blue",
#     description="Dark theme with blue accent",
#     colors=ThemeColors(
#         accent="#1976d2",
#         accent_hover="#2196f3",
#         ...
#     )
# ))
