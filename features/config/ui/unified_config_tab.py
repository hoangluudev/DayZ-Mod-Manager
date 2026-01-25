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

from shared.utils.locale_manager import tr
from shared.core.default_restore import default_start_bat_template
from shared.ui.theme_manager import ThemeManager
from features.config.ui.config_manager import (
    ConfigChangeManager, ConfigSnapshot, ChangePreviewDialog
)
from shared.ui.widgets import IconButton
from features.server_resources.ui.server_resources_tab import ResourcesBrowserWidget
from shared.ui.highlighters import ModsListHighlighter
from shared.ui.dialogs.mod_sort_dialog import ModSortDialog
from shared.ui.dialogs.mission_merge_dialog import MissionConfigMergeDialog
from constants.config import (
    CONFIG_FIELDS, ConfigFieldDef, AVAILABLE_MAPS, 
    LAUNCHER_DEFAULTS, get_mod_priority
)
from shared.core.process_utils import is_dayz_server_running


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
        self._last_subtab_index = 0
        
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
        self.tabs.currentChanged.connect(self._on_subtab_changed)
        
        # Create sub-tabs
        self.tab_launcher = self._create_launcher_tab()
        self.tab_server_config = self._create_server_config_tab()

        # Embedded resource browsers
        # NOTE: presets are stored separately per-scope to avoid overwriting between tabs.
        self._map_resources_browser = ResourcesBrowserWidget(preset_scope="map")
        self._mods_resources_browser = ResourcesBrowserWidget(preset_scope="mods")

        self.tab_map_resources = self._create_map_resources_tab()
        self.tab_mods_resources = self._mods_resources_browser
        
        self.tabs.addTab(self.tab_launcher, tr("config.tab_launcher"))
        self.tabs.addTab(self.tab_server_config, tr("config.tab_server"))
        self.tabs.addTab(self.tab_map_resources, tr("config.tab_map_resources"))
        self.tabs.addTab(self.tab_mods_resources, tr("config.tab_mods_resources"))
        
        content_layout.addWidget(self.tabs)
        
        layout.addWidget(self.content_widget)
        self.content_widget.setVisible(False)

    def _create_map_resources_tab(self) -> QWidget:
        """Create Map Resources tab with map-related action buttons."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        actions = QHBoxLayout()
        actions.addStretch()

        self.btn_mission_merger_map = IconButton("cog", "", size=16, icon_only=True)
        self.btn_mission_merger_map.setToolTip(
            f"<b>{tr('mission_merge.open_mission_merger_tooltip')}</b><br>{tr('mission_merge.open_mission_merger_description')}"
        )
        self.btn_mission_merger_map.setEnabled(False)
        self.btn_mission_merger_map.clicked.connect(self._open_mission_merger)
        actions.addWidget(self.btn_mission_merger_map)

        self.btn_fix_duplicates_map = IconButton("refresh", "", size=16, icon_only=True)
        self.btn_fix_duplicates_map.setToolTip(
            f"<b>{tr('mission_merge.duplicate_fixer_title')}</b><br>{tr('mission_merge.duplicate_fixer_info')}"
        )
        self.btn_fix_duplicates_map.setEnabled(False)
        self.btn_fix_duplicates_map.clicked.connect(self._open_duplicate_fixer)
        actions.addWidget(self.btn_fix_duplicates_map)

        layout.addLayout(actions)
        layout.addWidget(self._map_resources_browser)
        return widget

    # ==================== Launcher Tab ====================
    
    def _create_launcher_tab(self) -> QWidget:
        """Create the Launcher configuration sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Per-tab actions
        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_launcher_reset = IconButton("refresh", "", size=16, icon_only=True)
        self.btn_launcher_reset.setToolTip(f"{tr('config.reset_to_defaults')}\n{tr('tabs.launcher')}")
        self.btn_launcher_reset.clicked.connect(lambda: self._reset_to_defaults_for("launcher"))
        actions.addWidget(self.btn_launcher_reset)
        
        self.btn_launcher_restore = IconButton("undo", "", size=16, icon_only=True)
        self.btn_launcher_restore.setToolTip(f"{tr('config.restore_changes')}\n{tr('tabs.launcher')}")
        self.btn_launcher_restore.setEnabled(False)
        self.btn_launcher_restore.clicked.connect(lambda: self._restore_changes_for("launcher"))
        actions.addWidget(self.btn_launcher_restore)

        self.btn_launcher_save = IconButton("save", "", size=16, icon_only=True, object_name="primary")
        self.btn_launcher_save.setToolTip(f"{tr('common.save')}\n{tr('tabs.launcher')}")
        self.btn_launcher_save.setEnabled(False)
        self.btn_launcher_save.clicked.connect(lambda: self._preview_and_save(scope="launcher"))
        actions.addWidget(self.btn_launcher_save)
        layout.addLayout(actions)
        
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

        # Per-tab actions
        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_server_reset = IconButton("refresh", "", size=16, icon_only=True)
        self.btn_server_reset.setToolTip(f"{tr('config.reset_to_defaults')}\n{tr('tabs.config')}")
        self.btn_server_reset.clicked.connect(lambda: self._reset_to_defaults_for("server_config"))
        actions.addWidget(self.btn_server_reset)
        
        self.btn_server_restore = IconButton("undo", "", size=16, icon_only=True)
        self.btn_server_restore.setToolTip(f"{tr('config.restore_changes')}\n{tr('tabs.config')}")
        self.btn_server_restore.setEnabled(False)
        self.btn_server_restore.clicked.connect(lambda: self._restore_changes_for("server_config"))
        actions.addWidget(self.btn_server_restore)

        self.btn_server_save = IconButton("save", "", size=16, icon_only=True, object_name="primary")
        self.btn_server_save.setToolTip(f"{tr('common.save')}\n{tr('tabs.config')}")
        self.btn_server_save.setEnabled(False)
        self.btn_server_save.clicked.connect(lambda: self._preview_and_save(scope="server_config"))
        actions.addWidget(self.btn_server_save)
        layout.addLayout(actions)
        
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
            ("config.section.performance", ["guaranteedUpdates", "steamProtocolMaxDataSize", "loginQueueConcurrentPlayers", "loginQueueMaxPlayers"]),
            ("config.section.storage", ["storeHouseStateDisabled", "storageAutoFix", "disableBaseDamage", "disableContainerDamage"]),
        ]
        
        for title_key, fields in sections:
            scroll_layout.addWidget(self._create_config_section(title_key, fields))
        
        # Mission/Map section
        scroll_layout.addWidget(self._create_mission_section())
        
        # Mission/Map section - no longer has Mission Config Merger button here
        # (Mission Config Merger is now only in the header, next to Restore and Save buttons)
        
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
            self._refresh_action_states()
    
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
            self._refresh_action_states()
    
    def _on_config_changed(self, key: str, value):
        """Handle server config change."""
        if not self._loading:
            self.change_manager.update_server_config(key, value)
            self._refresh_action_states()
    
    def _on_changes_detected(self, has_changes: bool):
        """Handle change detection signal."""
        # Overall indicator only. Per-tab action enablement is refreshed as fields change.
        color = "#f0ad4e" if has_changes else "transparent"
        self.change_indicator.setStyleSheet(f"background-color: {color};")
        self._refresh_action_states()

    def _refresh_action_states(self) -> None:
        """Refresh per-tab action enablement based on current change state."""
        try:
            launcher_dirty = self.change_manager.has_unsaved_changes_for("launcher")
            server_dirty = self.change_manager.has_unsaved_changes_for("server_config")
        except Exception:
            launcher_dirty = False
            server_dirty = False

        if hasattr(self, "btn_launcher_save"):
            self.btn_launcher_save.setEnabled(launcher_dirty)
        if hasattr(self, "btn_launcher_restore"):
            self.btn_launcher_restore.setEnabled(launcher_dirty)
        if hasattr(self, "btn_server_save"):
            self.btn_server_save.setEnabled(server_dirty)
        if hasattr(self, "btn_server_restore"):
            self.btn_server_restore.setEnabled(server_dirty)

        any_dirty = launcher_dirty or server_dirty
        color = "#f0ad4e" if any_dirty else "transparent"
        self.change_indicator.setStyleSheet(f"background-color: {color};")

    # ==================== Profile Loading ====================
    
    def set_profile(self, profile_data: dict):
        """Set the current profile and load configuration."""
        self._loading = True
        self.current_profile = profile_data
        self.lbl_no_profile.setVisible(False)
        self.content_widget.setVisible(True)

        if hasattr(self, "btn_mission_merger_map"):
            self.btn_mission_merger_map.setEnabled(True)
        if hasattr(self, "btn_fix_duplicates_map"):
            self.btn_fix_duplicates_map.setEnabled(True)
        
        server_path = profile_data.get("server_path", "")
        self.txt_server_location.setText(server_path)
        
        # Set profile for resource browsers (for preset management)
        self._map_resources_browser.set_profile(profile_data)
        self._mods_resources_browser.set_profile(profile_data)
        
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
        self._refresh_action_states()

    def _update_resource_roots(self):
        """Update embedded resource browsers for config/ and mpmissions/<map>."""
        if not self.current_profile:
            self._map_resources_browser.set_root_path(None)
            self._mods_resources_browser.set_root_path(None)
            return

        server_path = Path(self.current_profile.get("server_path", ""))
        if server_path.is_file():
            server_path = server_path.parent

        if not server_path.exists():
            self._map_resources_browser.set_root_path(None)
            self._mods_resources_browser.set_root_path(None)
            return

        # Mods resources (server/config)
        config_root = server_path / "config"
        self._mods_resources_browser.set_root_path(config_root if config_root.exists() else None)

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

        self._map_resources_browser.set_root_path(mission_root if mission_root.exists() else None)
    
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

    def _restore_launcher_from_snapshot(self, snapshot: ConfigSnapshot) -> None:
        self._loading = True
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
        self._loading = False
        self._update_preview()

    def _restore_server_config_from_snapshot(self, snapshot: ConfigSnapshot) -> None:
        self._loading = True
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

        template = snapshot.server_config.get("mission_template")
        if template:
            for i in range(self.cmb_map.count()):
                if self.cmb_map.itemData(i) == template:
                    self.cmb_map.setCurrentIndex(i)
                    break
        self._loading = False
    
    def _restore_changes_for(self, scope: str):
        """Restore a single scope to its original state."""
        original = self.change_manager.restore_original_for(scope)
        if not original:
            return

        if scope == "launcher":
            self._restore_launcher_from_snapshot(original)
        elif scope == "server_config":
            self._restore_server_config_from_snapshot(original)
        else:
            return

        self._refresh_action_states()
        QMessageBox.information(self, tr("common.success"), tr("config.changes_restored"))

    def _reset_to_defaults_for(self, scope: str):
        """Reset a single scope to default values."""
        if QMessageBox.question(
            self, tr("common.confirm"), 
            tr("config.confirm_reset_to_defaults").format(scope=tr(f"tabs.{scope}"))
        ) != QMessageBox.Yes:
            return

        defaults = self.change_manager.reset_to_defaults_for(scope)
        if not defaults:
            return

        if scope == "launcher":
            self._restore_launcher_from_snapshot(defaults)
        elif scope == "server_config":
            self._restore_server_config_from_snapshot(defaults)
        else:
            return

        self._refresh_action_states()
        QMessageBox.information(self, tr("common.success"), tr("config.reset_to_defaults_success"))

    def discard_changes(self):
        """Discard unsaved changes without showing dialogs."""
        original = self.change_manager.restore_original()
        if original:
            self._restore_from_snapshot(original)

    # ==================== Save ====================
    
    def _preview_and_save(self, scope: str = "all"):
        """Show preview dialog and save if confirmed."""
        changes = self.change_manager.get_changes_summary()

        if scope == "launcher":
            changes = {"launcher": changes.get("launcher", []), "server_config": []}
        elif scope == "server_config":
            changes = {"launcher": [], "server_config": changes.get("server_config", [])}

        dialog = ChangePreviewDialog(changes, self)
        if dialog.exec() == QDialog.Accepted:
            if scope == "launcher":
                self._save_launcher_only()
            elif scope == "server_config":
                self._save_server_config_only()
            else:
                self._save_all()

    def _save_launcher_only(self) -> None:
        """Save start.bat + mods.txt only."""
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
            bat_content = self._generate_bat_content()
            (server_path / "start.bat").write_text(bat_content, encoding="utf-8")

            mods_text = self._format_mods_list(self._parse_mods_list(self.txt_mods.toPlainText()))
            (server_path / "mods.txt").write_text(mods_text, encoding="utf-8")

            self.change_manager.mark_saved_for("launcher")
            QMessageBox.information(self, tr("common.success"), tr("config.all_saved"))
            self.config_saved.emit()
            self._refresh_action_states()
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    def _save_server_config_only(self) -> None:
        """Save serverDZ.cfg only."""
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
            cfg_content = self._generate_cfg_content()
            (server_path / "serverDZ.cfg").write_text(cfg_content, encoding="utf-8")

            self.change_manager.mark_saved_for("server_config")
            self._load_server_config(str(server_path))
            QMessageBox.information(self, tr("common.success"), tr("config.all_saved"))
            self.config_saved.emit()
            self._refresh_action_states()
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
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
            
            # Reload server config to reflect saved changes
            self._load_server_config(str(server_path))
            
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
            server_path=server_path,
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
        
        # Get server_path for dependency management
        server_path = None
        if self.current_profile:
            server_path = Path(self.current_profile.get("server_path", ""))
            if not server_path.exists():
                server_path = None
        
        dialog = ModSortDialog(mods_list, self, server_path=server_path)
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
    
    def _open_duplicate_fixer(self):
        """Open the Duplicate Fixer dialog."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("config.select_profile_first"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        mission_template = self.cmb_map.currentData() or "dayzOffline.chernarusplus"
        
        from shared.ui.dialogs.mission_merge_dialog import DuplicateFixerDialog
        dialog = DuplicateFixerDialog(server_path, mission_template, self)
        dialog.exec()

    def _confirm_unsaved_for_scope(self, scope: str) -> bool:
        """Return True if it is OK to leave the current scope."""
        try:
            if not self.change_manager.has_unsaved_changes_for(scope):
                return True
        except Exception:
            return True

        from features.config.ui.config_manager import UnsavedChangesDialog
        dialog = UnsavedChangesDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return False

        action = dialog.get_result()
        if action == UnsavedChangesDialog.SAVE:
            self._preview_and_save(scope=scope)
            return True
        if action == UnsavedChangesDialog.DISCARD:
            self._restore_changes_for(scope)
            return True
        # CANCEL
        return False

    def _on_subtab_changed(self, new_index: int) -> None:
        prev_index = getattr(self, "_last_subtab_index", 0)
        if new_index == prev_index:
            return

        scope_by_index = {0: "launcher", 1: "server_config"}
        prev_scope = scope_by_index.get(prev_index)
        if prev_scope and not self._loading:
            if not self._confirm_unsaved_for_scope(prev_scope):
                try:
                    self.tabs.blockSignals(True)
                    self.tabs.setCurrentIndex(prev_index)
                finally:
                    self.tabs.blockSignals(False)
                return

        self._last_subtab_index = new_index
    
    def _on_mission_merge_completed(self, result: dict):
        """Handle mission merge completion."""
        # Refresh resources browser if visible
        if hasattr(self, '_map_resources_browser'):
            self._map_resources_browser.refresh()
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.change_manager.has_unsaved_changes()
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('config.unified_title')}</h2>")
        self.lbl_no_profile.setText(tr("config.select_profile_first"))
        
        self.tabs.setTabText(0, tr("config.tab_launcher"))
        self.tabs.setTabText(1, tr("config.tab_server"))
        self.tabs.setTabText(2, tr("config.tab_map_resources"))
        self.tabs.setTabText(3, tr("config.tab_mods_resources"))

        if hasattr(self, '_map_resources_browser'):
            self._map_resources_browser.update_texts()
        if hasattr(self, '_mods_resources_browser'):
            self._mods_resources_browser.update_texts()

        if hasattr(self, "btn_mission_merger_map"):
            self.btn_mission_merger_map.setToolTip(
                f"<b>{tr('mission_merge.open_mission_merger_tooltip')}</b><br>{tr('mission_merge.open_mission_merger_description')}"
            )
        if hasattr(self, "btn_fix_duplicates_map"):
            self.btn_fix_duplicates_map.setToolTip(
                f"<b>{tr('mission_merge.duplicate_fixer_title')}</b><br>{tr('mission_merge.duplicate_fixer_info')}"
            )
