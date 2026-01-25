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
from typing import Optional, Type

from xml.etree import ElementTree as ET

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QGroupBox,
    QMessageBox, QCheckBox, QTabWidget, QWidget,
    QProgressDialog, QHeaderView, QFrame,
    QTableWidget, QTableWidgetItem, QComboBox, QAbstractItemView,
    QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QApplication, QStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from shared.ui.components.table import ReusableTable, TableColumn, TableGroup

from features.config.core.mission_config_merger import (
    MissionConfigMerger, MergePreview, ModConfigInfo, 
    MergeStatus, ConfigEntry, get_mission_folder_path,
    ConfigFileType, detect_map_from_filename,
    is_map_specific_file, get_base_config_filename
)
from features.config.models.xml_config_models import (
    ConfigTypeRegistry, XMLMergeHelper, MergeStrategy, FieldMergeRule,
    TypesXMLModel, SpawnableTypesXMLModel, RandomPresetsXMLModel,
    EventsXMLModel, EventSpawnsXMLModel, IgnoreListXMLModel,
    WeatherXMLModel, EconomyCoreXMLModel, EnvironmentXMLModel,
    MapGroupXMLModel, MapProtoXMLModel
)
from shared.ui.widgets.icon_button import IconButton
from shared.ui.widgets.lazy_loading_dialog import LazyLoadingDialog
from shared.utils.locale_manager import tr
from features.mods.core.mod_name_manager import ModNameManager


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
        # Show readable display name for source mod when possible
        src_mod = str(entry.source_mod or "")
        display_src = src_mod
        try:
            # access name manager from parent dialog if available via Qt parent chain
            # Fallback to trying self.window() attribute
            parent = getattr(self, 'parent', None)
        except Exception:
            parent = None
        try:
            if hasattr(self, 'treeWidget') and getattr(self.treeWidget(), 'parent', None):
                maybe = self.treeWidget().parent()
            else:
                maybe = None
        except Exception:
            maybe = None
        try:
            nm = None
            if getattr(self, 'treeWidget', None) and self.treeWidget() is not None:
                win = self.treeWidget().window()
                nm = getattr(win, '_name_mgr', None)
            if nm:
                display_src = nm.get_original_name(src_mod)
        except Exception:
            display_src = src_mod
        self.setText(2, display_src)
        
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
        
        # Name manager resolves shortened folder names like @m1 to original display names
        try:
            self._name_mgr = ModNameManager(server_path)
        except Exception:
            self._name_mgr = None

        self.merger = MissionConfigMerger(
            self.mission_path,
            server_path,
            self.current_map,
            name_mgr=self._name_mgr,
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
        
        # Main content - horizontal splitter with table left and tabs right
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
        """Create main content area with source table on left and tabs on right."""
        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Source files with tabs for Valid/Invalid
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        sources_label = QLabel(f"<b>{tr('mission_merge.mods_with_configs')}</b>")
        left_layout.addWidget(sources_label)

        # Tab widget for Valid/Invalid source files
        self.source_tabs = QTabWidget()
        
        # Tab 1: Valid files (can be merged)
        valid_tab = QWidget()
        valid_layout = QVBoxLayout(valid_tab)
        valid_layout.setContentsMargins(4, 4, 4, 4)
        
        # Hint for double-click
        hint_label = QLabel("Double-click a row to view file details")
        hint_label.setStyleSheet("color: gray; font-size: 11px;")
        valid_layout.addWidget(hint_label)
        
        # Define columns for sources table
        source_columns = [
            TableColumn("file", tr("mission_merge.col_file"), QHeaderView.Stretch),
            TableColumn("type", tr("mission_merge.col_type"), QHeaderView.ResizeToContents),
            TableColumn("entries", tr("mission_merge.col_entries"), QHeaderView.ResizeToContents),
            TableColumn("action", tr("mission_merge.col_action"), QHeaderView.Interactive),
            TableColumn("target", tr("mission_merge.col_target"), QHeaderView.Interactive),
            TableColumn("status", tr("mission_merge.col_status"), QHeaderView.ResizeToContents),
        ]
        
        self.tbl_sources = ReusableTable(source_columns, has_checkbox=True)
        self.tbl_sources.setAlternatingRowColors(False)
        self.tbl_sources.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_sources.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_sources.verticalHeader().setDefaultSectionSize(32)
        self.tbl_sources.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive)
        self.tbl_sources.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.tbl_sources.setColumnWidth(4, 140)
        self.tbl_sources.setColumnWidth(5, 180)
        self.tbl_sources.verticalHeader().setVisible(False)
        self.tbl_sources.set_row_click_toggles_checkbox(True)
        self.tbl_sources.row_double_clicked.connect(self._on_source_file_selected)
        self.tbl_sources.setMinimumHeight(300)
        self.tbl_sources.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        valid_layout.addWidget(self.tbl_sources)
        
        self.source_tabs.addTab(valid_tab, tr("mission_merge.tab_valid_files"))
        
        # Tab 2: Invalid files (cannot be parsed/merged)
        invalid_tab = QWidget()
        invalid_layout = QVBoxLayout(invalid_tab)
        invalid_layout.setContentsMargins(4, 4, 4, 4)
        
        invalid_info = QLabel(tr("mission_merge.invalid_files_info"))
        invalid_info.setStyleSheet("color: #ff9800; font-size: 11px;")
        invalid_info.setWordWrap(True)
        invalid_layout.addWidget(invalid_info)
        
        # Hint for double-click
        invalid_hint = QLabel("Double-click a row to view file details")
        invalid_hint.setStyleSheet("color: gray; font-size: 11px;")
        invalid_layout.addWidget(invalid_hint)
        
        invalid_columns = [
            TableColumn("file", tr("mission_merge.col_file"), QHeaderView.Interactive),
            TableColumn("mod", tr("mission_merge.col_mod"), QHeaderView.ResizeToContents),
            TableColumn("reason", tr("mission_merge.col_reason"), QHeaderView.Stretch),
            TableColumn("path", tr("mission_merge.col_path"), QHeaderView.Interactive),
        ]

        self.tbl_invalid_sources = ReusableTable(invalid_columns, has_checkbox=False)
        self.tbl_invalid_sources.setAlternatingRowColors(False)
        self.tbl_invalid_sources.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_invalid_sources.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_invalid_sources.verticalHeader().setDefaultSectionSize(28)
        self.tbl_invalid_sources.setColumnWidth(0, 180)
        self.tbl_invalid_sources.setColumnWidth(3, 300)
        self.tbl_invalid_sources.verticalHeader().setVisible(False)
        self.tbl_invalid_sources.set_row_click_toggles_checkbox(True)
        self.tbl_invalid_sources.row_double_clicked.connect(self._on_invalid_file_selected)
        self.tbl_invalid_sources.setMinimumHeight(200)
        self.tbl_invalid_sources.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        invalid_layout.addWidget(self.tbl_invalid_sources)
        
        self.source_tabs.addTab(invalid_tab, tr("mission_merge.tab_invalid_files"))
        
        left_layout.addWidget(self.source_tabs)

        self.lbl_mapping_warnings = QLabel("")
        self.lbl_mapping_warnings.setStyleSheet("color: #ff9800; font-size: 11px;")
        self.lbl_mapping_warnings.setWordWrap(True)
        left_layout.addWidget(self.lbl_mapping_warnings)

        self.chk_ignore_mapping_warnings = QCheckBox(tr("mission_merge.ignore_mapping_warnings"))
        self.chk_ignore_mapping_warnings.setToolTip(tr("mission_merge.ignore_mapping_warnings_tooltip"))
        self.chk_ignore_mapping_warnings.setChecked(False)
        left_layout.addWidget(self.chk_ignore_mapping_warnings)
        
        main_splitter.addWidget(left_widget)

        # Right: Tab widget with Mission targets, File preview, Overview, etc.
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        # Tab 1: Mission Target Files
        targets_tab = self._create_targets_tab()
        self.tabs.addTab(targets_tab, tr("mission_merge.targets"))
        
        # Tab 2: File Preview (when selecting a file from left table)
        file_preview_tab = self._create_file_preview_tab()
        self.tabs.addTab(file_preview_tab, tr("mission_merge.tab_file_preview"))
        
        # Tab 3: Overview
        overview_tab = self._create_overview_tab()
        self.tabs.addTab(overview_tab, tr("mission_merge.tab_overview"))
        
        # Tab 4: Entries  
        entries_tab = self._create_entries_tab()
        self.tabs.addTab(entries_tab, tr("mission_merge.tab_entries"))
        
        right_layout.addWidget(self.tabs)
        main_splitter.addWidget(right_widget)
        
        # Set splitter sizes (60% left, 40% right)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setSizes([600, 400])
        
        layout.addWidget(main_splitter, stretch=1)
    
    def _create_targets_tab(self) -> QWidget:
        """Create tab showing mission target files."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Columns: file, exists, current entries, planned changes, planned mods
        target_columns = [
            TableColumn("file", tr("mission_merge.target_file"), QHeaderView.Interactive),
            TableColumn("exists", tr("mission_merge.exists"), QHeaderView.ResizeToContents),
            TableColumn("entries", tr("mission_merge.entries"), QHeaderView.ResizeToContents),
            TableColumn("planned_changes", tr("mission_merge.planned_changes"), QHeaderView.ResizeToContents),
            TableColumn("planned_mods", tr("mission_merge.planned_mods"), QHeaderView.Stretch),
        ]

        self.tbl_targets = ReusableTable(target_columns, has_checkbox=False)
        self.tbl_targets.setAlternatingRowColors(False)
        self.tbl_targets.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_targets.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_targets.setColumnWidth(0, 200)
        self.tbl_targets.verticalHeader().setVisible(False)
        self.tbl_targets.verticalHeader().setDefaultSectionSize(28)
        self.tbl_targets.set_row_click_toggles_checkbox(True)
        self.tbl_targets.setMinimumHeight(200)

        self.tbl_targets.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.tbl_targets)

        return widget
    
    def _create_file_preview_tab(self) -> QWidget:
        """Create tab for previewing selected source file content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Info label
        self.lbl_file_preview_info = QLabel(tr("mission_merge.select_file_to_preview"))
        self.lbl_file_preview_info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.lbl_file_preview_info)
        
        # File info
        info_layout = QHBoxLayout()
        self.lbl_file_name = QLabel("")
        self.lbl_file_name.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.lbl_file_name)
        info_layout.addStretch()
        self.lbl_file_entries = QLabel("")
        self.lbl_file_entries.setStyleSheet("color: #4caf50;")
        info_layout.addWidget(self.lbl_file_entries)
        layout.addLayout(info_layout)
        
        # XML content
        self.txt_file_preview = QTextEdit()
        self.txt_file_preview.setReadOnly(True)
        self.txt_file_preview.setFont(QFont("Consolas", 10))
        self.txt_file_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        self.txt_file_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.txt_file_preview.setMinimumHeight(200)
        layout.addWidget(self.txt_file_preview)
        
        return widget
    
    def _on_source_file_selected(self, row: int):
        """Handle double-click on source files table row."""
        # Skip if this is a group header
        if self.tbl_sources.is_group_header(row):
            return

        row_data = self.tbl_sources.get_row_data(row)
        if not row_data or not row_data.get("_file_path"):
            return

        file_path = Path(row_data["_file_path"])

        # Update file preview tab
        self._preview_xml_file(file_path)
    
    def _on_invalid_file_selected(self, row: int):
        """Handle double-click on invalid files table row."""
        row_data = self.tbl_invalid_sources.get_row_data(row)
        if not row_data or not row_data.get("path", {}).get("text"):
            return

        file_path = Path(row_data["path"]["text"])

        # Preview as text (not XML)
        self._preview_text_file(file_path)
    
    def _preview_xml_file(self, file_path: Path):
        """Preview a file as XML."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            self.lbl_file_name.setText(f"📄 {file_path.name}")
            
            # Detect config type using model + forgiving parsing for fragments
            try:
                _, root, model_class = XMLMergeHelper.parse_xml_file(file_path)
                entry_count = len([c for c in list(root) if isinstance(c.tag, str)])

                if model_class:
                    mergeable_fields = XMLMergeHelper.get_mergeable_fields(model_class)
                    merge_strategy = model_class.get_merge_strategy()
                    type_info = (
                        f"{tr('mission_merge.file_preview_type')}: {model_class.__name__} | "
                        f"{tr('mission_merge.file_preview_strategy')}: {self._strategy_label(merge_strategy)}"
                    )
                    if mergeable_fields:
                        type_info += (
                            f" | {tr('mission_merge.file_preview_mergeable')}: "
                            f"{', '.join(mergeable_fields)}"
                        )
                    self.lbl_file_entries.setText(f"{tr('mission_merge.entries')}: {entry_count} | {type_info}")
                else:
                    self.lbl_file_entries.setText(
                        f"{tr('mission_merge.entries')}: {entry_count} | {tr('mission_merge.file_preview_type')}: {tr('mission_merge.file_preview_unknown_type')}"
                    )
            except Exception:
                self.lbl_file_entries.setText(f"{tr('mission_merge.entries')}: ?")
            
            self.txt_file_preview.setText(content)
            self.lbl_file_preview_info.setText(str(file_path))
            
            # Switch to file preview tab
            self.tabs.setCurrentIndex(1)
            
        except Exception as e:
            self.txt_file_preview.setText(
                tr("mission_merge.file_preview_error_loading").format(error=str(e))
            )
    
    def _preview_text_file(self, file_path: Path):
        """Preview a file as plain text (for invalid XML files)."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            self.lbl_file_name.setText(
                tr("mission_merge.file_preview_invalid_title").format(name=file_path.name)
            )
            self.lbl_file_entries.setText(
                tr("mission_merge.file_preview_size").format(size=file_path.stat().st_size)
            )
            
            self.txt_file_preview.setText(content)
            self.lbl_file_preview_info.setText(str(file_path))
            
            # Switch to file preview tab
            self.tabs.setCurrentIndex(1)
            
        except Exception as e:
            self.txt_file_preview.setText(
                tr("mission_merge.file_preview_error_loading").format(error=str(e))
            )
    
    def _count_valid_entries(self, file_path: Path) -> int:
        """Count entries with valid mergeable data."""
        try:
            _, root, model_class = XMLMergeHelper.parse_xml_file(file_path)
            count = 0
            
            for child in root:
                if not isinstance(child.tag, str) or not child.tag.strip():
                    continue
                
                if model_class:
                    # Use model's entry key attribute
                    entry_key_attr = model_class.get_entry_key_attribute() if hasattr(model_class, 'get_entry_key_attribute') else "name"
                    if entry_key_attr and child.get(entry_key_attr):
                        count += 1
                    elif len(list(child)) > 0:  # Has children
                        count += 1
                else:
                    # Fallback to generic check
                    if child.get("name") or child.get("type") or child.get("id") or len(list(child)) > 0:
                        count += 1
            return count
        except:
            return 0
    
    def _is_file_valid_for_merge(self, file_path: Path) -> tuple[bool, str, Optional[Type]]:
        """Check if a file has valid data for merging.
        
        Returns: (is_valid, reason, model_class)
        """
        try:
            _, root, model_class = XMLMergeHelper.parse_xml_file(file_path)
            
            # Check if root has children
            children = [c for c in root if isinstance(c.tag, str)]
            if not children:
                return False, tr("mission_merge.no_valid_entries"), model_class
            
            # Check if any child has identifiable attributes
            valid_count = 0
            for child in children:
                if model_class:
                    entry_key_attr = model_class.get_entry_key_attribute() if hasattr(model_class, 'get_entry_key_attribute') else None
                    if entry_key_attr and child.get(entry_key_attr):
                        valid_count += 1
                    elif len(list(child)) > 0:
                        valid_count += 1
                else:
                    if child.get("name") or child.get("type") or child.get("id") or len(list(child)) > 0:
                        valid_count += 1
            
            if valid_count == 0:
                return False, tr("mission_merge.no_identifiable_entries"), model_class
            
            return True, "", model_class
        except ET.ParseError as e:
            return False, f"{tr('mission_merge.xml_parse_error')}: {str(e)}", None
        except Exception as e:
            return False, str(e), None

    def _strategy_label(self, strategy: MergeStrategy) -> str:
        mapping = {
            MergeStrategy.REPLACE: tr("mission_merge.strategy_replace"),
            MergeStrategy.MERGE_CHILDREN: tr("mission_merge.strategy_merge_children"),
            MergeStrategy.APPEND: tr("mission_merge.strategy_append"),
            MergeStrategy.SKIP: tr("mission_merge.strategy_skip"),
        }
        return mapping.get(strategy, getattr(strategy, "name", str(strategy)))

    def _display_mod_name(self, mod_name: str) -> str:
        """Return a user-friendly display name for a mod folder name."""
        try:
            if getattr(self, "_name_mgr", None) and mod_name:
                return self._name_mgr.get_original_name(str(mod_name))
        except Exception:
            pass
        return str(mod_name or "")
    
    def _get_merge_suggestion(self, file_path: Path, model_class: Optional[Type]) -> tuple[str, str]:
        """Get merge suggestion based on model.
        
        Returns: (action, suggested_target)
        """
        if not model_class:
            # Unknown type - suggest copy
            return "copy", file_path.name
        
        # Get merge strategy from model
        merge_strategy = model_class.get_merge_strategy()
        
        # Get target filename
        root_element = model_class.get_root_element()
        
        # Find matching target file
        suggested_target = file_path.name
        
        # Map model to standard DayZ filenames
        model_to_filename = {
            TypesXMLModel: "types.xml",
            SpawnableTypesXMLModel: "cfgspawnabletypes.xml",
            RandomPresetsXMLModel: "cfgrandompresets.xml",
            EventsXMLModel: "events.xml",
            EventSpawnsXMLModel: "cfgeventspawns.xml",
            IgnoreListXMLModel: "cfgignorelist.xml",
            WeatherXMLModel: "cfgweather.xml",
            EconomyCoreXMLModel: "cfgeconomycore.xml",
            EnvironmentXMLModel: "cfgenvironment.xml",
            MapGroupXMLModel: file_path.name,  # Keep original name for map files
            MapProtoXMLModel: file_path.name,
        }
        
        if model_class in model_to_filename:
            suggested_target = model_to_filename[model_class]
        
        # Determine action based on merge strategy
        if merge_strategy == MergeStrategy.REPLACE:
            return "merge", suggested_target
        elif merge_strategy == MergeStrategy.MERGE_CHILDREN:
            return "merge", suggested_target
        elif merge_strategy == MergeStrategy.APPEND:
            return "merge", suggested_target
        else:
            return "copy", suggested_target

    def _get_expected_target(self, model_class: Optional[Type]) -> Optional[str]:
        """Get the expected target filename for a model class."""
        if not model_class:
            return None
        model_to_filename = {
            TypesXMLModel: "types.xml",
            SpawnableTypesXMLModel: "cfgspawnabletypes.xml",
            RandomPresetsXMLModel: "cfgrandompresets.xml",
            EventsXMLModel: "events.xml",
            EventSpawnsXMLModel: "cfgeventspawns.xml",
            IgnoreListXMLModel: "cfgignorelist.xml",
            WeatherXMLModel: "cfgweather.xml",
            EconomyCoreXMLModel: "cfgeconomycore.xml",
            EnvironmentXMLModel: "cfgenvironment.xml",
            # MapGroup and MapProto don't have fixed targets
        }
        return model_to_filename.get(model_class)

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
        self.tbl_invalid_sources.setRowCount(0)
        self.merger.load_skipped_mods(self.skipped_mods)
        
        progress = QProgressDialog(
            tr("mission_merge.scanning"), tr("common.cancel"), 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()
        
        mod_infos = []
        try:
            progress.setValue(10)
            QApplication.processEvents()
            # Scan all XML files (including unknown parent class)
            mod_infos = self.merger.scan_all_mods(scan_all_xml=True)
            progress.setValue(80)
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("common.error"),
                f"{tr('mission_merge.scan_error')}\n\n{e}"
            )
            return
        finally:
            progress.setValue(100)
            QApplication.processEvents()
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

        self._available_targets = targets

        # Prepare data for ReusableTable
        table_data = []
        for filename in targets:
            file_path = self.mission_path / filename
            exists = file_path.exists()
            entries = "-"
            if exists:
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    entries = str(len(list(root)))
                except Exception:
                    entries = "?"

            table_data.append({
                "file": {"text": filename},
                "exists": {"text": "✓" if exists else "-"},
                "entries": {"text": entries},
                "planned_changes": {"text": "-"},
                "planned_mods": {"text": "-"},
                # Store additional data
                "_filename": filename,
                "_file_path": str(file_path),
                "_exists": exists
            })

        self.tbl_targets.set_data(table_data)
        self._update_targets_table_preview()

    def _update_targets_table_preview(self):
        """Update planned changes/mods columns based on the current preview selections."""
        if not hasattr(self, "tbl_targets"):
            return

        preview = getattr(self, "preview", None)
        resolved_map = getattr(preview, "resolved_conflicts", None) if preview else None
        resolved_map = resolved_map or {}

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

        include_conflicts = bool(getattr(self, "chk_include_conflicts", None) and self.chk_include_conflicts.isChecked())

        for row in range(self.tbl_targets.rowCount()):
            row_data = self.tbl_targets.get_row_data(row)
            if not row_data:
                continue
            filename = row_data["_filename"]

            planned_changes = "-"
            planned_mods = "-"

            if preview and filename in getattr(preview, "merge_results", {}):
                result = preview.merge_results.get(filename)
                new_count = len(getattr(result, "merged_entries", []) or [])
                resolved_for_file = (resolved_map.get(filename, []) or [])
                resolved_count = len([r for r in resolved_for_file if isinstance(r, dict) and r.get("entry") is not None])
                extra_conflicts = _remaining_conflict_count(filename, result) if include_conflicts else 0
                planned_changes = str(new_count + resolved_count + extra_conflicts)

                mods: set[str] = set()
                for e in getattr(result, "merged_entries", []) or []:
                    m = str(getattr(e, "source_mod", "") or "")
                    if m:
                        mods.add(m)
                for r in resolved_for_file:
                    if not isinstance(r, dict):
                        continue
                    e = r.get("entry")
                    if e is None:
                        continue
                    m = str(getattr(e, "source_mod", "") or "")
                    if m:
                        mods.add(m)
                if include_conflicts:
                    resolved_keys = _resolved_keys_for_file(filename)
                    for e in getattr(result, "conflict_entries", []) or []:
                        if str(getattr(e, "unique_key", "")) in resolved_keys:
                            continue
                        m = str(getattr(e, "source_mod", "") or "")
                        if m:
                            mods.add(m)

                mods_list = sorted(mods)
                # Convert to display names if possible
                try:
                    if getattr(self, "_name_mgr", None):
                        mods_display = [self._name_mgr.get_original_name(m) for m in mods_list]
                    else:
                        mods_display = mods_list
                except Exception:
                    mods_display = mods_list

                if not mods_display:
                    planned_mods = "-"
                elif len(mods_display) <= 3:
                    planned_mods = ", ".join(mods_display)
                else:
                    planned_mods = ", ".join(mods_display[:3]) + f" (+{len(mods_display) - 3} {tr('common.more')})"

            # Update the table data
            self.tbl_targets.set_cell_data(row, "planned_changes", {"text": planned_changes})
            self.tbl_targets.set_cell_data(row, "planned_mods", {"text": planned_mods})

    def _populate_sources_table(self, mod_infos: list[ModConfigInfo]):
        """Populate left tables with source XML files from mods - split into valid/invalid."""
        self._scanned_mod_infos = mod_infos
        self.tbl_invalid_sources.setRowCount(0)

        valid_count = 0
        invalid_count = 0

        # Prepare data for ReusableTable with groups
        groups_data = []

