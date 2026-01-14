"""
Settings Tab - Application Settings with sub-tabs for organization
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QFrame, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal

from src.utils.locale_manager import LocaleManager, tr
from src.core.settings_manager import SettingsManager
from src.core.app_config import AppConfigManager
from src.core.default_restore import restore_server_defaults
from src.ui.widgets import SectionBox, PathSelector, AccentColorSelector, IconButton
from src.ui.icons import Icons, ACCENT_COLORS
from src.ui.theme_manager import ThemeManager


class AppearanceTab(QWidget):
    """Appearance settings sub-tab (Theme, Language, Colors)."""
    
    language_changed = Signal()
    theme_changed = Signal(str)
    accent_changed = Signal(str)
    
    def __init__(self, settings: SettingsManager, locale: LocaleManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.locale = locale
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Language Section
        lang_box = SectionBox(tr("settings.language"))
        lang_form = QFormLayout()
        lang_form.setSpacing(12)
        
        self.cmb_language = QComboBox()
        self.cmb_language.addItem("English", "en")
        self.cmb_language.addItem("Tiếng Việt", "vi")
        self.cmb_language.currentIndexChanged.connect(self._on_language_changed)
        lang_form.addRow(tr("settings.select_language") + ":", self.cmb_language)
        
        self.lbl_lang_desc = QLabel(tr("settings.language_desc"))
        self.lbl_lang_desc.setStyleSheet("color: gray; font-size: 11px;")
        lang_form.addRow("", self.lbl_lang_desc)
        
        lang_box.add_layout(lang_form)
        layout.addWidget(lang_box)
        
        # Theme Section
        theme_box = SectionBox(tr("settings.theme"))
        theme_form = QFormLayout()
        theme_form.setSpacing(12)
        
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem(tr("settings.theme_dark"), "dark")
        self.cmb_theme.addItem(tr("settings.theme_light"), "light")
        self.cmb_theme.addItem(tr("settings.theme_system"), "system")
        self.cmb_theme.currentIndexChanged.connect(self._on_theme_changed)
        theme_form.addRow(tr("settings.theme") + ":", self.cmb_theme)
        
        theme_box.add_layout(theme_form)
        layout.addWidget(theme_box)
        
        # Accent Color Section
        color_box = SectionBox(tr("settings.accent_color"))
        color_layout = QVBoxLayout()
        color_layout.setSpacing(12)
        
        self.lbl_color_desc = QLabel(tr("settings.accent_color_desc"))
        self.lbl_color_desc.setStyleSheet("color: gray; font-size: 11px;")
        color_layout.addWidget(self.lbl_color_desc)
        
        self.color_selector = AccentColorSelector(
            self.settings.settings.accent_color or "#0078d4"
        )
        self.color_selector.color_changed.connect(self._on_accent_changed)
        color_layout.addWidget(self.color_selector)
        
        color_box.add_layout(color_layout)
        layout.addWidget(color_box)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load current settings into UI."""
        # Language
        current_lang = self.settings.settings.language
        index = self.cmb_language.findData(current_lang)
        if index >= 0:
            self.cmb_language.setCurrentIndex(index)
        
        # Theme
        current_theme = self.settings.settings.theme
        index = self.cmb_theme.findData(current_theme)
        if index >= 0:
            self.cmb_theme.setCurrentIndex(index)
        
        # Accent color
        accent = self.settings.settings.accent_color or "#0078d4"
        self.color_selector.set_color(accent)
    
    def _on_language_changed(self, index):
        """Handle language change."""
        lang = self.cmb_language.itemData(index)
        if lang:
            self.locale.set_language(lang)
            self.settings.settings.language = lang
            self.settings.save()
            self.language_changed.emit()
    
    def _on_theme_changed(self, index):
        """Handle theme change."""
        theme = self.cmb_theme.itemData(index)
        if theme:
            self.settings.settings.theme = theme
            self.settings.save()
            ThemeManager.apply_theme(theme, self.settings.settings.accent_color)
            self.theme_changed.emit(theme)
    
    def _on_accent_changed(self, color):
        """Handle accent color change."""
        self.settings.settings.accent_color = color
        self.settings.save()
        ThemeManager.apply_theme(self.settings.settings.theme, color)
        self.accent_changed.emit(color)
    
    def update_texts(self):
        """Update UI texts."""
        # Update theme combo items
        self.cmb_theme.setItemText(0, tr("settings.theme_dark"))
        self.cmb_theme.setItemText(1, tr("settings.theme_light"))
        self.cmb_theme.setItemText(2, tr("settings.theme_system"))
        self.lbl_lang_desc.setText(tr("settings.language_desc"))
        self.lbl_color_desc.setText(tr("settings.accent_color_desc"))


