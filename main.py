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
        
        # Set language from settings
        self.locale.set_language(self.settings.get("language", "en"))
        self.locale.add_observer(self._on_language_changed)
        
        self._setup_ui()
        self._setup_menu()
        self._update_texts()
        
        # Restore window state
        self._restore_window_state()
    
    def _setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"{tr('app.title')} v{get_version()}")
        self.setMinimumSize(1000, 700)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs (placeholders for now)
        self.tab_profiles = QWidget()
        self.tab_mods = QWidget()
        self.tab_launcher = QWidget()
        self.tab_config = QWidget()
        self.tab_settings = QWidget()
        
        self.tabs.addTab(self.tab_profiles, "")
        self.tabs.addTab(self.tab_mods, "")
        self.tabs.addTab(self.tab_launcher, "")
        self.tabs.addTab(self.tab_config, "")
        self.tabs.addTab(self.tab_settings, "")
        
        # Setup individual tabs
        self._setup_profiles_tab()
        self._setup_mods_tab()
        self._setup_settings_tab()
        
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
    
    def _setup_profiles_tab(self):
        """Setup the profiles tab content."""
        layout = QVBoxLayout(self.tab_profiles)
        
        # Header
        header = QHBoxLayout()
        self.lbl_profiles_title = QLabel()
        self.lbl_profiles_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(self.lbl_profiles_title)
        header.addStretch()
        
        self.btn_new_profile = QPushButton()
        self.btn_new_profile.clicked.connect(self._create_new_profile)
        header.addWidget(self.btn_new_profile)
        
        layout.addLayout(header)
        
        # Profile list placeholder
        self.lbl_no_profiles = QLabel()
        self.lbl_no_profiles.setAlignment(Qt.AlignCenter)
        self.lbl_no_profiles.setStyleSheet("color: gray; padding: 50px;")
        layout.addWidget(self.lbl_no_profiles)
        
        layout.addStretch()
    
    def _setup_mods_tab(self):
        """Setup the mods tab content."""
        layout = QVBoxLayout(self.tab_mods)
        
        header = QHBoxLayout()
        self.lbl_mods_title = QLabel()
        self.lbl_mods_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(self.lbl_mods_title)
        header.addStretch()
        
        self.btn_verify_integrity = QPushButton()
        self.btn_verify_integrity.clicked.connect(self._verify_integrity)
        header.addWidget(self.btn_verify_integrity)
        
        layout.addLayout(header)
        layout.addStretch()
    
    def _setup_settings_tab(self):
        """Setup the settings tab content."""
        layout = QVBoxLayout(self.tab_settings)
        
        # Theme selection
        theme_layout = QHBoxLayout()
        self.lbl_theme = QLabel()
        theme_layout.addWidget(self.lbl_theme)
        
        self.combo_theme = QComboBox()
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.combo_theme)
        theme_layout.addStretch()
        
        layout.addLayout(theme_layout)
        
        # Language selection
        lang_layout = QHBoxLayout()
        self.lbl_language = QLabel()
        lang_layout.addWidget(self.lbl_language)
        
        self.combo_language = QComboBox()
        self.combo_language.addItem("🇬🇧 English", "en")
        self.combo_language.addItem("🇻🇳 Tiếng Việt", "vi")
        self.combo_language.currentIndexChanged.connect(self._on_language_combo_changed)
        lang_layout.addWidget(self.combo_language)
        lang_layout.addStretch()
        
        layout.addLayout(lang_layout)

        # Restore defaults
        restore_layout = QHBoxLayout()
        self.btn_restore_app_defaults = QPushButton()
        self.btn_restore_app_defaults.clicked.connect(self._restore_app_defaults)
        restore_layout.addWidget(self.btn_restore_app_defaults)

        self.btn_restore_server_defaults = QPushButton()
        self.btn_restore_server_defaults.clicked.connect(self._restore_server_defaults)
        restore_layout.addWidget(self.btn_restore_server_defaults)
        restore_layout.addStretch()

        layout.addLayout(restore_layout)
        layout.addStretch()
    
    def _update_texts(self):
        """Update all UI texts with current language."""
        # Window title
        self.setWindowTitle(f"{tr('app.title')} v{get_version()}")
        
        # Tab names
        self.tabs.setTabText(0, tr("tabs.profiles"))
        self.tabs.setTabText(1, tr("tabs.mods"))
        self.tabs.setTabText(2, tr("tabs.launcher"))
        self.tabs.setTabText(3, tr("tabs.config"))
        self.tabs.setTabText(4, tr("tabs.settings"))
        
        # Menus
        self.menu_file.setTitle(tr("menu.file"))
        self.menu_settings.setTitle(tr("menu.settings"))
        self.menu_language.setTitle(tr("menu.language"))
        self.menu_help.setTitle(tr("menu.help"))
        self.action_exit.setText(tr("menu.exit"))
        self.action_about.setText(tr("menu.about"))
        
        # Profiles tab
        self.lbl_profiles_title.setText(tr("profiles.title"))
        self.btn_new_profile.setText(tr("profiles.new_profile"))
        self.lbl_no_profiles.setText(tr("profiles.no_profiles"))
        
        # Mods tab
        self.lbl_mods_title.setText(tr("mods.title"))
        self.btn_verify_integrity.setText(tr("mods.verify_integrity"))
        
        # Settings tab
        self.lbl_theme.setText(tr("settings.theme") + ":")
        self.lbl_language.setText(tr("settings.language_setting") + ":")
        self.btn_restore_app_defaults.setText(tr("settings.restore_app_defaults"))
        self.btn_restore_server_defaults.setText(tr("settings.restore_server_defaults"))
        
        # Update theme combo
        self.combo_theme.clear()
        self.combo_theme.addItem(tr("settings.theme_dark"), "dark")
        self.combo_theme.addItem(tr("settings.theme_light"), "light")
        self.combo_theme.addItem(tr("settings.theme_system"), "system")
        
        # Status bar
        self.status_bar.showMessage(tr("common.success"))
    
    def _on_language_changed(self, new_language: str):
        """Handle language change from observer."""
        self._update_texts()
    
    def _change_language(self, lang_code: str):
        """Change the application language."""
        self.locale.set_language(lang_code)
        self.settings.set("language", lang_code)
        
        # Update combo box selection
        index = self.combo_language.findData(lang_code)
        if index >= 0:
            self.combo_language.blockSignals(True)
            self.combo_language.setCurrentIndex(index)
            self.combo_language.blockSignals(False)
    
    def _on_language_combo_changed(self, index: int):
        """Handle language combo box change."""
        lang_code = self.combo_language.currentData()
        if lang_code:
            self._change_language(lang_code)
    
    def _on_theme_changed(self, index: int):
        """Handle theme change."""
        theme = self.combo_theme.currentData()
        if theme:
            self.settings.set("theme", theme)
            # Theme application would go here
    
    def _create_new_profile(self):
        """Create a new server profile."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("profiles.select_server_path"),
            "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            # Profile creation dialog would go here
            self.status_bar.showMessage(tr("profiles.profile_saved"))
    
    def _verify_integrity(self):
        """Run mod integrity verification."""
        # Would integrate with ModIntegrityChecker
        self.status_bar.showMessage(tr("mods.integrity_check") + "...")
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            tr("menu.about"),
            f"{get_app_name()}\n\n{tr('app.title')}\n\nVersion {get_version()}\n\n{get_app_description()}"
        )

    def _restore_app_defaults(self):
        """Restore application settings to defaults."""
        reply = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("dialogs.confirm_restore_app_defaults"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.settings.reset_to_defaults()

        # Apply restored language
        self.locale.set_language(self.settings.get("language", "en"))

        # Sync UI selections
        lang_code = self.settings.get("language", "en")
        lang_index = self.combo_language.findData(lang_code)
        if lang_index >= 0:
            self.combo_language.blockSignals(True)
            self.combo_language.setCurrentIndex(lang_index)
            self.combo_language.blockSignals(False)

        theme_code = self.settings.get("theme", "dark")
        theme_index = self.combo_theme.findData(theme_code)
        if theme_index >= 0:
            self.combo_theme.blockSignals(True)
            self.combo_theme.setCurrentIndex(theme_index)
            self.combo_theme.blockSignals(False)

        self._update_texts()
        self.status_bar.showMessage(tr("settings.restore_done"))

    def _restore_server_defaults(self):
        """Restore default server files (start.bat + serverDZ.cfg) into a chosen server folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dialogs.select_server_folder_for_restore"),
            self.settings.get("last_server_path", ""),
            QFileDialog.ShowDirsOnly,
        )
        if not folder:
            return

        self.settings.set("last_server_path", folder)

        reply = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("dialogs.confirm_restore_server_defaults"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            restore_server_defaults(folder, overwrite=True)
            self.status_bar.showMessage(tr("settings.restore_done"))
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("common.error"),
                f"{tr('settings.restore_failed')}: {e}",
            )
    
    def _restore_window_state(self):
        """Restore window size and position from settings."""
        width = self.settings.get("window_width", 1200)
        height = self.settings.get("window_height", 800)
        self.resize(width, height)
        
        if self.settings.get("window_maximized", False):
            self.showMaximized()
    
    def closeEvent(self, event):
        """Handle application close."""
        # Save window state
        if not self.isMaximized():
            self.settings.set("window_width", self.width())
            self.settings.set("window_height", self.height())
        self.settings.set("window_maximized", self.isMaximized())
        
        # Confirm exit if server is running
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