# Prepare data for invalid sources table
        invalid_table_data = []

        for mod_info in mod_infos:
            # Separate files into valid and invalid
            valid_files = []
            invalid_files = []

            for config_file in mod_info.config_files:
                is_valid_file, invalid_reason, model_class = self._is_file_valid_for_merge(config_file)
                if is_valid_file:
                    valid_files.append((config_file, model_class))
                else:
                    invalid_files.append((config_file, invalid_reason))

            # Determine display name (use original name if mapping exists)
            display_mod_name = mod_info.mod_name
            try:
                if getattr(self, "_name_mgr", None):
                    display_mod_name = self._name_mgr.get_original_name(mod_info.mod_name)
            except Exception:
                display_mod_name = mod_info.mod_name

            # Add valid files to main table grouped by mod
            if valid_files:
                group_rows = []
                for config_file, model_class in valid_files:
                    row_data = self._create_valid_file_row_data(config_file, mod_info.mod_name, model_class)
                    group_rows.append(row_data)
                    valid_count += 1

                # Create group for this mod
                mod_group = TableGroup(
                    name=display_mod_name,
                    display_name=f"{display_mod_name}",
                    rows=group_rows,
                    expanded=True
                )
                groups_data.append(mod_group)

            # Add invalid files to invalid table
            for config_file, reason in invalid_files:
                row_data = self._create_invalid_file_row_data(config_file, mod_info.mod_name, display_mod_name, reason)
                invalid_table_data.append(row_data)
                invalid_count += 1

        # Set data with groups to ReusableTable
        self.tbl_sources.set_data_with_groups(groups_data)

        # Set data to invalid sources table
        self.tbl_invalid_sources.set_data(invalid_table_data)

        # Update tab titles with counts
        self.source_tabs.setTabText(0, f"{tr('mission_merge.tab_valid_files')} ({valid_count})")
        self.source_tabs.setTabText(1, f"{tr('mission_merge.tab_invalid_files')} ({invalid_count})")

        self._update_new_files_count()
    
    def _create_valid_file_row_data(self, config_file: Path, mod_name: str, model_class: Optional[Type]) -> dict:
        """Create row data dictionary for a valid file row."""
        entries_count = 0
        config_type_name = "Unknown"
        parse_meta: dict = {}
        detected_model = model_class

        try:
            _, root, detected_model, parse_meta = XMLMergeHelper.parse_xml_file_with_meta(
                config_file, model_hint=model_class
            )
            entries_count = self._count_valid_entries(config_file)

            # Get type from model
            if detected_model:
                config_type_name = detected_model.__name__.replace("XMLModel", "")
            else:
                # Fallback to ConfigFileType
                file_type = ConfigFileType.from_root_element(root.tag)
                config_type_name = file_type.name if file_type != ConfigFileType.UNKNOWN else root.tag
        except Exception:
            # Keep defaults
            detected_model = model_class

        # Get merge suggestion from model
        action, suggested_target = self._get_merge_suggestion(config_file, model_class)

        # Compute initial status text (do not default everything to OK).
        status_text = tr("mission_merge.status_ok")
        status_color = QColor("#607d8b")
        try:
            if action == "merge":
                if detected_model:
                    expected_target = self._get_expected_target(detected_model)
                    if expected_target and suggested_target and str(suggested_target).lower() != str(expected_target).lower():
                        status_text = tr("mission_merge.status_type_mismatch").format(expected=expected_target)
                        status_color = QColor("#f44336")
                    else:
                        merge_strategy = detected_model.get_merge_strategy()
                        status_text = f"✓ {self._strategy_label(merge_strategy)}"
                        status_color = QColor("#4caf50")
                elif config_type_name == "Unknown":
                    status_text = tr("mission_merge.status_unknown_type")
                    status_color = QColor("#ff9800")
            elif action == "copy":
                status_text = tr("mission_merge.status_copy")
                status_color = QColor("#2196f3")
        except Exception:
            status_text = tr("mission_merge.status_ok")
            status_color = QColor("#607d8b")

        # Create tooltip for type
        type_tooltip = ""
        if detected_model:
            merge_strategy = detected_model.get_merge_strategy()
            extra = ""
            try:
                if parse_meta and (
                    parse_meta.get("has_tag_in_comment")
                    or parse_meta.get("unwrap_comments")
                    or parse_meta.get("used_extract_entries")
                ):
                    extra = f"\n\n{tr('mission_merge.hard_to_scan_warning')}"
            except Exception:
                extra = ""
            type_tooltip = f"Model: {detected_model.__name__}\nStrategy: {merge_strategy.name}{extra}"

        # Check if file is hard to scan
        is_hard = bool(
            parse_meta.get("has_tag_in_comment")
            or parse_meta.get("unwrap_comments")
            or parse_meta.get("used_extract_entries")
            or parse_meta.get("has_preamble")
            or parse_meta.get("has_postamble")
            or parse_meta.get("has_c_style_comments")
            or parse_meta.get("has_slashslash_comments")
        )

        # Determine display name
        display_name = mod_name
        try:
            if getattr(self, "_name_mgr", None):
                display_name = self._name_mgr.get_original_name(mod_name)
        except Exception:
            display_name = mod_name

        return {
            "checked": True,
            "file": {
                "text": config_file.name,
                "bold": True,
                "icon": self.style().standardIcon(QStyle.SP_MessageBoxWarning) if is_hard else None,
                "tooltip": tr("mission_merge.hard_to_scan_warning") if is_hard else None
            },
            "type": {
                "text": config_type_name,
                "color": QColor("#4caf50") if detected_model else QColor("#ff9800"),
                "tooltip": type_tooltip
            },
            "entries": {
                "text": str(entries_count),
                "color": QColor("#ff5252") if entries_count == 0 else None
            },
            "action": {
                "widget_type": "combo",
                "items": [
                    (tr("mission_merge.action_copy"), "copy"),
                    (tr("mission_merge.action_merge"), "merge")
                ],
                "current_data": "merge" if action == "merge" else "copy",
                "callback": lambda _row, _data: self._on_source_row_changed(_row),
            },
            "target": {
                "widget_type": "combo",
                "items": [(t, t) for t in getattr(self, "_available_targets", [])],
                "current_data": suggested_target,
                "callback": lambda _row, _data: self._on_source_row_changed(_row),
            },
            "status": {
                "text": status_text,
                "color": status_color
            },
            # Store additional data for processing
            "_file_path": str(config_file),
            "_mod_name": mod_name,
            "_display_name": display_name,
            "_config_type": config_type_name,
            "_is_valid": True,
            "_model_class": model_class,
            "_row_callback": lambda row: self._on_source_row_changed(row)
        }
    
    def _create_invalid_file_row_data(self, config_file: Path, folder_mod_name: str, display_mod_name: str, reason: str) -> dict:
        """Create row data dictionary for an invalid file row.

        Args:
            folder_mod_name: internal folder name (e.g., @m1)
            display_mod_name: resolved original display name to show in UI
        """
        return {
            "file": {
                "text": config_file.name,
                "color": QColor("#ff5252")
            },
            "mod": {
                "text": display_mod_name,
                "data": folder_mod_name  # Store internal folder name
            },
            "reason": {
                "text": reason[:80] + "..." if len(reason) > 80 else reason,
                "color": QColor("#ff9800"),
                "tooltip": reason
            },
            "path": {
                "text": str(config_file),
                "color": QColor("#888")
            }
        }

    def _on_source_row_changed(self, row: int):
        """Handle action/target changes for a row: enable/disable target and update status."""
        # Skip if row is a group header
        if self.tbl_sources.is_group_header(row):
            return

        action_combo = self.tbl_sources.get_cell_widget(row, "action")
        target_combo = self.tbl_sources.get_cell_widget(row, "target")

        if not isinstance(action_combo, QComboBox) or not isinstance(target_combo, QComboBox):
            return

        action = action_combo.currentData()
        target_combo.setEnabled(action == "merge")

        # Get row data for additional info
        row_data = self.tbl_sources.get_row_data(row)
        if not row_data:
            return

        model_class = row_data.get("_model_class")
        config_type_name = row_data.get("_config_type") or "Unknown"
        target_file = target_combo.currentData()

        # Update status cell
        status_text = tr("mission_merge.status_ok")
        status_color = QColor("#607d8b")

        if action == "merge":
            if model_class:
                # Check if selected target matches expected model target
                expected_target = self._get_expected_target(model_class)
                if expected_target and target_file and target_file.lower() != expected_target.lower():
                    # Wrong target selected
                    status_text = tr("mission_merge.status_type_mismatch").format(expected=expected_target)
                    status_color = QColor("#f44336")
                else:
                    # Good merge
                    merge_strategy = model_class.get_merge_strategy()
                    status_text = f"✓ {self._strategy_label(merge_strategy)}"
                    status_color = QColor("#4caf50")
            elif config_type_name == "Unknown":
                status_text = tr("mission_merge.status_unknown_type")
                status_color = QColor("#ff9800")
        elif action == "copy":
            status_text = tr("mission_merge.status_copy")
            status_color = QColor("#2196f3")

        # Update status cell
        self.tbl_sources.set_cell_data(row, "status", {
            "text": status_text,
            "color": status_color
        })

        self._update_new_files_count()
        self._refresh_mapping_warnings()

    def _refresh_mapping_warnings(self):
        """Aggregate invalid merge mappings and show a compact warning summary."""
        invalid = []
        checked_rows = self.tbl_sources.get_checked_row_indices()
        for row in checked_rows:
            # Skip group headers
            if self.tbl_sources.is_group_header(row):
                continue

            action_combo = self.tbl_sources.get_cell_widget(row, "action")
            if not isinstance(action_combo, QComboBox) or action_combo.currentData() != "merge":
                continue

            # Check if status indicates warning (orange color)
            status_widget = self.tbl_sources.get_cell_widget(row, "status")
            if status_widget and hasattr(status_widget, 'palette'):
                # For QLabel or similar widgets, check foreground color
                if status_widget.palette().color(status_widget.foregroundRole()).name().lower() == QColor("#ff9800").name().lower():
                    row_data = self.tbl_sources.get_row_data(row)
                    file_name = row_data.get("file", {}).get("text", "")
                    display_name = row_data.get("_display_name", "")
                    invalid.append(f"{display_name} / {file_name}")

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

        # Collect selected rows
        selected_by_mod: dict[str, list[Path]] = {}
        copy_by_mod: dict[str, list[Path]] = {}
        overrides: dict[Path, str] = {}

        checked_rows = self.tbl_sources.get_checked_row_indices()
        for row in checked_rows:
            # Skip group headers
            if self.tbl_sources.is_group_header(row):
                continue

            row_data = self.tbl_sources.get_row_data(row)
            if not row_data:
                continue

            src_path = Path(row_data["_file_path"])
            mod_name = row_data["_mod_name"]

            action_combo = self.tbl_sources.get_cell_widget(row, "action")
            target_combo = self.tbl_sources.get_cell_widget(row, "target")
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
            
        loading = LazyLoadingDialog(
            title=tr("mission_merge.generating_preview"),
            message=tr("mission_merge.analyzing"),
            parent=self
        )
        loading.show()
        
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
            loading.hide()
    
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

        # Update targets tab with planned changes grouped by mod
        self._update_targets_table_preview()
    
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

            # Add entries grouped by mod (marker)
            mod_groups: dict[str, QTreeWidgetItem] = {}
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

                mod_name = str(getattr(display_entry, "source_mod", "") or "")
                if not mod_name:
                    mod_name = "(unknown)"
                # Resolve display name if possible
                try:
                    if getattr(self, "_name_mgr", None) and mod_name and mod_name != "(unknown)":
                        display_group_name = self._name_mgr.get_original_name(mod_name)
                    else:
                        display_group_name = mod_name
                except Exception:
                    display_group_name = mod_name

                mod_item = mod_groups.get(mod_name)
                if mod_item is None:
                    mod_item = QTreeWidgetItem()
                    mod_item.setText(0, f"� {display_group_name}")
                    mod_item.setFont(0, QFont("", -1, QFont.Bold))
                    mod_item.setForeground(0, QColor("#4fc3f7"))
                    file_item.addChild(mod_item)
                    mod_groups[mod_name] = mod_item

                entry_item = EntryTreeItem(display_entry)
                mod_item.addChild(entry_item)
                count += 1
                
            if count > 0:
                self.tree_entries.addTopLevelItem(file_item)
                file_item.setExpanded(True)

                # Expand mod groups for quick scanning
                for mi in mod_groups.values():
                    try:
                        mi.setExpanded(True)
                    except Exception:
                        pass
    
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
                self.txt_file_preview.setText(
                    tr("mission_merge.overview_new_file_to_copy").format(file=filename[4:])
                )
                self.lbl_file_name.setText(f"📄 {filename[4:]}")
                self.lbl_file_entries.setText("")
            elif filename in self.preview.merge_results:
                result = self.preview.merge_results[filename]
                
                info = f"{tr('mission_merge.target_file')}: {filename}\n\n"
                info += f"{tr('mission_merge.new_entries')}: {result.new_entries}\n"
                info += f"{tr('mission_merge.duplicates')}: {result.duplicates}\n"
                info += f"{tr('mission_merge.conflicts')}: {result.conflicts}\n"

                self.txt_file_preview.setText(info)
                self.lbl_file_name.setText(f"📄 {filename}")
                self.lbl_file_entries.setText("")

            # Switch to file preview tab
            self.tabs.setCurrentIndex(1)
    
    def _on_entry_clicked(self, item, column):
        """Handle click on entry item."""
        if isinstance(item, EntryTreeItem):
            # Show XML preview
            xml_str = item.entry.to_xml_string()

            status_labels = {
                MergeStatus.NEW: tr("mission_merge.status_new"),
                MergeStatus.DUPLICATE: tr("mission_merge.status_duplicate"),
                MergeStatus.CONFLICT: tr("mission_merge.status_conflict"),
                MergeStatus.SKIPPED: tr("mission_merge.status_skipped"),
                MergeStatus.MANUAL: tr("mission_merge.status_manual"),
                MergeStatus.MERGED: tr("mission_merge.status_merged"),
            }
            status_text = status_labels.get(item.entry.status, str(getattr(item.entry.status, "value", item.entry.status)))

            # Show readable source mod name in preview (but keep original value for comments)
            src = str(item.entry.source_mod or "")
            try:
                display_src = self._name_mgr.get_original_name(src) if getattr(self, "_name_mgr", None) else src
            except Exception:
                display_src = src
            info = f"<!-- {tr('mission_merge.source')}: {display_src} -->\n"
            info += f"<!-- {tr('mission_merge.file')}: {item.entry.source_file.name} -->\n"
            info += f"<!-- {tr('mission_merge.status')}: {status_text} -->\n\n"
            info += xml_str

            self.txt_file_preview.setText(info)
            self.lbl_file_name.setText(f"🔎 {tr('mission_merge.entry_preview')}: {item.entry.unique_key}")
            self.lbl_file_entries.setText(f"{tr('mission_merge.status')}: {status_text}")

            # Switch to file preview tab
            self.tabs.setCurrentIndex(1)
    
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
                    try:
                        if getattr(self, "merger", None):
                            # Newer DayZ server layouts keep core config files in mission/db
                            dst_file = self.merger.get_target_mission_file_path(src_file.name)
                    except Exception:
                        pass
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
                        if getattr(self, "merger", None):
                            dst_file = self.merger.get_target_mission_file_path(src_file.name)
                    except Exception:
                        pass
                    try:
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
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

        # Optional name manager from parent dialog (maps @mN -> original mod name)
        self._name_mgr = getattr(parent, "_name_mgr", None)
        
        self.setWindowTitle(tr("mission_merge.conflict_resolver_title"))
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        self._setup_ui()
        self._populate_conflicts()

    def _display_mod_name(self, mod_name: str) -> str:
        """Return a user-friendly display name for a mod folder name."""
        try:
            if getattr(self, "_name_mgr", None) and mod_name:
                return self._name_mgr.get_original_name(str(mod_name))
        except Exception:
            pass
        return str(mod_name or "")

    def _entry_key(self, entry) -> str:
        """Return a stable key for a conflict entry across refreshes."""
        try:
            uk = getattr(entry, "unique_key", None)
            if uk:
                return str(uk)
        except Exception:
            pass
        try:
            # Fallback: combine source + name-ish.
            src_mod = str(getattr(entry, "source_mod", "") or "")
            src_file = str(getattr(getattr(entry, "source_file", None), "name", "") or "")
            name = ""
            el = getattr(entry, "element", None)
            if el is not None:
                name = str(el.get("name") or "")
            return f"{src_mod}|{src_file}|{name}"
        except Exception:
            return str(id(entry))
    
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
        self.status_bar.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                padding: 12px;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d2d2d, stop:1 #1e1e1e);
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin: 4px;
            }
        """)
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
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Determine file type and merge capability using XML models
        model_class = ConfigTypeRegistry.get_model_by_filename(filename)
        
        # Determine if this file type supports merging children
        is_mergeable = False
        if model_class:
            merge_strategy = model_class.get_merge_strategy()
            is_mergeable = merge_strategy in [MergeStrategy.MERGE_CHILDREN, MergeStrategy.APPEND]
            
            # Also check if model has mergeable fields
            mergeable_fields = XMLMergeHelper.get_mergeable_fields(model_class)
            if mergeable_fields:
                is_mergeable = True
        else:
            # Fallback to old ConfigFileType check
            file_type = ConfigFileType.from_filename(filename)
            is_mergeable = file_type in [ConfigFileType.RANDOMPRESETS, ConfigFileType.EVENTSPAWNS]
        
        info_text = tr("mission_merge.conflict_replace_info") if not is_mergeable else tr("mission_merge.conflict_merge_info")
        info = QLabel(info_text)
        info.setStyleSheet("color: #ff9800; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Show model info
        if model_class:
            model_info = QLabel(f"Model: {model_class.__name__} | Strategy: {model_class.get_merge_strategy().name}")
            model_info.setStyleSheet("color: #4caf50; font-size: 10px;")
            layout.addWidget(model_info)
        
        # Group conflicts by unique key
        conflicts_by_key = {}
        for entry in entries:
            key = entry.unique_key
            if not key:  # Assign default key for entries with empty/None unique_key
                key = f"unknown:{id(entry)}"
            if key not in conflicts_by_key:
                conflicts_by_key[key] = []
            conflicts_by_key[key].append(entry)
        
        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left: list of conflict keys
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_label = QLabel(tr("mission_merge.conflicting_entries"))
        left_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(left_label)
        
        conflict_list = QListWidget()
        conflict_list.setAlternatingRowColors(False)
        conflict_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #404040;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #333333;
            }
        """)
        for key in conflicts_by_key.keys():
            entries_for_key = conflicts_by_key[key]
            if len(entries_for_key) <= 1:
                continue  # Skip non-conflicts (only one entry)
            base_label = key.split(":", 1)[-1] if ":" in key else key
            entry_count = len(entries_for_key)
            item = QListWidgetItem(f"{base_label} ({tr('mission_merge.conflict_entry_count', count=entry_count)})")
            item.setData(Qt.UserRole, key)
            item.setData(Qt.UserRole + 1, base_label)
            conflict_list.addItem(item)
        left_layout.addWidget(conflict_list)
        main_splitter.addWidget(left_widget)
        
        # Right: Tab widget for options and result preview
        right_tabs = QTabWidget()
        
        # Tab 1: Resolution options
        options_tab = QWidget()
        options_layout = QVBoxLayout(options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)
        
        # Current state label and auto-pick controls
        state_row = QHBoxLayout()

        state_label = QLabel(tr("mission_merge.conflict_current_state", state=tr("mission_merge.conflict_state_none")))
        state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
        state_row.addWidget(state_label, stretch=1)

        # Auto-pick dropdown menu will be added after tab_data is created

        options_layout.addLayout(state_row)

        remaining_label = QLabel("")
        remaining_label.setStyleSheet("color: gray; font-size: 11px;")
        options_layout.addWidget(remaining_label)
        
        # Options table
        from shared.ui.components.table import ReusableTable, TableColumn
        # Keep the original conflict-resolve workflow: pick one (replace) or multiple (merge where supported).
        # Do not expose per-row Action/MergeInto columns here.
        options_columns = [
            TableColumn("source_mod", tr("mission_merge.source_mod"), QHeaderView.ResizeToContents),
            TableColumn("entry_preview", tr("mission_merge.entry_preview"), QHeaderView.Stretch),
            TableColumn("status", tr("mission_merge.status"), QHeaderView.ResizeToContents),
        ]
        options_table = ReusableTable(options_columns, has_checkbox=True)
        # Row click toggles checkbox (primary interaction) while keeping UI clean.
        options_table.set_row_click_toggles_checkbox(True)
        options_table.setAlternatingRowColors(False)
        options_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        options_table.verticalHeader().setVisible(False)
        options_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                gridline-color: #2d2d2d;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #2d2d2d;
            }
            QTableWidget::item:selected {
                background-color: #404040;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px;
                border: none;
                border-right: 1px solid #3c3c3c;
                font-weight: bold;
            }
            QCheckBox {
                background-color: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #666;
                background-color: #1e1e1e;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4caf50;
                background-color: #4caf50;
                border-radius: 3px;
            }
        """)
        options_layout.addWidget(options_table)
        
        # Entry XML preview
        preview_label = QLabel(tr("mission_merge.xml_preview"))
        preview_label.setStyleSheet("font-weight: bold;")
        options_layout.addWidget(preview_label)
        
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setFont(QFont("Consolas", 10))
        preview_text.setMaximumHeight(180)
        preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        options_layout.addWidget(preview_text)
        
        right_tabs.addTab(options_tab, tr("mission_merge.resolution_options"))
        
        # Tab 2: Result preview
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setContentsMargins(4, 4, 4, 4)
        
        result_info = QLabel(tr("mission_merge.result_preview_info"))
        result_info.setStyleSheet("color: gray; font-size: 11px;")
        result_info.setWordWrap(True)
        result_layout.addWidget(result_info)
        
        result_preview = QTextEdit()
        result_preview.setReadOnly(True)
        result_preview.setFont(QFont("Consolas", 10))
        result_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        result_layout.addWidget(result_preview)
        
        right_tabs.addTab(result_tab, tr("mission_merge.result_preview"))
        
        main_splitter.addWidget(right_tabs)
        main_splitter.setSizes([280, 720])
        
        layout.addWidget(main_splitter)
        
        # Store data for this tab
        tab_data = {
            "filename": filename,
            "conflicts_by_key": conflicts_by_key,
            "is_mergeable": is_mergeable,
            "conflict_list": conflict_list,
            "options_table": options_table,
            "preview_text": preview_text,
            "state_label": state_label,
            "remaining_label": remaining_label,
            "result_preview": result_preview,
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
        
        # Auto-pick dropdown menu with multiple options
        self._create_auto_pick_menu(state_row, tab_data)
        
        # Connect selection signal
        conflict_list.currentItemChanged.connect(
            lambda curr, prev, td=tab_data: self._on_conflict_selected(td, curr)
        )

        # Auto-pick menu is already connected in _create_auto_pick_menu

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

        # NOTE: Auto-pick is a bulk per-file action via the button.
        
        # Prepare data for ReusableTable
        table_data = []
        # Build a stable set of selected entry keys for this conflict.
        resolved = tab_data["resolved_by_key"].get(key, [])
        selected_keys = set()
        for sel in resolved:
            try:
                selected_keys.add(self._entry_key(sel.get("entry")))
            except Exception:
                continue
        for entry in entries:
            # Check if entry is selected (use stable key, not object identity)
            selected = (self._entry_key(entry) in selected_keys)
            try:
                display_mod = self._name_mgr.get_original_name(str(entry.source_mod)) if getattr(self, '_name_mgr', None) else str(entry.source_mod)
            except Exception:
                display_mod = str(entry.source_mod)
            
            xml_str = entry.to_xml_string()
            preview = xml_str[:100] + "..." if len(xml_str) > 100 else xml_str
            
            status_text = tr("mission_merge.selected") if selected else ""
            
            row_data = {
                "checked": selected,
                "source_mod": {
                    "text": display_mod,
                    "tooltip": display_mod
                },
                "entry_preview": {
                    "text": preview.replace("\n", " "),
                    "tooltip": xml_str
                },
                "status": {
                    "text": status_text,
                    "color": QColor("#4caf50") if selected else QColor("#888")
                },
                "_entry": entry,
                "_key": key
            }
            table_data.append(row_data)

        # Render rows
        options_table.set_data(table_data)
        
        # Show preview of first entry
        if entries:
            try:
                head_src = self._name_mgr.get_original_name(str(entries[0].source_mod)) if getattr(self, '_name_mgr', None) else str(entries[0].source_mod)
            except Exception:
                head_src = str(entries[0].source_mod)
            xml_preview = f"<!-- {tr('mission_merge.source')}: {head_src} -->\n"
            xml_preview += f"<!-- {tr('mission_merge.file')}: {entries[0].source_file.name} -->\n\n"
            xml_preview += entries[0].to_xml_string()
            preview_text.setText(xml_preview)
        
        # Connect handler EVERY TIME we set new data (set_data recreates checkboxes)
        # Store the previous connection lambda if any (to disconnect old one)
        old_connection = tab_data.get("_checkbox_connection")
        if old_connection:
            try:
                options_table.checkbox_toggled.disconnect(old_connection)
            except (TypeError, RuntimeError):
                pass
        
        # Connect new handler
        new_connection = lambda row, checked, td=tab_data: self._on_option_checkbox_toggled(td, row, checked)
        options_table.checkbox_toggled.connect(new_connection)
        tab_data["_checkbox_connection"] = new_connection

        # Update state label and result preview
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_status()

        # Update the left list item's resolved marker for this key
        self._update_conflict_key_marker(tab_data, key)

        try:
            options_table.viewport().update()
        except Exception:
            pass

    def _on_option_checkbox_toggled(self, tab_data: dict, row: int, checked: bool):
        """Handle checkbox toggle in options table."""
        options_table = tab_data["options_table"]
        is_mergeable = tab_data["is_mergeable"]
        conflict_key = tab_data.get("current_key")
        if not conflict_key:
            return

        # Keep preview in sync with the clicked row.
        try:
            self._update_entry_preview_from_tabdata(tab_data, row)
        except Exception:
            pass

        # Get entry from row data
        row_data = options_table.get_row_data(row)
        if not row_data:
            return
        entry = row_data.get("_entry")
        if not entry:
            return

        entry_key = self._entry_key(entry)

        # Keep the underlying row model in sync with the widget checkbox state.
        # Without this, any subsequent refresh can re-create checkboxes from stale
        # row_data["checked"], which looks like selection/state is not updating.
        row_data["checked"] = bool(checked)

        # Update stored selections
        selected_list = list(tab_data["resolved_by_key"].get(conflict_key, []))

        if checked:
            if not is_mergeable:
                # Non-mergeable files: only allow ONE selection (radio behavior)
                # Uncheck others (without re-rendering the whole table).
                for r, rd in enumerate(options_table._data):
                    if rd.get("_is_group_header"):
                        continue
                    should_check = (r == row)
                    rd["checked"] = should_check
                    options_table.set_row_checked(r, should_check)
                    status_cell = {"text": tr("mission_merge.selected"), "color": QColor("#4caf50")} if should_check else {"text": "", "color": QColor("#888")}
                    rd["status"] = status_cell
                    # Always use the same row index for set_cell_data since r is from _data enumeration
                    options_table.set_cell_data(r, "status", status_cell)
                
                tab_data["resolved_by_key"][conflict_key] = [{
                    "entry": entry,
                    "action": "replace",
                }]
            else:
                # Mergeable files: allow multi-select
                selected_list = [s for s in selected_list if self._entry_key(s.get("entry")) != entry_key]
                selected_list.append({"entry": entry, "action": "merge"})
                tab_data["resolved_by_key"][conflict_key] = selected_list
                # Update status for this row
                status_cell = {"text": tr("mission_merge.selected"), "color": QColor("#4caf50")}
                row_data["status"] = status_cell
                options_table.set_cell_data(row, "status", status_cell)
        else:
            # Unchecked -> remove from selection
            selected_list = [s for s in selected_list if self._entry_key(s.get("entry")) != entry_key]
            if selected_list:
                tab_data["resolved_by_key"][conflict_key] = selected_list
            else:
                tab_data["resolved_by_key"].pop(conflict_key, None)
            # Update status for this row
            status_cell = {"text": "", "color": QColor("#888")}
            row_data["status"] = status_cell
            options_table.set_cell_data(row, "status", status_cell)

        # Update action based on final selection count for mergeable files
        self._update_selection_actions(tab_data, conflict_key)

        # Update visuals & counters
        self._update_conflict_key_marker(tab_data, conflict_key)
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_status()

    def _on_action_changed(self, tab_data: dict, row: int, row_data: dict):
        """Handle action combo change."""
        entry = row_data.get("_entry")
        key = row_data.get("_key")
        if not entry or not key:
            return
        
        # Get new action from combo
        action_combo = tab_data["options_table"].get_cell_widget(row, "action")
        if isinstance(action_combo, QComboBox):
            new_action = action_combo.currentData()
        else:
            new_action = "replace"
        
        # Update resolved
        resolved = tab_data["resolved_by_key"].get(key, [])
        for sel in resolved:
            if sel.get("entry") is entry:
                sel["action"] = new_action
                break
        
        # Update status if selected
        if any(sel.get("entry") is entry for sel in resolved):
            row_data["status"] = {"text": tr("mission_merge.selected"), "color": QColor("#4caf50")}
            tab_data["options_table"]._render_data()
        
        self._update_selection_actions(tab_data, key)
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)

    def _on_target_changed(self, tab_data: dict, row: int, row_data: dict):
        """Handle target combo change."""
        # For now, target is per file, not per entry
        # Could implement per-entry target if needed
        pass

    @staticmethod
    def _deep_signature(elem: ET.Element):
        """Compute a stable deep signature for an XML element.

        Used to detect truly identical duplicates (including children) regardless
        of formatting/indentation.
        """
        try:
            tag = str(elem.tag)
        except Exception:
            tag = ""
        try:
            attrib = tuple(sorted((elem.attrib or {}).items()))
        except Exception:
            attrib = ()
        try:
            text = (elem.text or "").strip()
        except Exception:
            text = ""
        children = []
        try:
            for ch in list(elem):
                children.append(ConflictResolverDialog._deep_signature(ch))
        except Exception:
            children = []
        return (tag, attrib, text, tuple(children))

    def _update_conflict_key_marker(self, tab_data: dict, conflict_key: str):
        """Mark the selected conflict key in the left list as resolved/unresolved."""
        conflict_list = tab_data.get("conflict_list")
        resolved_by_key = tab_data.get("resolved_by_key") or {}
        if not conflict_list or not conflict_key:
            return

        is_resolved = bool(resolved_by_key.get(conflict_key))
        entry_count = len(tab_data.get("conflicts_by_key", {}).get(conflict_key, []))
        for i in range(conflict_list.count()):
            it = conflict_list.item(i)
            if not it:
                continue
            if it.data(Qt.UserRole) != conflict_key:
                continue

            base_label = it.data(Qt.UserRole + 1) or it.text().lstrip("✓ ").split(" (")[0]
            label_text = f"{base_label} ({tr('mission_merge.conflict_entry_count', count=entry_count)})"
            it.setText(("✓ " if is_resolved else "") + label_text)
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

        # Count current selections to determine action
        selected_count = 0
        for r in range(options_table.rowCount()):
            item = options_table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                selected_count += 1

        # Update stored selections
        selected_list = list(tab_data["resolved_by_key"].get(conflict_key, []))

        # Determine action based on selection count:
        # - 1 selection = replace
        # - multiple selections = merge (if supported), else only keep latest for non-mergeable
        if changed_item.checkState() == Qt.Checked:
            if not is_mergeable:
                # Non-mergeable files: only allow ONE selection (radio behavior)
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
                # Mergeable files: allow multi-select
                # Action is determined by total selection count later
                selected_list = [s for s in selected_list if s.get("entry") is not entry]
                selected_list.append({"entry": entry, "action": "merge"})  # Will be adjusted based on count
                tab_data["resolved_by_key"][conflict_key] = selected_list
        else:
            # Unchecked -> remove from selection
            selected_list = [s for s in selected_list if s.get("entry") is not entry]
            if selected_list:
                tab_data["resolved_by_key"][conflict_key] = selected_list
            else:
                tab_data["resolved_by_key"].pop(conflict_key, None)

        # Update action based on final selection count for mergeable files
        self._update_selection_actions(tab_data, conflict_key)

        # Update visuals & counters
        self._update_conflict_key_marker(tab_data, conflict_key)
        self._refresh_option_row_visuals(tab_data)
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_status()

    def _update_selection_actions(self, tab_data: dict, conflict_key: str):
        """Update action (replace/merge) based on selection count."""
        selections = tab_data["resolved_by_key"].get(conflict_key, [])
        if not selections:
            return
        
        is_mergeable = tab_data.get("is_mergeable", False)
        
        # Determine action based on count:
        # - 1 selection = replace
        # - multiple = merge (if supported)
        if len(selections) == 1:
            selections[0]["action"] = "replace"
        elif is_mergeable:
            for sel in selections:
                sel["action"] = "merge"
        else:
            # Non-mergeable shouldn't have multiple selections,
            # but just in case, keep only first
            selections[0]["action"] = "replace"
            tab_data["resolved_by_key"][conflict_key] = [selections[0]]

    def _update_state_label(self, tab_data: dict):
        """Update the state label showing current selection status."""
        state_label = tab_data.get("state_label")
        if not state_label:
            return
        
        conflict_key = tab_data.get("current_key")
        if not conflict_key:
            state_label.setText(tr("mission_merge.conflict_current_state", state=tr("mission_merge.conflict_state_none")))
            state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
            return
        
        selections = tab_data["resolved_by_key"].get(conflict_key, [])
        
        if not selections:
            state_text = tr("mission_merge.conflict_state_none")
            state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
        elif len(selections) == 1:
            entry = selections[0]["entry"]
            try:
                if getattr(entry, "element", None) is not None:
                    name = entry.element.get("name") or entry.source_mod
                else:
                    name = getattr(entry, "source_mod", "") or getattr(entry, "unique_key", "")
            except Exception:
                name = getattr(entry, "source_mod", "") or getattr(entry, "unique_key", "")
            state_text = tr("mission_merge.conflict_state_replace", name=name)
            state_label.setStyleSheet("color: #4caf50; font-weight: bold; padding: 4px; background-color: rgba(76, 175, 80, 0.1);")
        else:
            state_text = tr("mission_merge.conflict_state_merge", count=len(selections))
            state_label.setStyleSheet("color: #2196f3; font-weight: bold; padding: 4px; background-color: rgba(33, 150, 243, 0.1);")
        
        state_label.setText(tr("mission_merge.conflict_current_state", state=state_text))
        try:
            state_label.update()
            state_label.repaint()
        except Exception:
            pass

    def _update_remaining_label(self, tab_data: dict):
        """Update per-file remaining/resolved count label."""
        lbl = tab_data.get("remaining_label")
        if not lbl:
            return
        conflicts_by_key = tab_data.get("conflicts_by_key") or {}
        resolved_by_key = tab_data.get("resolved_by_key") or {}
        total = len(conflicts_by_key)
        resolved = 0
        for k in conflicts_by_key.keys():
            if resolved_by_key.get(k):
                resolved += 1
        remaining = max(0, total - resolved)
        lbl.setText(tr("mission_merge.remaining_count", remaining=remaining, total=total))
        try:
            lbl.update()
            lbl.repaint()
        except Exception:
            pass

    def _create_auto_pick_menu(self, parent_layout: QHBoxLayout, tab_data: dict):
        """Create auto-pick dropdown menu with multiple options."""
        from PySide6.QtWidgets import QComboBox, QMenu

        # Create dropdown button with better styling
        btn_auto_pick = QPushButton("⚡ " + tr("mission_merge.auto_pick"))
        btn_auto_pick.setToolTip(tr("mission_merge.auto_pick_tooltip"))
        btn_auto_pick.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)

        # Create menu
        menu = QMenu(btn_auto_pick)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3c3c3c;
            }
            QMenu::item {
                padding: 8px 16px;
                border-bottom: 1px solid #404040;
            }
            QMenu::item:selected {
                background-color: #404040;
            }
            QMenu::separator {
                height: 1px;
                background-color: #404040;
                margin: 4px 0px;
            }
        """)

        # Add menu actions with monochrome icons
        action_identical = menu.addAction("🔍 " + tr("mission_merge.auto_pick_identical"))
        action_identical.setToolTip(tr("mission_merge.auto_pick_identical_tooltip"))
        action_identical.triggered.connect(lambda: self._auto_pick_file_conflicts(tab_data, "identical"))

        action_first_mod = menu.addAction("📁 " + tr("mission_merge.auto_pick_first_mod"))
        action_first_mod.setToolTip(tr("mission_merge.auto_pick_first_mod_tooltip"))
        action_first_mod.triggered.connect(lambda: self._auto_pick_file_conflicts(tab_data, "first_mod"))

        action_most_common = menu.addAction("📈 " + tr("mission_merge.auto_pick_most_common"))
        action_most_common.setToolTip(tr("mission_merge.auto_pick_most_common_tooltip"))
        action_most_common.triggered.connect(lambda: self._auto_pick_file_conflicts(tab_data, "most_common"))

        menu.addSeparator()

        action_clear_all = menu.addAction("🗑 " + tr("mission_merge.auto_pick_clear_all"))
        action_clear_all.setToolTip(tr("mission_merge.auto_pick_clear_all_tooltip"))
        action_clear_all.triggered.connect(lambda: self._auto_pick_file_conflicts(tab_data, "clear_all"))

        # Connect button to show menu
        btn_auto_pick.clicked.connect(lambda: menu.exec(btn_auto_pick.mapToGlobal(btn_auto_pick.rect().bottomLeft())))

        # Add keyboard shortcut (Ctrl+A)
        from PySide6.QtGui import QShortcut, QKeySequence
        shortcut = QShortcut(QKeySequence("Ctrl+A"), btn_auto_pick)
        shortcut.activated.connect(lambda: menu.exec(btn_auto_pick.mapToGlobal(btn_auto_pick.rect().bottomLeft())))

        # Store menu reference
        tab_data["auto_pick_menu"] = menu
        tab_data["btn_auto_pick"] = btn_auto_pick
        tab_data["auto_pick_shortcut"] = shortcut

        parent_layout.addWidget(btn_auto_pick)

    def _auto_pick_file_conflicts(self, tab_data: dict, strategy: str = "identical"):
        """Bulk action: auto-pick conflicts in THIS file using specified strategy.

        Strategies:
        - "identical": Pick when all options are identical (original behavior)
        - "first_mod": Pick the first entry from each mod (prioritize by mod load order)
        - "most_common": Pick the most common entry across all conflicts
        - "clear_all": Clear all selections
        """
        conflicts_by_key = tab_data.get("conflicts_by_key") or {}
        if not conflicts_by_key:
            return

        resolved_by_key = tab_data.get("resolved_by_key") or {}
        picked = 0
        cleared = 0

        # Show progress for operations that might take time
        show_progress = len(conflicts_by_key) > 10
        progress = None
        if show_progress:
            from PySide6.QtWidgets import QProgressDialog
            progress = QProgressDialog(
                tr("mission_merge.auto_pick_progress"),
                tr("common.cancel"), 0, len(conflicts_by_key), self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.show()

        try:
            if strategy == "clear_all":
                # Clear all selections
                for i, conflict_key in enumerate(conflicts_by_key.keys()):
                    if show_progress and progress:
                        progress.setValue(i)
                        progress.setLabelText(f"{tr('mission_merge.auto_pick_clearing')} {i+1}/{len(conflicts_by_key)}")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            break

                    if resolved_by_key.get(conflict_key):
                        resolved_by_key.pop(conflict_key, None)
                        cleared += 1
            elif strategy == "identical":
                # Original behavior: only pick when all options are identical
                for i, (conflict_key, entries) in enumerate(conflicts_by_key.items()):
                    if show_progress and progress:
                        progress.setValue(i)
                        progress.setLabelText(f"{tr('mission_merge.auto_pick_analyzing')} {i+1}/{len(conflicts_by_key)}")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            break

                    if resolved_by_key.get(conflict_key):
                        continue
                    entries = list(entries or [])
                    if not entries:
                        continue
                    try:
                        sigs = []
                        for e in entries:
                            if e.element is not None:
                                sigs.append(self._deep_signature(e.element))
                        is_all_same = bool(sigs) and all(s == sigs[0] for s in sigs[1:])
                    except Exception:
                        is_all_same = False

                    if not is_all_same:
                        continue

                    resolved_by_key[conflict_key] = [{
                        "entry": entries[0],
                        "action": "replace",
                    }]
                    self._update_selection_actions(tab_data, conflict_key)
                    picked += 1
            elif strategy == "first_mod":
                # Pick first entry from each mod, preferring mods that appear first
                mod_priority = {}
                for i, (conflict_key, entries) in enumerate(conflicts_by_key.items()):
                    if show_progress and progress:
                        progress.setValue(i)
                        progress.setLabelText(f"{tr('mission_merge.auto_pick_analyzing')} {i+1}/{len(conflicts_by_key)}")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            break

                    if resolved_by_key.get(conflict_key):
                        continue

                    # Group entries by mod
                    by_mod = {}
                    for entry in entries:
                        mod = str(getattr(entry, "source_mod", ""))
                        if mod not in by_mod:
                            by_mod[mod] = []
                        by_mod[mod].append(entry)

                    # Sort mods by priority (first appearance in conflict list)
                    if not mod_priority:
                        # Build priority based on first conflict
                        for mod in by_mod.keys():
                            mod_priority[mod] = len(mod_priority)

                    sorted_mods = sorted(by_mod.keys(), key=lambda m: mod_priority.get(m, 999))

                    # Pick first entry from first mod
                    if sorted_mods:
                        first_mod = sorted_mods[0]
                        first_entry = by_mod[first_mod][0]

                        resolved_by_key[conflict_key] = [{
                            "entry": first_entry,
                            "action": "replace",
                        }]
                        self._update_selection_actions(tab_data, conflict_key)
                        picked += 1
            elif strategy == "most_common":
                # Pick the most common entry across all conflicts
                # This analyzes patterns across the entire file
                if show_progress and progress:
                    progress.setLabelText(tr("mission_merge.auto_pick_analyzing_patterns"))
                    QApplication.processEvents()

                entry_counts = {}
                for conflict_key, entries in conflicts_by_key.items():
                    if resolved_by_key.get(conflict_key):
                        continue

                    for entry in entries:
                        try:
                            if entry.element is not None:
                                sig = self._deep_signature(entry.element)
                                if sig not in entry_counts:
                                    entry_counts[sig] = {"count": 0, "entry": entry}
                                entry_counts[sig]["count"] += 1
                        except Exception:
                            continue

                # Find most common signature
                if entry_counts:
                    most_common_sig = max(entry_counts.keys(), key=lambda k: entry_counts[k]["count"])
                    most_common_entry = entry_counts[most_common_sig]["entry"]

                    # Apply to all unresolved conflicts
                    for i, (conflict_key, entries) in enumerate(conflicts_by_key.items()):
                        if show_progress and progress:
                            progress.setValue(i)
                            progress.setLabelText(f"{tr('mission_merge.auto_pick_applying')} {i+1}/{len(conflicts_by_key)}")
                            QApplication.processEvents()
                            if progress.wasCanceled():
                                break

                        if resolved_by_key.get(conflict_key):
                            continue

                        # Check if most common entry exists in this conflict
                        matching_entry = None
                        for entry in entries:
                            try:
                                if entry.element is not None and self._deep_signature(entry.element) == most_common_sig:
                                    matching_entry = entry
                                    break
                            except Exception:
                                continue

                        if matching_entry:
                            resolved_by_key[conflict_key] = [{
                                "entry": matching_entry,
                                "action": "replace",
                            }]
                            self._update_selection_actions(tab_data, conflict_key)
                            picked += 1

            if show_progress and progress:
                progress.setValue(len(conflicts_by_key))
                QApplication.processEvents()
                progress.close()

        except Exception as e:
            if show_progress and progress:
                progress.close()
            QMessageBox.critical(self, tr("common.error"), str(e))
            return

        # Update all left-list markers
        for conflict_key in conflicts_by_key.keys():
            self._update_conflict_key_marker(tab_data, conflict_key)

        # Refresh current selection/table
        conflict_list = tab_data.get("conflict_list")
        if conflict_list:
            curr = conflict_list.currentItem()
            if curr:
                self._on_conflict_selected(tab_data, curr)

        self._update_remaining_label(tab_data)
        self._update_status()
        
        # Force UI update before showing message box
        QApplication.processEvents()

        # Show result message
        if strategy == "clear_all":
            if cleared > 0:
                QMessageBox.information(self, tr("common.success"),
                    tr("mission_merge.auto_pick_cleared", count=cleared))
            else:
                QMessageBox.information(self, tr("common.info"),
                    tr("mission_merge.auto_pick_nothing_to_clear"))
        else:
            if picked <= 0:
                QMessageBox.information(self, tr("common.info"),
                    tr("mission_merge.auto_pick_not_applicable"))
            else:
                strategy_names = {
                    "identical": tr("mission_merge.auto_pick_identical"),
                    "first_mod": tr("mission_merge.auto_pick_first_mod"),
                    "most_common": tr("mission_merge.auto_pick_most_common"),
                }
                strategy_name = strategy_names.get(strategy, strategy)
                QMessageBox.information(self, tr("common.success"),
                    tr("mission_merge.auto_pick_applied_detailed", strategy=strategy_name, count=picked))
    
    def _update_result_preview(self, tab_data: dict):
        """Update the result preview showing merged/replaced result."""
        from xml.etree import ElementTree as ET
        
        result_preview = tab_data.get("result_preview")
        if not result_preview:
            return
        
        conflict_key = tab_data.get("current_key")
        if not conflict_key:
            result_preview.setText("")
            return
        
        selections = tab_data["resolved_by_key"].get(conflict_key, [])
        
        if not selections:
            result_preview.setText(f"<!-- {tr('mission_merge.conflict_state_none')} -->")
            return
        
        try:
            if len(selections) == 1:
                # Replace: show the selected entry
                entry = selections[0]["entry"]
                xml_preview = f"<!-- {tr('mission_merge.conflict_state_replace', name=self._display_mod_name(entry.source_mod))} -->\n\n"
                xml_preview += entry.to_xml_string()
                result_preview.setText(xml_preview)
            else:
                # Merge: build combined result
                xml_preview = f"<!-- {tr('mission_merge.conflict_state_merge', count=len(selections))} -->\n"
                sources = ", ".join([self._display_mod_name(sel["entry"].source_mod) for sel in selections])
                xml_preview += f"<!-- Sources: {sources} -->\n\n"
                
                # Get first entry as base
                first_entry = selections[0]["entry"]
                parent_tag = first_entry.element.tag
                parent_attrs = dict(first_entry.element.attrib)
                
                # Collect all children with deduplication using XMLMergeHelper
                all_children = []
                seen_signatures = set()
                
                for sel in selections:
                    entry = sel["entry"]
                    if entry.element is None:
                        continue
                    for child in entry.element:
                        try:
                            sig = XMLMergeHelper.get_element_signature(child)
                            if sig not in seen_signatures:
                                cloned = ET.Element(child.tag, child.attrib)
                                cloned.text = child.text
                                cloned.tail = child.tail
                                for subchild in child:
                                    cloned.append(subchild)
                                all_children.append(cloned)
                                seen_signatures.add(sig)
                        except Exception:
                            # If signature fails, use string representation
                            child_str = ET.tostring(child, encoding="unicode")
                            if child_str not in seen_signatures:
                                cloned = ET.Element(child.tag, child.attrib)
                                cloned.text = child.text
                                cloned.tail = child.tail
                                for subchild in child:
                                    cloned.append(subchild)
                                all_children.append(cloned)
                                seen_signatures.add(child_str)
                
                # Build merged XML
                attrs_str = " ".join([f'{k}="{v}"' for k, v in parent_attrs.items()])
                xml_preview += f"<{parent_tag} {attrs_str}>\n"
                for child in all_children:
                    child_str = ET.tostring(child, encoding="unicode").strip()
                    xml_preview += f"    {child_str}\n"
                xml_preview += f"</{parent_tag}>"
                
                result_preview.setText(xml_preview)
        except Exception as e:
            # If anything fails, show the first entry at least
            if selections:
                try:
                    entry = selections[0]["entry"]
                    xml_preview = f"<!-- Error: {str(e)} -->\n"
                    xml_preview += entry.to_xml_string()
                    result_preview.setText(xml_preview)
                except Exception:
                    result_preview.setText(f"<!-- Error building preview: {str(e)} -->")

    def _on_option_cell_clicked(self, tab_data: dict, row: int, col: int):
        """Allow selecting an option by clicking anywhere on its row."""
        self._update_entry_preview_from_tabdata(tab_data, row)

        # Toggle the checkbox when clicking any cell except checkbox itself
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
            # Status is in column 3 now (was 4 with Action column)
            status_item = options_table.item(r, 3)
            if status_item:
                status_item.setText(tr("mission_merge.selected") if checked else "")
                status_item.setForeground(QColor("#4caf50") if checked else QColor("#888"))

            bg = QColor("#1b3b1b") if checked else QColor("#000000")
            for c in range(1, options_table.columnCount()):
                cell = options_table.item(r, c)
                if cell:
                    cell.setBackground(bg)

    def _on_merge_action_changed(self, tab_data: dict, conflict_key: str, entry, combo: QComboBox):
        """Persist action changes for mergeable selections - DEPRECATED, kept for compatibility."""
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
        options_table = tab_data["options_table"]
        preview_text = tab_data["preview_text"]
        
        # Get entry from row data instead of using row index
        row_data = options_table.get_row_data(row)
        if not row_data:
            return
        entry = row_data.get("_entry")
        if not entry:
            return
            
        xml_preview = f"<!-- {tr('mission_merge.source')}: {self._display_mod_name(entry.source_mod)} -->\n"
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
        """Update status bar with detailed conflict count and progress information."""
        total_conflicts, resolved_count = self._compute_conflict_counts()
        unresolved = max(0, total_conflicts - resolved_count)

        force = bool(getattr(self, "chk_force_apply", None) and self.chk_force_apply.isChecked())

        # Calculate progress percentage
        progress_pct = 0
        if total_conflicts > 0:
            progress_pct = int((resolved_count / total_conflicts) * 100)

        if unresolved > 0:
            status_text = f"⚠ {unresolved} {tr('mission_merge.unresolved_conflicts_text')} | {progress_pct}% {tr('mission_merge.completed')}"
            if force:
                status_text += f" | 🔓 {tr('mission_merge.force_mode_enabled')}"

            self.status_bar.setText(status_text)
            self.status_bar.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-weight: bold;
                    padding: 12px;
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ff4444, stop:1 #cc0000);
                    border: 2px solid #ff6666;
                    border-radius: 6px;
                    margin: 4px;
                }
            """)
            self.btn_apply.setEnabled(True if force else False)
        else:
            status_text = f"✓ {tr('mission_merge.all_conflicts_resolved')} | 100% {tr('mission_merge.completed')}"
            self.status_bar.setText(status_text)
            self.status_bar.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-weight: bold;
                    padding: 12px;
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #44aa44, stop:1 #008800);
                    border: 2px solid #66cc66;
                    border-radius: 6px;
                    margin: 4px;
                }
            """)
            self.btn_apply.setEnabled(True)

        # Update window title with progress
        base_title = tr("mission_merge.conflict_resolver_title")
        if total_conflicts > 0:
            self.setWindowTitle(f"{base_title} ({resolved_count}/{total_conflicts})")
        else:
            self.setWindowTitle(base_title)

        # Keep per-tab remaining label in sync
        try:
            tab = self.tabs.currentWidget()
            tab_data = self._get_tab_data(tab)
            if tab_data:
                self._update_remaining_label(tab_data)
        except Exception:
            pass
    
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
                    merge_groups[parent_key]["sources"].append(self._display_mod_name(entry.source_mod))
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
                xml_content += f"<!-- Entry: {self._display_mod_name(entry.source_mod)} ({action}) -->\n"
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