class ConfigTab(QWidget):
    """Configuration settings sub-tab (Paths, Storage)."""
    
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Default Paths Section
        paths_box = SectionBox(tr("settings.default_paths"))
        paths_form = QFormLayout()
        paths_form.setSpacing(12)
        
        # Workshop path
        self.path_workshop = PathSelector(
            path=self.settings.settings.default_workshop_path or ""
        )
        self.path_workshop.path_changed.connect(self._on_workshop_changed)
        paths_form.addRow(tr("settings.default_workshop") + ":", self.path_workshop)
        
        # Server path
        self.path_server = PathSelector(
            path=self.settings.settings.default_server_path or ""
        )
        self.path_server.path_changed.connect(self._on_server_changed)
        paths_form.addRow(tr("settings.default_server") + ":", self.path_server)
        
        paths_box.add_layout(paths_form)
        layout.addWidget(paths_box)
        
        # Data Storage Section
        storage_box = SectionBox(tr("settings.data_storage"))
        storage_layout = QVBoxLayout()
        storage_layout.setSpacing(12)
        
        self.chk_custom_storage = QCheckBox(tr("settings.use_custom_storage"))
        self.chk_custom_storage.stateChanged.connect(self._on_storage_toggle)
        storage_layout.addWidget(self.chk_custom_storage)
        
        storage_form = QFormLayout()
        storage_form.setSpacing(8)
        
        # Data path
        self.path_data = PathSelector(
            path=self.settings.settings.data_storage_path or ""
        )
        self.path_data.path_changed.connect(self._on_data_path_changed)
        storage_form.addRow(tr("settings.data_path") + ":", self.path_data)
        
        # Profiles path
        self.path_profiles = PathSelector(
            path=self.settings.settings.profiles_storage_path or ""
        )
        self.path_profiles.path_changed.connect(self._on_profiles_path_changed)
        storage_form.addRow(tr("settings.profiles_path") + ":", self.path_profiles)
        
        storage_layout.addLayout(storage_form)
        
        self.lbl_storage_note = QLabel(tr("settings.storage_note"))
        self.lbl_storage_note.setStyleSheet("color: #ff9800; font-size: 11px;")
        self.lbl_storage_note.setWordWrap(True)
        storage_layout.addWidget(self.lbl_storage_note)
        
        storage_box.add_layout(storage_layout)
        layout.addWidget(storage_box)
        
        # Restore Defaults Section
        restore_box = SectionBox(tr("settings.restore_section"))
        restore_layout = QVBoxLayout()
        restore_layout.setSpacing(12)
        
        self.lbl_restore_desc = QLabel(tr("settings.restore_desc"))
        self.lbl_restore_desc.setWordWrap(True)
        restore_layout.addWidget(self.lbl_restore_desc)
        
        btn_layout = QHBoxLayout()
        self.btn_restore = IconButton(
            icon_name="restore",
            text=tr("settings.restore_defaults"),
            size=16
        )
        self.btn_restore.clicked.connect(self._restore_defaults)
        btn_layout.addWidget(self.btn_restore)
        btn_layout.addStretch()
        restore_layout.addLayout(btn_layout)
        
        restore_box.add_layout(restore_layout)
        layout.addWidget(restore_box)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load current settings into UI."""
        self.path_workshop.set_path(self.settings.settings.default_workshop_path or "")
        self.path_server.set_path(self.settings.settings.default_server_path or "")
        self.path_data.set_path(self.settings.settings.data_storage_path or "")
        self.path_profiles.set_path(self.settings.settings.profiles_storage_path or "")
        
        self.chk_custom_storage.setChecked(self.settings.settings.use_custom_storage)
        self._update_storage_ui_state()
    
    def _update_storage_ui_state(self):
        """Enable/disable storage path controls."""
        enabled = self.chk_custom_storage.isChecked()
        self.path_data.set_enabled(enabled)
        self.path_profiles.set_enabled(enabled)
    
    def _on_storage_toggle(self, state):
        """Handle storage toggle."""
        self._update_storage_ui_state()
        self.settings.settings.use_custom_storage = bool(state)
        self.settings.save()
    
    def _on_workshop_changed(self, path):
        """Handle workshop path change."""
        self.settings.settings.default_workshop_path = path
        self.settings.save()
    
    def _on_server_changed(self, path):
        """Handle server path change."""
        self.settings.settings.default_server_path = path
        self.settings.save()
    
    def _on_data_path_changed(self, path):
        """Handle data path change."""
        self.settings.settings.data_storage_path = path
        self.settings.save()
    
    def _on_profiles_path_changed(self, path):
        """Handle profiles path change."""
        self.settings.settings.profiles_storage_path = path
        self.settings.save()
    
    def _restore_defaults(self):
        """Restore server default files."""
        reply = QMessageBox.question(
            self,
            tr("settings.confirm_restore"),
            tr("settings.restore_warning"),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = restore_server_defaults()
            if success:
                QMessageBox.information(
                    self,
                    tr("common.success"),
                    tr("settings.restore_success")
                )
            else:
                QMessageBox.warning(
                    self,
                    tr("common.error"),
                    tr("settings.restore_failed")
                )
    
    def update_texts(self):
        """Update UI texts."""
        self.lbl_storage_note.setText(tr("settings.storage_note"))
        self.lbl_restore_desc.setText(tr("settings.restore_desc"))
        self.chk_custom_storage.setText(tr("settings.use_custom_storage"))


class BehaviorTab(QWidget):
    """Behavior settings sub-tab."""
    
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Behavior Section
        behavior_box = SectionBox(tr("settings.behavior"))
        behavior_layout = QVBoxLayout()
        behavior_layout.setSpacing(12)
        
        self.chk_auto_backup = QCheckBox(tr("settings.auto_backup"))
        self.chk_auto_backup.stateChanged.connect(self._on_setting_changed)
        behavior_layout.addWidget(self.chk_auto_backup)
        
        self.chk_confirm_actions = QCheckBox(tr("settings.confirm_actions"))
        self.chk_confirm_actions.stateChanged.connect(self._on_setting_changed)
        behavior_layout.addWidget(self.chk_confirm_actions)
        
        self.chk_copy_bikeys = QCheckBox(tr("settings.auto_copy_bikeys"))
        self.chk_copy_bikeys.stateChanged.connect(self._on_setting_changed)
        behavior_layout.addWidget(self.chk_copy_bikeys)
        
        behavior_box.add_layout(behavior_layout)
        layout.addWidget(behavior_box)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load current settings into UI."""
        self.chk_auto_backup.setChecked(self.settings.settings.auto_backup)
        self.chk_confirm_actions.setChecked(self.settings.settings.confirm_actions)
        self.chk_copy_bikeys.setChecked(self.settings.settings.auto_copy_bikeys)
    
    def _on_setting_changed(self):
        """Handle setting checkbox change."""
        self.settings.settings.auto_backup = self.chk_auto_backup.isChecked()
        self.settings.settings.confirm_actions = self.chk_confirm_actions.isChecked()
        self.settings.settings.auto_copy_bikeys = self.chk_copy_bikeys.isChecked()
        self.settings.save()
    
    def update_texts(self):
        """Update UI texts."""
        self.chk_auto_backup.setText(tr("settings.auto_backup"))
        self.chk_confirm_actions.setText(tr("settings.confirm_actions"))
        self.chk_copy_bikeys.setText(tr("settings.auto_copy_bikeys"))


