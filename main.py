"""
DayZ Mod Manager & Server Controller
Main Application Entry Point
"""

import sys
import signal
import atexit
from pathlib import Path
from typing import List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QPushButton, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QFileDialog, QComboBox, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QIcon

from src.core.app_config import get_version, get_app_name, get_app_description
from src.core.settings_manager import SettingsManager
from src.core.profile_manager import ProfileManager
from src.core.default_restore import restore_server_defaults
from src.utils.locale_manager import LocaleManager, tr

# Import UI components
from src.ui.sidebar_widget import SidebarWidget
from src.ui.theme_manager import ThemeManager
from src.ui.profiles_tab import ProfilesTab
from src.ui.mods_tab import ModsTab
from src.ui.launcher_tab import LauncherTab
from src.ui.config_tab import ConfigTab
from src.ui.settings_tab import SettingsTab


class ProcessManager:
    """Manages cleanup of subprocesses on application exit."""
    
    def __init__(self):
        self._processes: List = []
        self._file_handles: List = []
        
        # Register cleanup handlers
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def register_process(self, process) -> None:
        """Register a subprocess for cleanup."""
        self._processes.append(process)
    
    def register_file_handle(self, handle) -> None:
        """Register a file handle for cleanup."""
        self._file_handles.append(handle)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self) -> None:
        """Clean up all registered resources."""
        print("Cleaning up resources...")
        
        # Terminate processes
        for proc in self._processes:
            try:
                if hasattr(proc, 'terminate'):
                    proc.terminate()
                    proc.wait(timeout=5)
            except Exception as e:
                print(f"Error terminating process: {e}")
        
        # Close file handles
        for handle in self._file_handles:
            try:
                if hasattr(handle, 'close'):
                    handle.close()
            except Exception as e:
                print(f"Error closing file handle: {e}")
        
        self._processes.clear()
        self._file_handles.clear()
        print("Cleanup complete.")


