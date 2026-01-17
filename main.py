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
    QMessageBox, QFileDialog, QComboBox, QSplitter, QFrame, QDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QIcon

from src.core.app_config import get_version, get_app_name, get_app_description
from src.core.settings_manager import SettingsManager
from src.core.profile_manager import ProfileManager
from src.core.default_restore import restore_server_defaults
from src.utils.locale_manager import LocaleManager, tr
from src.constants import (
    SIDEBAR_ITEMS,
    TabIndex,
    WindowDimensions,
    APP_DEFAULTS,
)

# Import UI components
from src.ui.sidebar_widget import SidebarWidget
from src.ui.theme_manager import ThemeManager
from src.ui.profiles_tab import ProfilesTab
from src.ui.mods_tab import ModsTab
from src.ui.unified_config_tab import UnifiedConfigTab
from src.ui.settings_tab import SettingsTab
from src.ui.icons import Icons
from src.ui.widgets import IconButton
from src.ui.config_manager import UnsavedChangesDialog


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
    
    def __init__(self):
        super().__init__()

        # First-run bootstrap (creates default configs in writable storage)
        try:
            from src.core.storage_paths import bootstrap_first_run
            bootstrap_first_run()
        except Exception:
            pass
        
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
        self.setWindowTitle(tr('app.title'))
        self.setMinimumSize(WindowDimensions.MIN_WIDTH, WindowDimensions.MIN_HEIGHT)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar navigation
        self.sidebar = SidebarWidget()
        self.sidebar.set_footer_text("")
        
        # Add navigation items from centralized constants
        for nav_item in SIDEBAR_ITEMS:
            self.sidebar.add_item(nav_item.icon_name, tr(nav_item.translation_key), tr(nav_item.tooltip_key) if nav_item.tooltip_key else "")
        
        self.sidebar.set_current_index(0)
        self.sidebar.item_selected.connect(self._on_sidebar_item_selected)
        
        main_layout.addWidget(self.sidebar)
        
        # Content area
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Stacked widget for page content
        self.stack = QStackedWidget()
        
        # Create page instances
        self.tab_profiles = ProfilesTab()
        self.tab_mods = ModsTab()
        self.tab_config = UnifiedConfigTab()
        self.tab_settings = SettingsTab()
        
        # Add pages to stack
        self.stack.addWidget(self.tab_profiles)
        self.stack.addWidget(self.tab_mods)
        self.stack.addWidget(self.tab_config)
        self.stack.addWidget(self.tab_settings)
        
        content_layout.addWidget(self.stack)
        
        main_layout.addWidget(content_container, stretch=1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()
    
    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        self.menu_file = menubar.addMenu("")
        self.action_exit = QAction("", self)
        self.action_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.action_exit)
        
        # View menu
        self.menu_view = menubar.addMenu("")
        
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
    
    def _update_status_bar(self):
        """Update status bar with version and current profile info."""
        profile_name = self.current_profile.get("name", tr("common.none")) if self.current_profile else tr("common.none")
        status_text = f"v{get_version()} | {tr('profiles.current')}: {profile_name}"
        self.status_bar.showMessage(status_text)
    
    def _connect_signals(self):
        """Connect signals between tabs."""
        # Profile selection updates other tabs
        self.tab_profiles.profile_selected.connect(self._on_profile_selected)
        
        # Settings language change
        self.tab_settings.language_changed.connect(self._update_all_texts)
        
        # Settings theme change
        if hasattr(self.tab_settings, 'theme_changed'):
            self.tab_settings.theme_changed.connect(self._on_theme_changed)
    
    def _on_sidebar_item_selected(self, index: int):
        """Handle sidebar navigation item selection."""
        # Check for unsaved changes if leaving config tab
        current_index = self.stack.currentIndex()
        if current_index == TabIndex.CONFIG and self.tab_config.has_unsaved_changes():
            dialog = UnsavedChangesDialog(self)
            if dialog.exec() == QDialog.Accepted:
                action = dialog.get_result()
                if action == UnsavedChangesDialog.SAVE:
                    self.tab_config._preview_and_save()
                elif action == UnsavedChangesDialog.CANCEL:
                    # Stay on current tab
                    self.sidebar.set_current_index(current_index)
                    return
                elif action == UnsavedChangesDialog.DISCARD:
                    self.tab_config.discard_changes()
                # else: continue
        
        self.stack.setCurrentIndex(index)
    
    def _on_profile_selected(self, profile_data: dict):
        """Handle profile selection."""
        self.current_profile = profile_data
        
        # Update other tabs with selected profile
        self.tab_config.set_profile(profile_data)
        self.tab_mods.set_profile(profile_data)
        
        # Update status bar
        self._update_status_bar()
    
    def _on_theme_changed(self, theme_id: str):
        """Handle theme change from settings tab."""
        if not theme_id:
            return

        ThemeManager.apply_theme(theme_id)
        self.settings.settings.theme = theme_id
        self.settings.save()

        # Refresh sidebar icons
        try:
            self.sidebar.refresh_icons()
        except Exception:
            pass

        # Refresh theme-aware logos (e.g., About tab)
        try:
            if hasattr(self.tab_settings, "tab_about"):
                self.tab_settings.tab_about.update_texts()
        except Exception:
            pass
    
    def _update_texts(self):
        """Update all UI texts with current language."""
        # Window title
        self.setWindowTitle(f"{get_app_name()} v{get_version()}")
        
        # Sidebar items from centralized constants
        for nav_item in SIDEBAR_ITEMS:
            self.sidebar.update_item_text(
                nav_item.index,
                nav_item.icon_name,
                tr(nav_item.translation_key),
                tr(nav_item.tooltip_key) if nav_item.tooltip_key else ""
            )
        
        # Menus
        self.menu_file.setTitle(tr("menu.file"))
        self.menu_view.setTitle(tr("menu.view"))
        self.menu_language.setTitle(tr("menu.language"))
        self.menu_help.setTitle(tr("menu.help"))
        self.action_exit.setText(tr("menu.exit"))
        self.action_about.setText(tr("menu.about"))
        
        # Status bar
        self._update_status_bar()
    
    def _update_all_texts(self):
        """Update texts in all tabs."""
        self._update_texts()
        self.tab_profiles.update_texts()
        self.tab_mods.update_texts()
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
        width = self.settings.settings.window_width or WindowDimensions.DEFAULT_WIDTH
        height = self.settings.settings.window_height or WindowDimensions.DEFAULT_HEIGHT
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

    # App/window icon (runtime). The embedded EXE icon is configured in the PyInstaller spec.
    app.setWindowIcon(Icons.get_app_icon())
    
    # Set application style
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.setWindowIcon(Icons.get_app_icon())
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
