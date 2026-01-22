"""
Navigation Constants
Defines sidebar menu items, tab indices, and navigation structure.

This module centralizes all navigation-related constants to make it easy to:
- Add/remove/reorder menu items
- Change icons consistently
- Update translation keys
- Maintain tab index mapping
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional


class TabIndex(IntEnum):
    """
    Tab indices for the main stacked widget.
    
    Use these instead of magic numbers throughout the codebase.
    Order here determines the order in the sidebar.
    """
    PROFILES = 0
    MODS = 1
    CONFIG = 2
    SETTINGS = 3


@dataclass(frozen=True)
class NavigationItem:
    """
    Represents a sidebar navigation item.
    
    Attributes:
        id: Unique identifier matching TabIndex
        icon_name: Icon name from Icons registry (e.g., "folder", "puzzle")
        translation_key: Key for localized text (e.g., "tabs.profiles")
        tooltip_key: Optional separate tooltip translation key
        enabled: Whether the item is enabled by default
    """
    id: TabIndex
    icon_name: str
    translation_key: str
    tooltip_key: Optional[str] = None
    enabled: bool = True
    
    @property
    def index(self) -> int:
        """Get numeric index for stacked widget."""
        return int(self.id)


# ============================================================================
# SIDEBAR MENU ITEMS
# ============================================================================
# To add a new menu item:
# 1. Add a new TabIndex enum value
# 2. Add a NavigationItem here
# 3. Create the corresponding tab widget
# 4. Add translation keys to locale files
# ============================================================================

SIDEBAR_ITEMS: List[NavigationItem] = [
    NavigationItem(
        id=TabIndex.PROFILES,
        icon_name="folder",
        translation_key="tabs.profiles",
        tooltip_key="tabs.profiles_tooltip",
    ),
    NavigationItem(
        id=TabIndex.MODS,
        icon_name="puzzle",
        translation_key="tabs.mods",
        tooltip_key="tabs.mods_tooltip",
    ),
    NavigationItem(
        id=TabIndex.CONFIG,
        icon_name="cog",
        translation_key="tabs.config",
        tooltip_key="tabs.config_tooltip",
    ),
    NavigationItem(
        id=TabIndex.SETTINGS,
        icon_name="settings",
        translation_key="tabs.settings",
        tooltip_key="tabs.settings_tooltip",
    ),
]


def get_sidebar_item(tab_index: TabIndex) -> Optional[NavigationItem]:
    """
    Get NavigationItem by TabIndex.
    
    Args:
        tab_index: The tab index to look up
        
    Returns:
        NavigationItem if found, None otherwise
    """
    for item in SIDEBAR_ITEMS:
        if item.id == tab_index:
            return item
    return None


def get_sidebar_item_by_index(index: int) -> Optional[NavigationItem]:
    """
    Get NavigationItem by numeric index.
    
    Args:
        index: Numeric index (0, 1, 2, ...)
        
    Returns:
        NavigationItem if index is valid, None otherwise
    """
    if 0 <= index < len(SIDEBAR_ITEMS):
        return SIDEBAR_ITEMS[index]
    return None
