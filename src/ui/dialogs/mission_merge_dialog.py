"""Mission Config Merge Dialog

Provides a visual interface for:
- Scanning installed mods for config files (types.xml, events.xml, etc.)
- Previewing what will be merged into mission folder
- Showing new entries, duplicates, and conflicts  
- Handling map-specific files and preset selection
- Allowing user to mark mods as "already processed"
- Executing merge with proper deduplication
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from xml.etree import ElementTree as ET

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QGroupBox,
    QMessageBox, QCheckBox, QTabWidget, QWidget,
    QProgressDialog, QHeaderView, QFrame,
    QTableWidget, QTableWidgetItem, QComboBox, QAbstractItemView,
    QSplitter, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from src.core.mission_config_merger import (
    MissionConfigMerger, MergePreview, ModConfigInfo, 
    MergeStatus, ConfigEntry, get_mission_folder_path,
    ConfigFileType, detect_map_from_filename,
    is_map_specific_file, get_base_config_filename
)
from src.ui.widgets.icon_button import IconButton
from src.utils.locale_manager import tr


# Patterns to detect preset files (normal, hard, hardcore, etc.)
PRESET_PATTERNS = [
    r'(easy|normal|medium|hard|hardcore|extreme|vanilla|modded|custom)',
    r'(preset[_\-]?\d*)',
    r'(config[_\-]?\d+)',
    r'(option[_\-]?\d+)',
]


def detect_preset_name(filename: str) -> Optional[str]:
    """Detect if filename contains a preset indicator."""
    name_lower = filename.lower()
    for pattern in PRESET_PATTERNS:
        match = re.search(pattern, name_lower, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def is_preset_file(filename: str) -> bool:
    """Check if filename appears to be a preset variant."""
    return detect_preset_name(filename) is not None


class FileConfigItem(QTreeWidgetItem):
    """Tree item representing a single config file within a mod."""
    
    def __init__(self, file_path: Path, entries_count: int, current_map: str):
        super().__init__()
        self.file_path = file_path
        self.entries_count = entries_count
        self.current_map = current_map
        
        self.setText(0, file_path.name)
        self.setText(1, str(entries_count))
        
        # Analyze file type
        self._analyze_file()
        
        # Default: checked for merge
        self.setCheckState(0, Qt.Checked)
        
    def _analyze_file(self):
        """Analyze file and set status/recommendation."""
        filename = self.file_path.name
        file_type = ConfigFileType.from_filename(filename)
        
        # Check if it's a new file type (not standard DayZ config)
        if file_type == ConfigFileType.UNKNOWN:
            self.setText(2, tr("mission_merge.file_type_new"))
            self.setForeground(2, QColor("#2196f3"))
            self.setData(0, Qt.UserRole + 1, "new_file")  # Action type
            return
            
        # Check for map-specific
        map_name = detect_map_from_filename(filename)
        if map_name:
            if map_name.lower() in [self.current_map.lower(), "all"]:
                self.setText(2, f"✓ {tr('mission_merge.map_match')} ({map_name})")
                self.setForeground(2, QColor("#4caf50"))
                self.setData(0, Qt.UserRole + 1, "merge")
            else:
                self.setText(2, f"⚠ {tr('mission_merge.map_mismatch')} ({map_name})")
                self.setForeground(2, QColor("#ff9800"))
                self.setCheckState(0, Qt.Unchecked)  # Uncheck by default
                self.setData(0, Qt.UserRole + 1, "skip_map")
            return
            
        # Check for preset
        preset = detect_preset_name(filename)
        if preset:
            self.setText(2, f"⚙ {tr('mission_merge.preset')}: {preset}")
            self.setForeground(2, QColor("#9c27b0"))
            self.setData(0, Qt.UserRole + 1, "preset")
            return
            
        # Standard merge file
        self.setText(2, tr("mission_merge.file_type_merge"))
        self.setForeground(2, QColor("#4caf50"))
        self.setData(0, Qt.UserRole + 1, "merge")


class ModConfigTreeItem(QTreeWidgetItem):
    """Tree item representing a mod with expandable config files."""
    
    def __init__(self, mod_info: ModConfigInfo, current_map: str):
        super().__init__()
        self.mod_info = mod_info
        self.current_map = current_map
        self.file_items: list[FileConfigItem] = []
        
        self.setText(0, mod_info.mod_name)
        self.setText(1, str(len(mod_info.config_files)))
        self.setText(2, str(mod_info.entries_count))
        
        # Status indicator  
        if mod_info.needs_manual_review:
            self.setText(3, tr("mission_merge.needs_review"))
            self.setForeground(3, QColor("#ff9800"))
        else:
            self.setText(3, tr("mission_merge.ready"))
            self.setForeground(3, QColor("#4caf50"))
            
        # Checkbox for selection
        self.setCheckState(0, Qt.Checked)
        
        # Add child items for each config file
        self._add_file_items()
        
    def _add_file_items(self):
        """Add child tree items for each config file."""
        from xml.etree import ElementTree as ET
        
        for config_file in self.mod_info.config_files:
            try:
                tree = ET.parse(config_file)
                root = tree.getroot()
                entries = len(list(root))
            except:
                entries = 0
                
            file_item = FileConfigItem(config_file, entries, self.current_map)
            self.file_items.append(file_item)
            self.addChild(file_item)
            
    def get_selected_files(self) -> list[Path]:
        """Get list of files that are checked for merging."""
        return [
            item.file_path 
            for item in self.file_items 
            if item.checkState(0) == Qt.Checked
        ]
        
    def get_new_files(self) -> list[Path]:
        """Get list of files marked as 'new file' (copy whole file)."""
        return [
            item.file_path
            for item in self.file_items
            if item.data(0, Qt.UserRole + 1) == "new_file" and item.checkState(0) == Qt.Checked
        ]


class EntryTreeItem(QTreeWidgetItem):
    """Tree item representing a config entry."""
    
    def __init__(self, entry: ConfigEntry):
        super().__init__()
        self.entry = entry
        self.setText(0, entry.unique_key.split(":", 1)[-1] if ":" in entry.unique_key else entry.unique_key)
        self.setText(1, entry.tag)
        self.setText(2, entry.source_mod)
        
        # Status with color
        status_text, color = self._get_status_display(entry.status)
        self.setText(3, status_text)
        self.setForeground(3, QColor(color))
        
    def _get_status_display(self, status: MergeStatus) -> tuple[str, str]:
        """Get display text and color for status."""
        mapping = {
            MergeStatus.NEW: (tr("mission_merge.status_new"), "#4caf50"),
            MergeStatus.DUPLICATE: (tr("mission_merge.status_duplicate"), "#9e9e9e"),
            MergeStatus.CONFLICT: (tr("mission_merge.status_conflict"), "#f44336"),
            MergeStatus.SKIPPED: (tr("mission_merge.status_skipped"), "#607d8b"),
            MergeStatus.MANUAL: (tr("mission_merge.status_manual"), "#ff9800"),
            MergeStatus.MERGED: (tr("mission_merge.status_merged"), "#2196f3"),
        }
        return mapping.get(status, ("Unknown", "#888"))


class MissionConfigMergeDialog(QDialog):
    """Dialog for merging mod configs into mission folder."""
    
    merge_completed = Signal(dict)  # Emits {filename: count} of merged entries
    
    def __init__(self, server_path: Path, mission_template: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.server_path = server_path
        self.mission_template = mission_template
        self.mission_path = get_mission_folder_path(server_path, mission_template)
        
        # Extract map name from template
        parts = mission_template.split(".")
        self.current_map = parts[-1] if len(parts) > 1 else "chernarusplus"
        
        self.merger = MissionConfigMerger(
            self.mission_path, server_path, self.current_map
        )
        self.preview: Optional[MergePreview] = None
        self.skipped_mods: set[str] = set()
        self._conflict_entries: dict = {}  # Store conflict data for resolution
        
        self._setup_ui()
        self.setWindowTitle(tr("mission_merge.title"))
        self.setMinimumSize(1400, 850)
        self.resize(1600, 900)
        
        # Auto scan on open
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._scan_mods)
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header with info
        self._create_header(layout)
        
        # Main content - vertical layout (no splitter)
        self._create_main_content(layout)
        
        # Summary bar
        self._create_summary_bar(layout)
        
        # Action buttons
        self._create_action_buttons(layout)
        
    def _create_header(self, layout: QVBoxLayout):
        """Create header with title and action buttons."""
        header = QHBoxLayout()
        
        title = QLabel(f"<h2>{tr('mission_merge.title')}</h2>")
        header.addWidget(title)
        
        header.addStretch()
        
        # Scan button
        self.btn_scan = IconButton("refresh", text=tr("mission_merge.scan"), size=16)
        self.btn_scan.clicked.connect(self._scan_mods)
        header.addWidget(self.btn_scan)
        
        # Mark processed button (applies to all checked mods)
        self.btn_mark_processed = IconButton("check", text=tr("mission_merge.mark_processed"), size=16)
        self.btn_mark_processed.clicked.connect(self._mark_checked_as_processed)
        self.btn_mark_processed.setToolTip(tr("mission_merge.mark_processed_tooltip"))
        header.addWidget(self.btn_mark_processed)
        
        # Select all files button (only selects files, not mods)
        self.btn_select_all = QPushButton(tr("mission_merge.select_all_files"))
        self.btn_select_all.clicked.connect(self._select_all_files)
        header.addWidget(self.btn_select_all)
        
        # Deselect all files button
        self.btn_deselect_all = QPushButton(tr("mission_merge.deselect_all_files"))
        self.btn_deselect_all.clicked.connect(self._deselect_all_files)
        header.addWidget(self.btn_deselect_all)
        
        layout.addLayout(header)
        
        # Mission path info
        self.lbl_mission = QLabel(f"{tr('mission_merge.mission_folder')}: {self.mission_path}")
        self.lbl_mission.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.lbl_mission)
        
    def _create_main_content(self, layout: QVBoxLayout):
        """Create main content area with two side-by-side tables and preview tabs."""
        tables_row = QHBoxLayout()

        # Left: Source files (mods)
        sources_group = QGroupBox(tr("mission_merge.mods_with_configs"))
        sources_layout = QVBoxLayout(sources_group)

        self.tbl_sources = QTableWidget(0, 7)
        self.tbl_sources.setHorizontalHeaderLabels([
            "",  # Checkbox - no header text
            tr("mission_merge.col_file"),
            tr("mission_merge.col_parent"),
            tr("mission_merge.col_entries"),
            tr("mission_merge.col_action"),
            tr("mission_merge.col_target"),
            tr("mission_merge.col_status"),
        ])
        self.tbl_sources.setAlternatingRowColors(False)
        self.tbl_sources.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_sources.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_sources.setMinimumHeight(350)
        self.tbl_sources.verticalHeader().setDefaultSectionSize(32)  # Row height
        self.tbl_sources.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Checkbox
        self.tbl_sources.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # File
        self.tbl_sources.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Parent
        self.tbl_sources.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Entries
        self.tbl_sources.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)  # Action
        self.tbl_sources.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive)  # Target
        self.tbl_sources.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)  # Status
        self.tbl_sources.setColumnWidth(4, 160)  # Action combo width
        self.tbl_sources.setColumnWidth(5, 200)  # Target combo width
        self.tbl_sources.verticalHeader().setVisible(False)

        from PySide6.QtWidgets import QSizePolicy
        self.tbl_sources.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sources_layout.addWidget(self.tbl_sources)

        self.lbl_mapping_warnings = QLabel("")
        self.lbl_mapping_warnings.setStyleSheet("color: #ff9800; font-size: 11px;")
        self.lbl_mapping_warnings.setWordWrap(True)
        sources_layout.addWidget(self.lbl_mapping_warnings)

        self.chk_ignore_mapping_warnings = QCheckBox(tr("mission_merge.ignore_mapping_warnings"))
        self.chk_ignore_mapping_warnings.setToolTip(tr("mission_merge.ignore_mapping_warnings_tooltip"))
        self.chk_ignore_mapping_warnings.setChecked(False)
        sources_layout.addWidget(self.chk_ignore_mapping_warnings)
        tables_row.addWidget(sources_group, stretch=3)

        # Right: Mission target files
        targets_group = QGroupBox(tr("mission_merge.targets"))
        targets_layout = QVBoxLayout(targets_group)

        self.tbl_targets = QTableWidget(0, 5)
        self.tbl_targets.setHorizontalHeaderLabels([
            tr("mission_merge.target_file"),
            tr("mission_merge.col_parent"),
            tr("mission_merge.exists"),
            tr("mission_merge.entries"),
            tr("mission_merge.col_path"),
        ])
        self.tbl_targets.setAlternatingRowColors(False)
        self.tbl_targets.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_targets.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_targets.setMinimumHeight(350)
        self.tbl_targets.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)  # File
        self.tbl_targets.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Parent
        self.tbl_targets.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Exists
        self.tbl_targets.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Entries
        self.tbl_targets.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # Path
        self.tbl_targets.setColumnWidth(0, 200)  # File name width
        self.tbl_targets.verticalHeader().setVisible(False)
        self.tbl_targets.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tbl_targets.verticalHeader().setDefaultSectionSize(28)  # Row height

        targets_layout.addWidget(self.tbl_targets)
        tables_row.addWidget(targets_group, stretch=2)

        layout.addLayout(tables_row)
        
        # Preview tabs (bottom)
        preview_group = QGroupBox(tr("mission_merge.preview_title"))
        preview_layout = QVBoxLayout(preview_group)
        
        self.tabs = QTabWidget()
        
        # Overview tab
        overview_tab = self._create_overview_tab()
        self.tabs.addTab(overview_tab, tr("mission_merge.tab_overview"))
        
        # Entries tab  
        entries_tab = self._create_entries_tab()
        self.tabs.addTab(entries_tab, tr("mission_merge.tab_entries"))
        
        # Preview XML tab
        preview_tab = self._create_xml_preview_tab()
        self.tabs.addTab(preview_tab, tr("mission_merge.tab_preview"))
        
        preview_layout.addWidget(self.tabs)
        layout.addWidget(preview_group, stretch=1)
        
    def _create_overview_tab(self) -> QWidget:
        """Create overview tab showing summary by file."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.tree_overview = QTreeWidget()
        self.tree_overview.setHeaderLabels([
            tr("mission_merge.target_file"),
            tr("mission_merge.new_entries"),
            tr("mission_merge.duplicates"),
            tr("mission_merge.conflicts")
        ])
        self.tree_overview.setRootIsDecorated(False)
        self.tree_overview.setAlternatingRowColors(False)
        self.tree_overview.itemClicked.connect(self._on_overview_item_clicked)
        
        header = self.tree_overview.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.tree_overview)
        return widget
    
    def _create_entries_tab(self) -> QWidget:
        """Create entries tab showing individual entries."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Filter buttons
        filter_layout = QHBoxLayout()
        self.chk_show_new = QCheckBox(tr("mission_merge.show_new"))
        self.chk_show_new.setChecked(True)
        self.chk_show_new.stateChanged.connect(self._filter_entries)
        filter_layout.addWidget(self.chk_show_new)
        
        self.chk_show_dup = QCheckBox(tr("mission_merge.show_duplicates"))
        self.chk_show_dup.setChecked(False)
        self.chk_show_dup.stateChanged.connect(self._filter_entries)
        filter_layout.addWidget(self.chk_show_dup)
        
        self.chk_show_conflict = QCheckBox(tr("mission_merge.show_conflicts"))
        self.chk_show_conflict.setChecked(True)
        self.chk_show_conflict.stateChanged.connect(self._filter_entries)
        filter_layout.addWidget(self.chk_show_conflict)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Entries tree
        self.tree_entries = QTreeWidget()
        self.tree_entries.setHeaderLabels([
            tr("mission_merge.entry_name"),
            tr("mission_merge.entry_type"),
            tr("mission_merge.source_mod"),
            tr("mission_merge.status")
        ])
        self.tree_entries.setRootIsDecorated(True)
        self.tree_entries.setAlternatingRowColors(False)
        self.tree_entries.itemClicked.connect(self._on_entry_clicked)
        
        header = self.tree_entries.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.tree_entries)
        return widget
    
    def _create_xml_preview_tab(self) -> QWidget:
        """Create XML preview tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        self.lbl_preview_info = QLabel(tr("mission_merge.select_entry_to_preview"))
        self.lbl_preview_info.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_preview_info)
        
        # XML text view
        self.txt_xml_preview = QTextEdit()
        self.txt_xml_preview.setReadOnly(True)
        self.txt_xml_preview.setFont(QFont("Consolas", 10))
        self.txt_xml_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        layout.addWidget(self.txt_xml_preview)
        
        return widget
    
    def _create_summary_bar(self, layout: QVBoxLayout):
        """Create summary statistics bar."""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("QFrame { background-color: rgba(0,0,0,0.1); padding: 8px; }")
        
        summary_layout = QHBoxLayout(frame)
        
        self.lbl_total_mods = QLabel(f"{tr('mission_merge.total_mods')}: 0")
        summary_layout.addWidget(self.lbl_total_mods)
        
        summary_layout.addWidget(QLabel("|"))
        
        self.lbl_total_new = QLabel(f"{tr('mission_merge.new_entries')}: 0")
        self.lbl_total_new.setStyleSheet("color: #4caf50; font-weight: bold;")
        summary_layout.addWidget(self.lbl_total_new)
        
        summary_layout.addWidget(QLabel("|"))
        
        self.lbl_total_dup = QLabel(f"{tr('mission_merge.duplicates')}: 0")
        self.lbl_total_dup.setStyleSheet("color: #9e9e9e;")
        summary_layout.addWidget(self.lbl_total_dup)
        
        summary_layout.addWidget(QLabel("|"))
        
        self.lbl_total_conflict = QLabel(f"{tr('mission_merge.conflicts')}: 0")
        self.lbl_total_conflict.setStyleSheet("color: #f44336;")
        summary_layout.addWidget(self.lbl_total_conflict)
        
        summary_layout.addWidget(QLabel("|"))
        
        self.lbl_new_files = QLabel(f"{tr('mission_merge.new_files')}: 0")
        self.lbl_new_files.setStyleSheet("color: #2196f3;")
        summary_layout.addWidget(self.lbl_new_files)
        
        summary_layout.addStretch()
        layout.addWidget(frame)
    
    def _create_action_buttons(self, layout: QVBoxLayout):
        """Create bottom action buttons."""
        buttons = QHBoxLayout()
        
        self.btn_preview = IconButton("browse", text=tr("mission_merge.preview"), size=18)
        self.btn_preview.clicked.connect(self._generate_preview)
        self.btn_preview.setEnabled(False)
        buttons.addWidget(self.btn_preview)
        
        # Resolve conflicts button
        self.btn_resolve_conflicts = IconButton("cog", text=tr("mission_merge.resolve_conflicts"), size=18)
        self.btn_resolve_conflicts.clicked.connect(self._open_conflict_resolver)
        self.btn_resolve_conflicts.setEnabled(False)
        self.btn_resolve_conflicts.setToolTip(tr("mission_merge.resolve_conflicts_tooltip"))
        buttons.addWidget(self.btn_resolve_conflicts)
        
        buttons.addStretch()
        
        self.chk_include_conflicts = QCheckBox(tr("mission_merge.include_conflicts"))
        self.chk_include_conflicts.setToolTip(tr("mission_merge.include_conflicts_tooltip"))
        buttons.addWidget(self.chk_include_conflicts)
        
        self.btn_merge = IconButton("save", text=tr("mission_merge.merge"), size=18, object_name="primary")
        self.btn_merge.clicked.connect(self._execute_merge)
        self.btn_merge.setEnabled(False)
        buttons.addWidget(self.btn_merge)
        
        self.btn_close = QPushButton(tr("common.close"))
        self.btn_close.clicked.connect(self.reject)
        buttons.addWidget(self.btn_close)
        
        layout.addLayout(buttons)
    
    # ========== Actions ==========
    
    def _scan_mods(self):
        """Scan all mods for config files."""
        self.tbl_sources.setRowCount(0)
        self.tbl_targets.setRowCount(0)
        self.merger.load_skipped_mods(self.skipped_mods)
        
        progress = QProgressDialog(
            tr("mission_merge.scanning"), tr("common.cancel"), 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        mod_infos = []
        try:
            mod_infos = self.merger.scan_all_mods()
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("common.error"),
                f"{tr('mission_merge.scan_error')}\n\n{e}"
            )
            return
        finally:
            progress.close()

        self._populate_targets_table()
        self._populate_sources_table(mod_infos)

        self.lbl_total_mods.setText(f"{tr('mission_merge.total_mods')}: {len(mod_infos)}")
        self._update_new_files_count()

        if mod_infos:
            self.btn_preview.setEnabled(True)
        else:
            QMessageBox.information(
                self, tr("common.info"),
                tr("mission_merge.no_configs_found")
            )
    
    def _update_new_files_count(self):
        """Update count of new files to be copied."""
        count = 0
        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item or use_item.checkState() != Qt.Checked:
                continue
            action_combo = self.tbl_sources.cellWidget(row, 4)
            if isinstance(action_combo, QComboBox) and action_combo.currentData() == "copy":
                count += 1
        self.lbl_new_files.setText(f"{tr('mission_merge.new_files')}: {count}")

    def _get_target_parent_tag(self, target_filename: str) -> str:
        """Get parent/root tag for a target mission file.

        If the file exists in mission folder, parse to get actual root tag.
        Otherwise fall back to expected root tag based on filename.
        """
        from xml.etree import ElementTree as ET

        file_path = self.mission_path / target_filename
        if file_path.exists():
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                return (root.tag or "").strip()
            except Exception:
                # If unreadable, still return expected root tag
                pass

        ft = ConfigFileType.from_filename(target_filename)
        return (ft.root_element or "").strip()

    def _populate_targets_table(self):
        """Populate right table with mission config targets."""
        # Build list of targets: known DayZ filenames + any existing *.xml in mission folder.
        known = []
        for ft in ConfigFileType:
            if ft == ConfigFileType.UNKNOWN:
                continue
            if not ft.filename:
                continue
            known.append(ft.filename)

        existing = []
        try:
            if self.mission_path.exists():
                existing = sorted([p.name for p in self.mission_path.glob("*.xml") if p.is_file()])
        except OSError:
            existing = []

        targets = []
        for name in known + [n for n in existing if n not in known]:
            targets.append(name)

        from xml.etree import ElementTree as ET

        self._available_targets = targets
        self.tbl_targets.setRowCount(0)
        for filename in targets:
            file_path = self.mission_path / filename
            exists = file_path.exists()
            parent = ConfigFileType.from_filename(filename).root_element or "-"
            entries = "-"
            if exists:
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    parent = root.tag
                    entries = str(len(list(root)))
                except Exception:
                    entries = "?"

            row = self.tbl_targets.rowCount()
            self.tbl_targets.insertRow(row)
            self.tbl_targets.setItem(row, 0, QTableWidgetItem(filename))
            self.tbl_targets.setItem(row, 1, QTableWidgetItem(parent))
            self.tbl_targets.setItem(row, 2, QTableWidgetItem("✓" if exists else "-"))
            self.tbl_targets.setItem(row, 3, QTableWidgetItem(entries))
            self.tbl_targets.setItem(row, 4, QTableWidgetItem(str(file_path)))

    def _populate_sources_table(self, mod_infos: list[ModConfigInfo]):
        """Populate left table with source XML files from mods."""
        from xml.etree import ElementTree as ET

        self._scanned_mod_infos = mod_infos
        self.tbl_sources.setRowCount(0)

        for mod_info in mod_infos:
            # Add mod header row
            header_row = self.tbl_sources.rowCount()
            self.tbl_sources.insertRow(header_row)
            
            # Mod header spans all columns
            mod_header = QTableWidgetItem(f"📦 {mod_info.mod_name}")
            mod_header.setFont(QFont("", -1, QFont.Bold))
            mod_header.setBackground(QColor("#3a3a3a"))
            mod_header.setForeground(QColor("#4fc3f7"))
            mod_header.setFlags(Qt.ItemIsEnabled)  # Not selectable
            self.tbl_sources.setItem(header_row, 0, mod_header)
            self.tbl_sources.setSpan(header_row, 0, 1, 7)  # Span all columns
            
            # Add config files for this mod
            for config_file in mod_info.config_files:
                file_type = ConfigFileType.from_filename(config_file.name)
                entries_count = 0
                parent_tag = file_type.root_element or "-"
                try:
                    tree = ET.parse(config_file)
                    root = tree.getroot()
                    parent_tag = root.tag
                    file_type = ConfigFileType.from_root_element(root.tag)
                    entries_count = len(list(root))
                except Exception:
                    # Leave inferred from filename; mark manual in status later
                    pass

                row = self.tbl_sources.rowCount()
                self.tbl_sources.insertRow(row)
                
                # Use checkbox
                use_item = QTableWidgetItem("")
                use_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                use_item.setCheckState(Qt.Checked)
                use_item.setData(Qt.UserRole, str(config_file))
                use_item.setData(Qt.UserRole + 1, mod_info.mod_name)
                use_item.setData(Qt.UserRole + 2, file_type.name)
                self.tbl_sources.setItem(row, 0, use_item)
                
                # File name - bold
                file_item = QTableWidgetItem(config_file.name)
                file_font = file_item.font()
                file_font.setBold(True)
                file_item.setFont(file_font)
                self.tbl_sources.setItem(row, 1, file_item)
                
                # Parent and entries
                self.tbl_sources.setItem(row, 2, QTableWidgetItem(parent_tag))
                self.tbl_sources.setItem(row, 3, QTableWidgetItem(str(entries_count)))

                # Action combo
                action_combo = QComboBox()
                action_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
                action_combo.setMinimumWidth(160)
                action_combo.addItem(tr("mission_merge.action_copy"), userData="copy")
                action_combo.addItem(tr("mission_merge.action_merge"), userData="merge")

                # Default: merge when known type, else copy
                if file_type == ConfigFileType.UNKNOWN:
                    action_combo.setCurrentIndex(0)
                else:
                    action_combo.setCurrentIndex(1)
                self.tbl_sources.setCellWidget(row, 4, action_combo)

                # Target combo
                target_combo = QComboBox()
                target_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
                target_combo.setMinimumWidth(200)
                for t in getattr(self, "_available_targets", []):
                    target_combo.addItem(t, userData=t)
                default_target = (
                    get_base_config_filename(config_file.name)
                    if is_map_specific_file(config_file.name)
                    else (file_type.filename or config_file.name)
                )
                idx = target_combo.findData(default_target)
                if idx >= 0:
                    target_combo.setCurrentIndex(idx)
                self.tbl_sources.setCellWidget(row, 5, target_combo)

                # Status
                status_item = QTableWidgetItem(tr("mission_merge.status_ok"))
                status_item.setForeground(QColor("#607d8b"))
                self.tbl_sources.setItem(row, 6, status_item)

                def _on_change(_=None, r=row):
                    self._on_source_row_changed(r)

                action_combo.currentIndexChanged.connect(_on_change)
                target_combo.currentIndexChanged.connect(_on_change)

                self._on_source_row_changed(row)

        self._update_new_files_count()

    def _on_source_row_changed(self, row: int):
        """Handle action/target changes for a row: enable/disable target and update status."""
        action_combo = self.tbl_sources.cellWidget(row, 4)
        target_combo = self.tbl_sources.cellWidget(row, 5)
        status_item = self.tbl_sources.item(row, 6)
        use_item = self.tbl_sources.item(row, 0)

        if not isinstance(action_combo, QComboBox) or not isinstance(target_combo, QComboBox):
            return
        if not status_item or not use_item:
            return

        action = action_combo.currentData()
        target_combo.setEnabled(action == "merge")

        # Validation: parent class mismatch (types/events/etc.)
        file_type_name = use_item.data(Qt.UserRole + 2) or "UNKNOWN"
        try:
            source_type = ConfigFileType[file_type_name]
        except Exception:
            source_type = ConfigFileType.UNKNOWN
        target_file = target_combo.currentData()

        # Source parent tag displayed in column 2 (actual root when readable)
        source_parent = (self.tbl_sources.item(row, 2).text() if self.tbl_sources.item(row, 2) else "").strip()
        target_parent = self._get_target_parent_tag(str(target_file)) if target_file else ""

        if action == "merge":
            if source_type == ConfigFileType.UNKNOWN:
                status_item.setText(tr("mission_merge.status_unknown_type"))
                status_item.setForeground(QColor("#ff9800"))
            else:
                if source_parent and target_parent and source_parent.lower() != target_parent.lower():
                    status_item.setText(
                        tr("mission_merge.status_type_mismatch").format(
                            source=source_parent,
                            target=target_parent,
                        )
                    )
                    status_item.setForeground(QColor("#ff9800"))
                else:
                    status_item.setText(tr("mission_merge.status_ok"))
                    status_item.setForeground(QColor("#607d8b"))
        else:
            status_item.setText(tr("mission_merge.status_copy"))
            status_item.setForeground(QColor("#2196f3"))

        self._update_new_files_count()
        self._refresh_mapping_warnings()
        self._refresh_mapping_warnings()

    def _refresh_mapping_warnings(self):
        """Aggregate invalid merge mappings and show a compact warning summary."""
        invalid = []
        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item or use_item.checkState() != Qt.Checked:
                continue
            action_combo = self.tbl_sources.cellWidget(row, 4)
            if not isinstance(action_combo, QComboBox) or action_combo.currentData() != "merge":
                continue
            status_item = self.tbl_sources.item(row, 6)
            if status_item and status_item.foreground().color().name().lower() == QColor("#ff9800").name().lower():
                file_item = self.tbl_sources.item(row, 1)
                file_ = file_item.text() if file_item else ""
                mod_name = str(use_item.data(Qt.UserRole + 1) or "")
                invalid.append(f"{mod_name} / {file_}")

        if invalid:
            shown = ", ".join(invalid[:3])
            more = "" if len(invalid) <= 3 else f" (+{len(invalid) - 3})"
            self.lbl_mapping_warnings.setText(
                tr("mission_merge.mapping_warnings").format(count=len(invalid), items=shown + more)
            )
        else:
            self.lbl_mapping_warnings.setText("")
    
    def _generate_preview(self):
        """Generate merge preview for selected mods."""
        # Mapping warnings are informational only (mods can be non-standard).
        self._refresh_mapping_warnings()
        # Always allow continuing without prompting.

        # Collect selected rows
        selected_by_mod: dict[str, list[Path]] = {}
        copy_by_mod: dict[str, list[Path]] = {}
        overrides: dict[Path, str] = {}

        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item or use_item.checkState() != Qt.Checked:
                continue

            src_path = Path(str(use_item.data(Qt.UserRole)))
            mod_name = str(use_item.data(Qt.UserRole + 1) or "")
            action_combo = self.tbl_sources.cellWidget(row, 4)
            target_combo = self.tbl_sources.cellWidget(row, 5)
            if not isinstance(action_combo, QComboBox) or not isinstance(target_combo, QComboBox):
                continue

            action = action_combo.currentData()
            if action == "copy":
                copy_by_mod.setdefault(mod_name, []).append(src_path)
                continue

            target_filename = str(target_combo.currentData() or "")
            if target_filename:
                overrides[src_path] = target_filename
            selected_by_mod.setdefault(mod_name, []).append(src_path)

        selected_mods: list[ModConfigInfo] = []
        for mod_info in getattr(self, "_scanned_mod_infos", []):
            files = selected_by_mod.get(mod_info.mod_name, [])
            if not files:
                continue
            selected_mods.append(
                ModConfigInfo(
                    mod_name=mod_info.mod_name,
                    mod_path=mod_info.mod_path,
                    config_files=files,
                    entries_count=0,
                    needs_manual_review=mod_info.needs_manual_review,
                    manual_review_reason=mod_info.manual_review_reason,
                )
            )

        if not selected_mods and not copy_by_mod:
            QMessageBox.warning(self, tr("common.warning"), tr("mission_merge.select_mods"))
            return
            
        progress = QProgressDialog(
            tr("mission_merge.analyzing"), tr("common.cancel"), 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        try:
            if selected_mods:
                self.preview = self.merger.preview_merge(selected_mods, target_overrides=overrides)
            else:
                self.preview = MergePreview(mission_path=self.mission_path)
            
            # Store new files info for merge
            self.preview.new_files_to_copy = copy_by_mod
            
            # Collect conflict entries for resolution
            self._collect_conflict_entries()
            
            self._update_preview_ui()
            self.btn_merge.setEnabled(
                self.preview.total_new > 0 or 
                self.preview.total_conflicts > 0 or
                any(len(files) > 0 for files in copy_by_mod.values())
            )
            
            # Enable conflict resolver if there are conflicts
            self.btn_resolve_conflicts.setEnabled(self.preview.total_conflicts > 0)
        finally:
            progress.close()
    
    def _collect_conflict_entries(self):
        """Collect conflict entries for the conflict resolution dialog."""
        self._conflict_entries = {}
        if not self.preview:
            return
        
        for filename, result in self.preview.merge_results.items():
            conflicts = [e for e in result.conflict_entries if e.status == MergeStatus.CONFLICT]
            if conflicts:
                self._conflict_entries[filename] = conflicts
    
    def _update_preview_ui(self):
        """Update UI with preview data."""
        if not self.preview:
            return

        resolved_map = getattr(self.preview, "resolved_conflicts", None) or {}

        def _resolved_keys_for_file(filename: str) -> set[str]:
            keys: set[str] = set()
            for res in resolved_map.get(filename, []) or []:
                if not isinstance(res, dict):
                    continue
                entry = res.get("entry")
                if entry is not None and getattr(entry, "unique_key", None):
                    keys.add(str(entry.unique_key))
            return keys

        def _remaining_conflict_count(filename: str, result) -> int:
            resolved_keys = _resolved_keys_for_file(filename)
            if not resolved_keys:
                return int(getattr(result, "conflicts", 0) or 0)

            by_key: dict[str, int] = {}
            for e in getattr(result, "conflict_entries", []) or []:
                k = str(getattr(e, "unique_key", ""))
                if not k:
                    continue
                by_key[k] = by_key.get(k, 0) + 1

            resolved_entries = sum(by_key.get(k, 0) for k in resolved_keys)
            return max(0, int(getattr(result, "conflicts", 0) or 0) - int(resolved_entries))
            
        # Update summary (adjust conflicts by resolved selections)
        remaining_total_conflicts = 0
        for fn, res in self.preview.merge_results.items():
            remaining_total_conflicts += _remaining_conflict_count(fn, res)

        self.lbl_total_new.setText(f"{tr('mission_merge.new_entries')}: {self.preview.total_new}")
        self.lbl_total_dup.setText(f"{tr('mission_merge.duplicates')}: {self.preview.total_duplicates}")
        self.lbl_total_conflict.setText(f"{tr('mission_merge.conflicts')}: {remaining_total_conflicts}")
        
        # Count new files
        new_files_map = getattr(self.preview, 'new_files_to_copy', {})
        new_files_count = sum(len(files) for files in new_files_map.values())
        self.lbl_new_files.setText(f"{tr('mission_merge.new_files')}: {new_files_count}")
        
        # Update overview tree
        self.tree_overview.clear()
        for filename, result in self.preview.merge_results.items():
            item = QTreeWidgetItem()
            item.setText(0, filename)
            item.setText(1, str(result.new_entries))
            item.setText(2, str(result.duplicates))
            remaining_conflicts = _remaining_conflict_count(filename, result)
            item.setText(3, str(remaining_conflicts))
            
            # Color code
            if remaining_conflicts > 0:
                item.setForeground(0, QColor("#f44336"))
            elif result.new_entries > 0:
                item.setForeground(0, QColor("#4caf50"))
            else:
                item.setForeground(0, QColor("#9e9e9e"))
                
            item.setData(0, Qt.UserRole, filename)
            self.tree_overview.addTopLevelItem(item)
        
        # Add new files section
        if new_files_map:
            for mod_name, files in new_files_map.items():
                for f in files:
                    item = QTreeWidgetItem()
                    item.setText(0, f"[NEW] {f.name}")
                    item.setText(1, tr("mission_merge.copy_whole_file"))
                    item.setText(2, "-")
                    item.setText(3, "-")
                    item.setForeground(0, QColor("#2196f3"))
                    item.setData(0, Qt.UserRole, f"new:{f}")
                    self.tree_overview.addTopLevelItem(item)
        
        # Update entries tree
        self._populate_entries_tree()
    
    def _populate_entries_tree(self):
        """Populate entries tree grouped by file."""
        self.tree_entries.clear()
        
        if not self.preview:
            return
            
        show_new = self.chk_show_new.isChecked()
        show_dup = self.chk_show_dup.isChecked()
        show_conflict = self.chk_show_conflict.isChecked()
        
        resolved_map = getattr(self.preview, "resolved_conflicts", None) or {}

        def _resolved_keys_for_file(filename: str) -> set[str]:
            keys: set[str] = set()
            for res in resolved_map.get(filename, []) or []:
                if not isinstance(res, dict):
                    continue
                entry = res.get("entry")
                if entry is not None and getattr(entry, "unique_key", None):
                    keys.add(str(entry.unique_key))
            return keys

        for filename, result in self.preview.merge_results.items():
            file_item = QTreeWidgetItem()
            file_item.setText(0, filename)
            file_item.setFont(0, QFont("", -1, QFont.Bold))
            
            count = 0
            
            resolved_keys = _resolved_keys_for_file(filename)

            # Add entries
            all_entries = result.merged_entries + result.conflict_entries
            for entry in all_entries:
                display_entry = entry
                if entry.status == MergeStatus.CONFLICT and str(getattr(entry, "unique_key", "")) in resolved_keys:
                    display_entry = ConfigEntry(
                        element=entry.element,
                        unique_key=entry.unique_key,
                        source_mod=entry.source_mod,
                        source_file=entry.source_file,
                        status=MergeStatus.MERGED,
                    )

                if entry.status == MergeStatus.NEW and not show_new:
                    continue
                if entry.status == MergeStatus.DUPLICATE and not show_dup:
                    continue
                if entry.status == MergeStatus.CONFLICT and not show_conflict:
                    continue
                    
                entry_item = EntryTreeItem(display_entry)
                file_item.addChild(entry_item)
                count += 1
                
            if count > 0:
                self.tree_entries.addTopLevelItem(file_item)
                file_item.setExpanded(True)
    
    def _filter_entries(self):
        """Re-filter entries based on checkboxes."""
        self._populate_entries_tree()
    
    def _on_mod_selected(self):
        """Handle mod selection in tree."""
        # Legacy handler from tree-based UI; kept to avoid breaking imports.
        return
    
    def _on_item_checked(self, item, column):
        """Handle checkbox state change."""
        # Legacy handler from tree-based UI; kept to avoid breaking imports.
        return
    
    def _on_overview_item_clicked(self, item, column):
        """Handle click on overview item."""
        filename = item.data(0, Qt.UserRole)
        if filename and self.preview:
            if filename.startswith("new:"):
                # New file - show file path
                self.txt_xml_preview.setText(f"New file to copy: {filename[4:]}")
            elif filename in self.preview.merge_results:
                result = self.preview.merge_results[filename]
                
                info = f"{tr('mission_merge.target_file')}: {filename}\n\n"
                info += f"{tr('mission_merge.new_entries')}: {result.new_entries}\n"
                info += f"{tr('mission_merge.duplicates')}: {result.duplicates}\n"
                info += f"{tr('mission_merge.conflicts')}: {result.conflicts}\n"
                
                self.txt_xml_preview.setText(info)
            self.tabs.setCurrentIndex(2)  # Switch to preview tab
    
    def _on_entry_clicked(self, item, column):
        """Handle click on entry item."""
        if isinstance(item, EntryTreeItem):
            # Show XML preview
            xml_str = item.entry.to_xml_string()
            info = f"<!-- {tr('mission_merge.source')}: {item.entry.source_mod} -->\n"
            info += f"<!-- {tr('mission_merge.file')}: {item.entry.source_file.name} -->\n"
            info += f"<!-- {tr('mission_merge.status')}: {item.entry.status.value} -->\n\n"
            info += xml_str
            
            self.txt_xml_preview.setText(info)
            self.lbl_preview_info.setText(f"{item.entry.unique_key}")
            self.tabs.setCurrentIndex(2)  # Switch to preview tab
    
    def _mark_checked_as_processed(self):
        """Mark all checked mods as processed/skipped."""
        marked: set[str] = set()
        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item or use_item.checkState() != Qt.Checked:
                continue
            mod_name = str(use_item.data(Qt.UserRole + 1) or "")
            if not mod_name:
                continue
            marked.add(mod_name)

        if marked:
            self.skipped_mods.update(marked)
            # Uncheck all rows belonging to these mods
            for row in range(self.tbl_sources.rowCount()):
                use_item = self.tbl_sources.item(row, 0)
                if not use_item:
                    continue
                mod_name = str(use_item.data(Qt.UserRole + 1) or "")
                if mod_name in marked:
                    use_item.setCheckState(Qt.Unchecked)
                    status_item = self.tbl_sources.item(row, 6)
                    if status_item:
                        status_item.setText(tr("mission_merge.status_skipped"))
                        status_item.setForeground(QColor("#607d8b"))
            self._update_new_files_count()
            self._refresh_mapping_warnings()
        
        if marked:
            QMessageBox.information(
                self,
                tr("common.info"),
                f"{tr('mission_merge.marked_processed')}: {len(marked)} mods"
            )
    
    def _select_all_files(self):
        """Select all file rows (not mod header rows) that are not skipped."""
        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item:
                continue
            # Skip mod header rows (they have no checkbox/data)
            if use_item.data(Qt.UserRole) is None:
                continue
            mod_name = str(use_item.data(Qt.UserRole + 1) or "")
            if mod_name and mod_name in self.skipped_mods:
                continue
            use_item.setCheckState(Qt.Checked)

        self._update_new_files_count()
        self._refresh_mapping_warnings()
    
    def _deselect_all_files(self):
        """Deselect all file rows (not mod header rows)."""
        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item:
                continue
            # Skip mod header rows (they have no checkbox/data)
            if use_item.data(Qt.UserRole) is None:
                continue
            use_item.setCheckState(Qt.Unchecked)

        self._update_new_files_count()
        self._refresh_mapping_warnings()
    
    def _execute_merge(self):
        """Execute the merge operation."""
        if not self.preview:
            return

        # Mapping warnings are non-blocking (mods often use non-standard XML).
        self._refresh_mapping_warnings()
        
        # Count what will be merged
        new_files_map = getattr(self.preview, 'new_files_to_copy', {})
        new_files_count = sum(len(files) for files in new_files_map.values())
        
        # Confirm
        msg = tr("mission_merge.confirm_merge").format(
            new=self.preview.total_new,
            conflicts=self.preview.total_conflicts if self.chk_include_conflicts.isChecked() else 0
        )
        if getattr(self, "lbl_mapping_warnings", None) and self.lbl_mapping_warnings.text().strip():
            msg += "\n\n" + self.lbl_mapping_warnings.text().strip()
        if new_files_count > 0:
            msg += f"\n\n{tr('mission_merge.new_files_to_copy')}: {new_files_count}"
        
        reply = QMessageBox.question(
            self, tr("common.confirm"), msg,
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            # Execute entry merge
            result = {}
            if self.preview.merge_results:
                result = self.merger.execute_merge(
                    self.preview,
                    include_conflicts=self.chk_include_conflicts.isChecked()
                )
            
            # Copy new files
            overwrite_names: set[str] = set()
            for files in new_files_map.values():
                for src_file in files:
                    dst_file = self.mission_path / src_file.name
                    if dst_file.exists():
                        overwrite_names.add(dst_file.name)

            if overwrite_names:
                shown = "\n".join(f"- {n}" for n in sorted(overwrite_names)[:10])
                more = "" if len(overwrite_names) <= 10 else f"\n... (+{len(overwrite_names) - 10})"
                reply2 = QMessageBox.question(
                    self,
                    tr("common.confirm"),
                    tr("mission_merge.copy_overwrite_confirm").format(files=f"{shown}{more}"),
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply2 != QMessageBox.Yes:
                    return

            for mod_name, files in new_files_map.items():
                for src_file in files:
                    dst_file = self.mission_path / src_file.name
                    try:
                        shutil.copy2(src_file, dst_file)
                        result[f"[COPIED] {src_file.name}"] = 1
                    except Exception as e:
                        result[f"[FAILED] {src_file.name}"] = 0
            
            # Show result
            summary = "\n".join(f"  {f}: {c}" for f, c in result.items())
            QMessageBox.information(
                self, tr("common.success"),
                f"{tr('mission_merge.merge_complete')}\n\n{summary}"
            )
            
            self.merge_completed.emit(result)
            
            # Refresh preview
            self._generate_preview()
            
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _open_conflict_resolver(self):
        """Open the conflict resolution dialog."""
        if not self._conflict_entries:
            QMessageBox.information(
                self, tr("common.info"),
                tr("mission_merge.no_conflicts")
            )
            return
        
        dialog = ConflictResolverDialog(
            self._conflict_entries,
            self.preview,
            parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            # Apply resolved conflicts
            resolved = dialog.get_resolved_conflicts()
            if resolved and self.preview:
                self.preview.resolved_conflicts = resolved
                self._update_preview_ui()
                QMessageBox.information(
                    self, tr("common.success"),
                    tr("mission_merge.conflicts_resolved", count=len(resolved))
                )
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.setWindowTitle(tr("mission_merge.title"))


class ConflictResolverDialog(QDialog):
    """
    Dialog for resolving merge conflicts.
    
    Handles different conflict types:
    - types.xml: Choose one entry to replace
    - cfgrandompresets.xml: Can merge items from multiple sources
    """
    
    def __init__(self, conflict_entries: dict, preview: MergePreview,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.conflict_entries = conflict_entries
        self.preview = preview
        self._resolved: dict = {}
        
        self.setWindowTitle(tr("mission_merge.conflict_resolver_title"))
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        self._setup_ui()
        self._populate_conflicts()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(f"<h2>{tr('mission_merge.conflict_resolver_title')}</h2>")
        layout.addWidget(header)
        
        info_label = QLabel(tr("mission_merge.conflict_resolver_info"))
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Main content: file tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._update_status)
        layout.addWidget(self.tabs, stretch=1)
        
        # Status bar showing unresolved conflicts
        self.status_bar = QLabel()
        self.status_bar.setStyleSheet("color: #ff9800; font-weight: bold; padding: 8px;")
        layout.addWidget(self.status_bar)

        # Force apply toggle (bypass strict validation/gating)
        self.chk_force_apply = QCheckBox(tr("mission_merge.force_apply"))
        self.chk_force_apply.setToolTip(tr("mission_merge.force_apply_tooltip"))
        self.chk_force_apply.stateChanged.connect(self._update_status)
        layout.addWidget(self.chk_force_apply)
        
        # Action buttons
        buttons = QHBoxLayout()
        buttons.addStretch()
        
        self.btn_preview = QPushButton(tr("mission_merge.preview_merge_result"))
        self.btn_preview.clicked.connect(self._show_merge_preview)
        buttons.addWidget(self.btn_preview)
        
        self.btn_apply = QPushButton(tr("common.apply"))
        self.btn_apply.clicked.connect(self._apply_resolution)
        buttons.addWidget(self.btn_apply)
        
        self.btn_cancel = QPushButton(tr("common.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)
        
        layout.addLayout(buttons)
    
    def _populate_conflicts(self):
        """Populate conflict tabs for each file with conflicts."""
        for filename, entries in self.conflict_entries.items():
            tab = self._create_conflict_tab(filename, entries)
            self.tabs.addTab(tab, f"{filename} ({len(entries)})")
        
        self._update_status()

    def _get_tab_data(self, tab: QWidget) -> Optional[dict]:
        """Return the mutable tab_data dict for a conflict tab."""
        if tab is None:
            return None
        td = getattr(tab, "_tab_data", None)
        if isinstance(td, dict):
            return td
        # Fallback for older sessions
        td = tab.property("tab_data")
        return td if isinstance(td, dict) else None
    
    def _create_conflict_tab(self, filename: str, entries: list) -> QWidget:
        """Create a tab for resolving conflicts in a specific file."""
        from PySide6.QtWidgets import QSplitter, QListWidget, QListWidgetItem
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Determine file type for merge strategy
        file_type = ConfigFileType.from_filename(filename)
        is_mergeable = file_type in [ConfigFileType.RANDOMPRESETS, ConfigFileType.EVENTSPAWNS]  # Files where items can be merged
        
        info_text = tr("mission_merge.conflict_replace_info") if not is_mergeable else tr("mission_merge.conflict_merge_info")
        info = QLabel(info_text)
        info.setStyleSheet("color: #ff9800; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Group conflicts by unique key
        conflicts_by_key = {}
        for entry in entries:
            key = entry.unique_key
            if key not in conflicts_by_key:
                conflicts_by_key[key] = []
            conflicts_by_key[key].append(entry)
        
        # Create splitter: list of conflicts on left, details on right
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: list of conflict keys
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_label = QLabel(tr("mission_merge.conflicting_entries"))
        left_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(left_label)
        
        conflict_list = QListWidget()
        conflict_list.setAlternatingRowColors(False)
        for key in conflicts_by_key.keys():
            base_label = key.split(":", 1)[-1] if ":" in key else key
            item = QListWidgetItem(base_label)
            item.setData(Qt.UserRole, key)
            item.setData(Qt.UserRole + 1, base_label)
            conflict_list.addItem(item)
        left_layout.addWidget(conflict_list)
        splitter.addWidget(left_widget)
        
        # Right: conflict resolution options
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_label = QLabel(tr("mission_merge.resolution_options"))
        right_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(right_label)
        
        # Options table
        options_table = QTableWidget()
        options_table.setColumnCount(5)
        options_table.setAlternatingRowColors(False)
        options_table.setHorizontalHeaderLabels([
            tr("mission_merge.select"),
            tr("mission_merge.source_mod"),
            tr("mission_merge.entry_preview"),
            tr("mission_merge.action"),
            tr("mission_merge.status"),
        ])
        options_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        options_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        options_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        options_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        options_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        options_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        options_table.verticalHeader().setVisible(False)
        right_layout.addWidget(options_table)
        
        # Preview text
        preview_label = QLabel(tr("mission_merge.xml_preview"))
        preview_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(preview_label)
        
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setFont(QFont("Consolas", 10))
        preview_text.setMaximumHeight(200)
        preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        right_layout.addWidget(preview_text)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # Store data for this tab
        tab_data = {
            "filename": filename,
            "conflicts_by_key": conflicts_by_key,
            "is_mergeable": is_mergeable,
            "conflict_list": conflict_list,
            "options_table": options_table,
            "preview_text": preview_text,
            "resolved_by_key": {},  # {conflict_key: [{entry, action}, ...]}
            "current_key": None,
            "current_entries": [],
            "_handlers_connected": False,
            "_in_change": False,
        }
        # Store tab data as a plain Python attribute to ensure mutations
        # are visible everywhere (Qt dynamic properties can behave like copies).
        widget._tab_data = tab_data  # type: ignore[attr-defined]
        widget.setProperty("tab_data", tab_data)
        
        # Connect selection signal
        conflict_list.currentItemChanged.connect(
            lambda curr, prev, td=tab_data: self._on_conflict_selected(td, curr)
        )
        
        # Select first item and trigger selection
        if conflict_list.count() > 0:
            conflict_list.setCurrentRow(0)
            # Manually trigger selection for first item
            first_item = conflict_list.item(0)
            if first_item:
                self._on_conflict_selected(tab_data, first_item)
        
        return widget
    
    def _on_conflict_selected(self, tab_data: dict, item):
        """Handle conflict selection in list."""
        if not item:
            return
        
        key = item.data(Qt.UserRole)
        entries = tab_data["conflicts_by_key"].get(key, [])
        is_mergeable = tab_data["is_mergeable"]
        options_table = tab_data["options_table"]
        preview_text = tab_data["preview_text"]

        tab_data["current_key"] = key
        tab_data["current_entries"] = entries
        
        # Completely clear the table
        while options_table.rowCount() > 0:
            options_table.removeRow(0)
        
        # Helper to check whether entry is selected in stored state
        def _is_entry_selected(conflict_key: str, entry_obj) -> tuple[bool, str]:
            selected = tab_data["resolved_by_key"].get(conflict_key, [])
            for sel in selected:
                if sel.get("entry") is entry_obj:
                    return True, str(sel.get("action") or "replace")
            return False, "replace"

        tab_data["_in_change"] = True
        for entry in entries:
            row = options_table.rowCount()
            options_table.insertRow(row)

            # Always use a checkable item for selection.
            # - mergeable: allow multi-select
            # - non-mergeable: enforce exactly one selected (radio-like behavior)
            selected, selected_action = _is_entry_selected(key, entry)
            check_item = QTableWidgetItem("")
            check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            check_item.setData(Qt.UserRole, entry)
            check_item.setData(Qt.UserRole + 1, key)
            check_item.setCheckState(Qt.Checked if selected else Qt.Unchecked)
            options_table.setItem(row, 0, check_item)
            
            # Source mod
            mod_item = QTableWidgetItem(str(entry.source_mod))
            mod_item.setFlags(mod_item.flags() & ~Qt.ItemIsEditable)
            options_table.setItem(row, 1, mod_item)
            
            # Entry preview (truncated)
            xml_str = entry.to_xml_string()
            preview = xml_str[:100] + "..." if len(xml_str) > 100 else xml_str
            preview_item = QTableWidgetItem(str(preview.replace("\n", " ")))
            preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
            preview_item.setToolTip(xml_str)
            options_table.setItem(row, 2, preview_item)
            
            # Action combo (for mergeable files)
            if is_mergeable:
                action_combo = QComboBox()
                action_combo.addItem(tr("mission_merge.action_replace"), "replace")
                action_combo.addItem(tr("mission_merge.action_merge_items"), "merge")
                # Restore last chosen action for this entry if selected
                idx = action_combo.findData(selected_action)
                if idx >= 0:
                    action_combo.setCurrentIndex(idx)
                options_table.setCellWidget(row, 3, action_combo)

                action_combo.currentIndexChanged.connect(
                    lambda _=None, td=tab_data, ck=key, e=entry, combo=action_combo: self._on_merge_action_changed(td, ck, e, combo)
                )
            else:
                action_item = QTableWidgetItem(str(tr("mission_merge.action_replace")))
                action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
                options_table.setItem(row, 3, action_item)

            status_item = QTableWidgetItem(tr("mission_merge.selected") if selected else "")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_item.setForeground(QColor("#4caf50") if selected else QColor("#888"))
            options_table.setItem(row, 4, status_item)

        tab_data["_in_change"] = False

        # Ensure row visuals match stored state
        self._refresh_option_row_visuals(tab_data)
        
        # Show preview of first entry
        if entries:
            xml_preview = f"<!-- {tr('mission_merge.source')}: {entries[0].source_mod} -->\n"
            xml_preview += f"<!-- {tr('mission_merge.file')}: {entries[0].source_file.name} -->\n\n"
            xml_preview += entries[0].to_xml_string()
            preview_text.setText(xml_preview)
        
        # Connect handlers once per tab
        if not tab_data.get("_handlers_connected"):
            options_table.itemChanged.connect(lambda changed_item, td=tab_data: self._on_option_item_changed(td, changed_item))
            options_table.itemClicked.connect(lambda clicked_item, td=tab_data: self._on_option_item_changed(td, clicked_item))
            options_table.cellClicked.connect(lambda r, c, td=tab_data: self._on_option_cell_clicked(td, r, c))
            tab_data["_handlers_connected"] = True

        self._update_status()

        # Update the left list item's resolved marker for this key
        self._update_conflict_key_marker(tab_data, key)

    def _update_conflict_key_marker(self, tab_data: dict, conflict_key: str):
        """Mark the selected conflict key in the left list as resolved/unresolved."""
        conflict_list = tab_data.get("conflict_list")
        resolved_by_key = tab_data.get("resolved_by_key") or {}
        if not conflict_list or not conflict_key:
            return

        is_resolved = bool(resolved_by_key.get(conflict_key))
        for i in range(conflict_list.count()):
            it = conflict_list.item(i)
            if not it:
                continue
            if it.data(Qt.UserRole) != conflict_key:
                continue

            base_label = it.data(Qt.UserRole + 1) or it.text().lstrip("✓ ")
            it.setText(("✓ " if is_resolved else "") + str(base_label))
            it.setForeground(QColor("#4caf50") if is_resolved else QColor("#d4d4d4"))
            break

    def _on_option_item_changed(self, tab_data: dict, changed_item: QTableWidgetItem):
        """Handle selection changes in the options table."""
        if not changed_item:
            return
        if tab_data.get("_in_change"):
            return

        options_table = tab_data["options_table"]
        is_mergeable = tab_data["is_mergeable"]
        conflict_key = changed_item.data(Qt.UserRole + 1) or tab_data.get("current_key")
        if not conflict_key:
            return

        row = changed_item.row()
        col = changed_item.column()
        if col != 0:
            return

        entry = changed_item.data(Qt.UserRole)
        if not entry:
            return

        # Update stored selections
        selected_list = list(tab_data["resolved_by_key"].get(conflict_key, []))

        def _get_action_for_row(r: int) -> str:
            if not is_mergeable:
                return "replace"
            action_widget = options_table.cellWidget(r, 3)
            if isinstance(action_widget, QComboBox):
                return str(action_widget.currentData() or "replace")
            return "replace"

        if changed_item.checkState() == Qt.Checked:
            if not is_mergeable:
                # Radio-like: only one selection allowed for replace-only
                tab_data["_in_change"] = True
                try:
                    for r in range(options_table.rowCount()):
                        item = options_table.item(r, 0)
                        if not item:
                            continue
                        if r != row and item.checkState() == Qt.Checked:
                            item.setCheckState(Qt.Unchecked)
                finally:
                    tab_data["_in_change"] = False

                tab_data["resolved_by_key"][conflict_key] = [{
                    "entry": entry,
                    "action": "replace",
                }]
            else:
                # Mergeable: add to selection (allow multiple)
                action = _get_action_for_row(row)
                # Replace any previous selection for the same entry
                selected_list = [s for s in selected_list if s.get("entry") is not entry]
                selected_list.append({"entry": entry, "action": action})
                tab_data["resolved_by_key"][conflict_key] = selected_list
        else:
            # Unchecked -> remove from selection
            selected_list = [s for s in selected_list if s.get("entry") is not entry]
            if selected_list:
                tab_data["resolved_by_key"][conflict_key] = selected_list
            else:
                tab_data["resolved_by_key"].pop(conflict_key, None)

        # Update visuals & counters
        self._update_conflict_key_marker(tab_data, conflict_key)
        self._refresh_option_row_visuals(tab_data)
        self._update_status()

    def _on_option_cell_clicked(self, tab_data: dict, row: int, col: int):
        """Allow selecting an option by clicking anywhere on its row."""
        self._update_entry_preview_from_tabdata(tab_data, row)

        # Don't toggle when clicking the action combobox cell.
        if tab_data.get("is_mergeable") and col == 3:
            return

        # Toggle the checkbox when clicking any other cell.
        if col != 0:
            sel_item = tab_data.get("options_table").item(row, 0) if tab_data.get("options_table") else None
            if sel_item:
                sel_item.setCheckState(Qt.Unchecked if sel_item.checkState() == Qt.Checked else Qt.Checked)

    def _refresh_option_row_visuals(self, tab_data: dict):
        """Update per-row status text and highlight based on checked state."""
        options_table = tab_data.get("options_table")
        if not options_table:
            return

        for r in range(options_table.rowCount()):
            sel_item = options_table.item(r, 0)
            if not sel_item:
                continue

            checked = sel_item.checkState() == Qt.Checked
            status_item = options_table.item(r, 4)
            if status_item:
                status_item.setText(tr("mission_merge.selected") if checked else "")
                status_item.setForeground(QColor("#4caf50") if checked else QColor("#888"))

            bg = QColor("#1b3b1b") if checked else QColor("#000000")
            for c in range(1, options_table.columnCount()):
                cell = options_table.item(r, c)
                if cell:
                    cell.setBackground(bg)

    def _on_merge_action_changed(self, tab_data: dict, conflict_key: str, entry, combo: QComboBox):
        """Persist action changes for mergeable selections."""
        if tab_data.get("_in_change"):
            return
        if not tab_data.get("is_mergeable"):
            return
        if not conflict_key:
            return
        if not isinstance(combo, QComboBox):
            return

        selections = list((tab_data.get("resolved_by_key") or {}).get(conflict_key, []))
        if not selections:
            return

        updated = False
        new_action = str(combo.currentData() or "replace")
        for sel in selections:
            if sel.get("entry") is entry:
                sel["action"] = new_action
                updated = True
                break

        if updated:
            tab_data["resolved_by_key"][conflict_key] = selections
    
    def _update_entry_preview_from_tabdata(self, tab_data: dict, row: int):
        """Update preview when a row is selected."""
        entries = tab_data.get("current_entries", [])
        preview_text = tab_data["preview_text"]
        
        if row < len(entries):
            entry = entries[row]
            xml_preview = f"<!-- {tr('mission_merge.source')}: {entry.source_mod} -->\n"
            xml_preview += f"<!-- {tr('mission_merge.file')}: {entry.source_file.name} -->\n\n"
            xml_preview += entry.to_xml_string()
            preview_text.setText(xml_preview)
    
    def get_resolved_conflicts(self) -> dict:
        """Get the resolved conflicts from all tabs."""
        resolved = {}
        
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab_data = self._get_tab_data(tab)
            if not tab_data:
                continue
            
            filename = tab_data["filename"]
            for _key, selections in (tab_data.get("resolved_by_key") or {}).items():
                if not selections:
                    continue
                resolved.setdefault(filename, []).extend(selections)
        
        return resolved

    def _compute_conflict_counts(self) -> tuple[int, int]:
        """Return (total_conflict_keys, resolved_conflict_keys) across all tabs."""
        total = 0
        resolved = 0

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab_data = self._get_tab_data(tab)
            if not tab_data:
                continue

            conflicts_by_key = tab_data.get("conflicts_by_key") or {}
            resolved_by_key = tab_data.get("resolved_by_key") or {}
            total += len(conflicts_by_key)

            for key in conflicts_by_key.keys():
                if resolved_by_key.get(key):
                    resolved += 1

        return total, resolved
    
    def _update_status(self):
        """Update status bar with conflict count."""
        total_conflicts, resolved_count = self._compute_conflict_counts()
        unresolved = max(0, total_conflicts - resolved_count)
        
        force = bool(getattr(self, "chk_force_apply", None) and self.chk_force_apply.isChecked())

        if unresolved > 0:
            self.status_bar.setText(
                f"⚠️ {tr('mission_merge.unresolved_conflicts', count=unresolved)}"
            )
            self.status_bar.setStyleSheet(
                "color: #ff5252; font-weight: bold; padding: 8px; background-color: rgba(255, 82, 82, 0.1);"
            )
            self.btn_apply.setEnabled(True if force else False)
        else:
            self.status_bar.setText(
                f"✅ {tr('mission_merge.all_conflicts_resolved')}"
            )
            self.status_bar.setStyleSheet("color: #4caf50; font-weight: bold; padding: 8px; background-color: rgba(76, 175, 80, 0.1);")
            self.btn_apply.setEnabled(True)
    
    def _apply_resolution(self):
        """Apply conflict resolution only if all conflicts are resolved."""
        from xml.etree import ElementTree as ET

        total_conflicts, resolved_conflicts = self._compute_conflict_counts()
        
        resolved = self.get_resolved_conflicts()

        force = bool(getattr(self, "chk_force_apply", None) and self.chk_force_apply.isChecked())
        
        if (resolved_conflicts < total_conflicts) and not force:
            QMessageBox.warning(
                self,
                tr("common.warning"),
                tr("mission_merge.must_resolve_all_conflicts")
            )
            return

        # In force mode, skip strict validations to allow continuing even when
        # some mods use non-standard structures/identifiers.
        if force:
            self.accept()
            return
        
        # Check for duplicate names in resolved entries (for replace actions)
        for filename, resolutions in resolved.items():
            names = {}
            replace_count_per_conflict = {}  # Track replace actions per conflict key
            
            for res in resolutions:
                entry = res["entry"]
                action = res["action"]
                name = entry.element.get("name")
                conflict_key = entry.unique_key
                
                # For non-mergeable files, ensure only ONE replace per conflict
                if action == "replace":
                    if conflict_key not in replace_count_per_conflict:
                        replace_count_per_conflict[conflict_key] = 0
                    replace_count_per_conflict[conflict_key] += 1
                    
                    if replace_count_per_conflict[conflict_key] > 1:
                        QMessageBox.warning(
                            self,
                            tr("common.warning"),
                            tr("mission_merge.multiple_replace_detected", key=conflict_key.split(":")[-1], file=filename)
                        )
                        return
                
                if action == "replace" and name:
                    if name in names:
                        QMessageBox.warning(
                            self,
                            tr("common.warning"),
                            tr("mission_merge.duplicate_name_detected", name=name, file=filename)
                        )
                        return
                    names[name] = True
        
        # For merge actions, check for duplicate child item names
        for filename, resolutions in resolved.items():
            merge_groups = {}
            for res in resolutions:
                if res["action"] == "merge":
                    entry = res["entry"]
                    parent_key = self._get_parent_key(entry.element)
                    if parent_key not in merge_groups:
                        merge_groups[parent_key] = set()

                    def _child_signature(ch) -> str:
                        name = ch.get("name")
                        if name:
                            return f"{ch.tag}:name:{name}"
                        # Special-case event spawn positions
                        if ch.tag.lower() == "pos":
                            x = ch.get("x") or ""
                            y = ch.get("y") or ""
                            z = ch.get("z") or ""
                            a = ch.get("a") or ""
                            return f"pos:{x}:{y}:{z}:{a}"
                        # Fallback: tag + sorted attributes
                        attrs = ";".join([f"{k}={v}" for k, v in sorted((ch.attrib or {}).items())])
                        return f"{ch.tag}:{attrs}"

                    for child in entry.element:
                        sig = _child_signature(child)
                        if sig in merge_groups[parent_key]:
                            QMessageBox.warning(
                                self,
                                tr("common.warning"),
                                tr("mission_merge.duplicate_child_item", name=sig, parent=parent_key, file=filename)
                            )
                            return
                        merge_groups[parent_key].add(sig)
        
        self.accept()
    
    def _show_merge_preview(self):
        """Show preview of final merge result."""
        from xml.etree import ElementTree as ET
        
        resolved = self.get_resolved_conflicts()
        
        if not resolved:
            QMessageBox.information(
                self,
                tr("common.info"),
                tr("mission_merge.no_selections_to_preview")
            )
            return
        
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle(tr("mission_merge.merge_result_preview"))
        preview_dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(preview_dialog)
        
        header = QLabel(f"<h3>{tr('mission_merge.merge_result_preview')}</h3>")
        layout.addWidget(header)
        
        info = QLabel(tr("mission_merge.merge_preview_info"))
        info.setStyleSheet("color: gray; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Tabs for each file
        tabs = QTabWidget()
        
        for filename, resolutions in resolved.items():
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Consolas", 10))
            text_edit.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                }
            """)
            
            # Build merged XML preview
            xml_content = f"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
            xml_content += f"<!-- Merged from {len(resolutions)} selected entries -->\n\n"
            
            # Group resolutions by parent key (for merge action)
            merge_groups = {}
            replace_entries = []
            
            for res in resolutions:
                entry = res["entry"]
                action = res["action"]
                
                if action == "merge":
                    # Group by parent element attributes (e.g., cargo name)
                    parent_key = self._get_parent_key(entry.element)
                    if parent_key not in merge_groups:
                        merge_groups[parent_key] = {
                            "parent_tag": entry.element.tag,
                            "parent_attrs": dict(entry.element.attrib),
                            "children": [],
                            "sources": []
                        }
                    def _child_signature(ch) -> str:
                        name = ch.get("name")
                        if name:
                            return f"{ch.tag}:name:{name}"
                        if ch.tag.lower() == "pos":
                            x = ch.get("x") or ""
                            y = ch.get("y") or ""
                            z = ch.get("z") or ""
                            a = ch.get("a") or ""
                            return f"pos:{x}:{y}:{z}:{a}"
                        attrs = ";".join([f"{k}={v}" for k, v in sorted((ch.attrib or {}).items())])
                        return f"{ch.tag}:{attrs}"

                    existing_sigs = {_child_signature(c) for c in merge_groups[parent_key]["children"]}
                    for child in entry.element:
                        sig = _child_signature(child)
                        if sig not in existing_sigs:
                            # Clone the child element
                            cloned = ET.Element(child.tag, child.attrib)
                            cloned.text = child.text
                            cloned.tail = child.tail
                            for subchild in child:
                                cloned.append(subchild)
                            merge_groups[parent_key]["children"].append(cloned)
                            existing_sigs.add(sig)
                    merge_groups[parent_key]["sources"].append(entry.source_mod)
                else:
                    replace_entries.append((entry, action))
            
            # Build XML for merged groups
            for parent_key, merge_data in merge_groups.items():
                sources_str = ", ".join(merge_data["sources"])
                xml_content += f"<!-- Merged from: {sources_str} -->\n"
                
                # Reconstruct parent element with all children
                parent_tag = merge_data["parent_tag"]
                attrs_str = " ".join([f'{k}=\"{v}\"' for k, v in merge_data["parent_attrs"].items()])
                xml_content += f"<{parent_tag} {attrs_str}>\n"
                
                for child in merge_data["children"]:
                    child_str = ET.tostring(child, encoding="unicode").strip()
                    xml_content += f"    {child_str}\n"
                
                xml_content += f"</{parent_tag}>\n\n"
            
            # Add replace entries
            for entry, action in replace_entries:
                xml_content += f"<!-- Entry: {entry.source_mod} ({action}) -->\n"
                xml_content += entry.to_xml_string() + "\n\n"
            
            text_edit.setText(xml_content)
            tabs.addTab(text_edit, f"{filename} ({len(resolutions)})")
        
        layout.addWidget(tabs)
        
        close_btn = QPushButton(tr("common.close"))
        close_btn.clicked.connect(preview_dialog.close)
        layout.addWidget(close_btn)
        
        preview_dialog.exec()
    
    def _get_parent_key(self, element: ET.Element) -> str:
        """Get a unique key for parent element based on its attributes."""
        # For cargo elements, use tag + name attribute
        name = element.get("name")
        if name:
            return f"{element.tag}:{name}"
        # Fallback to tag only
        return element.tag
