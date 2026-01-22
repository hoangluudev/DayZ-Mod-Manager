"""
Launcher Tab - Server start.bat Configuration
"""

import re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QMessageBox, QFileDialog, QComboBox, QFrame,
    QListWidget, QListWidgetItem, QAbstractItemView, QDialog,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from shared.ui.widgets import IconButton
from shared.ui.theme_manager import ThemeManager
from shared.ui.dialogs.mod_sort_dialog import ModSortDialog
from shared.utils.locale_manager import tr
from shared.core.default_restore import default_start_bat_template


# Priority keywords for mod sorting (lower index = higher priority)
MOD_PRIORITY_KEYWORDS = [
    # Core/Foundation mods - highest priority
    ["cf", "communityframework", "community-framework", "community_framework"],
    ["community-online-tools", "cot", "communityonlinetools"],
    ["dabs", "dabs framework", "dabsframework"],
    ["vppadmintools", "vpp", "vppadmin"],
    # Expansion core
    ["expansion", "dayzexpansion", "expansioncore"],
    ["expansionmod"],
    # Common frameworks
    ["gamelab", "gamelabs"],
    ["soundlib", "sound library"],
    ["buildersitems", "builderstitems"],
    ["airdrop"],
    # Everything else has lower priority
]


def get_mod_priority(mod_name: str) -> int:
    """Get priority score for a mod (lower = higher priority)."""
    name_lower = mod_name.lower().replace("@", "").replace(" ", "").replace("-", "").replace("_", "")
    
    for priority, keywords in enumerate(MOD_PRIORITY_KEYWORDS):
        for keyword in keywords:
            keyword_clean = keyword.replace(" ", "").replace("-", "").replace("_", "")
            if keyword_clean in name_lower or name_lower in keyword_clean:
                return priority
    
    return len(MOD_PRIORITY_KEYWORDS) + 1  # Lower priority for unknown mods


