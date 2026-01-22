"""
UI Dimension Constants
Defines sizes, margins, and spacing used throughout the UI.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SidebarDimensions:
    """Sidebar layout dimensions."""
    
    # Width states
    EXPANDED_WIDTH: int = 220
    COLLAPSED_WIDTH: int = 76
    
    # Item sizing (expanded mode)
    ITEM_HEIGHT: int = 44
    ITEM_SPACING: int = 2
    ICON_SIZE: int = 20
    
    # Item sizing (collapsed mode)
    COLLAPSED_ITEM_HEIGHT: int = 56
    COLLAPSED_ITEM_SPACING: int = 6
    COLLAPSED_ICON_SIZE: int = 22
    COLLAPSED_TILE_WIDTH: int = 56
    COLLAPSED_TILE_RADIUS: int = 14
    
    # Branding/Logo sizing
    LOGO_EXPANDED_MIN: int = 112
    LOGO_EXPANDED_MAX: int = 150
    LOGO_COLLAPSED_MIN: int = 26
    LOGO_COLLAPSED_MAX: int = 44
    
    # Animation
    COLLAPSE_ANIMATION_DURATION: int = 220


@dataclass(frozen=True)
class WindowDimensions:
    """Main window dimensions."""
    
    MIN_WIDTH: int = 1200
    MIN_HEIGHT: int = 800
    DEFAULT_WIDTH: int = 1200
    DEFAULT_HEIGHT: int = 800


@dataclass(frozen=True)
class IconSizes:
    """Standard icon sizes used in the app."""
    
    TINY: int = 12
    SMALL: int = 16
    MEDIUM: int = 20
    LARGE: int = 24
    XLARGE: int = 32
    XXLARGE: int = 48
    
    # Specific use cases
    SIDEBAR_ICON: int = 20
    SIDEBAR_COLLAPSED_ICON: int = 22
    TOOLBAR_ICON: int = 20
    BUTTON_ICON: int = 18
    STATUS_ICON: int = 16
    DIALOG_ICON: int = 48


@dataclass(frozen=True)
class Spacing:
    """Standard spacing values."""
    
    NONE: int = 0
    TINY: int = 2
    SMALL: int = 4
    MEDIUM: int = 8
    LARGE: int = 12
    XLARGE: int = 16
    XXLARGE: int = 24
    
    # Margins
    CONTENT_MARGIN: int = 16
    SECTION_MARGIN: int = 24
    DIALOG_MARGIN: int = 20


@dataclass(frozen=True)
class BorderRadius:
    """Standard border radius values."""
    
    NONE: int = 0
    SMALL: int = 4
    MEDIUM: int = 8
    LARGE: int = 12
    XLARGE: int = 16
    ROUND: int = 9999  # For pill shapes
