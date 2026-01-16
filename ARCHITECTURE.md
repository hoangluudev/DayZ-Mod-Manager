# Project Architecture

This document describes the refactored project structure following Python/PySide6 best practices.

## Directory Structure

```
DayzModManager/
├── main.py                 # Application entry point
├── package.json            # npm scripts for running/building
├── requirements.txt        # Python dependencies
├── DayzModManager.spec     # PyInstaller build spec
│
├── src/
│   ├── __init__.py
│   │
│   ├── constants/          # Centralized constants
│   │   ├── __init__.py     # Export all constants
│   │   ├── navigation.py   # Sidebar items, tab indices
│   │   ├── theme.py        # Theme modes, colors
│   │   ├── ui.py           # Dimensions, spacing
│   │   ├── app.py          # App defaults, languages
│   │   └── icons.py        # Icon name constants
│   │
│   ├── core/               # Business logic & data
│   │   ├── __init__.py
│   │   ├── app_config.py   # App metadata (version, name)
│   │   ├── settings_manager.py  # User settings persistence
│   │   ├── profile_manager.py   # Server profiles management
│   │   ├── mod_worker.py   # Background mod operations
│   │   ├── mod_integrity.py     # Mod validation
│   │   ├── environment.py  # Dev/prod environment config
│   │   ├── types.py        # Type definitions, protocols
│   │   └── default_restore.py   # Default configs restore
│   │
│   ├── ui/                 # User interface
│   │   ├── __init__.py
│   │   ├── base.py         # Base widget classes
│   │   ├── factories.py    # UI factory functions
│   │   ├── sidebar_widget.py    # Main navigation
│   │   ├── theme_manager.py     # Theme application
│   │   ├── icons.py             # SVG icon rendering
│   │   ├── profiles_tab.py      # Profiles management tab
│   │   ├── mods_tab.py          # Mods management tab
│   │   ├── unified_config_tab.py # Server config tab
│   │   ├── settings_tab.py      # App settings tab
│   │   └── widgets/             # Reusable widgets
│   │       ├── __init__.py
│   │       ├── icon_button.py
│   │       ├── section_box.py
│   │       ├── path_selector.py
│   │       └── color_picker.py
│   │
│   └── utils/              # Utilities
│       ├── __init__.py
│       ├── locale_manager.py    # i18n/translations
│       ├── mod_utils.py         # Mod helper functions
│       ├── assets.py            # Asset path helpers
│       └── resources.py         # Resource utilities
│
├── configs/                # Configuration files
│   ├── app.json           # App metadata
│   ├── settings.json      # User settings
│   └── defaults/          # Default server files
│
├── locales/               # Translation files
│   ├── en.json
│   └── vi.json
│
├── profiles/              # User server profiles
│
└── assets/                # Static assets
    ├── icons/
    └── themes/
```

## Key Concepts

### 1. Constants Module (`src/constants/`)

All magic numbers, strings, and configuration values are centralized:

```python
from src.constants import (
    SIDEBAR_ITEMS,      # Menu items definition
    TabIndex,           # Tab index enum
    SidebarDimensions,  # UI dimensions
    ThemeMode,          # Theme options
    APP_DEFAULTS,       # Default values
    IconNames,          # Icon name constants
)

# Adding a new menu item:
# 1. Add TabIndex enum value in navigation.py
# 2. Add NavigationItem in SIDEBAR_ITEMS
# 3. Create the tab widget
# 4. Add to stack in main.py
```

### 2. Navigation Registry

Menu items are defined declaratively:

```python
# src/constants/navigation.py
SIDEBAR_ITEMS = [
    NavigationItem(
        id=TabIndex.PROFILES,
        icon_name="folder",
        translation_key="tabs.profiles",
    ),
    # Add more items here...
]
```

### 3. Base Classes (`src/ui/base.py`)

Common functionality for tabs:

