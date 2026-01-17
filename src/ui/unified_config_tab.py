"""
Unified Configuration Tab - Combines Launcher and Server Config with change tracking.
Refactored to use BaseTab pattern and centralized constants.
"""

import re
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QMessageBox, QFileDialog, QComboBox, QScrollArea,
    QFrame, QTabWidget, QDialog
)
from PySide6.QtCore import Qt, Signal

from src.utils.locale_manager import tr
from src.core.default_restore import default_start_bat_template
from src.ui.theme_manager import ThemeManager
from src.ui.config_manager import (
    ConfigChangeManager, ConfigSnapshot, ChangePreviewDialog
)
from src.ui.widgets import IconButton
from src.ui.server_resources_tab import ResourcesBrowserWidget
from src.ui.highlighters import ModsListHighlighter
from src.ui.dialogs.mod_sort_dialog import ModSortDialog
from src.ui.dialogs.mission_merge_dialog import MissionConfigMergeDialog
from src.constants.config import (
    CONFIG_FIELDS, ConfigFieldDef, AVAILABLE_MAPS, 
    LAUNCHER_DEFAULTS, get_mod_priority
)
from src.core.process_utils import is_dayz_server_running


class UnifiedConfigTab(QWidget):
    """
    Unified Configuration Tab combining Launcher and Server Config.
    Features change tracking with save/restore functionality.
    """
    
    config_saved = Signal()  # Emitted when config is saved
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self.change_manager = ConfigChangeManager()
        self._loading = False  # Flag to prevent change detection during load
        self.config_widgets = {}  # Will store server config widgets
        
        self._setup_ui()
        self._connect_change_signals()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header with action buttons
        self._setup_header(layout)
        
        # No profile message
        self.lbl_no_profile = QLabel(tr("config.select_profile_first"))
        self.lbl_no_profile.setAlignment(Qt.AlignCenter)
        self.lbl_no_profile.setStyleSheet("color: gray; padding: 30px; font-size: 14px;")
        layout.addWidget(self.lbl_no_profile)
        
        # Content with sub-tabs
        self._setup_content(layout)
        
        # Connect change manager signal
        self.change_manager.changes_detected.connect(self._on_changes_detected)
    
    def _setup_header(self, layout: QVBoxLayout):
        """Setup header with title and action buttons."""
        header = QHBoxLayout()
        
        self.lbl_title = QLabel(f"<h2>{tr('config.unified_title')}</h2>")
        header.addWidget(self.lbl_title)
        header.addStretch()

        # Mission config merger
        self.btn_mission_merger_header = IconButton("cog", tr("mission_merge.open_mission_merger"), size=16)
        self.btn_mission_merger_header.setEnabled(False)
        self.btn_mission_merger_header.clicked.connect(self._open_mission_merger)
        header.addWidget(self.btn_mission_merger_header)
        
        # Restore button
        self.btn_restore = IconButton("undo", tr("config.restore_changes"), size=16)
        self.btn_restore.setEnabled(False)
        self.btn_restore.clicked.connect(self._restore_changes)
        header.addWidget(self.btn_restore)
        
        # Preview & Save button
        self.btn_save = IconButton("save", tr("common.save"), size=16)
        self.btn_save.setObjectName("primary")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._preview_and_save)
        header.addWidget(self.btn_save)
        
        layout.addLayout(header)
    
    def _setup_content(self, layout: QVBoxLayout):
        """Setup main content area with tabs."""
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Change indicator
        self.change_indicator = QFrame()
        self.change_indicator.setFixedHeight(4)
        self.change_indicator.setStyleSheet("background-color: transparent;")
        content_layout.addWidget(self.change_indicator)
        
        # Tab widget for sub-sections
        self.tabs = QTabWidget()
        
        # Create sub-tabs
        self.tab_launcher = self._create_launcher_tab()
        self.tab_server_config = self._create_server_config_tab()

        # Embedded resource browsers
        self.tab_map_resources = ResourcesBrowserWidget()
        self.tab_mods_resources = ResourcesBrowserWidget()
        
        self.tabs.addTab(self.tab_launcher, tr("config.tab_launcher"))
        self.tabs.addTab(self.tab_server_config, tr("config.tab_server"))
        self.tabs.addTab(self.tab_map_resources, tr("config.tab_map_resources"))
        self.tabs.addTab(self.tab_mods_resources, tr("config.tab_mods_resources"))
        
        content_layout.addWidget(self.tabs)
        
        layout.addWidget(self.content_widget)
        self.content_widget.setVisible(False)

    # ==================== Launcher Tab ====================
    
    def _create_launcher_tab(self) -> QWidget:
        """Create the Launcher configuration sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Current file indicator
        self.lbl_bat_file = QLabel()
        self.lbl_bat_file.setStyleSheet(
            f"color: {ThemeManager.get_accent_color()}; font-size: 12px;"
        )
        scroll_layout.addWidget(self.lbl_bat_file)
        
        # Basic Settings section
        scroll_layout.addWidget(self._create_basic_settings_section())
        
        # Launch Flags section
        scroll_layout.addWidget(self._create_flags_section())
        
        # Mods section
        scroll_layout.addWidget(self._create_mods_section())
        
        # Preview section
        scroll_layout.addWidget(self._create_preview_section())
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_basic_settings_section(self) -> QGroupBox:
        """Create basic settings group box."""
        basic_box = QGroupBox(tr("launcher.basic_settings"))
        basic_form = QFormLayout(basic_box)
        
        self.txt_server_name = QLineEdit()
        self.txt_server_name.setPlaceholderText("DayZ_Server")
        basic_form.addRow(tr("launcher.server_name") + ":", self.txt_server_name)
        
        loc_layout = QHBoxLayout()
        self.txt_server_location = QLineEdit()
        self.txt_server_location.setPlaceholderText("D:\\DayZServer")
        loc_layout.addWidget(self.txt_server_location)
        btn_browse = QPushButton(tr("common.browse"))
        btn_browse.clicked.connect(self._browse_location)
        loc_layout.addWidget(btn_browse)
        basic_form.addRow(tr("launcher.server_location") + ":", loc_layout)
        
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(LAUNCHER_DEFAULTS.port)
        basic_form.addRow(tr("launcher.param_port") + ":", self.spin_port)
        
        self.txt_config = QLineEdit()
        self.txt_config.setText(LAUNCHER_DEFAULTS.config_file)
        basic_form.addRow(tr("launcher.param_config") + ":", self.txt_config)
        
        self.spin_cpu = QSpinBox()
        self.spin_cpu.setRange(1, 64)
        self.spin_cpu.setValue(LAUNCHER_DEFAULTS.cpu_count)
        basic_form.addRow(tr("launcher.param_cpu") + ":", self.spin_cpu)
        
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(60, 999999)
        self.spin_timeout.setValue(LAUNCHER_DEFAULTS.timeout)
        self.spin_timeout.setSuffix(f" {tr('launcher.seconds')}")
        basic_form.addRow(tr("launcher.restart_timeout") + ":", self.spin_timeout)
        
        return basic_box
    
    def _create_flags_section(self) -> QGroupBox:
        """Create launch flags group box."""
        flags_box = QGroupBox(tr("launcher.flags"))
        flags_layout = QHBoxLayout(flags_box)
        
        self.chk_dologs = QCheckBox("-doLogs")
        self.chk_dologs.setChecked(LAUNCHER_DEFAULTS.do_logs)
        flags_layout.addWidget(self.chk_dologs)
        
        self.chk_adminlog = QCheckBox("-adminLog")
        self.chk_adminlog.setChecked(LAUNCHER_DEFAULTS.admin_log)
        flags_layout.addWidget(self.chk_adminlog)
        
        self.chk_netlog = QCheckBox("-netLog")
        self.chk_netlog.setChecked(LAUNCHER_DEFAULTS.net_log)
        flags_layout.addWidget(self.chk_netlog)
        
        self.chk_freezecheck = QCheckBox("-freezeCheck")
        self.chk_freezecheck.setChecked(LAUNCHER_DEFAULTS.freeze_check)
        flags_layout.addWidget(self.chk_freezecheck)
        
        flags_layout.addStretch()
        return flags_box
    
    def _create_mods_section(self) -> QGroupBox:
        """Create mods configuration group box."""
        mods_box = QGroupBox(tr("launcher.param_mods"))
        mods_layout = QVBoxLayout(mods_box)
        
        # Header with controls
        mods_header = QHBoxLayout()
        
        self.chk_use_mods_file = QCheckBox(tr("launcher.use_mods_file"))
        self.chk_use_mods_file.setChecked(LAUNCHER_DEFAULTS.use_mods_file)
        self.chk_use_mods_file.setToolTip(tr("launcher.mods_file_tooltip"))
        mods_header.addWidget(self.chk_use_mods_file)
        
        mods_header.addStretch()
        
        btn_load_mods = IconButton("download", tr("launcher.load_installed_mods"), size=14)
        btn_load_mods.clicked.connect(self._load_mods_from_server)
        mods_header.addWidget(btn_load_mods)
        
        btn_fix_mods = IconButton("check", tr("launcher.fix_mods_format"), size=14)
        btn_fix_mods.clicked.connect(self._fix_mods_format_clicked)
        mods_header.addWidget(btn_fix_mods)

        btn_sort_mods = IconButton("sort", tr("launcher.sort_mods"), size=14)
        btn_sort_mods.clicked.connect(self._open_sort_dialog)
        mods_header.addWidget(btn_sort_mods)
        
        mods_layout.addLayout(mods_header)
        
        # Mods text area
        self.txt_mods = QTextEdit()
        self.txt_mods.setPlaceholderText("@CF;@Dabs Framework;@VPPAdminTools;...")
        self.txt_mods.setMaximumHeight(100)
        mods_layout.addWidget(self.txt_mods)
        
        self.lbl_mods_info = QLabel()
        self.lbl_mods_info.setStyleSheet("color: gray; font-size: 11px;")
        mods_layout.addWidget(self.lbl_mods_info)

        self.lbl_mods_warnings = QLabel("")
        self.lbl_mods_warnings.setWordWrap(True)
        self.lbl_mods_warnings.setStyleSheet("color: #f0ad4e; font-size: 11px;")
        mods_layout.addWidget(self.lbl_mods_warnings)

        # Highlight formatting issues
        self._mods_highlighter = ModsListHighlighter(self.txt_mods.document())
        
        return mods_box
    
    def _create_preview_section(self) -> QGroupBox:
        """Create batch file preview group box."""
        preview_box = QGroupBox(tr("launcher.preview"))
        preview_layout = QVBoxLayout(preview_box)
        
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setStyleSheet("font-family: Consolas, monospace;")
        self.txt_preview.setMinimumHeight(150)
        preview_layout.addWidget(self.txt_preview)
        
        return preview_box

    # ==================== Server Config Tab ====================
    
    def _create_server_config_tab(self) -> QWidget:
        """Create the Server Config sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Current file indicator
        self.lbl_cfg_file = QLabel()
        self.lbl_cfg_file.setStyleSheet(
            f"color: {ThemeManager.get_accent_color()}; font-size: 12px;"
        )
        scroll_layout.addWidget(self.lbl_cfg_file)
        
        # Create config sections
        sections = [
            ("config.section.server_info", ["hostname", "password", "passwordAdmin", "maxPlayers", "instanceId"]),
            ("config.section.security", ["verifySignatures", "forceSameBuild", "enableWhitelist"]),
            ("config.section.gameplay", ["disableVoN", "vonCodecQuality", "disable3rdPerson", "disableCrosshair", "disableRespawnDialog", "respawnTime"]),
            ("config.section.time", ["serverTime", "serverTimeAcceleration", "serverNightTimeAcceleration", "serverTimePersistent"]),
            ("config.section.performance", ["guaranteedUpdates", "loginQueueConcurrentPlayers", "loginQueueMaxPlayers"]),
            ("config.section.storage", ["storeHouseStateDisabled", "storageAutoFix", "disableBaseDamage", "disableContainerDamage"]),
        ]
        
        for title_key, fields in sections:
            scroll_layout.addWidget(self._create_config_section(title_key, fields))
        
        # Mission/Map section
        scroll_layout.addWidget(self._create_mission_section())
        
        # Mission Config Merger button
        merger_box = QGroupBox(tr("mission_merge.title"))
        merger_layout = QVBoxLayout(merger_box)
        
        merger_info = QLabel(tr("mission_merge.open_mission_merger"))
        merger_info.setStyleSheet("color: gray; font-size: 11px;")
        merger_layout.addWidget(merger_info)
        
        self.btn_mission_merger = IconButton("cog", tr("mission_merge.open_mission_merger"), size=16)
        self.btn_mission_merger.clicked.connect(self._open_mission_merger)
        merger_layout.addWidget(self.btn_mission_merger)
        
        scroll_layout.addWidget(merger_box)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_config_section(self, title_key: str, field_names: list) -> QGroupBox:
        """Create a configuration section with fields."""
        group = QGroupBox(tr(title_key))
        form = QFormLayout(group)
        
        for field_name in field_names:
            self._add_config_field(form, field_name)
        
        return group
    
    def _add_config_field(self, form: QFormLayout, field_name: str):
        """Add a config field to the form."""
        field_def = CONFIG_FIELDS.get(field_name)
        if not field_def:
            return
        
        widget = self._create_field_widget(field_def)
        
        if field_def.tooltip_key:
            widget.setToolTip(tr(field_def.tooltip_key))
        
        form.addRow(QLabel(f"{field_name}:"), widget)
        self.config_widgets[field_name] = widget
    
    def _create_field_widget(self, field_def: ConfigFieldDef) -> QWidget:
        """Create appropriate widget for field type."""
        if field_def.type == "text":
            widget = QLineEdit()
            widget.setText(str(field_def.default))
        elif field_def.type == "int":
            widget = QSpinBox()
            widget.setRange(field_def.min_val or 0, field_def.max_val or 100000)
            widget.setValue(field_def.default)
        elif field_def.type == "bool":
            widget = QCheckBox()
            widget.setChecked(field_def.default)
        else:
            widget = QLineEdit()
            widget.setText(str(field_def.default))
        return widget
    
    def _create_mission_section(self) -> QGroupBox:
        """Create mission/map selection section."""
        mission_box = QGroupBox(tr("config.section.mission"))
        mission_form = QFormLayout(mission_box)
        
        self.cmb_map = QComboBox()
        for map_opt in AVAILABLE_MAPS:
            self.cmb_map.addItem(map_opt.display_name, map_opt.template)
        mission_form.addRow(tr("config.map") + ":", self.cmb_map)
        
        return mission_box

    # ==================== Change Tracking ====================
    
    def _connect_change_signals(self):
        """Connect widget signals to detect changes."""
        # Launcher widgets
        self.txt_server_name.textChanged.connect(lambda: self._on_launcher_changed("server_name", self.txt_server_name.text()))
        self.txt_server_location.textChanged.connect(lambda: self._on_launcher_changed("server_location", self.txt_server_location.text()))
        self.spin_port.valueChanged.connect(lambda v: self._on_launcher_changed("port", v))
        self.txt_config.textChanged.connect(lambda: self._on_launcher_changed("config_file", self.txt_config.text()))
        self.spin_cpu.valueChanged.connect(lambda v: self._on_launcher_changed("cpu_count", v))
        self.spin_timeout.valueChanged.connect(lambda v: self._on_launcher_changed("timeout", v))
        
        self.chk_dologs.stateChanged.connect(lambda s: self._on_launcher_changed("do_logs", s == Qt.Checked))
        self.chk_adminlog.stateChanged.connect(lambda s: self._on_launcher_changed("admin_log", s == Qt.Checked))
        self.chk_netlog.stateChanged.connect(lambda s: self._on_launcher_changed("net_log", s == Qt.Checked))
        self.chk_freezecheck.stateChanged.connect(lambda s: self._on_launcher_changed("freeze_check", s == Qt.Checked))
        self.chk_use_mods_file.stateChanged.connect(lambda s: self._on_launcher_changed("use_mods_file", s == Qt.Checked))
        
        self.txt_mods.textChanged.connect(self._on_mods_changed)
    
    def _connect_config_change_signals(self):
        """Connect server config widget signals."""
        for field_name, widget in self.config_widgets.items():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(lambda t, f=field_name: self._on_config_changed(f, t))
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(lambda v, f=field_name: self._on_config_changed(f, v))
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(lambda s, f=field_name: self._on_config_changed(f, s == Qt.Checked))
        
        self.cmb_map.currentIndexChanged.connect(lambda i: self._on_config_changed("mission_template", self.cmb_map.currentData()))
        self.cmb_map.currentIndexChanged.connect(lambda i: self._update_resource_roots())
    
    def _on_launcher_changed(self, key: str, value):
        """Handle launcher config change."""
        if not self._loading:
            self.change_manager.update_launcher_config(key, value)
            self._update_preview()
    
    def _on_mods_changed(self):
        """Handle mods text change."""
        if not self._loading:
            mods_text = self.txt_mods.toPlainText()
            self.change_manager.update_launcher_config("mods", mods_text)
            
            # Update mods count
            mods_list = self._parse_mods_list(mods_text)
            self.lbl_mods_info.setText(f"{tr('mods.selected')}: {len(mods_list)} mods")
            self._update_mods_warnings()
            self._update_preview()
    
    def _on_config_changed(self, key: str, value):
        """Handle server config change."""
        if not self._loading:
            self.change_manager.update_server_config(key, value)
    
    def _on_changes_detected(self, has_changes: bool):
        """Handle change detection signal."""
        self.btn_save.setEnabled(has_changes)
        self.btn_restore.setEnabled(has_changes)
        
        # Update change indicator
        color = "#f0ad4e" if has_changes else "transparent"
        self.change_indicator.setStyleSheet(f"background-color: {color};")

    # ==================== Profile Loading ====================
    
    def set_profile(self, profile_data: dict):
        """Set the current profile and load configuration."""
        self._loading = True
        self.current_profile = profile_data
        self.lbl_no_profile.setVisible(False)
        self.content_widget.setVisible(True)

        if hasattr(self, "btn_mission_merger_header"):
            self.btn_mission_merger_header.setEnabled(True)
        
        server_path = profile_data.get("server_path", "")
        self.txt_server_location.setText(server_path)
        
        # Load configurations
        self._load_launcher_config(server_path)
        self._load_server_config(server_path)
        
        # Connect config change signals (only once)
        if not hasattr(self, '_config_signals_connected'):
            self._connect_config_change_signals()
            self._config_signals_connected = True
        
        # Take initial snapshot
        snapshot = self._create_snapshot()
        self.change_manager.set_original_state(snapshot)
        
        self._loading = False
        self._update_preview()
        self._update_resource_roots()

    def _update_resource_roots(self):
        """Update embedded resource browsers for config/ and mpmissions/<map>."""
        if not self.current_profile:
            self.tab_map_resources.set_root_path(None)
            self.tab_mods_resources.set_root_path(None)
            return

        server_path = Path(self.current_profile.get("server_path", ""))
        if server_path.is_file():
            server_path = server_path.parent

        if not server_path.exists():
            self.tab_map_resources.set_root_path(None)
            self.tab_mods_resources.set_root_path(None)
            return

        # Mods resources (server/config)
        config_root = server_path / "config"
        self.tab_mods_resources.set_root_path(config_root if config_root.exists() else None)

        # Map resources (server/mpmissions/<template>)
        template = self.cmb_map.currentData() or "dayzOffline.chernarusplus"
        mission_root = server_path / "mpmissions" / template

        # Fallback: find folder containing template name
        if not mission_root.exists():
            mpmissions_root = server_path / "mpmissions"
            if mpmissions_root.exists():
                for folder in mpmissions_root.iterdir():
                    if folder.is_dir() and template in folder.name:
                        mission_root = folder
                        break

        self.tab_map_resources.set_root_path(mission_root if mission_root.exists() else None)
    
    def _load_launcher_config(self, server_path: str):
        """Load launcher configuration from files."""
        path = Path(server_path)
        
        # Load mods.txt
        mods_file = path / "mods.txt"
        if mods_file.exists():
            try:
                mods_text = mods_file.read_text(encoding="utf-8", errors="replace")
                self.txt_mods.setText(mods_text)
            except Exception:
                pass
        
        # Load start.bat
        bat_path = path / "start.bat"
        if bat_path.exists():
            self._parse_bat_file(bat_path)
            self.lbl_bat_file.setText(str(bat_path))
        else:
            self._set_default_launcher_values()
            self.lbl_bat_file.setText(tr('launcher.new_from_template'))

        self._update_mods_warnings()
    
    def _parse_bat_file(self, path: Path):
        """Parse batch file and populate fields."""
        try:
            content = path.read_text(encoding="utf-8")
            
            patterns = {
                "serverName": (self.txt_server_name, r'set\s+serverName=(.+)'),
                "serverPort": (self.spin_port, r'set\s+serverPort=(\d+)'),
                "serverConfig": (self.txt_config, r'set\s+serverConfig=(.+)'),
                "serverCPU": (self.spin_cpu, r'set\s+serverCPU=(\d+)'),
            }
            
            for name, (widget, pattern) in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if isinstance(widget, QLineEdit):
                        widget.setText(value)
                    elif isinstance(widget, QSpinBox):
                        try:
                            widget.setValue(int(value))
                        except ValueError:
                            pass
            
            # Parse timeout
            timeout_match = re.search(r'timeout\s+(\d+)\s*$', content, re.MULTILINE)
            if timeout_match:
                try:
                    self.spin_timeout.setValue(int(timeout_match.group(1)))
                except ValueError:
                    pass
            
            # Parse flags
            start_match = re.search(r'start\s+"[^"]*"\s+"[^"]*"(.+)', content)
            if start_match:
                flags = start_match.group(1).lower()
                self.chk_dologs.setChecked("-dologs" in flags)
                self.chk_adminlog.setChecked("-adminlog" in flags)
                self.chk_netlog.setChecked("-netlog" in flags)
                self.chk_freezecheck.setChecked("-freezecheck" in flags)
                
        except Exception:
            self._set_default_launcher_values()
    
    def _set_default_launcher_values(self):
        """Set default values for launcher fields."""
        d = LAUNCHER_DEFAULTS
        self.txt_server_name.setText(d.server_name)
        self.txt_config.setText(d.config_file)
        self.spin_port.setValue(d.port)
        self.spin_cpu.setValue(d.cpu_count)
        self.spin_timeout.setValue(d.timeout)
        self.chk_dologs.setChecked(d.do_logs)
        self.chk_adminlog.setChecked(d.admin_log)
        self.chk_netlog.setChecked(d.net_log)
        self.chk_freezecheck.setChecked(d.freeze_check)
    
    def _load_server_config(self, server_path: str):
        """Load server configuration from serverDZ.cfg."""
        cfg_path = Path(server_path) / "serverDZ.cfg"
        
        if cfg_path.exists():
            try:
                content = cfg_path.read_text(encoding="utf-8")
                self.lbl_cfg_file.setText(str(cfg_path))
                
                for field_name, widget in self.config_widgets.items():
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
                
                # Parse mission template
                mission_match = re.search(r'template\s*=\s*["\']?([^"\'\s;]+)["\']?\s*;', content)
                if mission_match:
                    template = mission_match.group(1).strip()
                    for i in range(self.cmb_map.count()):
                        if self.cmb_map.itemData(i) == template:
                            self.cmb_map.setCurrentIndex(i)
                            break
                            
            except Exception:
                self._set_default_config_values()
        else:
            self._set_default_config_values()
            self.lbl_cfg_file.setText(tr('config.new_config'))
    
    def _set_default_config_values(self):
        """Set default values for config fields."""
        for field_name, field_def in CONFIG_FIELDS.items():
            widget = self.config_widgets.get(field_name)
            if not widget:
                continue
            
            if isinstance(widget, QLineEdit):
                widget.setText(str(field_def.default))
            elif isinstance(widget, QSpinBox):
                widget.setValue(field_def.default)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(field_def.default)
        
        self.cmb_map.setCurrentIndex(0)

    # ==================== Snapshot / Restore ====================
    
    def _create_snapshot(self) -> ConfigSnapshot:
        """Create a snapshot of current configuration state."""
        snapshot = ConfigSnapshot()
        
        # Launcher config
        snapshot.launcher = {
            "server_name": self.txt_server_name.text(),
            "server_location": self.txt_server_location.text(),
            "port": self.spin_port.value(),
            "config_file": self.txt_config.text(),
            "cpu_count": self.spin_cpu.value(),
            "timeout": self.spin_timeout.value(),
            "do_logs": self.chk_dologs.isChecked(),
            "admin_log": self.chk_adminlog.isChecked(),
            "net_log": self.chk_netlog.isChecked(),
            "freeze_check": self.chk_freezecheck.isChecked(),
            "use_mods_file": self.chk_use_mods_file.isChecked(),
            "mods": self.txt_mods.toPlainText(),
        }
        
        # Server config
        for field_name, widget in self.config_widgets.items():
            if isinstance(widget, QLineEdit):
                snapshot.server_config[field_name] = widget.text()
            elif isinstance(widget, QSpinBox):
                snapshot.server_config[field_name] = widget.value()
            elif isinstance(widget, QCheckBox):
                snapshot.server_config[field_name] = widget.isChecked()
        
        snapshot.server_config["mission_template"] = self.cmb_map.currentData()
        
        return snapshot
    
    def _restore_from_snapshot(self, snapshot: ConfigSnapshot):
        """Restore UI from a configuration snapshot."""
        self._loading = True
        
        # Restore launcher config
        lc = snapshot.launcher
        self.txt_server_name.setText(lc.get("server_name", ""))
        self.txt_server_location.setText(lc.get("server_location", ""))
        self.spin_port.setValue(lc.get("port", LAUNCHER_DEFAULTS.port))
        self.txt_config.setText(lc.get("config_file", LAUNCHER_DEFAULTS.config_file))
        self.spin_cpu.setValue(lc.get("cpu_count", LAUNCHER_DEFAULTS.cpu_count))
        self.spin_timeout.setValue(lc.get("timeout", LAUNCHER_DEFAULTS.timeout))
        self.chk_dologs.setChecked(lc.get("do_logs", LAUNCHER_DEFAULTS.do_logs))
        self.chk_adminlog.setChecked(lc.get("admin_log", LAUNCHER_DEFAULTS.admin_log))
        self.chk_netlog.setChecked(lc.get("net_log", LAUNCHER_DEFAULTS.net_log))
        self.chk_freezecheck.setChecked(lc.get("freeze_check", LAUNCHER_DEFAULTS.freeze_check))
        self.chk_use_mods_file.setChecked(lc.get("use_mods_file", LAUNCHER_DEFAULTS.use_mods_file))
        self.txt_mods.setText(lc.get("mods", ""))
        
        # Restore server config
        for field_name, widget in self.config_widgets.items():
            value = snapshot.server_config.get(field_name)
            if value is None:
                continue
            
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
        
        # Restore map selection
        template = snapshot.server_config.get("mission_template")
        if template:
            for i in range(self.cmb_map.count()):
                if self.cmb_map.itemData(i) == template:
                    self.cmb_map.setCurrentIndex(i)
                    break
        
        self._loading = False
        self._update_preview()
    
    def _restore_changes(self):
        """Restore configuration to original state."""
        original = self.change_manager.restore_original()
        if original:
            self._restore_from_snapshot(original)
            QMessageBox.information(self, tr("common.success"), tr("config.changes_restored"))

    def discard_changes(self):
        """Discard unsaved changes without showing dialogs."""
        original = self.change_manager.restore_original()
        if original:
            self._restore_from_snapshot(original)

    # ==================== Save ====================
    
    def _preview_and_save(self):
        """Show preview dialog and save if confirmed."""
        changes = self.change_manager.get_changes_summary()
        
        dialog = ChangePreviewDialog(changes, self)
        if dialog.exec() == QDialog.Accepted:
            self._save_all()
    
    def _save_all(self):
        """Save all configuration to files."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return

        if is_dayz_server_running():
            QMessageBox.warning(self, tr("common.warning"), tr("dialogs.server_running_save_blocked"))
            return
        
        try:
            # Save start.bat
            bat_content = self._generate_bat_content()
            (server_path / "start.bat").write_text(bat_content, encoding="utf-8")
            
            # Save mods.txt
            mods_text = self._format_mods_list(self._parse_mods_list(self.txt_mods.toPlainText()))
            (server_path / "mods.txt").write_text(mods_text, encoding="utf-8")
            
            # Save serverDZ.cfg
            cfg_content = self._generate_cfg_content()
            (server_path / "serverDZ.cfg").write_text(cfg_content, encoding="utf-8")
            
            # Mark as saved
            self.change_manager.mark_saved()
            
            QMessageBox.information(self, tr("common.success"), tr("config.all_saved"))
            self.config_saved.emit()
            
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _generate_bat_content(self) -> str:
        """Generate the batch file content."""
        flags = []
        if self.chk_dologs.isChecked():
            flags.append("-dologs")
        if self.chk_adminlog.isChecked():
            flags.append("-adminlog")
        if self.chk_netlog.isChecked():
            flags.append("-netlog")
        if self.chk_freezecheck.isChecked():
            flags.append("-freezecheck")
        
        flags_str = " ".join(flags)
        
        use_mods_file = self.chk_use_mods_file.isChecked()
        if use_mods_file:
            mods_param = '"-mod=%modlist%"'
            mods_file_section = '::Load mods from mods.txt\nset /p modlist=<mods.txt\n'
        else:
            mods_list = self._parse_mods_list(self.txt_mods.toPlainText())
            mods_text = self._format_mods_list(mods_list)
            mods_param = f'"-mod={mods_text}"' if mods_text else ""
            mods_file_section = ""
        
        return f'''@echo off
:start

::Server name
set serverName={self.txt_server_name.text()}

::Server files location
set serverLocation="{self.txt_server_location.text()}"

::Server Port
set serverPort={self.spin_port.value()}

::Server config
set serverConfig={self.txt_config.text()}

::Logical CPU cores to use
set serverCPU={self.spin_cpu.value()}

::Sets title for terminal
title %serverName% batch

::DayZServer location
cd "%serverLocation%"

{mods_file_section}echo (%time%) %serverName% started.

::Launch parameters
start "DayZ Server" /min "DayZServer_x64.exe" -config=%serverConfig% -port=%serverPort% "-profiles=config" {mods_param} -cpuCount=%serverCPU% {flags_str}

::Time in seconds before kill server process
timeout {self.spin_timeout.value()}

taskkill /im DayZServer_x64.exe /F

::Time in seconds to wait before restart
timeout 10

goto start
'''
    
    def _generate_cfg_content(self) -> str:
        """Generate the server config file content."""
        lines = [
            "// serverDZ.cfg",
            "// DayZ Server Configuration",
            "// Generated by DayZ Mod Manager",
            ""
        ]
        
        for field_name, widget in self.config_widgets.items():
            if isinstance(widget, QLineEdit):
                value = f'"{widget.text()}"'
            elif isinstance(widget, QSpinBox):
                value = str(widget.value())
            elif isinstance(widget, QCheckBox):
                value = "1" if widget.isChecked() else "0"
            else:
                value = '""'
            
            lines.append(f'{field_name} = {value};')
        
        mission_template = self.cmb_map.currentData() or "dayzOffline.chernarusplus"
        
        lines.extend([
            "",
            "// Mission configuration",
            "class Missions",
            "{",
            "    class DayZ",
            "    {",
            f'        template="{mission_template}";',
            "    };",
            "};",
        ])
        
        return "\n".join(lines)

    # ==================== Mods Helpers ====================
    
    def _update_preview(self):
        """Update the batch file preview."""
        if self._loading:
            return
        
        content = self._generate_bat_content()
        self.txt_preview.setText(content)
        
        mods_list = self._parse_mods_list(self.txt_mods.toPlainText())
        self.lbl_mods_info.setText(f"{tr('mods.selected')}: {len(mods_list)} mods")
        self._update_mods_warnings()
    
    def _browse_location(self):
        """Browse for server location."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("profiles.select_server_path"),
            self.txt_server_location.text()
        )
        if folder:
            self.txt_server_location.setText(folder)
    
    def _load_mods_from_server(self):
        """Load mods from installed @folders."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        mod_folders = []
        try:
            for item in server_path.iterdir():
                if item.is_dir() and item.name.startswith("@"):
                    mod_folders.append(item.name)
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
            return
        
        if not mod_folders:
            QMessageBox.information(self, tr("common.info"), tr("launcher.no_installed_mods"))
            return

        dialog = ModSortDialog(
            mod_folders, self,
            title_key="launcher.load_installed_mods_title",
            info_key="launcher.load_installed_mods_info",
            auto_sort_on_open=True,
        )
        if dialog.exec() == QDialog.Accepted:
            selected_mods = dialog.get_sorted_mods()
            mods_str = self._format_mods_list(selected_mods)
            self.txt_mods.setText(mods_str)
            QMessageBox.information(self, tr("common.success"), f"{tr('launcher.mods_loaded')}: {len(selected_mods)}")
    
    def _open_sort_dialog(self):
        """Open mod sorting dialog."""
        issues = self._check_mods_format_issues(self.txt_mods.toPlainText())
        if issues:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("common.warning"))
            box.setText(tr("launcher.mods_format_warning"))

            btn_fix = box.addButton(tr("launcher.fix_mods_format"), QMessageBox.AcceptRole)
            btn_continue = box.addButton(tr("launcher.continue_anyway"), QMessageBox.DestructiveRole)
            btn_cancel = box.addButton(tr("common.cancel"), QMessageBox.RejectRole)
            box.setDefaultButton(btn_fix)
            box.exec()

            clicked = box.clickedButton()
            if clicked == btn_cancel:
                return
            if clicked == btn_fix:
                self._fix_mods_format_clicked()

        mods_list = self._parse_mods_list(self.txt_mods.toPlainText())
        if not mods_list:
            QMessageBox.information(self, tr("common.info"), tr("launcher.no_mods_to_sort"))
            return
        
        dialog = ModSortDialog(mods_list, self)
        if dialog.exec() == QDialog.Accepted:
            sorted_mods = dialog.get_sorted_mods()
            mods_str = self._format_mods_list(sorted_mods)
            self.txt_mods.setText(mods_str)
    
    @staticmethod
    def _parse_mods_list(text: str) -> list:
        """Parse mods text into a list."""
        if not text:
            return []
        cleaned = text.replace("\r", "").replace("\n", ";")
        parts = [p.strip().strip('"').strip() for p in cleaned.split(";")]
        mods = []
        seen = set()
        for part in parts:
            if not part:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            mods.append(part)
        return mods
    
    @staticmethod
    def _format_mods_list(mods: list) -> str:
        """Format mods list as semicolon-separated string."""
        normalized = [m.strip().strip('"').strip() for m in (mods or []) if m and m.strip()]
        if not normalized:
            return ""
        return ";".join(normalized) + ";"

    def _check_mods_format_issues(self, text: str) -> list[str]:
        """Check for formatting issues in mods text."""
        issues: list[str] = []
        if not text:
            return issues
        if re.search(r"\s+;", text):
            issues.append("space_before_semicolon")
        if re.search(r";\s+", text):
            issues.append("space_after_semicolon")
        if re.search(r";{2,}", text):
            issues.append("double_semicolon")
        stripped = text.strip()
        if stripped and not stripped.endswith(";"):
            issues.append("missing_trailing_semicolon")
        return issues

    def _fix_mods_format_text(self, text: str) -> str:
        """Fix formatting issues in mods text."""
        if not text:
            return ""
        cleaned = text.replace("\r", "\n").replace("\n", ";")
        cleaned = re.sub(r"\s*;\s*", ";", cleaned)
        cleaned = re.sub(r";{2,}", ";", cleaned)
        cleaned = cleaned.strip()
        if cleaned and not cleaned.endswith(";"):
            cleaned += ";"
        return cleaned

    def _fix_mods_format_clicked(self):
        """Handle fix mods format button click."""
        current = self.txt_mods.toPlainText()
        fixed = self._fix_mods_format_text(current)
        if fixed != current:
            self.txt_mods.setText(fixed)
        else:
            QMessageBox.information(self, tr("common.info"), tr("launcher.no_mods_format_issues"))

    def _update_mods_warnings(self):
        """Update mods warnings label."""
        if not hasattr(self, "lbl_mods_warnings"):
            return
        issues = self._check_mods_format_issues(self.txt_mods.toPlainText())
        if not issues:
            self.lbl_mods_warnings.setText("")
            return
        self.lbl_mods_warnings.setText(tr("launcher.mods_format_warning_inline"))
    
    def _open_mission_merger(self):
        """Open the Mission Config Merger dialog."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("config.select_profile_first"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        mission_template = self.cmb_map.currentData() or "dayzOffline.chernarusplus"
        
        dialog = MissionConfigMergeDialog(server_path, mission_template, self)
        dialog.merge_completed.connect(self._on_mission_merge_completed)
        dialog.exec()
    
    def _on_mission_merge_completed(self, result: dict):
        """Handle mission merge completion."""
        # Refresh resources browser if visible
        if hasattr(self, 'tab_map_resources'):
            self.tab_map_resources.refresh()
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.change_manager.has_unsaved_changes()
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('config.unified_title')}</h2>")
        if hasattr(self, "btn_mission_merger_header"):
            self.btn_mission_merger_header.setText(tr("mission_merge.open_mission_merger"))
        self.btn_restore.setText(tr("config.restore_changes"))
        self.btn_save.setText(tr("common.save"))
        self.lbl_no_profile.setText(tr("config.select_profile_first"))
        
        self.tabs.setTabText(0, tr("config.tab_launcher"))
        self.tabs.setTabText(1, tr("config.tab_server"))
        self.tabs.setTabText(2, tr("config.tab_map_resources"))
        self.tabs.setTabText(3, tr("config.tab_mods_resources"))

        if hasattr(self, "tab_map_resources"):
            self.tab_map_resources.update_texts()
        if hasattr(self, "tab_mods_resources"):
            self.tab_mods_resources.update_texts()
