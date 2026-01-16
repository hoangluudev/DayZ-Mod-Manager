"""
UI Package - User interface components and views
"""

from src.ui.icons import Icons
from src.ui.theme_manager import ThemeManager
from src.ui.sidebar_widget import SidebarWidget
from src.ui.config_manager import ConfigChangeManager, ConfigSnapshot
from src.ui.base import BaseTab, BaseSubTab, BaseDialog, CardWidget, EmptyStateWidget, ObservableMixin
from src.ui.factories import (
    create_header_layout,
    create_form_section,
    create_action_button,
    create_status_label,
    create_button_row,
    FormBuilder,
)
from src.ui.highlighters import ModsListHighlighter
from src.ui.dialogs import ModSortDialog

__all__ = [
    # Icons and theme
    'Icons',
    'ThemeManager',
    
    # Core widgets
    'SidebarWidget',
    'ConfigChangeManager',
    'ConfigSnapshot',
    
    # Base classes
    'BaseTab',
    'BaseSubTab',
    'BaseDialog',
    'CardWidget',
    'EmptyStateWidget',
    'ObservableMixin',
    
    # Factories
    'create_header_layout',
    'create_form_section',
    'create_action_button',
    'create_status_label',
    'create_button_row',
    'FormBuilder',
    
    # Highlighters
    'ModsListHighlighter',
    
    # Dialogs
    'ModSortDialog',
]
