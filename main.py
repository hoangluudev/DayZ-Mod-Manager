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
    QTabWidget, QLabel, QPushButton, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QIcon

from src.core.app_config import get_version, get_app_name, get_app_description
from src.core.settings_manager import SettingsManager
from src.core.profile_manager import ProfileManager
from src.core.default_restore import restore_server_defaults
from src.utils.locale_manager import LocaleManager, tr

# Import UI tabs
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
    """Main application window."""
    
    language_changed = Signal(str)
    
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
        
        # Restore window state
        self._restore_window_state()
    
    def _setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"{tr('app.title')} v{get_version()}")
        self.setMinimumSize(1100, 750)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)
        
        # Create tab instances
        self.tab_profiles = ProfilesTab()
        self.tab_mods = ModsTab()
        self.tab_launcher = LauncherTab()
        self.tab_config = ConfigTab()
        self.tab_settings = SettingsTab()
        
        # Add tabs
        self.tabs.addTab(self.tab_profiles, "")
        self.tabs.addTab(self.tab_mods, "")
        self.tabs.addTab(self.tab_launcher, "")
        self.tabs.addTab(self.tab_config, "")
        self.tabs.addTab(self.tab_settings, "")
        
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
        
        # Settings menu
        self.menu_settings = menubar.addMenu("")
        
        # Language submenu
        self.menu_language = self.menu_settings.addMenu("")
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
        
        # Settings language change
        self.tab_settings.language_changed.connect(self._update_all_texts)
    
    def _on_profile_selected(self, profile_data: dict):
        """Handle profile selection."""
        self.current_profile = profile_data
        
        # Update other tabs with selected profile
        self.tab_mods.set_profile(profile_data)
        self.tab_launcher.set_profile(profile_data)
        self.tab_config.set_profile(profile_data)
        
        # Show status
        profile_name = profile_data.get("name", "")
        self.status_bar.showMessage(f"{tr('profiles.current')}: {profile_name}")
    
    def _update_texts(self):
        """Update all UI texts with current language."""
        # Window title
        self.setWindowTitle(f"{tr('app.title')} v{get_version()}")
        
        # Tab names
        self.tabs.setTabText(0, f"📂 {tr('tabs.profiles')}")
        self.tabs.setTabText(1, f"🧩 {tr('tabs.mods')}")
        self.tabs.setTabText(2, f"🚀 {tr('tabs.launcher')}")
        self.tabs.setTabText(3, f"⚙️ {tr('tabs.config')}")
        self.tabs.setTabText(4, f"🔧 {tr('tabs.settings')}")
        
        # Menus
        self.menu_file.setTitle(tr("menu.file"))
        self.menu_settings.setTitle(tr("menu.settings"))
        self.menu_language.setTitle(tr("menu.language"))
        self.menu_help.setTitle(tr("menu.help"))
        self.action_exit.setText(tr("menu.exit"))
        self.action_about.setText(tr("menu.about"))
        
        # Status bar
        if self.current_profile:
            profile_name = self.current_profile.get("name", "")
            self.status_bar.showMessage(f"{tr('profiles.current')}: {profile_name}")
        else:
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
