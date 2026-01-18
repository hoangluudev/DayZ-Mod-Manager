"""
Settings Tab - Application Settings with sub-tabs for organization
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QFrame, QTabWidget, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices

from src.utils.locale_manager import LocaleManager, tr
from src.core.settings_manager import SettingsManager
from src.core.app_config import AppConfigManager
from src.core.default_restore import restore_server_defaults
from src.ui.widgets import SectionBox, PathSelector, IconButton
from src.ui.icons import Icons
from src.ui.theme_manager import ThemeManager
from src.ui.base import BaseTab, BaseSubTab
from src.ui.factories import create_action_button


class AppearanceTab(BaseSubTab):
    """Appearance settings sub-tab (Theme, Language)."""
    
    language_changed = Signal()
    theme_changed = Signal(str)
    
    def __init__(self, settings: SettingsManager, locale: LocaleManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.locale = locale
        self._setup_content()
        self._load_settings()
    
    def _setup_content(self):
        
        # Language Section
        self.lang_box = SectionBox(tr("settings.language"))
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
        
        self.lang_box.add_layout(lang_form)
        self.add_widget(self.lang_box)
        
        # Date Format Section
        self.date_box = SectionBox(tr("settings.date_format"))
        date_form = QFormLayout()
        date_form.setSpacing(12)
        
        self.cmb_date_format = QComboBox()
        self.cmb_date_format.addItem("dd/MM/yyyy (31/12/2024)", "dd/MM/yyyy")
        self.cmb_date_format.addItem("MM/dd/yyyy (12/31/2024)", "MM/dd/yyyy")
        self.cmb_date_format.addItem("yyyy-MM-dd (2024-12-31)", "yyyy-MM-dd")
        self.cmb_date_format.addItem("yyyy/MM/dd (2024/12/31)", "yyyy/MM/dd")
        self.cmb_date_format.addItem("dd-MM-yyyy (31-12-2024)", "dd-MM-yyyy")
        self.cmb_date_format.addItem("dd.MM.yyyy (31.12.2024)", "dd.MM.yyyy")
        self.cmb_date_format.currentIndexChanged.connect(self._on_date_format_changed)
        date_form.addRow(tr("settings.select_date_format") + ":", self.cmb_date_format)
        
        self.lbl_date_desc = QLabel(tr("settings.date_format_desc"))
        self.lbl_date_desc.setStyleSheet("color: gray; font-size: 11px;")
        date_form.addRow("", self.lbl_date_desc)
        
        self.date_box.add_layout(date_form)
        self.add_widget(self.date_box)
        
        # Theme Section - CurseForge-style theme cards
        self.theme_box = SectionBox(tr("settings.theme"))
        theme_layout = QVBoxLayout()
        theme_layout.setSpacing(10)

        self.lbl_theme_desc = QLabel(tr("settings.theme_desc"))
        self.lbl_theme_desc.setStyleSheet("color: gray; font-size: 11px;")
        theme_layout.addWidget(self.lbl_theme_desc)

        # Scrollable grid of theme cards
        self.theme_scroll = QScrollArea()
        self.theme_scroll.setWidgetResizable(True)
        self.theme_scroll.setFrameShape(QFrame.NoFrame)

        self.theme_grid_host = QWidget()
        self.theme_grid = QGridLayout(self.theme_grid_host)
        self.theme_grid.setContentsMargins(0, 0, 0, 0)
        self.theme_grid.setHorizontalSpacing(12)
        self.theme_grid.setVerticalSpacing(12)
        self.theme_scroll.setWidget(self.theme_grid_host)
        theme_layout.addWidget(self.theme_scroll)

        self.theme_box.add_layout(theme_layout)
        self.add_widget(self.theme_box)
        
        self.add_stretch()

    def _rebuild_theme_cards(self):
        # Clear existing cards
        while self.theme_grid.count():
            item = self.theme_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        from src.ui.themes import ThemeRegistry

        self._theme_cards = {}
        themes = ThemeRegistry.get_theme_list()  # [(id, name), ...]
        current_theme_id = self.settings.settings.theme

        # 2-column layout like CurseForge
        cols = 2
        row = 0
        col = 0
        for theme_id, _ in themes:
            pack = ThemeRegistry.get(theme_id)
            if pack is None:
                continue

            display_name = pack.name
            if theme_id == "default":
                # Localized display name for the default theme.
                display_name = tr("theme.default")

            card = QFrame()
            card.setObjectName("themeCard")
            card.setProperty("selected", theme_id == current_theme_id)
            card.setCursor(Qt.PointingHandCursor)

            outer = QVBoxLayout(card)
            outer.setContentsMargins(12, 12, 12, 12)
            outer.setSpacing(10)

            # Preview area (CurseForge-like): accent block + skeleton bars
            preview = QFrame()
            preview.setObjectName("themeCardPreview")
            preview.setFixedHeight(52)
            preview_l = QHBoxLayout(preview)
            preview_l.setContentsMargins(10, 10, 10, 10)
            preview_l.setSpacing(10)

            preview_accent = QFrame()
            preview_accent.setObjectName("themeCardAccent")
            preview_accent.setFixedSize(32, 32)
            preview_accent.setStyleSheet(
                f"background-color: {pack.colors.accent}; border-radius: 10px;"
            )
            preview_l.addWidget(preview_accent)

            bars_col = QVBoxLayout()
            bars_col.setContentsMargins(0, 0, 0, 0)
            bars_col.setSpacing(6)

            bar1 = QFrame()
            bar1.setObjectName("themeCardSkeleton")
            bar1.setFixedHeight(10)
            bar1.setStyleSheet(
                f"background-color: {pack.colors.surface}; border-radius: 6px;"
            )
            bar2 = QFrame()
            bar2.setObjectName("themeCardSkeleton")
            bar2.setFixedHeight(10)
            bar2.setStyleSheet(
                f"background-color: {pack.colors.background_tertiary}; border-radius: 6px;"
            )

            bars_col.addWidget(bar1)
            bars_col.addWidget(bar2)
            preview_l.addLayout(bars_col, stretch=1)
            outer.addWidget(preview)

            # Bottom row: name + optional desc + selected check icon
            bottom = QHBoxLayout()
            bottom.setContentsMargins(0, 0, 0, 0)
            bottom.setSpacing(10)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(2)

            name = QLabel(display_name)
            name.setObjectName("themeCardName")
            text_col.addWidget(name)

            if pack.description:
                desc = QLabel(pack.description or "")
                desc.setObjectName("themeCardDesc")
                desc.setWordWrap(True)
                text_col.addWidget(desc)

            bottom.addLayout(text_col, stretch=1)

            check = QLabel()
            check.setObjectName("themeCheck")
            check.setFixedSize(22, 22)
            check.setAlignment(Qt.AlignCenter)
            if theme_id == current_theme_id:
                check.setPixmap(Icons.get_icon("check", color=pack.colors.accent, size=18).pixmap(18, 18))
            bottom.addWidget(check, alignment=Qt.AlignRight | Qt.AlignVCenter)
            outer.addLayout(bottom)

            def _on_click(_evt=None, tid=theme_id):
                self._select_theme_card(tid)

            card.mousePressEvent = _on_click  # type: ignore[attr-defined]

            self._theme_cards[theme_id] = (card, check)

            self.theme_grid.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

        # Fill remaining space
        self.theme_grid.setColumnStretch(0, 1)
        self.theme_grid.setColumnStretch(1, 1)

    def _select_theme_card(self, theme_id: str):
        if not theme_id:
            return

        # Persist
        self.settings.settings.theme = theme_id
        self.settings.save()

        # Apply
        ThemeManager.apply_theme(theme_id)
        self.theme_changed.emit(theme_id)

        # Update UI selection
        for tid, (card, check) in getattr(self, "_theme_cards", {}).items():
            selected = tid == theme_id
            card.setProperty("selected", selected)
            if selected:
                from src.ui.themes import ThemeRegistry
                pack = ThemeRegistry.get(tid) or ThemeRegistry.get_default()
                check.setPixmap(Icons.get_icon("check", color=pack.colors.accent, size=18).pixmap(18, 18))
            else:
                check.clear()
            card.style().unpolish(card)
            card.style().polish(card)
    
    def _load_settings(self):
        """Load current settings into UI."""
        # Language
        current_lang = self.settings.settings.language
        index = self.cmb_language.findData(current_lang)
        if index >= 0:
            self.cmb_language.setCurrentIndex(index)
                # Date format
        current_date_format = self.settings.settings.datetime_format
        index = self.cmb_date_format.findData(current_date_format)
        if index >= 0:
            self.cmb_date_format.setCurrentIndex(index)
                # Theme cards
        self._rebuild_theme_cards()
    
    def _on_language_changed(self, index):
        """Handle language change."""
        lang = self.cmb_language.itemData(index)
        if lang:
            self.locale.set_language(lang)
            self.settings.settings.language = lang
            self.settings.save()
            self.language_changed.emit()

    def _on_date_format_changed(self, index):
        """Handle date format change."""
        date_format = self.cmb_date_format.itemData(index)
        if date_format:
            self.settings.settings.datetime_format = date_format
            self.settings.save()

    def update_texts(self):
        """Update UI texts."""
        self.lang_box.setTitle(tr("settings.language"))
        self.lbl_lang_desc.setText(tr("settings.language_desc"))
        self.date_box.setTitle(tr("settings.date_format"))
        self.lbl_date_desc.setText(tr("settings.date_format_desc"))
        self.theme_box.setTitle(tr("settings.theme"))
        self.lbl_theme_desc.setText(tr("settings.theme_desc"))
        # Rebuild cards so any translated strings (if added later) refresh.
        try:
            self._rebuild_theme_cards()
        except Exception:
            pass


class ConfigTab(BaseSubTab):
    """Configuration settings sub-tab (Paths, Storage)."""
    
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._setup_content()
        self._load_settings()
    
    def _setup_content(self):

        # Config Files Section (shows independent generated configs)
        try:
            from src.core.storage_paths import (
                get_configs_path,
                get_settings_file_path,
                get_app_config_file_path,
            )
        except Exception:
            get_configs_path = None  # type: ignore
            get_settings_file_path = None  # type: ignore
            get_app_config_file_path = None  # type: ignore

        if get_settings_file_path and get_app_config_file_path:
            self.files_box = SectionBox(tr("settings.config_files"))
            files_layout = QVBoxLayout()
            files_layout.setSpacing(10)

            files_form = QFormLayout()
            files_form.setSpacing(8)

            self.lbl_settings_file = QLabel(str(get_settings_file_path()))
            self.lbl_settings_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
            files_form.addRow(tr("settings.settings_file") + ":", self.lbl_settings_file)

            self.lbl_app_file = QLabel(str(get_app_config_file_path()))
            self.lbl_app_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
            files_form.addRow(tr("settings.app_config_file") + ":", self.lbl_app_file)

            files_layout.addLayout(files_form)

            btn_open = IconButton(icon_name="folder", text=tr("settings.open_config_folder"), size=16)
            btn_open.clicked.connect(lambda: self._open_configs_folder(get_configs_path() if get_configs_path else None))
            files_layout.addWidget(btn_open, alignment=Qt.AlignLeft)

            self.files_box.add_layout(files_layout)
            self.add_widget(self.files_box)
        
        # Default Paths Section
        self.paths_box = SectionBox(tr("settings.default_paths"))
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
        
        self.paths_box.add_layout(paths_form)
        self.add_widget(self.paths_box)
        
        # Data Storage Section
        self.storage_box = SectionBox(tr("settings.data_storage"))
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
        
        self.storage_box.add_layout(storage_layout)
        self.add_widget(self.storage_box)
        
        # Restore Defaults Section
        self.restore_box = SectionBox(tr("settings.restore_section"))
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
        
        self.restore_box.add_layout(restore_layout)
        self.add_widget(self.restore_box)
        
        self.add_stretch()

    def _open_configs_folder(self, path: Path | None):
        try:
            if path is None:
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception:
            pass
    
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
        if hasattr(self, 'files_box'):
            self.files_box.setTitle(tr("settings.config_files"))
        self.paths_box.setTitle(tr("settings.default_paths"))
        self.storage_box.setTitle(tr("settings.data_storage"))
        self.restore_box.setTitle(tr("settings.restore_section"))
        self.lbl_storage_note.setText(tr("settings.storage_note"))
        self.lbl_restore_desc.setText(tr("settings.restore_desc"))
        self.chk_custom_storage.setText(tr("settings.use_custom_storage"))


class BehaviorTab(BaseSubTab):
    """Behavior settings sub-tab."""
    
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._setup_content()
        self._load_settings()
    
    def _setup_content(self):
        
        # Behavior Section
        self.behavior_box = SectionBox(tr("settings.behavior"))
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
        
        self.behavior_box.add_layout(behavior_layout)
        self.add_widget(self.behavior_box)
        
        self.add_stretch()
    
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
        self.behavior_box.setTitle(tr("settings.behavior"))
        self.chk_auto_backup.setText(tr("settings.auto_backup"))
        self.chk_confirm_actions.setText(tr("settings.confirm_actions"))
        self.chk_copy_bikeys.setText(tr("settings.auto_copy_bikeys"))


class AboutTab(BaseSubTab):
    """About sub-tab."""
    
    def __init__(self, app_config: AppConfigManager, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self._setup_content()
    
    def _setup_content(self):
        
        # About Section
        self.about_box = SectionBox(tr("settings.about"))
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
        
        self.about_box.add_layout(about_layout)
        self.add_widget(self.about_box)
        
        self.add_stretch()
    
    def update_texts(self):
        """Update UI texts."""
        self.about_box.setTitle(tr("settings.about"))
        # Texts are static, but the logo may change with theme.
        try:
            self.logo_label.setPixmap(Icons.get_app_logo_pixmap(size=96, variant="auto"))
        except Exception:
            pass


class SettingsTab(BaseTab):
    """Tab for application settings with sub-tabs."""
    
    language_changed = Signal()
    theme_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent, scrollable=False, title_key="settings.title")
        self.settings = SettingsManager()
        self.locale = LocaleManager()
        self.app_config = AppConfigManager()
        
        self._setup_content()
    
    def _setup_content(self):
        # Tab widget for sub-tabs
        self.tab_widget = QTabWidget()
        
        # Create sub-tabs
        self.tab_appearance = AppearanceTab(self.settings, self.locale)
        self.tab_appearance.language_changed.connect(self.language_changed.emit)
        self.tab_appearance.theme_changed.connect(self.theme_changed.emit)
        
        self.tab_config = ConfigTab(self.settings)
        self.tab_behavior = BehaviorTab(self.settings)
        self.tab_about = AboutTab(self.app_config)
        
        # Add sub-tabs
        self.tab_widget.addTab(self.tab_appearance, tr("settings.appearance"))
        self.tab_widget.addTab(self.tab_config, tr("settings.paths"))
        self.tab_widget.addTab(self.tab_behavior, tr("settings.behavior"))
        self.tab_widget.addTab(self.tab_about, tr("settings.about"))
        
        self.add_widget(self.tab_widget)
    
    def update_texts(self):
        """Update all UI texts with current language."""
        super().update_texts()
        
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
