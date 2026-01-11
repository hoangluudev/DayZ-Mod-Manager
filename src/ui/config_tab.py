"""
Config Tab - serverDZ.cfg Visual Editor
"""

import re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QMessageBox, QFileDialog, QComboBox, QScrollArea,
    QFrame, QToolTip
)
from PySide6.QtCore import Qt, QPoint

from src.utils.locale_manager import tr


# Configuration field definitions with tooltips
CONFIG_FIELDS = {
    "hostname": {
        "type": "text",
        "default": "DayZ Server",
        "tooltip": "config.tooltip.hostname"
    },
    "password": {
        "type": "text",
        "default": "",
        "tooltip": "config.tooltip.password"
    },
    "passwordAdmin": {
        "type": "text",
        "default": "",
        "tooltip": "config.tooltip.password_admin"
    },
    "maxPlayers": {
        "type": "int",
        "default": 60,
        "min": 1,
        "max": 127,
        "tooltip": "config.tooltip.max_players"
    },
    "verifySignatures": {
        "type": "int",
        "default": 2,
        "min": 0,
        "max": 2,
        "tooltip": "config.tooltip.verify_signatures"
    },
    "forceSameBuild": {
        "type": "bool",
        "default": True,
        "tooltip": "config.tooltip.force_same_build"
    },
    "disableVoN": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.disable_von"
    },
    "vonCodecQuality": {
        "type": "int",
        "default": 20,
        "min": 0,
        "max": 30,
        "tooltip": "config.tooltip.von_quality"
    },
    "enableWhitelist": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.whitelist"
    },
    "disable3rdPerson": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.disable_3p"
    },
    "disableCrosshair": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.disable_crosshair"
    },
    "serverTime": {
        "type": "text",
        "default": "SystemTime",
        "tooltip": "config.tooltip.server_time"
    },
    "serverTimeAcceleration": {
        "type": "int",
        "default": 1,
        "min": 0,
        "max": 64,
        "tooltip": "config.tooltip.time_accel"
    },
    "serverNightTimeAcceleration": {
        "type": "int",
        "default": 1,
        "min": 0,
        "max": 64,
        "tooltip": "config.tooltip.night_accel"
    },
    "serverTimePersistent": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.time_persistent"
    },
    "guaranteedUpdates": {
        "type": "bool",
        "default": True,
        "tooltip": "config.tooltip.guaranteed_updates"
    },
    "loginQueueConcurrentPlayers": {
        "type": "int",
        "default": 5,
        "min": 1,
        "max": 25,
        "tooltip": "config.tooltip.login_queue"
    },
    "loginQueueMaxPlayers": {
        "type": "int",
        "default": 500,
        "min": 1,
        "max": 500,
        "tooltip": "config.tooltip.login_queue_max"
    },
    "instanceId": {
        "type": "int",
        "default": 1,
        "min": 1,
        "max": 999,
        "tooltip": "config.tooltip.instance_id"
    },
    "storeHouseStateDisabled": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.store_house"
    },
    "storageAutoFix": {
        "type": "bool",
        "default": True,
        "tooltip": "config.tooltip.storage_fix"
    },
    "respawnTime": {
        "type": "int",
        "default": 5,
        "min": 0,
        "max": 1800,
        "tooltip": "config.tooltip.respawn_time"
    },
    "timeStampFormat": {
        "type": "text",
        "default": "Short",
        "tooltip": "config.tooltip.timestamp"
    },
    "logAverageFps": {
        "type": "int",
        "default": 1,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.log_fps"
    },
    "logMemory": {
        "type": "int",
        "default": 1,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.log_memory"
    },
    "logPlayers": {
        "type": "int",
        "default": 1,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.log_players"
    },
    "adminLogPlayerHitsOnly": {
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.admin_log_hits"
    },
    "adminLogPlacement": {
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.admin_log_placement"
    },
    "adminLogBuildActions": {
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.admin_log_build"
    },
    "adminLogPlayerList": {
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.admin_log_list"
    },
    "lightingConfig": {
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 1,
        "tooltip": "config.tooltip.lighting"
    },
    "disablePersonalLight": {
        "type": "bool",
        "default": True,
        "tooltip": "config.tooltip.personal_light"
    },
    "disableBaseDamage": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.base_damage"
    },
    "disableContainerDamage": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.container_damage"
    },
    "disableRespawnDialog": {
        "type": "bool",
        "default": False,
        "tooltip": "config.tooltip.respawn_dialog"
    },
}