```python
from src.ui.base import BaseTab, BaseSubTab, CardWidget, EmptyStateWidget

class MyTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent, scrollable=True, title_key="my.title")
        self._setup_content()
    
    def _setup_content(self):
        # Add header buttons
        btn = create_action_button("plus", text="Add", on_click=self._add_item)
        self.add_header_button(btn)
        
        # Add content
        self.add_widget(my_widget)
    
    def update_texts(self):
        super().update_texts()
        # Update tab-specific translations
```

### 4. UI Factories (`src/ui/factories.py`)

Factory functions to reduce boilerplate:

```python
from src.ui.factories import (
    create_action_button,
    create_status_label,
    create_form_section,
    FormBuilder,
)

# Create action button with icon
btn = create_action_button("save", text="Save", on_click=self._save)

# Create status label
status = create_status_label("Success!", "success")

# Build forms declaratively
form = FormBuilder()
form.add_row("Name:", self.name_input)
form.add_row("Path:", self.path_selector)
section = form.build("My Section")
```

### 5. Mod Utilities (`src/utils/mod_utils.py`)

Helper functions for mod operations:

```python
from src.utils.mod_utils import (
    format_file_size,
    scan_workshop_mods,
    scan_installed_mods,
    find_mod_bikeys,
)

# Scan workshop for mods
mods = scan_workshop_mods(workshop_path, server_path)

# Format file size
size_str = format_file_size(1234567)  # "1.2 MB"
```

### 6. Background Workers (`src/core/mod_worker.py`)

Long-running operations in background threads:

```python
from src.core.mod_worker import ModWorker

worker = ModWorker(
    operation="add",  # or "remove", "update"
    server_path=server,
    workshop_path=workshop,
    mods=[(workshop_id, mod_folder), ...],
)
worker.progress.connect(self._on_progress)
worker.finished.connect(self._on_finished)
worker.start()
```

## Design Patterns

### Observer Pattern

Use `ObservableMixin` for components that need to notify listeners:

```python
from src.ui.base import ObservableMixin

class MyClass(ObservableMixin):
    def __init__(self):
        self._init_observable()
    
    def do_something(self):
        self._notify_observers("event_name", data)
```

### Factory Pattern

Use factory functions for creating consistent UI components:

```python
# Instead of:
btn = QPushButton("Save")
btn.setIcon(Icons.get_icon("save"))
btn.clicked.connect(self._save)

# Use:
btn = create_action_button("save", text="Save", on_click=self._save)
```

### Card Pattern

Use `CardWidget` for clickable content cards:

```python
from src.ui.base import CardWidget

class MyCard(CardWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent, clickable=True)
        # self.card_layout is available for adding content
        self.card_layout.addWidget(QLabel(data.name))
        
        # Handle clicks
        self.clicked.connect(self._on_click)
```

## Adding New Features

### Adding a New Tab

1. Create enum value in `src/constants/navigation.py`:
   ```python
   class TabIndex(IntEnum):
       # ...existing...
       MY_TAB = 4
   ```

2. Add to SIDEBAR_ITEMS:
   ```python
   NavigationItem(
       id=TabIndex.MY_TAB,
       icon_name="my_icon",
       translation_key="tabs.my_tab",
   ),
   ```

3. Create tab widget extending `BaseTab`:
   ```python
   # src/ui/my_tab.py
   class MyTab(BaseTab):
       def __init__(self, parent=None):
           super().__init__(parent, title_key="my_tab.title")
           self._setup_content()
   ```

4. Add to stack in `main.py`:
   ```python
   self.my_tab = MyTab()
   self.stack.addWidget(self.my_tab)
   ```

### Adding New Settings

1. Add field to settings dataclass in `settings_manager.py`
2. Add UI controls in `settings_tab.py`
3. Connect signals to save on change

## Code Style

- Use type hints for function parameters and returns
- Use dataclasses for data structures
- Use enums for fixed sets of values
- Prefer composition over inheritance
- Keep files under 500 lines; split if larger
- Use factory functions for UI creation
- Centralize all constants in `src/constants/`
