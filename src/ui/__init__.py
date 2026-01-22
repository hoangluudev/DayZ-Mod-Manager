"""
UI Package - User interface components and views
"""

from shared.ui.icons import Icons
from shared.ui.theme_manager import ThemeManager
from shared.ui.sidebar_widget import SidebarWidget
from shared.ui.config_manager import ConfigChangeManager, ConfigSnapshot
from shared.ui.base import BaseTab, BaseSubTab, BaseDialog, CardWidget, EmptyStateWidget, ObservableMixin
from shared.ui.factories import (
    create_header_layout,
    create_form_section,
    create_action_button,
    create_status_label,
    create_button_row,
    FormBuilder,
)
from shared.ui.highlighters import ModsListHighlighter
from shared.ui.dialogs import ModSortDialog

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