class ConfigTab(QWidget):
    """Tab for editing serverDZ.cfg visually."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self.cfg_path = None
        self.widgets = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        self.lbl_title = QLabel(f"<h2>{tr('config.title')}</h2>")
        header.addWidget(self.lbl_title)
        header.addStretch()
        
        self.btn_load = QPushButton(f"📂 {tr('config.load')}")
        self.btn_load.clicked.connect(self._load_config)
        header.addWidget(self.btn_load)
        
        self.btn_restore = QPushButton(f"🔄 {tr('settings.restore_defaults')}")
        self.btn_restore.clicked.connect(self._restore_defaults)
        header.addWidget(self.btn_restore)
        
        self.btn_save = QPushButton(f"💾 {tr('common.save')}")
        self.btn_save.clicked.connect(self._save_config)
        header.addWidget(self.btn_save)
        
        layout.addLayout(header)
        
        # No profile message
        self.lbl_no_profile = QLabel(tr("config.select_profile_first"))
        self.lbl_no_profile.setAlignment(Qt.AlignCenter)
        self.lbl_no_profile.setStyleSheet("color: gray; padding: 30px; font-size: 14px;")
        layout.addWidget(self.lbl_no_profile)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        
        # Current file indicator
        self.lbl_current_file = QLabel()
        self.lbl_current_file.setStyleSheet("color: #0078d4; font-size: 12px;")
        content_layout.addWidget(self.lbl_current_file)
        
        # Server Info section
        server_box = QGroupBox(tr("config.section.server_info"))
        server_form = QFormLayout(server_box)
        self._add_field(server_form, "hostname")
        self._add_field(server_form, "password")
        self._add_field(server_form, "passwordAdmin")
        self._add_field(server_form, "maxPlayers")
        self._add_field(server_form, "instanceId")
        content_layout.addWidget(server_box)
        
        # Security section
        security_box = QGroupBox(tr("config.section.security"))
        security_form = QFormLayout(security_box)
        self._add_field(security_form, "verifySignatures")
        self._add_field(security_form, "forceSameBuild")
        self._add_field(security_form, "enableWhitelist")
        content_layout.addWidget(security_box)
        
        # Gameplay section
        gameplay_box = QGroupBox(tr("config.section.gameplay"))
        gameplay_form = QFormLayout(gameplay_box)
        self._add_field(gameplay_form, "disableVoN")
        self._add_field(gameplay_form, "vonCodecQuality")
        self._add_field(gameplay_form, "disable3rdPerson")
        self._add_field(gameplay_form, "disableCrosshair")
        self._add_field(gameplay_form, "disableRespawnDialog")
        self._add_field(gameplay_form, "respawnTime")
        content_layout.addWidget(gameplay_box)
        
        # Time section
        time_box = QGroupBox(tr("config.section.time"))
        time_form = QFormLayout(time_box)
        self._add_field(time_form, "serverTime")
        self._add_field(time_form, "serverTimeAcceleration")
        self._add_field(time_form, "serverNightTimeAcceleration")
        self._add_field(time_form, "serverTimePersistent")
        self._add_field(time_form, "lightingConfig")
        self._add_field(time_form, "disablePersonalLight")
        content_layout.addWidget(time_box)
        
        # Performance section
        perf_box = QGroupBox(tr("config.section.performance"))
        perf_form = QFormLayout(perf_box)
        self._add_field(perf_form, "guaranteedUpdates")
        self._add_field(perf_form, "loginQueueConcurrentPlayers")
        self._add_field(perf_form, "loginQueueMaxPlayers")
        content_layout.addWidget(perf_box)
        
        # Storage section
        storage_box = QGroupBox(tr("config.section.storage"))
        storage_form = QFormLayout(storage_box)
        self._add_field(storage_form, "storeHouseStateDisabled")
        self._add_field(storage_form, "storageAutoFix")
        self._add_field(storage_form, "disableBaseDamage")
        self._add_field(storage_form, "disableContainerDamage")
        content_layout.addWidget(storage_box)
        
        # Logging section
        logging_box = QGroupBox(tr("config.section.logging"))
        logging_form = QFormLayout(logging_box)
        self._add_field(logging_form, "timeStampFormat")
        self._add_field(logging_form, "logAverageFps")
        self._add_field(logging_form, "logMemory")
        self._add_field(logging_form, "logPlayers")
        self._add_field(logging_form, "adminLogPlayerHitsOnly")
        self._add_field(logging_form, "adminLogPlacement")
        self._add_field(logging_form, "adminLogBuildActions")
        self._add_field(logging_form, "adminLogPlayerList")
        content_layout.addWidget(logging_box)
        
        content_layout.addStretch()
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        self.content_widget.setVisible(False)
    
    def _add_field(self, form: QFormLayout, field_name: str):
        """Add a config field to the form."""
        field_def = CONFIG_FIELDS.get(field_name)
        if not field_def:
            return
        
        field_type = field_def["type"]
        default = field_def["default"]
        tooltip_key = field_def.get("tooltip", "")
        
        # Create appropriate widget
        if field_type == "text":
            widget = QLineEdit()
            widget.setText(str(default))
        elif field_type == "int":
            widget = QSpinBox()
            widget.setRange(field_def.get("min", 0), field_def.get("max", 100000))
            widget.setValue(default)
        elif field_type == "bool":
            widget = QCheckBox()
            widget.setChecked(default)
        else:
            widget = QLineEdit()
            widget.setText(str(default))
        
        # Set tooltip
        if tooltip_key:
            tooltip = tr(tooltip_key)
            widget.setToolTip(tooltip)
        
        # Label with info icon
        label = QLabel(f"{field_name}:")
        label.setToolTip(tr(tooltip_key) if tooltip_key else "")
        
        form.addRow(label, widget)
        self.widgets[field_name] = widget
    
    def set_profile(self, profile_data: dict):
        """Set the current profile."""
        self.current_profile = profile_data
        self.lbl_no_profile.setVisible(False)
        self.content_widget.setVisible(True)
        
        # Try to load existing config
        server_path = profile_data.get("server_path", "")
        cfg_path = Path(server_path) / "serverDZ.cfg"
        if cfg_path.exists():
            self._load_cfg_file(cfg_path)
        else:
            self._restore_defaults()
    
    def _load_config(self):
        """Load a config file."""
        if self.current_profile:
            initial = self.current_profile.get("server_path", "")
        else:
            initial = ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("config.load"),
            initial,
            "Config Files (*.cfg);;All Files (*)"
        )
        
        if file_path:
            self._load_cfg_file(Path(file_path))
    
    def _load_cfg_file(self, path: Path):
        """Parse and load a cfg file."""
        try:
            content = path.read_text(encoding="utf-8")
            self.cfg_path = path
            self.lbl_current_file.setText(f"📄 {path}")
            
            # Parse each field
            for field_name, widget in self.widgets.items():
                pattern = rf'{field_name}\s*=\s*(.+?);'
                match = re.search(pattern, content)
                
                if match:
                    value = match.group(1).strip().strip('"')
                    
                    if isinstance(widget, QLineEdit):
                        widget.setText(value)
                    elif isinstance(widget, QSpinBox):
                        try:
                            widget.setValue(int(value))
                        except ValueError:
                            pass
                    elif isinstance(widget, QCheckBox):
                        widget.setChecked(value.lower() in ("1", "true"))
                        
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _restore_defaults(self):
        """Restore all fields to default values."""
        for field_name, field_def in CONFIG_FIELDS.items():
            widget = self.widgets.get(field_name)
            if not widget:
                continue
            
            default = field_def["default"]
            
            if isinstance(widget, QLineEdit):
                widget.setText(str(default))
            elif isinstance(widget, QSpinBox):
                widget.setValue(default)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(default)
        
        self.cfg_path = None
        self.lbl_current_file.setText(f"✨ {tr('config.new_config')}")
    
    def _save_config(self):
        """Save the config file."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("config.select_profile_first"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        save_path = server_path / "serverDZ.cfg"
        
        try:
            content = self._generate_cfg_content()
            save_path.write_text(content, encoding="utf-8")
            self.cfg_path = save_path
            self.lbl_current_file.setText(f"📄 {save_path}")
            QMessageBox.information(self, tr("common.success"), tr("config.saved"))
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _generate_cfg_content(self) -> str:
        """Generate the cfg file content from form values."""
        lines = [
            "// serverDZ.cfg",
            "// DayZ Server Configuration",
            "// Generated by DayZ Mod Manager",
            ""
        ]
        
        for field_name, widget in self.widgets.items():
            field_def = CONFIG_FIELDS.get(field_name, {})
            field_type = field_def.get("type", "text")
            
            if isinstance(widget, QLineEdit):
                value = f'"{widget.text()}"'
            elif isinstance(widget, QSpinBox):
                value = str(widget.value())
            elif isinstance(widget, QCheckBox):
                value = "1" if widget.isChecked() else "0"
            else:
                value = '""'
            
            lines.append(f'{field_name} = {value};')
        
        # Add mods section placeholder
        lines.extend([
            "",
            "// Mods (managed by DayZ Mod Manager)",
            'Mods = "";',
            'serverMod = "";',
            ""
        ])
        
        return "\n".join(lines)
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('config.title')}</h2>")
        self.btn_load.setText(f"📂 {tr('config.load')}")
        self.btn_restore.setText(f"🔄 {tr('settings.restore_defaults')}")
        self.btn_save.setText(f"💾 {tr('common.save')}")
        self.lbl_no_profile.setText(tr("config.select_profile_first"))
