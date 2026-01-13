"""
Settings Tab - Application Settings
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from src.utils.locale_manager import LocaleManager, tr
from src.core.settings_manager import SettingsManager
from src.core.app_config import AppConfigManager
from src.core.default_restore import restore_server_defaults


class SettingsTab(QWidget):
    """Tab for application settings."""
    
    language_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.locale = LocaleManager()
        self.app_config = AppConfigManager()
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        self.lbl_title = QLabel(f"<h2>{tr('settings.title')}</h2>")
        layout.addWidget(self.lbl_title)
        
        # Language section
        lang_box = QGroupBox(tr("settings.language"))
        lang_layout = QFormLayout(lang_box)
        
        self.cmb_language = QComboBox()
        self.cmb_language.addItem("English", "en")
        self.cmb_language.addItem("Tiếng Việt", "vi")
        self.cmb_language.currentIndexChanged.connect(self._on_language_changed)
        
        self.lbl_lang_desc = QLabel(tr("settings.language_desc"))
        lang_layout.addRow(tr("settings.select_language") + ":", self.cmb_language)
        lang_layout.addRow("", self.lbl_lang_desc)
        
        layout.addWidget(lang_box)
        
        # Default paths section
        paths_box = QGroupBox(tr("settings.default_paths"))
        paths_layout = QFormLayout(paths_box)
        
        # Default workshop path
        ws_layout = QHBoxLayout()
        self.lbl_workshop_path = QLabel()
        self.lbl_workshop_path.setStyleSheet("color: gray;")
        ws_layout.addWidget(self.lbl_workshop_path, 1)
        self.btn_browse_workshop = QPushButton(tr("common.browse"))
        self.btn_browse_workshop.clicked.connect(self._browse_workshop)
        ws_layout.addWidget(self.btn_browse_workshop)
        paths_layout.addRow(tr("settings.default_workshop") + ":", ws_layout)
        
        # Default server path
        sv_layout = QHBoxLayout()
        self.lbl_server_path = QLabel()
        self.lbl_server_path.setStyleSheet("color: gray;")
        sv_layout.addWidget(self.lbl_server_path, 1)
        self.btn_browse_server = QPushButton(tr("common.browse"))
        self.btn_browse_server.clicked.connect(self._browse_server)
        sv_layout.addWidget(self.btn_browse_server)
        paths_layout.addRow(tr("settings.default_server") + ":", sv_layout)
        
        layout.addWidget(paths_box)
        
        # Data storage section
        storage_box = QGroupBox(tr("settings.data_storage"))
        storage_layout = QFormLayout(storage_box)
        
        self.chk_use_custom_storage = QCheckBox(tr("settings.use_custom_storage"))
        self.chk_use_custom_storage.stateChanged.connect(self._on_storage_toggle)
        storage_layout.addRow("", self.chk_use_custom_storage)
        
        # Data storage path
        data_layout = QHBoxLayout()
        self.lbl_data_path = QLabel()
        self.lbl_data_path.setStyleSheet("color: gray;")
        data_layout.addWidget(self.lbl_data_path, 1)
        self.btn_browse_data = QPushButton(tr("common.browse"))
        self.btn_browse_data.clicked.connect(self._browse_data_path)
        data_layout.addWidget(self.btn_browse_data)
        storage_layout.addRow(tr("settings.data_path") + ":", data_layout)
        
        # Profiles storage path
        profiles_layout = QHBoxLayout()
        self.lbl_profiles_path = QLabel()
        self.lbl_profiles_path.setStyleSheet("color: gray;")
        profiles_layout.addWidget(self.lbl_profiles_path, 1)
        self.btn_browse_profiles = QPushButton(tr("common.browse"))
        self.btn_browse_profiles.clicked.connect(self._browse_profiles_path)
        profiles_layout.addWidget(self.btn_browse_profiles)
        storage_layout.addRow(tr("settings.profiles_path") + ":", profiles_layout)
        
        self.lbl_storage_note = QLabel(tr("settings.storage_note"))
        self.lbl_storage_note.setStyleSheet("color: #ff9800; font-size: 11px;")
        self.lbl_storage_note.setWordWrap(True)
        storage_layout.addRow("", self.lbl_storage_note)
        
        layout.addWidget(storage_box)
        
        # Behavior section
        behavior_box = QGroupBox(tr("settings.behavior"))
        behavior_layout = QVBoxLayout(behavior_box)
        
        self.chk_auto_backup = QCheckBox(tr("settings.auto_backup"))
        self.chk_auto_backup.setChecked(True)
        self.chk_auto_backup.stateChanged.connect(self._on_setting_changed)
        behavior_layout.addWidget(self.chk_auto_backup)
        
        self.chk_confirm_actions = QCheckBox(tr("settings.confirm_actions"))
        self.chk_confirm_actions.setChecked(True)
        self.chk_confirm_actions.stateChanged.connect(self._on_setting_changed)
        behavior_layout.addWidget(self.chk_confirm_actions)
        
        self.chk_copy_bikeys = QCheckBox(tr("settings.auto_copy_bikeys"))
        self.chk_copy_bikeys.setChecked(True)
        self.chk_copy_bikeys.stateChanged.connect(self._on_setting_changed)
        behavior_layout.addWidget(self.chk_copy_bikeys)
        
        layout.addWidget(behavior_box)
        
        # Restore defaults section
        restore_box = QGroupBox(tr("settings.restore_section"))
        restore_layout = QVBoxLayout(restore_box)
        
        self.lbl_restore_desc = QLabel(tr("settings.restore_desc"))
        self.lbl_restore_desc.setWordWrap(True)
        restore_layout.addWidget(self.lbl_restore_desc)
        
        btn_layout = QHBoxLayout()
        self.btn_restore = QPushButton(f"🔄 {tr('settings.restore_defaults')}")
        self.btn_restore.clicked.connect(self._restore_defaults)
        btn_layout.addWidget(self.btn_restore)
        btn_layout.addStretch()
        restore_layout.addLayout(btn_layout)
        
        layout.addWidget(restore_box)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # About section
        about_box = QGroupBox(tr("settings.about"))
        about_layout = QVBoxLayout(about_box)
        
        version = self.app_config.version
        app_name = self.app_config.name
        
        self.lbl_about = QLabel(f"""
            <p><b>{app_name}</b></p>
            <p>{tr('settings.version')}: {version}</p>
            <p>{tr('settings.description')}</p>
        """)
        self.lbl_about.setTextFormat(Qt.RichText)
        about_layout.addWidget(self.lbl_about)
        
        layout.addWidget(about_box)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load current settings into UI."""
        # Language
        current_lang = self.settings.settings.language
        index = self.cmb_language.findData(current_lang)
        if index >= 0:
            self.cmb_language.setCurrentIndex(index)
        
        # Paths
        workshop = self.settings.settings.default_workshop_path or tr("settings.not_set")
        server = self.settings.settings.default_server_path or tr("settings.not_set")
        self.lbl_workshop_path.setText(workshop)
        self.lbl_server_path.setText(server)
        
        # Data storage
        self.chk_use_custom_storage.setChecked(self.settings.settings.use_custom_storage)
        data_path = self.settings.settings.data_storage_path or tr("settings.not_set")
        profiles_path = self.settings.settings.profiles_storage_path or tr("settings.not_set")
        self.lbl_data_path.setText(data_path)
        self.lbl_profiles_path.setText(profiles_path)
        self._update_storage_ui_state()
        
        # Behavior
        self.chk_auto_backup.setChecked(self.settings.settings.auto_backup)
        self.chk_confirm_actions.setChecked(self.settings.settings.confirm_actions)
        self.chk_copy_bikeys.setChecked(self.settings.settings.auto_copy_bikeys)
    
    def _update_storage_ui_state(self):
        """Enable/disable storage path controls based on checkbox."""
        enabled = self.chk_use_custom_storage.isChecked()
        self.btn_browse_data.setEnabled(enabled)
        self.btn_browse_profiles.setEnabled(enabled)
        self.lbl_data_path.setEnabled(enabled)
        self.lbl_profiles_path.setEnabled(enabled)
    
    def _on_storage_toggle(self, state):
        """Handle storage toggle checkbox change."""
        self._update_storage_ui_state()
        self.settings.settings.use_custom_storage = bool(state)
        self.settings.save()
    
    def _browse_data_path(self):
        """Browse for custom data storage path."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.select_data_path"),
            self.settings.settings.data_storage_path or ""
        )
        if folder:
            self.settings.settings.data_storage_path = folder
            self.settings.save()
            self.lbl_data_path.setText(folder)
    
    def _browse_profiles_path(self):
        """Browse for custom profiles storage path."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.select_profiles_path"),
            self.settings.settings.profiles_storage_path or ""
        )
        if folder:
            self.settings.settings.profiles_storage_path = folder
            self.settings.save()
            self.lbl_profiles_path.setText(folder)
    
    def _on_language_changed(self, index):
        """Handle language change."""
        lang = self.cmb_language.itemData(index)
        if lang:
            self.locale.set_language(lang)
            self.settings.settings.language = lang
            self.settings.save()
            self.language_changed.emit()
    
    def _on_setting_changed(self):
        """Handle setting checkbox change."""
        self.settings.settings.auto_backup = self.chk_auto_backup.isChecked()
        self.settings.settings.confirm_actions = self.chk_confirm_actions.isChecked()
        self.settings.settings.auto_copy_bikeys = self.chk_copy_bikeys.isChecked()
        self.settings.save()
    
    def _browse_workshop(self):
        """Browse for default workshop path."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.select_workshop"),
            self.settings.settings.default_workshop_path or ""
        )
        if folder:
            self.settings.settings.default_workshop_path = folder
            self.settings.save()
            self.lbl_workshop_path.setText(folder)
    
    def _browse_server(self):
        """Browse for default server path."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.select_server"),
            self.settings.settings.default_server_path or ""
        )
        if folder:
            self.settings.settings.default_server_path = folder
            self.settings.save()
            self.lbl_server_path.setText(folder)
    
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
                    tr("common.warning"),
                    tr("settings.restore_failed")
                )
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('settings.title')}</h2>")
        
        # Update workshop path display
        if self.settings.settings.default_workshop_path:
            self.lbl_workshop_path.setText(self.settings.settings.default_workshop_path)
        else:
            self.lbl_workshop_path.setText(tr("settings.not_set"))
        
        # Update server path display
        if self.settings.settings.default_server_path:
            self.lbl_server_path.setText(self.settings.settings.default_server_path)
        else:
            self.lbl_server_path.setText(tr("settings.not_set"))
        
        self.btn_browse_workshop.setText(tr("common.browse"))
        self.btn_browse_server.setText(tr("common.browse"))
        self.btn_browse_data.setText(tr("common.browse"))
        self.btn_browse_profiles.setText(tr("common.browse"))
        self.chk_use_custom_storage.setText(tr("settings.use_custom_storage"))
        self.lbl_storage_note.setText(tr("settings.storage_note"))
        self.chk_auto_backup.setText(tr("settings.auto_backup"))
        self.chk_confirm_actions.setText(tr("settings.confirm_actions"))
        self.chk_copy_bikeys.setText(tr("settings.auto_copy_bikeys"))
        self.btn_restore.setText(f"🔄 {tr('settings.restore_defaults')}")
        
        # Update data storage path display
        if self.settings.settings.data_storage_path:
            self.lbl_data_path.setText(self.settings.settings.data_storage_path)
        else:
            self.lbl_data_path.setText(tr("settings.not_set"))
        
        # Update profiles path display  
        if self.settings.settings.profiles_storage_path:
            self.lbl_profiles_path.setText(self.settings.settings.profiles_storage_path)
        else:
            self.lbl_profiles_path.setText(tr("settings.not_set"))
        
        # Refresh about section
        version = self.app_config.version
        app_name = self.app_config.name
        self.lbl_about.setText(f"""
            <p><b>{app_name}</b></p>
            <p>{tr('settings.version')}: {version}</p>
            <p>{tr('settings.description')}</p>
        """)