class AboutTab(QWidget):
    """About sub-tab."""
    
    def __init__(self, app_config: AppConfigManager, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # About Section
        about_box = SectionBox(tr("settings.about"))
        about_layout = QVBoxLayout()
        about_layout.setSpacing(12)
        
        # App icon/logo (theme-aware: monochrome on dark, color on light)
        self.logo_label = QLabel()
        self.logo_label.setPixmap(Icons.get_app_logo_pixmap(size=96, variant="auto"))
        self.logo_label.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(self.logo_label)
        
        # App name and version
        name_label = QLabel(f"<h2>{self.app_config.name}</h2>")
        name_label.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(name_label)
        
        version_label = QLabel(f"{tr('settings.version')}: {self.app_config.version}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: gray;")
        about_layout.addWidget(version_label)
        
        # Description
        desc_label = QLabel(tr("settings.description"))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-top: 16px;")
        about_layout.addWidget(desc_label)
        
        about_box.add_layout(about_layout)
        layout.addWidget(about_box)
        
        layout.addStretch()
    
    def update_texts(self):
        """Update UI texts."""
        # Texts are static, but the logo may change with theme.
        try:
            self.logo_label.setPixmap(Icons.get_app_logo_pixmap(size=96, variant="auto"))
        except Exception:
            pass


class SettingsTab(QWidget):
    """Tab for application settings with sub-tabs."""
    
    language_changed = Signal()
    theme_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.locale = LocaleManager()
        self.app_config = AppConfigManager()
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        self.lbl_title = QLabel(f"<h2>{tr('settings.title')}</h2>")
        layout.addWidget(self.lbl_title)
        
        # Tab widget for sub-tabs
        self.tab_widget = QTabWidget()
        
        # Create sub-tabs
        self.tab_appearance = AppearanceTab(self.settings, self.locale)
        self.tab_appearance.language_changed.connect(self.language_changed.emit)
        self.tab_appearance.theme_changed.connect(self.theme_changed.emit)
        
        self.tab_config = ConfigTab(self.settings)
        self.tab_behavior = BehaviorTab(self.settings)
        self.tab_about = AboutTab(self.app_config)
        
        # Add sub-tabs with icons
        self.tab_widget.addTab(self.tab_appearance, tr("settings.appearance"))
        self.tab_widget.addTab(self.tab_config, tr("settings.paths"))
        self.tab_widget.addTab(self.tab_behavior, tr("settings.behavior"))
        self.tab_widget.addTab(self.tab_about, tr("settings.about"))
        
        layout.addWidget(self.tab_widget)
    
    def update_texts(self):
        """Update all UI texts with current language."""
        self.lbl_title.setText(f"<h2>{tr('settings.title')}</h2>")
        
        # Update tab titles
        self.tab_widget.setTabText(0, tr("settings.appearance"))
        self.tab_widget.setTabText(1, tr("settings.paths"))
        self.tab_widget.setTabText(2, tr("settings.behavior"))
        self.tab_widget.setTabText(3, tr("settings.about"))
        
        # Update sub-tabs
        self.tab_appearance.update_texts()
        self.tab_config.update_texts()
        self.tab_behavior.update_texts()
        self.tab_about.update_texts()