class MainWindow(QMainWindow):
    """Main application window with Vortex-style sidebar navigation."""
    
    language_changed = Signal(str)
    
    # Tab indices
    TAB_PROFILES = 0
    TAB_MODS = 1
    TAB_LAUNCHER = 2
    TAB_CONFIG = 3
    TAB_SETTINGS = 4
    
    def __init__(self):
        super().__init__()
        
        # Initialize managers
        self.settings = SettingsManager()
        self.profiles = ProfileManager()
        self.locale = LocaleManager()
        self.process_manager = ProcessManager()
        
        # Current selected profile
        self.current_profile = None
        
        # Set language from settings
        self.locale.set_language(self.settings.settings.language)
        self.locale.add_observer(self._on_language_changed)
        
        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._update_texts()
        
        # Apply theme from settings
        ThemeManager.apply_theme(self.settings.settings.theme)
        
        # Restore window state
        self._restore_window_state()
    
    def _setup_ui(self):
        """Initialize the user interface with sidebar layout."""
        self.setWindowTitle(f"{tr('app.title')} v{get_version()}")
        self.setMinimumSize(1200, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar navigation
        self.sidebar = SidebarWidget()
        self.sidebar.set_footer_text(f"v{get_version()}")
        
        # Add navigation items
        self.sidebar.add_item("📂", tr("tabs.profiles"))
        self.sidebar.add_item("🧩", tr("tabs.mods"))
        self.sidebar.add_item("🚀", tr("tabs.launcher"))
        self.sidebar.add_item("⚙️", tr("tabs.config"))
        self.sidebar.add_item("🔧", tr("tabs.settings"))
        
        self.sidebar.set_current_index(0)
        self.sidebar.item_selected.connect(self._on_sidebar_item_selected)
        
        main_layout.addWidget(self.sidebar)
        
        # Content area
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Profile indicator bar
        self.profile_bar = QFrame()
        self.profile_bar.setObjectName("profileBar")
        self.profile_bar.setFixedHeight(40)
        self.profile_bar.setStyleSheet("""
            QFrame#profileBar {
                background-color: rgba(0, 120, 212, 0.1);
                border-bottom: 1px solid rgba(0, 120, 212, 0.3);
            }
        """)
        profile_bar_layout = QHBoxLayout(self.profile_bar)
        profile_bar_layout.setContentsMargins(16, 0, 16, 0)
        
        self.lbl_current_profile = QLabel()
        self.lbl_current_profile.setStyleSheet("font-weight: bold;")
        profile_bar_layout.addWidget(self.lbl_current_profile)
        
        profile_bar_layout.addStretch()
        
        # Theme toggle button
        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setFixedSize(32, 32)
        self.btn_theme.setToolTip(tr("settings.theme"))
        self.btn_theme.clicked.connect(self._toggle_theme)
        profile_bar_layout.addWidget(self.btn_theme)
        
        content_layout.addWidget(self.profile_bar)
        
        # Stacked widget for page content
        self.stack = QStackedWidget()
        
        # Create page instances
        self.tab_profiles = ProfilesTab()
        self.tab_mods = ModsTab()
        self.tab_launcher = LauncherTab()
        self.tab_config = ConfigTab()
        self.tab_settings = SettingsTab()
        
        # Add pages to stack
        self.stack.addWidget(self.tab_profiles)
        self.stack.addWidget(self.tab_mods)
        self.stack.addWidget(self.tab_launcher)
        self.stack.addWidget(self.tab_config)
        self.stack.addWidget(self.tab_settings)
        
        content_layout.addWidget(self.stack)
        
        main_layout.addWidget(content_container, stretch=1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("common.loading"))
    
    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        self.menu_file = menubar.addMenu("")
        self.action_exit = QAction("", self)
        self.action_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.action_exit)
        
        # View menu (Theme)
        self.menu_view = menubar.addMenu("")
        
        self.menu_theme = self.menu_view.addMenu("")
        self.action_theme_system = QAction("🖥️ System", self)
        self.action_theme_dark = QAction("🌙 Dark", self)
        self.action_theme_light = QAction("☀️ Light", self)
        self.action_theme_system.triggered.connect(lambda: self._set_theme("system"))
        self.action_theme_dark.triggered.connect(lambda: self._set_theme("dark"))
        self.action_theme_light.triggered.connect(lambda: self._set_theme("light"))
        self.menu_theme.addAction(self.action_theme_system)
        self.menu_theme.addAction(self.action_theme_dark)
        self.menu_theme.addAction(self.action_theme_light)
        
        # Language submenu
        self.menu_language = self.menu_view.addMenu("")
        self.action_lang_en = QAction("🇬🇧 English", self)
        self.action_lang_vi = QAction("🇻🇳 Tiếng Việt", self)
        self.action_lang_en.triggered.connect(lambda: self._change_language("en"))
        self.action_lang_vi.triggered.connect(lambda: self._change_language("vi"))
        self.menu_language.addAction(self.action_lang_en)
        self.menu_language.addAction(self.action_lang_vi)
        
        # Help menu
        self.menu_help = menubar.addMenu("")
        self.action_about = QAction("", self)
        self.action_about.triggered.connect(self._show_about)
        self.menu_help.addAction(self.action_about)
    
    def _connect_signals(self):
        """Connect signals between tabs."""
        # Profile selection updates other tabs
        self.tab_profiles.profile_selected.connect(self._on_profile_selected)

        # Mods installation -> update Launcher mods list/mods.txt
        self.tab_mods.mods_list_updated.connect(self.tab_launcher.apply_installed_mods_text)
        
        # Settings language change
        self.tab_settings.language_changed.connect(self._update_all_texts)
        
        # Settings theme change
        if hasattr(self.tab_settings, 'theme_changed'):
            self.tab_settings.theme_changed.connect(self._on_theme_changed)
    
    def _on_sidebar_item_selected(self, index: int):
        """Handle sidebar navigation item selection."""
        self.stack.setCurrentIndex(index)
    
    def _on_profile_selected(self, profile_data: dict):
        """Handle profile selection."""
        self.current_profile = profile_data
        
        # Update other tabs with selected profile
        self.tab_mods.set_profile(profile_data)
        self.tab_launcher.set_profile(profile_data)
        self.tab_config.set_profile(profile_data)
        
        # Update profile indicator
        profile_name = profile_data.get("name", "")
        self.lbl_current_profile.setText(f"📂 {tr('profiles.current')}: {profile_name}")
        self.status_bar.showMessage(f"{tr('profiles.current')}: {profile_name}")
    
    def _toggle_theme(self):
        """Toggle between dark and light themes."""
        current = self.settings.settings.theme
        if current == "dark":
            new_theme = "light"
            self.btn_theme.setText("☀️")
        else:
            new_theme = "dark"
            self.btn_theme.setText("🌙")
        
        self._set_theme(new_theme)
    
    def _set_theme(self, theme: str):
        """Set application theme."""
        ThemeManager.apply_theme(theme)
        self.settings.settings.theme = theme
        self.settings.save()
        
        # Update button icon
        if theme == "light":
            self.btn_theme.setText("☀️")
        else:
            self.btn_theme.setText("🌙")
    
    def _on_theme_changed(self, theme: str):
        """Handle theme change from settings tab."""
        self._set_theme(theme)
    
    def _update_texts(self):
        """Update all UI texts with current language."""
        # Window title
        self.setWindowTitle(f"{tr('app.title')} v{get_version()}")
        
        # Sidebar items
        self.sidebar.update_item_text(0, "📂", tr("tabs.profiles"))
        self.sidebar.update_item_text(1, "🧩", tr("tabs.mods"))
        self.sidebar.update_item_text(2, "🚀", tr("tabs.launcher"))
        self.sidebar.update_item_text(3, "⚙️", tr("tabs.config"))
        self.sidebar.update_item_text(4, "🔧", tr("tabs.settings"))
        
        # Menus
        self.menu_file.setTitle(tr("menu.file"))
        self.menu_view.setTitle(tr("menu.view"))
        self.menu_theme.setTitle(tr("settings.theme"))
        self.menu_language.setTitle(tr("menu.language"))
        self.menu_help.setTitle(tr("menu.help"))
        self.action_exit.setText(tr("menu.exit"))
        self.action_about.setText(tr("menu.about"))
        
        # Profile bar
        if self.current_profile:
            profile_name = self.current_profile.get("name", "")
            self.lbl_current_profile.setText(f"📂 {tr('profiles.current')}: {profile_name}")
            self.status_bar.showMessage(f"{tr('profiles.current')}: {profile_name}")
        else:
            self.lbl_current_profile.setText(f"📂 {tr('profiles.no_profiles')}")
            self.status_bar.showMessage(tr("common.success"))
    
    def _update_all_texts(self):
        """Update texts in all tabs."""
        self._update_texts()
        self.tab_profiles.update_texts()
        self.tab_mods.update_texts()
        self.tab_launcher.update_texts()
        self.tab_config.update_texts()
        self.tab_settings.update_texts()
    
    def _on_language_changed(self, new_language: str):
        """Handle language change from observer."""
        self._update_all_texts()
    
    def _change_language(self, lang_code: str):
        """Change the application language."""
        self.locale.set_language(lang_code)
        self.settings.settings.language = lang_code
        self.settings.save()
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            tr("menu.about"),
            f"{get_app_name()}\n\n{tr('app.title')}\n\nVersion {get_version()}\n\n{get_app_description()}"
        )
    
    def _restore_window_state(self):
        """Restore window size and position from settings."""
        width = self.settings.settings.window_width or 1200
        height = self.settings.settings.window_height or 800
        self.resize(width, height)
        
        if self.settings.settings.window_maximized:
            self.showMaximized()
    
    def closeEvent(self, event):
        """Handle application close."""
        # Save window state
        if not self.isMaximized():
            self.settings.settings.window_width = self.width()
            self.settings.settings.window_height = self.height()
        self.settings.settings.window_maximized = self.isMaximized()
        self.settings.save()
        
        # Confirm exit
        reply = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("dialogs.confirm_exit"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.process_manager.cleanup()
            event.accept()
        else:
            event.ignore()


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName(get_app_name())
    app.setOrganizationName("DayzModManager")
    app.setApplicationVersion(get_version())
    
    # Set application style
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