class LauncherTab(QWidget):
    """Tab for configuring server launcher (start.bat)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self.bat_path = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        self.lbl_title = QLabel(f"<h2>{tr('launcher.title')}</h2>")
        header.addWidget(self.lbl_title)
        header.addStretch()
        
        self.btn_load = IconButton("browse", tr("launcher.load_bat"), size=16)
        self.btn_load.clicked.connect(self._load_bat)
        header.addWidget(self.btn_load)
        
        self.btn_generate = IconButton("restore", tr("launcher.generate_bat"), size=16)
        self.btn_generate.clicked.connect(self._generate_from_default)
        header.addWidget(self.btn_generate)
        
        self.btn_save = IconButton("save", tr("common.save"), size=16)
        self.btn_save.clicked.connect(self._save_bat)
        header.addWidget(self.btn_save)
        
        layout.addLayout(header)
        
        # No profile message
        self.lbl_no_profile = QLabel(tr("launcher.select_profile_first"))
        self.lbl_no_profile.setAlignment(Qt.AlignCenter)
        self.lbl_no_profile.setStyleSheet("color: gray; padding: 30px; font-size: 14px;")
        layout.addWidget(self.lbl_no_profile)
        
        # Content
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Current file indicator
        self.lbl_current_file = QLabel()
        self.lbl_current_file.setStyleSheet(
            f"color: {ThemeManager.get_accent_color()}; font-size: 12px;"
        )
        content_layout.addWidget(self.lbl_current_file)
        
        # Configuration section
        config_box = QGroupBox(tr("launcher.launch_params"))
        config_form = QFormLayout(config_box)
        
        # Server name
        self.txt_server_name = QLineEdit()
        self.txt_server_name.setPlaceholderText("DayZ_Server")
        self.txt_server_name.textChanged.connect(self._update_preview)
        config_form.addRow(tr("launcher.server_name") + ":", self.txt_server_name)
        
        # Server location
        loc_layout = QHBoxLayout()
        self.txt_server_location = QLineEdit()
        self.txt_server_location.setPlaceholderText("D:\\DayZServer")
        self.txt_server_location.textChanged.connect(self._update_preview)
        loc_layout.addWidget(self.txt_server_location)
        self.btn_browse_loc = QPushButton(tr("common.browse"))
        self.btn_browse_loc.clicked.connect(self._browse_location)
        loc_layout.addWidget(self.btn_browse_loc)
        config_form.addRow(tr("launcher.server_location") + ":", loc_layout)
        
        # Port
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(2302)
        self.spin_port.valueChanged.connect(self._update_preview)
        config_form.addRow(tr("launcher.param_port") + ":", self.spin_port)
        
        # Config file
        self.txt_config = QLineEdit()
        self.txt_config.setText("serverDZ.cfg")
        self.txt_config.textChanged.connect(self._update_preview)
        config_form.addRow(tr("launcher.param_config") + ":", self.txt_config)
        
        # CPU count
        self.spin_cpu = QSpinBox()
        self.spin_cpu.setRange(1, 64)
        self.spin_cpu.setValue(4)
        self.spin_cpu.valueChanged.connect(self._update_preview)
        config_form.addRow(tr("launcher.param_cpu") + ":", self.spin_cpu)
        
        # Checkboxes for flags
        flags_layout = QHBoxLayout()
        self.chk_dologs = QCheckBox("-doLogs")
        self.chk_dologs.setChecked(True)
        self.chk_dologs.stateChanged.connect(self._update_preview)
        flags_layout.addWidget(self.chk_dologs)
        
        self.chk_adminlog = QCheckBox("-adminLog")
        self.chk_adminlog.setChecked(True)
        self.chk_adminlog.stateChanged.connect(self._update_preview)
        flags_layout.addWidget(self.chk_adminlog)
        
        self.chk_netlog = QCheckBox("-netLog")
        self.chk_netlog.setChecked(True)
        self.chk_netlog.stateChanged.connect(self._update_preview)
        flags_layout.addWidget(self.chk_netlog)
        
        self.chk_freezecheck = QCheckBox("-freezeCheck")
        self.chk_freezecheck.setChecked(True)
        self.chk_freezecheck.stateChanged.connect(self._update_preview)
        flags_layout.addWidget(self.chk_freezecheck)
        
        flags_layout.addStretch()
        config_form.addRow(tr("launcher.flags") + ":", flags_layout)
        
        # Restart timeout
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(60, 999999)
        self.spin_timeout.setValue(86440)
        self.spin_timeout.setSuffix(" seconds")
        self.spin_timeout.valueChanged.connect(self._update_preview)
        config_form.addRow(tr("launcher.restart_timeout") + ":", self.spin_timeout)
        
        content_layout.addWidget(config_box)
        
        # Mods section
        mods_box = QGroupBox(tr("launcher.param_mods"))
        mods_layout = QVBoxLayout(mods_box)
        
        # Mod list method selection
        method_layout = QHBoxLayout()
        self.chk_use_mods_file = QCheckBox(tr("launcher.use_mods_file"))
        self.chk_use_mods_file.setChecked(True)
        self.chk_use_mods_file.setToolTip(tr("launcher.mods_file_tooltip"))
        self.chk_use_mods_file.stateChanged.connect(self._update_preview)
        method_layout.addWidget(self.chk_use_mods_file)
        method_layout.addStretch()
        
        # Load installed mods from server folder
        self.btn_load_from_server = IconButton("download", tr("launcher.load_installed_mods"), size=14)
        self.btn_load_from_server.clicked.connect(self._load_mods_from_server)
        method_layout.addWidget(self.btn_load_from_server)
        
        # Sorting button
        self.btn_sort_mods = IconButton("sort", tr("launcher.sort_mods"), size=14)
        self.btn_sort_mods.clicked.connect(self._open_sort_dialog)
        method_layout.addWidget(self.btn_sort_mods)
        
        self.btn_save_mods_file = IconButton("save", tr("launcher.save_mods_file"), size=14)
        self.btn_save_mods_file.clicked.connect(self._save_mods_file)
        method_layout.addWidget(self.btn_save_mods_file)
        
        mods_layout.addLayout(method_layout)
        
        # Mods text area
        self.txt_mods = QTextEdit()
        self.txt_mods.setPlaceholderText("@CF;@Dabs Framework;@VPPAdminTools;...")
        self.txt_mods.setMaximumHeight(80)
        self.txt_mods.textChanged.connect(self._update_preview)
        mods_layout.addWidget(self.txt_mods)
        
        self.lbl_mods_info = QLabel()
        self.lbl_mods_info.setStyleSheet("color: gray; font-size: 11px;")
        mods_layout.addWidget(self.lbl_mods_info)
        
        content_layout.addWidget(mods_box)
        
        # Preview section
        preview_box = QGroupBox(tr("launcher.preview"))
        preview_layout = QVBoxLayout(preview_box)
        
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e1e;")
        self.txt_preview.setMinimumHeight(200)
        preview_layout.addWidget(self.txt_preview)
        
        content_layout.addWidget(preview_box)
        
        layout.addWidget(self.content_widget)
        self.content_widget.setVisible(False)
    
    def set_profile(self, profile_data: dict):
        """Set the current profile."""
        self.current_profile = profile_data
        self.lbl_no_profile.setVisible(False)
        self.content_widget.setVisible(True)
        
        # Set server location from profile
        server_path = profile_data.get("server_path", "")
        self.txt_server_location.setText(server_path)
        
        # Try to load existing mods.txt
        self._load_mods_file()
        
        # Try to load existing start.bat
        bat_path = Path(server_path) / "start.bat"
        if bat_path.exists():
            self._load_bat_file(bat_path)
        else:
            self._generate_from_default()
    
    def _browse_location(self):
        """Browse for server location."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("profiles.select_server_path"),
            self.txt_server_location.text()
        )
        if folder:
            self.txt_server_location.setText(folder)
    
    def _load_bat(self):
        """Load an existing start.bat file."""
        if self.current_profile:
            initial = self.current_profile.get("server_path", "")
        else:
            initial = ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("launcher.load_bat"),
            initial,
            "Batch Files (*.bat);;All Files (*)"
        )
        
        if file_path:
            self._load_bat_file(Path(file_path))
    
    def _load_bat_file(self, path: Path):
        """Parse and load a batch file."""
        try:
            content = path.read_text(encoding="utf-8")
            self.bat_path = path
            self.lbl_current_file.setText(str(path))
            
            # Parse variables
            self._parse_bat_content(content)
            
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _parse_bat_content(self, content: str):
        """Parse batch file content and populate fields."""
        # Parse set commands
        patterns = {
            "serverName": (self.txt_server_name, r'set\s+serverName=(.+)'),
            "serverLocation": (self.txt_server_location, r'set\s+serverLocation="?([^"\n]+)"?'),
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
        
        # Parse flags from start command
        start_match = re.search(r'start\s+"[^"]*"\s+"[^"]*"(.+)', content)
        if start_match:
            flags = start_match.group(1).lower()
            self.chk_dologs.setChecked("-dologs" in flags)
            self.chk_adminlog.setChecked("-adminlog" in flags)
            self.chk_netlog.setChecked("-netlog" in flags)
            self.chk_freezecheck.setChecked("-freezecheck" in flags)
        
        self._update_preview()
    
    def _generate_from_default(self):
        """Generate batch file from default template."""
        template_path = default_start_bat_template()
        if template_path.exists():
            self._load_bat_file(template_path)
            self.bat_path = None  # Clear so save goes to server folder
            self.lbl_current_file.setText(tr('launcher.new_from_template'))
            
            # Update location from profile
            if self.current_profile:
                self.txt_server_location.setText(self.current_profile.get("server_path", ""))
        else:
            # Generate manually
            self.txt_server_name.setText("DayZ_Server")
            self.txt_config.setText("serverDZ.cfg")
            self.spin_port.setValue(2302)
            self.spin_cpu.setValue(4)
            self.chk_dologs.setChecked(True)
            self.chk_adminlog.setChecked(True)
            self.chk_netlog.setChecked(True)
            self.chk_freezecheck.setChecked(True)
            self.spin_timeout.setValue(86440)
            
            if self.current_profile:
                self.txt_server_location.setText(self.current_profile.get("server_path", ""))
            
            self._update_preview()
    
    def _update_preview(self):
        """Update the preview text."""
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
        
        # Get mods string (normalize to a single-line ; separated list)
        mods_list = self._parse_mods_list(self.txt_mods.toPlainText())
        mods_text = self._format_mods_list(mods_list)
        mods_count = len(mods_list)
        self.lbl_mods_info.setText(f"{tr('mods.selected')}: {mods_count} mods")
        
        # Determine mod parameter method
        use_mods_file = self.chk_use_mods_file.isChecked()
        
        if use_mods_file:
            mods_param = '"-mod=%modlist%"'
            mods_file_section = f'''::Load mods from mods.txt
set /p modlist=<mods.txt
'''
        else:
            if mods_text:
                mods_param = f'"-mod={mods_text}"'
            else:
                mods_param = ""
            mods_file_section = ""
        
        content = f'''@echo off
:start

::Server name
set serverName={self.txt_server_name.text()}

::Server files location
set serverLocation="{self.txt_server_location.text()}"

::Server Port
set serverPort={self.spin_port.value()}

::Server config
set serverConfig={self.txt_config.text()}

::Logical CPU cores to use (Equal or less than available)
set serverCPU={self.spin_cpu.value()}

::Sets title for terminal (DONT edit)
title %serverName% batch

::DayZServer location (DONT edit)
cd "%serverLocation%"

{mods_file_section}echo (%time%) %serverName% started.

::Launch parameters (edit end: -config=|-port=|-profiles=|-doLogs|-adminLog|-netLog|-freezeCheck|-filePatching|-BEpath=|-cpuCount=)
start "DayZ Server" /min "DayZServer_x64.exe" -config=%serverConfig% -port=%serverPort% "-profiles=config" {mods_param} -cpuCount=%serverCPU% {flags_str}

::Time in seconds before kill server process
timeout {self.spin_timeout.value()}

taskkill /im DayZServer_x64.exe /F

::Time in seconds to wait before restart
timeout 10

::Go back to the top and repeat the whole cycle again
goto start
'''
        self.txt_preview.setText(content)
    
    def _save_bat(self):
        """Save the batch file."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("launcher.select_profile_first"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        save_path = server_path / "start.bat"
        
        try:
            content = self.txt_preview.toPlainText()
            save_path.write_text(content, encoding="utf-8")
            self.bat_path = save_path
            self.lbl_current_file.setText(str(save_path))
            
            # Also save mods.txt if using file method
            if self.chk_use_mods_file.isChecked():
                self._save_mods_file()
            
            QMessageBox.information(self, tr("common.success"), tr("launcher.bat_saved"))
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _load_mods_from_server(self):
        """Load mods from actual installed @folders in server directory."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("launcher.select_profile_first"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        # Scan for @folders in server directory
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
        
        # Sort by priority (core/framework first)
        mod_folders.sort(key=lambda x: (get_mod_priority(x), x.lower()))
        
        mods_str = self._format_mods_list(mod_folders)
        self.txt_mods.setText(mods_str)
        
        QMessageBox.information(
            self, 
            tr("common.success"), 
            f"{tr('launcher.mods_loaded')}: {len(mod_folders)}"
        )

    def _open_sort_dialog(self):
        """Open dialog to manually sort mods order."""
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

    def apply_installed_mods_text(self, mods_text: str):
        """Apply a new mods list text (typically after installation) and persist to mods.txt."""
        normalized = self._format_mods_list(self._parse_mods_list(mods_text))
        self.txt_mods.setText(normalized)
        # Keep mods.txt in sync if a profile is active
        if self.current_profile:
            self._save_mods_file()
    
    def _save_mods_file(self):
        """Save mods list to mods.txt file."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            return
        
        mods_text = self._format_mods_list(self._parse_mods_list(self.txt_mods.toPlainText()))
        mods_file = server_path / "mods.txt"
        
        try:
            mods_file.write_text(mods_text, encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, tr("common.warning"), str(e))
    
    def _load_mods_file(self):
        """Load mods from existing mods.txt file."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        mods_file = server_path / "mods.txt"
        
        if mods_file.exists():
            try:
                mods_text = mods_file.read_text(encoding="utf-8").strip()
                # Normalize on load to avoid newline issues with `set /p` in batch.
                normalized = self._format_mods_list(self._parse_mods_list(mods_text))
                self.txt_mods.setText(normalized)
            except Exception:
                pass

    @staticmethod
    def _parse_mods_list(text: str) -> list[str]:
        """Parse mods text into a list of mod folder tokens."""
        if not text:
            return []
        cleaned = text.replace("\r", "").replace("\n", ";")
        parts = [p.strip().strip('"').strip() for p in cleaned.split(";")]
        mods: list[str] = []
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
    def _format_mods_list(mods: list[str]) -> str:
        """Format a mods list as a single-line ';' separated string suitable for mods.txt."""
        normalized = [m.strip().strip('"').strip() for m in (mods or []) if m and m.strip()]
        if not normalized:
            return ""
        return ";".join(normalized) + ";"
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('launcher.title')}</h2>")
        self.btn_load.setText(tr("launcher.load_bat"))
        self.btn_generate.setText(tr("launcher.generate_bat"))
        self.btn_save.setText(tr("common.save"))
        self.lbl_no_profile.setText(tr("launcher.select_profile_first"))
        
        # Update mods section
        if hasattr(self, 'mods_box'):
            self.mods_box.setTitle(tr("launcher.section.mods"))
        if hasattr(self, 'chk_use_mods_file'):
            self.chk_use_mods_file.setText(tr("launcher.use_mods_file"))
        if hasattr(self, 'btn_load_from_server'):
            self.btn_load_from_server.setText(tr("launcher.load_installed_mods"))
        if hasattr(self, 'btn_sort_mods'):
            self.btn_sort_mods.setText(tr("launcher.sort_mods"))
        if hasattr(self, 'btn_save_mods_file'):
            self.btn_save_mods_file.setText(tr("launcher.save_mods_file"))
