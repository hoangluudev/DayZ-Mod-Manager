# DayZ Mod Manager & Server Controller

A comprehensive desktop application for managing DayZ server mods, configurations, and server operations.

## 📁 Project Structure

```
DayzModManager/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── README.md                   # This file
│
├── src/                        # Source code
│   ├── __init__.py
│   │
│   ├── core/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── mod_integrity.py    # Mod verification & installation
│   │   ├── profile_manager.py  # Server profile management
│   │   └── settings_manager.py # App settings persistence
│   │
│   ├── models/                 # Data models
│   │   ├── __init__.py
│   │   └── mod_models.py       # Mod, Profile, Report dataclasses
│   │
│   ├── ui/                     # UI components (PySide6)
│   │   ├── __init__.py
│   │   ├── tabs/               # Tab widgets (to be implemented)
│   │   ├── dialogs/            # Dialog windows
│   │   └── widgets/            # Reusable widgets
│   │
│   └── utils/                  # Utility modules
│       ├── __init__.py
│       └── locale_manager.py   # Multi-language support
│
├── locales/                    # Language files
│   ├── en.json                 # English translations
│   └── vi.json                 # Vietnamese translations
│
├── assets/                     # Static assets
│   ├── icons/                  # Application icons
│   └── themes/                 # Theme stylesheets
│
├── configs/                    # Configuration templates
│   └── settings.json           # App settings (auto-generated)
│   └── defaults/               # Default templates for restore
│       ├── start.bat
│       └── serverDZ.cfg
│
└── profiles/                   # Server profiles (user data)
    └── *.json                  # Individual profile files
```

## 🚀 Features

### Implemented (Boilerplate)

#### ✅ Multi-language System (`src/utils/locale_manager.py`)
- JSON-based locale files
- English and Vietnamese support
- Nested key access (`tr("mods.install")`)
- Placeholder substitution
- Runtime language switching
- Observer pattern for UI updates

#### ✅ Mod Integrity Checker (`src/core/mod_integrity.py`)
- Check mod installation status
- Verify bikey files in server keys folder
- Smart installation (only copy missing components)
- Duplicate mod detection
- Generate integrity reports
- Support for partial installations

#### ✅ Profile Management (`src/core/profile_manager.py`)
- Create/edit/delete server profiles
- JSON persistence
- Path validation

#### ✅ Settings Management (`src/core/settings_manager.py`)
- Theme selection (Dark/Light/System)
- Language preference
- Window state persistence
- Auto-save functionality

### To Be Implemented
- [ ] Workshop browser integration
- [ ] SteamCMD integration
- [ ] Server launcher generation
- [ ] Configuration file editor
- [ ] Spawn rate visual editor
- [ ] Server process management

## 📦 Installation

1. **Clone or download** this project

2. **Create virtual environment** (recommended):
   ```powershell
   cd DayzModManager
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```powershell
   python main.py
   ```

## 🔧 Version Management

Application version is centrally managed in `configs/app.json`. To update version:

1. Edit `configs/app.json` and change the `"version"` field
2. Or use the provided script: `python update_version.py`
3. The version will be automatically reflected throughout the application

Example `configs/app.json`:
```json
{
    "version": "1.0.1",
    "name": "DayZ Mod Manager",
    "description": "DayZ Mod Manager & Server Controller",
    "author": "Your Name",
    "license": "MIT"
}
```

The version is accessible throughout the application:
```python
from src import __version__  # From centralized config
from src.core.app_config import get_version, get_app_name
```

## 🔁 Restore Defaults

- Default server templates live in `configs/defaults/`.
- In the app, open the Settings tab and use:
    - "Restore App Defaults" (resets app settings)
    - "Restore Server Defaults" (overwrites `start.bat` and `serverDZ.cfg` in a selected server folder)

## 🔧 Usage Examples

### Multi-language System

```python
from src.utils.locale_manager import LocaleManager, tr

# Initialize (singleton)
locale = LocaleManager()

# Get translation
text = locale.get("mods.install")  # "Install" or "Cài đặt"

# Switch language
locale.set_language("vi")

# With placeholders
error = locale.get("errors.file_not_found", path="/some/path")

# Shorthand function
from src.utils.locale_manager import tr
button_text = tr("common.save")

# Listen for language changes
def on_language_changed(new_lang):
    update_ui()
locale.add_observer(on_language_changed)
```

### Mod Integrity Checker

```python
from pathlib import Path
from src.core.mod_integrity import ModIntegrityChecker

# Initialize checker
checker = ModIntegrityChecker(
    server_path="C:/DayZServer",
    workshop_path="C:/Steam/steamapps/workshop/content/221100"
)

# Check all installed mods
report = checker.check_all_mods()
print(f"Status: {report.status}")
print(f"Fully installed: {report.fully_installed}")
print(f"Issues: {len(report.issues)}")

# Check specific mod
mod_info = checker.check_mod("@CF")
if mod_info.needs_bikey:
    print(f"{mod_info.name} is missing bikey files")

# Smart install (only copy missing components)
success, actions = checker.smart_install_mod(
    "@CF",
    source_path=Path("C:/Workshop/123456789"),
    copy_bikeys=True
)

# Extract all bikeys from installed mods
count, bikeys = checker.extract_all_bikeys()
print(f"Extracted {count} bikeys")

# Generate text report
text_report = checker.generate_report_text(report)
print(text_report)
```

### Server Profiles

```python
from pathlib import Path
from src.core.profile_manager import ProfileManager

# Initialize manager
manager = ProfileManager()

# Create profile
profile = manager.create_profile("My Server", Path("D:/DayZServer"))
manager.save_profile(profile)

# Get profile
my_profile = manager.get_profile("My Server")

# List all profiles
for profile in manager.get_all_profiles():
    print(f"{profile.name}: {profile.server_path}")
```

## 🌐 Adding New Languages

1. Create a new locale file in `locales/` (e.g., `de.json`)
2. Copy structure from `en.json`
3. Translate all values
4. Add language to `LANGUAGES` dict in `locale_manager.py`
5. Add menu option in `main.py`

## 🎨 Theming

The application supports Dark/Light/System themes. Theme stylesheets can be placed in `assets/themes/`.

## ⚠️ Clean Exit

The application ensures proper cleanup:
- All subprocesses (Server/SteamCMD) are terminated
- File handles are closed
- Settings are saved
- Handles SIGINT/SIGTERM signals

## 📄 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
