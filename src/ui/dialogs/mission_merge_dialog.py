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

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QGroupBox,
    QMessageBox, QCheckBox, QTabWidget, QWidget,
    QProgressDialog, QHeaderView, QFrame,
    QTableWidget, QTableWidgetItem, QComboBox, QAbstractItemView
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
        
        self._setup_ui()
        self.setWindowTitle(tr("mission_merge.title"))
        self.setMinimumSize(1400, 850)
        self.resize(1600, 900)
        
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
        
        # Select all button
        self.btn_select_all = QPushButton(tr("common.select_all"))
        self.btn_select_all.clicked.connect(self._select_all_mods)
        header.addWidget(self.btn_select_all)
        
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
        
        self.lbl_manual = QLabel(f"{tr('mission_merge.needs_manual')}: 0")
        self.lbl_manual.setStyleSheet("color: #ff9800;")
        summary_layout.addWidget(self.lbl_manual)
        
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
        # Block preview if there are invalid merge mappings selected
        self._refresh_mapping_warnings()
        if self.lbl_mapping_warnings.text().strip():
            QMessageBox.warning(self, tr("common.warning"), tr("mission_merge.fix_mapping_before_preview"))
            return

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
            self._update_preview_ui()
            self.btn_merge.setEnabled(
                self.preview.total_new > 0 or 
                self.preview.total_conflicts > 0 or
                any(len(files) > 0 for files in copy_by_mod.values())
            )
        finally:
            progress.close()
    
    def _update_preview_ui(self):
        """Update UI with preview data."""
        if not self.preview:
            return
            
        # Update summary
        self.lbl_total_new.setText(f"{tr('mission_merge.new_entries')}: {self.preview.total_new}")
        self.lbl_total_dup.setText(f"{tr('mission_merge.duplicates')}: {self.preview.total_duplicates}")
        self.lbl_total_conflict.setText(f"{tr('mission_merge.conflicts')}: {self.preview.total_conflicts}")
        self.lbl_manual.setText(f"{tr('mission_merge.needs_manual')}: {len(self.preview.mods_needing_manual)}")
        
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
            item.setText(3, str(result.conflicts))
            
            # Color code
            if result.conflicts > 0:
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
        
        for filename, result in self.preview.merge_results.items():
            file_item = QTreeWidgetItem()
            file_item.setText(0, filename)
            file_item.setFont(0, QFont("", -1, QFont.Bold))
            
            count = 0
            
            # Add entries
            all_entries = result.merged_entries + result.conflict_entries
            for entry in all_entries:
                if entry.status == MergeStatus.NEW and not show_new:
                    continue
                if entry.status == MergeStatus.DUPLICATE and not show_dup:
                    continue
                if entry.status == MergeStatus.CONFLICT and not show_conflict:
                    continue
                    
                entry_item = EntryTreeItem(entry)
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
    
    def _select_all_mods(self):
        """Select all mods that are not skipped."""
        for row in range(self.tbl_sources.rowCount()):
            use_item = self.tbl_sources.item(row, 0)
            if not use_item:
                continue
            mod_name = str(use_item.data(Qt.UserRole + 1) or "")
            if mod_name and mod_name in self.skipped_mods:
                continue
            use_item.setCheckState(Qt.Checked)

        self._update_new_files_count()
        self._refresh_mapping_warnings()
    
    def _execute_merge(self):
        """Execute the merge operation."""
        if not self.preview:
            return

        # Safety: prevent merge if current mapping shows warnings
        self._refresh_mapping_warnings()
        if getattr(self, "lbl_mapping_warnings", None) and self.lbl_mapping_warnings.text().strip():
            QMessageBox.warning(self, tr("common.warning"), tr("mission_merge.fix_mapping_before_preview"))
            return
        
        # Count what will be merged
        new_files_map = getattr(self.preview, 'new_files_to_copy', {})
        new_files_count = sum(len(files) for files in new_files_map.values())
        
        # Confirm
        msg = tr("mission_merge.confirm_merge").format(
            new=self.preview.total_new,
            conflicts=self.preview.total_conflicts if self.chk_include_conflicts.isChecked() else 0
        )
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
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.setWindowTitle(tr("mission_merge.title"))