class DuplicateFixerDialog(QDialog):
    """Dialog for finding and fixing duplicate entries in mission config files."""
    
    def __init__(self, server_path: Path, mission_template: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.server_path = server_path
        self.mission_template = mission_template
        self.mission_path = get_mission_folder_path(server_path, mission_template)
        
        self._duplicates: dict[str, list[dict]] = {}  # filename -> list of duplicate groups
        
        self._setup_ui()
        self.setWindowTitle(tr("mission_merge.duplicate_fixer_title"))
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        
        # Auto scan on open
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._scan_duplicates)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(f"<h2>{tr('mission_merge.duplicate_fixer_title')}</h2>")
        header.addWidget(title)
        header.addStretch()
        
        self.btn_scan = IconButton("refresh", text=tr("mission_merge.scan"), size=16)
        self.btn_scan.clicked.connect(self._scan_duplicates)
        header.addWidget(self.btn_scan)
        
        layout.addLayout(header)
        
        # Info label
        self.lbl_info = QLabel(tr("mission_merge.duplicate_fixer_info"))
        self.lbl_info.setStyleSheet("color: gray; font-size: 11px;")
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)
        
        # Mission path info
        self.lbl_mission = QLabel(f"{tr('mission_merge.mission_folder')}: {self.mission_path}")
        self.lbl_mission.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.lbl_mission)
        
        # Main content: file tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)
        
        # Summary bar
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.StyledPanel)
        summary_frame.setStyleSheet("QFrame { background-color: rgba(0,0,0,0.1); padding: 8px; }")
        
        summary_layout = QHBoxLayout(summary_frame)
        
        self.lbl_files_scanned = QLabel(f"{tr('mission_merge.files_scanned')}: 0")
        summary_layout.addWidget(self.lbl_files_scanned)
        
        summary_layout.addWidget(QLabel("|"))
        
        self.lbl_total_duplicates = QLabel(f"{tr('mission_merge.total_duplicates')}: 0")
        self.lbl_total_duplicates.setStyleSheet("color: #f44336; font-weight: bold;")
        summary_layout.addWidget(self.lbl_total_duplicates)

        summary_layout.addWidget(QLabel("|"))

        self.lbl_remaining_groups = QLabel(tr("mission_merge.remaining_groups", remaining=0))
        self.lbl_remaining_groups.setStyleSheet("color: #ff9800; font-weight: bold;")
        summary_layout.addWidget(self.lbl_remaining_groups)
        
        summary_layout.addStretch()
        layout.addWidget(summary_frame)
        
        # Action buttons
        buttons = QHBoxLayout()
        buttons.addStretch()
        
        self.btn_fix_selected = QPushButton(tr("mission_merge.fix_selected_duplicates"))
        self.btn_fix_selected.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold;")
        self.btn_fix_selected.clicked.connect(self._fix_selected_duplicates)
        self.btn_fix_selected.setEnabled(False)
        buttons.addWidget(self.btn_fix_selected)
        
        self.btn_close = QPushButton(tr("common.close"))
        self.btn_close.clicked.connect(self.reject)
        buttons.addWidget(self.btn_close)
        
        layout.addLayout(buttons)
    
    def _scan_duplicates(self):
        """Scan mission folder for duplicate entries."""
        self.tabs.clear()
        self._duplicates.clear()

        xml_files = [p for p in self.mission_path.glob("*.xml") if p.is_file()]
        progress = QProgressDialog(
            tr("mission_merge.scanning_duplicates"), tr("common.cancel"), 0, len(xml_files), self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()
        
        try:
            files_with_dups = 0
            total_dup_groups = 0
            
            for i, xml_file in enumerate(xml_files, start=1):
                if progress.wasCanceled():
                    break

                progress.setLabelText(
                    f"{tr('mission_merge.scanning_duplicates')}: {xml_file.name} ({i}/{len(xml_files)})"
                )
                progress.setValue(i - 1)
                QApplication.processEvents()
                
                try:
                    duplicates = self._find_duplicates_in_file(xml_file)
                    if duplicates:
                        self._duplicates[xml_file.name] = duplicates
                        self._create_file_tab(xml_file.name, duplicates)
                        files_with_dups += 1
                        total_dup_groups += len(duplicates)
                except Exception:
                    pass
            
            self.lbl_files_scanned.setText(f"{tr('mission_merge.files_scanned')}: {len(xml_files)}")
            self.lbl_total_duplicates.setText(f"{tr('mission_merge.total_duplicates')}: {total_dup_groups}")
            self._update_remaining_summary()

            # Only enable the fix button when the user has explicitly resolved
            # at least one group (manual selection or auto-select).
            self.btn_fix_selected.setEnabled(False)
            
            if total_dup_groups == 0:
                QMessageBox.information(
                    self, tr("common.info"),
                    tr("mission_merge.no_duplicates_found")
                )
                
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
        finally:
            try:
                progress.setValue(len(xml_files))
                QApplication.processEvents()
            except Exception:
                pass
            progress.close()
    
    def _find_duplicates_in_file(self, file_path: Path) -> list[dict]:
        """Find duplicate entries in a single XML file.

        NOTE: Some file types (notably mapgroup*) legitimately repeat the same `name`
        many times at different positions. For those we must dedupe by a stronger
        signature (e.g., name+pos), otherwise everything becomes a false duplicate.
        """
        # Use robust parsing for potentially malformed XML
        try:
            _tree, root, model = XMLMergeHelper.parse_xml_file(file_path)
        except Exception:
            tree = ET.parse(file_path)
            root = tree.getroot()
            model = ConfigTypeRegistry.get_model_by_root_element(str(getattr(root, "tag", "") or ""))

        # cfgspawnabletypes.xml: allow repeated <type name="..."> as separate loot options.
        # Do not flag duplicates for this file.
        try:
            if (model is SpawnableTypesXMLModel) or (
                isinstance(getattr(root, "tag", None), str) and str(root.tag).lower() == "spawnabletypes"
            ):
                return []
        except Exception:
            pass

        # If the model has no repeating entry element, duplicates-by-entry don't apply.
        entry_tag: Optional[str] = None
        if model is not None:
            try:
                entry_tag = model.get_entry_element()
            except Exception:
                entry_tag = None

        all_children = list(root)

        # Track first-seen occurrences without storing everything. Only materialize
        # a list when we actually encounter a duplicate key.
        first_seen: dict[str, tuple[int, ET.Element]] = {}
        duplicates_by_key: dict[str, list[tuple[int, ET.Element]]] = {}

        for i, child in enumerate(all_children):
            if not isinstance(child.tag, str):
                continue

            # If we know the entry tag, only consider those elements.
            if entry_tag and child.tag.lower() != entry_tag.lower():
                continue

            key = XMLMergeHelper.get_element_signature(child, model)
            if not key:
                continue

            if key in duplicates_by_key:
                duplicates_by_key[key].append((i, child))
                continue

            if key in first_seen:
                first = first_seen.pop(key)
                duplicates_by_key[key] = [first, (i, child)]
            else:
                first_seen[key] = (i, child)

        def _label_for(elem: ET.Element, fallback: str) -> str:
            try:
                if str(elem.tag).lower() == "group":
                    name = elem.get("name", "")
                    pos = elem.get("pos", "")
                    if name and pos:
                        return f"{name} @ {pos}"
                    if name:
                        return name
            except Exception:
                pass
            name = elem.get("name")
            if name:
                return name
            return fallback

        duplicates: list[dict] = []
        for key, entries in duplicates_by_key.items():
            if len(entries) <= 1:
                continue
            label = _label_for(entries[0][1], key)
            duplicates.append({
                "key": key,
                "label": label,
                "entries": entries,
                "file_path": file_path,
            })

        # Stable ordering for UI
        duplicates.sort(key=lambda d: (d.get("label") or "", d.get("key") or ""))
        return duplicates
    
    def _create_file_tab(self, filename: str, duplicates: list[dict]):
        """Create a tab for fixing duplicates in a specific file."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Determine file type and merge capability using XML models
        model_class = ConfigTypeRegistry.get_model_by_filename(filename)
        is_mergeable = False
        if model_class:
            try:
                merge_strategy = model_class.get_merge_strategy()
                is_mergeable = merge_strategy in [MergeStrategy.MERGE_CHILDREN, MergeStrategy.APPEND]
            except Exception:
                is_mergeable = False
            try:
                mergeable_fields = XMLMergeHelper.get_mergeable_fields(model_class)
                if mergeable_fields:
                    is_mergeable = True
            except Exception:
                pass
        
        # Info
        info_text = tr("mission_merge.conflict_replace_info") if not is_mergeable else tr("mission_merge.conflict_merge_info")
        info = QLabel(info_text)
        info.setStyleSheet("color: #ff9800; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        if model_class:
            try:
                model_info = QLabel(f"Model: {model_class.__name__} | Strategy: {model_class.get_merge_strategy().name}")
                model_info.setStyleSheet("color: #4caf50; font-size: 10px;")
                layout.addWidget(model_info)
            except Exception:
                pass
        
        # Splitter: list on left, preview on right
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: list of duplicate groups
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_label = QLabel(f"{tr('mission_merge.duplicate_entries')} ({len(duplicates)})")
        left_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(left_label)
        
        dup_list = QListWidget()
        dup_list.setAlternatingRowColors(False)
        for i, dup_group in enumerate(duplicates):
            name = dup_group.get("label") or dup_group.get("key") or "(unknown)"
            count = len(dup_group["entries"])
            item = QListWidgetItem(f"{name} ({count} entries)")
            item.setData(Qt.UserRole, i)
            item.setForeground(QColor("#f44336"))
            dup_list.addItem(item)
        left_layout.addWidget(dup_list)
        splitter.addWidget(left_widget)
        
        # Right: options + result preview (aligned with ConflictResolverDialog)
        right_tabs = QTabWidget()

        # Tab 1: Resolution options
        options_tab = QWidget()
        options_layout = QVBoxLayout(options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)

        state_row = QHBoxLayout()

        state_label = QLabel(tr("mission_merge.conflict_current_state", state=tr("mission_merge.conflict_state_none")))
        state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
        state_row.addWidget(state_label, stretch=1)

        btn_auto_pick = QPushButton(tr("mission_merge.auto_pick_file"))
        btn_auto_pick.setToolTip(tr("mission_merge.auto_pick_file_tooltip"))
        state_row.addWidget(btn_auto_pick)

        options_layout.addLayout(state_row)

        remaining_label = QLabel("")
        remaining_label.setStyleSheet("color: gray; font-size: 11px;")
        options_layout.addWidget(remaining_label)

        auto_pick_label = QLabel("")
        auto_pick_label.setStyleSheet("color: gray; font-size: 11px;")
        options_layout.addWidget(auto_pick_label)

        options_table = QTableWidget()
        options_table.setColumnCount(4)
        options_table.setAlternatingRowColors(False)
        options_table.setHorizontalHeaderLabels([
            "",  # Checkbox
            tr("mission_merge.index"),
            tr("mission_merge.entry_preview"),
            tr("mission_merge.status"),
        ])
        options_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        options_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        options_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        options_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        options_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        options_table.verticalHeader().setVisible(False)
        options_layout.addWidget(options_table, stretch=1)

        preview_label = QLabel(tr("mission_merge.xml_preview"))
        preview_label.setStyleSheet("font-weight: bold;")
        options_layout.addWidget(preview_label)

        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setFont(QFont("Consolas", 9))
        preview_text.setMaximumHeight(200)
        preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        options_layout.addWidget(preview_text)

        right_tabs.addTab(options_tab, tr("mission_merge.resolution_options"))

        # Tab 2: Result preview
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setContentsMargins(4, 4, 4, 4)

        result_info = QLabel(tr("mission_merge.result_preview_info"))
        result_info.setStyleSheet("color: gray; font-size: 11px;")
        result_info.setWordWrap(True)
        result_layout.addWidget(result_info)

        result_preview = QTextEdit()
        result_preview.setReadOnly(True)
        result_preview.setFont(QFont("Consolas", 9))
        result_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        result_layout.addWidget(result_preview)

        right_tabs.addTab(result_tab, tr("mission_merge.result_preview"))

        splitter.addWidget(right_tabs)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # Store tab data
        tab_data = {
            "filename": filename,
            "duplicates": duplicates,
            "dup_list": dup_list,
            "options_table": options_table,
            "preview_text": preview_text,
            "state_label": state_label,
            "remaining_label": remaining_label,
            "auto_pick_label": auto_pick_label,
            "btn_auto_pick": btn_auto_pick,
            "result_preview": result_preview,
            "model_class": model_class,
            "is_mergeable": is_mergeable,
            "resolved_by_group": {},  # {dup_index: [selected_row_indices]}
            "_auto_picked_groups": 0,
            "_auto_picked_entries": 0,
            "_handlers_connected": False,
            "_in_change": False,
        }
        widget._tab_data = tab_data
        
        # Connect signals
        dup_list.currentItemChanged.connect(
            lambda curr, prev, td=tab_data: self._on_duplicate_selected(td, curr)
        )

        btn_auto_pick.clicked.connect(lambda _=False, td=tab_data: self._auto_pick_file_groups(td))
        
        # Connect signals
        options_table.itemChanged.connect(lambda item, td=tab_data: self._on_keep_selection_changed(td, item))
        options_table.itemClicked.connect(lambda item, td=tab_data: self._on_keep_selection_changed(td, item))
        options_table.cellClicked.connect(lambda r, c, td=tab_data: self._on_option_row_clicked(td, r, c))
        
        self.tabs.addTab(widget, f"{filename} ({len(duplicates)})")
        
        # Select first item
        if dup_list.count() > 0:
            dup_list.setCurrentRow(0)
    
    def _on_duplicate_selected(self, tab_data: dict, item):
        """Handle duplicate group selection."""
        if not item:
            return
        
        dup_index = item.data(Qt.UserRole)
        duplicates = tab_data["duplicates"]
        options_table = tab_data["options_table"]
        preview_text = tab_data["preview_text"]
        
        if dup_index >= len(duplicates):
            return
        
        dup_group = duplicates[dup_index]
        entries = dup_group["entries"]

        # NOTE: Auto-pick is a bulk per-file action via the button.
        
        # Clear and populate options table
        tab_data["_in_change"] = True
        try:
            options_table.setRowCount(0)
            tab_data["_current_dup_index"] = dup_index
        finally:
            tab_data["_in_change"] = False
        
        # Previously selected rows for this group
        selected_rows = list(tab_data.get("resolved_by_group", {}).get(dup_index, []) or [])
        
        tab_data["_in_change"] = True
        try:
            for i, (entry_idx, element) in enumerate(entries):
                row = options_table.rowCount()
                options_table.insertRow(row)
                
                # Selection checkbox
                selected = i in selected_rows
                sel_item = QTableWidgetItem("")
                sel_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                sel_item.setData(Qt.UserRole, i)  # row index in entries list
                sel_item.setData(Qt.UserRole + 1, dup_index)
                sel_item.setCheckState(Qt.Checked if selected else Qt.Unchecked)
                options_table.setItem(row, 0, sel_item)
                
                # Index
                idx_item = QTableWidgetItem(f"#{entry_idx}")
                idx_item.setFlags(idx_item.flags() & ~Qt.ItemIsEditable)
                options_table.setItem(row, 1, idx_item)
                
                # Preview
                xml_str = ET.tostring(element, encoding="unicode")
                preview = xml_str[:80] + "..." if len(xml_str) > 80 else xml_str
                preview_item = QTableWidgetItem(preview.replace("\n", " "))
                preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
                preview_item.setToolTip(xml_str)
                options_table.setItem(row, 2, preview_item)

                # Status
                status_item = QTableWidgetItem(tr("mission_merge.selected") if selected else "")
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                status_item.setForeground(QColor("#4caf50") if selected else QColor("#888"))
                options_table.setItem(row, 3, status_item)
        finally:
            tab_data["_in_change"] = False
        
        # Show preview of first entry
        if entries:
            title = dup_group.get("label") or dup_group.get("key") or "(unknown)"
            xml_preview = f"<!-- Duplicate entry: {title} -->\n"
            xml_preview += f"<!-- {len(entries)} occurrences found -->\n\n"
            xml_preview += ET.tostring(entries[0][1], encoding="unicode")
            preview_text.setText(xml_preview)

        # Update state label and result preview
        self._refresh_option_row_visuals(tab_data)
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_remaining_summary()

        # Update left list item marker
        self._update_duplicate_group_marker(tab_data, dup_index)

        try:
            options_table.viewport().update()
        except Exception:
            pass
    
    def _on_keep_selection_changed(self, tab_data: dict, changed_item: QTableWidgetItem):
        """Handle checkbox changes.

        Behavior:
        - Non-mergeable files: only one selection (radio behavior) => replace
        - Mergeable files: allow multiple selections => merge
        """
        if not changed_item:
            return
        if tab_data.get("_in_change"):
            return
        if changed_item.column() != 0:
            return

        options_table = tab_data["options_table"]
        dup_index = changed_item.data(Qt.UserRole + 1) or tab_data.get("_current_dup_index")
        if dup_index is None:
            return

        is_mergeable = bool(tab_data.get("is_mergeable"))

        row = changed_item.row()
        selected_rows: list[int] = []
        for r in range(options_table.rowCount()):
            it = options_table.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                try:
                    selected_rows.append(int(it.data(Qt.UserRole)))
                except Exception:
                    pass

        # Non-mergeable -> enforce single selection (keep latest checked)
        if not is_mergeable and changed_item.checkState() == Qt.Checked:
            chosen = changed_item.data(Qt.UserRole)
            tab_data["_in_change"] = True
            try:
                for r in range(options_table.rowCount()):
                    it = options_table.item(r, 0)
                    if not it:
                        continue
                    if it is changed_item:
                        continue
                    if it.checkState() == Qt.Checked:
                        it.setCheckState(Qt.Unchecked)
            finally:
                tab_data["_in_change"] = False
            selected_rows = [int(chosen)] if chosen is not None else []

        # Persist selection
        if selected_rows:
            tab_data["resolved_by_group"][int(dup_index)] = sorted(set(selected_rows))
        else:
            tab_data.get("resolved_by_group", {}).pop(int(dup_index), None)

        # Update markers + visuals
        self._update_duplicate_group_marker(tab_data, int(dup_index))
        self._refresh_option_row_visuals(tab_data)
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_remaining_summary()
    
    def _on_option_row_clicked(self, tab_data: dict, row: int, col: int):
        """Update preview and toggle selection by clicking on a row."""
        options_table = tab_data["options_table"]
        preview_text = tab_data["preview_text"]
        dup_index = tab_data.get("_current_dup_index")
        
        if dup_index is None:
            return
        
        duplicates = tab_data["duplicates"]
        if dup_index >= len(duplicates):
            return
        
        dup_group = duplicates[dup_index]
        entries = dup_group["entries"]
        
        if row < len(entries):
            # Update preview
            title = dup_group.get("label") or dup_group.get("key") or "(unknown)"
            xml_preview = f"<!-- Duplicate entry: {title} -->\n"
            xml_preview += f"<!-- Entry {row+1}/{len(entries)} -->\n\n"
            xml_preview += ET.tostring(entries[row][1], encoding="unicode")
            preview_text.setText(xml_preview)

            # Toggle selection if clicking outside the checkbox column
            if col != 0:
                item = options_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

        try:
            options_table.viewport().update()
        except Exception:
            pass
    
    def _fix_selected_duplicates(self):
        """Apply fixes for selected duplicates."""
        # Collect all selections
        fixes_by_file: dict[str, list[dict]] = {}
        estimated_remove_entries = 0
        selected_groups = 0
        
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab_data = getattr(tab, "_tab_data", None)
            if not tab_data:
                continue
            
            filename = tab_data["filename"]
            duplicates = tab_data["duplicates"]
            selections = tab_data.get("resolved_by_group", {})
            is_mergeable = bool(tab_data.get("is_mergeable"))
            model_class = tab_data.get("model_class")

            for dup_idx, selected_rows_raw in (selections or {}).items():
                try:
                    dup_idx = int(dup_idx)
                except Exception:
                    continue
                if dup_idx < 0 or dup_idx >= len(duplicates):
                    continue
                dup_group = duplicates[dup_idx]
                selected_rows = list(selected_rows_raw or [])
                if not selected_rows:
                    continue

                # Determine action
                action = "replace"
                if len(selected_rows) > 1 and is_mergeable:
                    action = "merge"

                fixes_by_file.setdefault(filename, []).append({
                    "key": dup_group.get("key"),
                    "label": dup_group.get("label"),
                    "entries": dup_group["entries"],
                    "selected_rows": selected_rows,
                    "action": action,
                    "file_path": dup_group["file_path"],
                    "model_class": model_class,
                })

                try:
                    estimated_remove_entries += max(0, int(len(dup_group.get("entries") or [])) - 1)
                except Exception:
                    pass
                selected_groups += 1
        
        if not fixes_by_file:
            QMessageBox.warning(self, tr("common.warning"), tr("mission_merge.no_fixes_selected"))
            return

        total_files = len([f for f in fixes_by_file.keys()])
        
        # Confirm
        reply = QMessageBox.question(
            self, tr("common.confirm"),
            tr("mission_merge.confirm_fix_duplicates_detailed").format(
                entries=estimated_remove_entries,
                groups=selected_groups,
                files=total_files,
            )
            if "confirm_fix_duplicates_detailed" in (tr("mission_merge.confirm_fix_duplicates_detailed") or "")
            else tr("mission_merge.confirm_fix_duplicates").format(count=estimated_remove_entries),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            fixed_count = 0
            
            for filename, fixes in fixes_by_file.items():
                file_path = self.mission_path / filename
                
                if not file_path.exists():
                    continue

                # Parse (robust first) and keep the model for stable signatures
                try:
                    tree, root, model = XMLMergeHelper.parse_xml_file(file_path)
                except Exception:
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    model = ConfigTypeRegistry.get_model_by_root_element(str(getattr(root, "tag", "") or ""))

                def _entry_sig(el: ET.Element) -> Optional[str]:
                    try:
                        return XMLMergeHelper.get_element_signature(el, model)
                    except Exception:
                        return None

                def _child_sig(ch: ET.Element, model_class: Optional[Type]) -> str:
                    try:
                        s = XMLMergeHelper.get_element_signature(ch, model_class)
                    except Exception:
                        s = None
                    if s:
                        return str(s)
                    try:
                        return str((str(ch.tag), tuple(sorted((ch.attrib or {}).items())), (ch.text or "").strip()))
                    except Exception:
                        return str(id(ch))

                # Apply each fix group by matching the duplicate key against the CURRENT parsed tree.
                # This avoids index-shift bugs when earlier removals/merges change child positions.
                for fix in fixes:
                    group_key = fix.get("key")
                    if not group_key:
                        continue

                    selected_rows = [int(x) for x in (fix.get("selected_rows") or []) if str(x).isdigit()]
                    if not selected_rows:
                        selected_rows = [0]

                    action = str(fix.get("action") or "replace")
                    model_class = fix.get("model_class")

                    current_children = list(root)
                    occurrences: list[ET.Element] = []
                    for ch in current_children:
                        if not isinstance(getattr(ch, "tag", None), str):
                            continue
                        if _entry_sig(ch) == group_key:
                            occurrences.append(ch)

                    if len(occurrences) <= 1:
                        continue

                    # Clamp selected rows to current occurrences length
                    selected_rows = [r for r in selected_rows if 0 <= r < len(occurrences)]
                    if not selected_rows:
                        selected_rows = [0]

                    keep_el = occurrences[selected_rows[0]]

                    # Elements chosen for merge/keep context
                    selected_els = [occurrences[r] for r in selected_rows]

                    # Remove all duplicates except the kept one
                    for ch in occurrences:
                        if ch is keep_el:
                            continue
                        try:
                            root.remove(ch)
                            fixed_count += 1
                        except Exception:
                            pass

                    # Merge: replace kept element with merged children from selected entries
                    if action == "merge" and len(selected_els) > 1:
                        try:
                            keep_pos = list(root).index(keep_el)
                        except ValueError:
                            keep_pos = None

                        merged = ET.Element(keep_el.tag, dict(keep_el.attrib))
                        try:
                            merged.text = keep_el.text
                        except Exception:
                            pass

                        seen_child = set()
                        for el in selected_els:
                            for child in list(el):
                                sig = _child_sig(child, model_class)
                                if sig in seen_child:
                                    continue
                                cloned = ET.Element(child.tag, dict(child.attrib))
                                cloned.text = child.text
                                cloned.tail = child.tail
                                for subchild in list(child):
                                    cloned.append(subchild)
                                merged.append(cloned)
                                seen_child.add(sig)

                        try:
                            root.remove(keep_el)
                        except Exception:
                            pass

                        if keep_pos is None:
                            root.append(merged)
                        else:
                            try:
                                root.insert(int(keep_pos), merged)
                            except Exception:
                                root.append(merged)
                
                # Save
                try:
                    ET.indent(tree, space="    ")
                except AttributeError:
                    pass
                
                tree.write(file_path, encoding="utf-8", xml_declaration=True)
            
            QMessageBox.information(
                self, tr("common.success"),
                tr("mission_merge.duplicates_fixed").format(count=fixed_count)
            )
            
            # Rescan
            self._scan_duplicates()
            
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    def _update_duplicate_group_marker(self, tab_data: dict, dup_index: int):
        """Mark duplicate group as resolved/unresolved in the left list."""
        dup_list = tab_data.get("dup_list")
        if not dup_list:
            return
        resolved = bool((tab_data.get("resolved_by_group") or {}).get(dup_index))
        for i in range(dup_list.count()):
            it = dup_list.item(i)
            if not it:
                continue
            if it.data(Qt.UserRole) != dup_index:
                continue
            text = it.text().lstrip("✓ ")
            it.setText(("✓ " if resolved else "") + text)
            it.setForeground(QColor("#4caf50") if resolved else QColor("#f44336"))
            break

    def _update_remaining_label(self, tab_data: dict):
        """Update per-file remaining/resolved count label."""
        lbl = tab_data.get("remaining_label")
        if not lbl:
            return
        total = len(tab_data.get("duplicates") or [])
        resolved_by_group = tab_data.get("resolved_by_group") or {}
        resolved = 0
        for i in range(total):
            if resolved_by_group.get(i):
                resolved += 1
        remaining = max(0, total - resolved)
        lbl.setText(tr("mission_merge.remaining_count", remaining=remaining, total=total))

    def _auto_pick_file_groups(self, tab_data: dict):
        """Bulk action: auto-pick duplicate groups in THIS file when all options are identical."""
        duplicates = list(tab_data.get("duplicates", []) or [])
        if not duplicates:
            return

        resolved_by_group = tab_data.get("resolved_by_group") or {}
        picked = 0
        picked_entries = 0

        for dup_index, dup_group in enumerate(duplicates):
            if resolved_by_group.get(dup_index):
                continue
            entries = list((dup_group or {}).get("entries") or [])
            if not entries:
                continue
            try:
                sigs = [self._deep_signature(el) for _idx, el in entries]
                is_all_same = bool(sigs) and all(s == sigs[0] for s in sigs[1:])
            except Exception:
                is_all_same = False

            if not is_all_same:
                continue

            tab_data["resolved_by_group"][dup_index] = [0]
            picked += 1
            try:
                picked_entries += max(0, int(len(entries)) - 1)
            except Exception:
                pass
            self._update_duplicate_group_marker(tab_data, dup_index)

        # Refresh current selection/table
        dup_list = tab_data.get("dup_list")
        if dup_list:
            curr = dup_list.currentItem()
            if curr:
                self._on_duplicate_selected(tab_data, curr)

        self._update_remaining_label(tab_data)
        self._update_remaining_summary()

        tab_data["_auto_picked_groups"] = int(picked)
        tab_data["_auto_picked_entries"] = int(picked_entries)
        self._update_auto_pick_label(tab_data)

        if picked <= 0:
            QMessageBox.information(self, tr("common.info"), tr("mission_merge.auto_pick_not_applicable"))
        else:
            QMessageBox.information(
                self,
                tr("common.success"),
                tr("mission_merge.auto_pick_applied_details").format(groups=picked, entries=picked_entries)
                if "auto_pick_applied_details" in (tr("mission_merge.auto_pick_applied_details") or "")
                else tr("mission_merge.auto_pick_applied", count=picked),
            )

    def _update_auto_pick_label(self, tab_data: dict):
        """Update per-file label showing auto-selected counts (for transparency)."""
        lbl = tab_data.get("auto_pick_label")
        if not lbl:
            return
        g = int(tab_data.get("_auto_picked_groups") or 0)
        e = int(tab_data.get("_auto_picked_entries") or 0)
        if g <= 0:
            lbl.setText("")
            return
        try:
            lbl.setText(tr("mission_merge.auto_pick_summary").format(groups=g, entries=e))
        except Exception:
            lbl.setText(f"Auto selected: {g} groups / {e} entries")

    def _update_remaining_summary(self):
        """Update overall remaining groups label in the summary bar."""
        remaining = 0
        any_selected = False
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab_data = getattr(tab, "_tab_data", None)
            if not tab_data:
                continue
            total = len(tab_data.get("duplicates") or [])
            resolved_by_group = tab_data.get("resolved_by_group") or {}
            if resolved_by_group:
                any_selected = True
            resolved = 0
            for gi in range(total):
                if resolved_by_group.get(gi):
                    resolved += 1
            remaining += max(0, total - resolved)
        try:
            self.lbl_remaining_groups.setText(tr("mission_merge.remaining_groups", remaining=remaining))
        except Exception:
            pass

        try:
            self.btn_fix_selected.setEnabled(bool(any_selected))
        except Exception:
            pass

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
            status_item = options_table.item(r, 3)
            if status_item:
                status_item.setText(tr("mission_merge.selected") if checked else "")
                status_item.setForeground(QColor("#4caf50") if checked else QColor("#888"))

            bg = QColor("#1b3b1b") if checked else QColor("#000000")
            for c in range(1, options_table.columnCount()):
                cell = options_table.item(r, c)
                if cell:
                    cell.setBackground(bg)

    def _update_state_label(self, tab_data: dict):
        """Update the state label showing current selection status."""
        state_label = tab_data.get("state_label")
        if not state_label:
            return

        dup_index = tab_data.get("_current_dup_index")
        if dup_index is None:
            state_label.setText(tr("mission_merge.conflict_current_state", state=tr("mission_merge.conflict_state_none")))
            state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
            return

        selections = list((tab_data.get("resolved_by_group") or {}).get(dup_index, []) or [])

        if not selections:
            state_text = tr("mission_merge.conflict_state_none")
            state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
        elif len(selections) == 1:
            # Replace
            try:
                dup_group = tab_data.get("duplicates", [])[dup_index]
                entries = dup_group.get("entries") or []
                el = entries[int(selections[0])][1] if entries else None
                name = (el.get("name") if el is not None else None) or (dup_group.get("label") or dup_group.get("key") or "")
            except Exception:
                name = ""
            state_text = tr("mission_merge.conflict_state_replace", name=name)
            state_label.setStyleSheet("color: #4caf50; font-weight: bold; padding: 4px; background-color: rgba(76, 175, 80, 0.1);")
        else:
            state_text = tr("mission_merge.conflict_state_merge", count=len(selections))
            state_label.setStyleSheet("color: #2196f3; font-weight: bold; padding: 4px; background-color: rgba(33, 150, 243, 0.1);")

        state_label.setText(tr("mission_merge.conflict_current_state", state=state_text))

    def _update_result_preview(self, tab_data: dict):
        """Update the result preview showing merged/replaced result."""
        result_preview = tab_data.get("result_preview")
        if not result_preview:
            return

        dup_index = tab_data.get("_current_dup_index")
        if dup_index is None:
            result_preview.setText("")
            return

        selections = list((tab_data.get("resolved_by_group") or {}).get(dup_index, []) or [])
        duplicates = tab_data.get("duplicates", [])
        if dup_index >= len(duplicates):
            result_preview.setText("")
            return

        entries = list(duplicates[dup_index].get("entries") or [])
        if not selections:
            result_preview.setText(f"<!-- {tr('mission_merge.conflict_state_none')} -->")
            return

        is_mergeable = bool(tab_data.get("is_mergeable"))
        model_class = tab_data.get("model_class")

        if len(selections) == 1 or not is_mergeable:
            try:
                el = entries[int(selections[0])][1]
            except Exception:
                el = entries[0][1] if entries else None
            if el is None:
                result_preview.setText("")
                return
            xml_preview = f"<!-- {tr('mission_merge.conflict_state_replace', name='')} -->\n\n"
            xml_preview += ET.tostring(el, encoding="unicode")
            result_preview.setText(xml_preview)
            return

        # Merge preview
        xml_preview = f"<!-- {tr('mission_merge.conflict_state_merge', count=len(selections))} -->\n\n"
        try:
            base_el = entries[int(selections[0])][1]
        except Exception:
            base_el = entries[0][1]

        merged = ET.Element(base_el.tag, dict(base_el.attrib))
        try:
            merged.text = base_el.text
        except Exception:
            pass

        seen = set()
        for sel_row in selections:
            try:
                el = entries[int(sel_row)][1]
            except Exception:
                continue
            for child in list(el):
                try:
                    sig = XMLMergeHelper.get_element_signature(child, model_class)
                except Exception:
                    sig = None
                if not sig:
                    try:
                        sig = (str(child.tag), tuple(sorted((child.attrib or {}).items())), (child.text or "").strip())
                    except Exception:
                        sig = id(child)
                if sig in seen:
                    continue
                cloned = ET.Element(child.tag, dict(child.attrib))
                cloned.text = child.text
                cloned.tail = child.tail
                for subchild in list(child):
                    cloned.append(subchild)
                merged.append(cloned)
                seen.add(sig)

        xml_preview += ET.tostring(merged, encoding="unicode")
        result_preview.setText(xml_preview)

    @staticmethod
    def _deep_signature(elem: ET.Element):
        """Compute a stable deep signature for an XML element."""
        try:
            tag = str(elem.tag)
        except Exception:
            tag = ""
        try:
            attrib = tuple(sorted((elem.attrib or {}).items()))
        except Exception:
            attrib = ()
        try:
            text = (elem.text or "").strip()
        except Exception:
            text = ""
        children = []
        try:
            for ch in list(elem):
                children.append(DuplicateFixerDialog._deep_signature(ch))
        except Exception:
            children = []
        return (tag, attrib, text, tuple(children))
