"""
Mods Tab - Mod Management with Add/Remove/Update functionality
Refactored to use base classes and utilities.
"""

from pathlib import Path
from shared.ui.components.table import ReusableTable, TableColumn
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from features.mods.core.mod_integrity import ModIntegrityChecker
from features.profiles.core.profile_manager import ProfileManager
from features.settings.core.settings_manager import SettingsManager
from features.mods.core.mod_worker import ModWorker
from features.mods.core.mod_name_manager import ModNameManager
from shared.ui.icons import Icons
from shared.ui.widgets.icon_button import IconButton
from shared.ui.base import BaseTab
from shared.ui.factories import create_action_button
from shared.ui.theme_manager import ThemeManager
from shared.utils.locale_manager import tr
from shared.utils.mod_utils import (
    format_file_size, find_mod_bikeys, format_mods_txt,
    scan_workshop_mods, scan_installed_mods, get_mod_version,
    get_folder_size, format_datetime
)
from features.settings.core.settings_manager import SettingsManager


# Column constants
class WorkshopColumns:
    CHECK, NAME, VERSION, SIZE, DATE, STATUS = range(6)

class InstalledColumns:
    CHECK, NAME, VERSION, SIZE, DATE, BIKEY, ACTIONS = range(7)


class ModsTab(BaseTab):
    """Tab for managing server mods."""

    mods_list_updated = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent, scrollable=False, title_key="mods.title")
        self.current_profile = None
        self.profile_manager = ProfileManager()
        self.settings = SettingsManager()
        self.worker = None
        self._current_operation: str | None = None
        self.progress_dialog = None
        self._workshop_items: list[tuple[str, str, str, int, bool, object]] = []  # Added install_date
        self._installed_items: list[tuple[str, str, int, bool, list, object]] = []  # Added install_date
        self._populating = False
        
        self._setup_content()
    
    def _setup_content(self):
        """Setup the main content area."""
        # Header buttons
        self.btn_refresh = create_action_button(
            "refresh", text=tr("common.refresh"), size=18,
            on_click=self._refresh_all
        )
        self.add_header_button(self.btn_refresh)
        
        # No profile message
        self.lbl_no_profile = QLabel(tr("mods.select_profile_first"))
        self.lbl_no_profile.setAlignment(Qt.AlignCenter)
        self.lbl_no_profile.setStyleSheet("color: gray; padding: 30px; font-size: 14px;")
        self.add_widget(self.lbl_no_profile)
        
        # Content widget with splitter
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Setup panels
        left_panel = self._create_workshop_panel()
        right_panel = self._create_installed_panel()
        
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([500, 500])
        
        content_layout.addWidget(self.splitter)
        self.add_widget(self.content_widget)
        self.content_widget.setVisible(False)
    
    def _create_workshop_panel(self) -> QWidget:
        """Create the workshop (source) mods panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        
        self.workshop_box = QGroupBox(tr("mods.workshop_source"))
        box_layout = QVBoxLayout(self.workshop_box)
        
        # Workshop path
        self.lbl_workshop_path = QLabel()
        self.lbl_workshop_path.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_workshop_path.setWordWrap(True)
        box_layout.addWidget(self.lbl_workshop_path)
        
        # Search
        self.search_workshop = QLineEdit()
        self.search_workshop.setPlaceholderText(f"{tr('common.search')}...")
        self.search_workshop.textChanged.connect(self._filter_workshop_table)
        self.search_workshop.setClearButtonEnabled(True)
        box_layout.addWidget(self.search_workshop)
        
        # Actions
        actions = QHBoxLayout()
        self.btn_add_selected = IconButton("plus", text=tr("mods.add_to_server"), size=18, object_name="primary")
        self.btn_add_selected.clicked.connect(self._add_selected_mods)
        actions.addWidget(self.btn_add_selected)
        
        self.btn_select_all_ws = QPushButton(tr("common.select_all"))
        self.btn_select_all_ws.clicked.connect(self._select_all_workshop)
        actions.addWidget(self.btn_select_all_ws)
        
        self.btn_deselect_all_ws = QPushButton(tr("common.deselect_all"))
        self.btn_deselect_all_ws.clicked.connect(self._deselect_all_workshop)
        actions.addWidget(self.btn_deselect_all_ws)
        
        actions.addStretch()
        
        # Optimize mod names checkbox
        from PySide6.QtWidgets import QCheckBox
        self.chk_optimize_names = QCheckBox(tr("mods.optimize_names"))
        self.chk_optimize_names.setToolTip(tr("mods.optimize_names_tooltip"))
        self.chk_optimize_names.setChecked(False)
        actions.addWidget(self.chk_optimize_names)
        
        actions.addWidget(QLabel("|"))
        
        self.lbl_ws_count = QLabel("0 mods")
        self.lbl_ws_count.setStyleSheet(f"color: {ThemeManager.get_accent_color()};")
        actions.addWidget(self.lbl_ws_count)
        box_layout.addLayout(actions)
        
        # Table
        self.workshop_table = self._create_workshop_table()
        box_layout.addWidget(self.workshop_table)
        
        layout.addWidget(self.workshop_box)
        return panel
    
    def _create_installed_panel(self) -> QWidget:
        """Create the installed mods panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        
        self.installed_box = QGroupBox(tr("mods.server_installed"))
        box_layout = QVBoxLayout(self.installed_box)
        
        # Server path
        self.lbl_server_path = QLabel()
        self.lbl_server_path.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_server_path.setWordWrap(True)
        box_layout.addWidget(self.lbl_server_path)
        
        # Search
        self.search_installed = QLineEdit()
        self.search_installed.setPlaceholderText(f"{tr('common.search')}...")
        self.search_installed.textChanged.connect(self._filter_installed_table)
        self.search_installed.setClearButtonEnabled(True)
        box_layout.addWidget(self.search_installed)
        
        # Actions
        actions = QHBoxLayout()
        self.btn_remove_selected = IconButton("trash", text=tr("mods.remove_from_server"), size=18, object_name="danger")
        self.btn_remove_selected.clicked.connect(self._remove_selected_mods)
        actions.addWidget(self.btn_remove_selected)
        
        self.btn_copy_all_bikeys = IconButton("key", text=tr("mods.copy_all_bikeys"), size=18)
        self.btn_copy_all_bikeys.clicked.connect(self._copy_all_bikeys)
        self.btn_copy_all_bikeys.setEnabled(False)  # Enable when mods without bikeys exist
        actions.addWidget(self.btn_copy_all_bikeys)

        self.btn_optimize_installed = IconButton("sort", text=tr("mods.optimize_installed"), size=18)
        self.btn_optimize_installed.setToolTip(tr("mods.optimize_installed_tooltip"))
        self.btn_optimize_installed.clicked.connect(self._optimize_installed_mods)
        actions.addWidget(self.btn_optimize_installed)
        
        self.btn_select_all_inst = QPushButton(tr("common.select_all"))
        self.btn_select_all_inst.clicked.connect(self._select_all_installed)
        actions.addWidget(self.btn_select_all_inst)
        
        self.btn_deselect_all_inst = QPushButton(tr("common.deselect_all"))
        self.btn_deselect_all_inst.clicked.connect(self._deselect_all_installed)
        actions.addWidget(self.btn_deselect_all_inst)
        
        actions.addStretch()
        self.lbl_inst_count = QLabel("0 mods")
        self.lbl_inst_count.setStyleSheet("color: #4caf50;")
        actions.addWidget(self.lbl_inst_count)
        box_layout.addLayout(actions)
        
        # Table
        self.installed_table = self._create_installed_table()
        box_layout.addWidget(self.installed_table)
        
        layout.addWidget(self.installed_box)
        return panel
    
    def _create_workshop_table(self) -> ReusableTable:
        """Create and configure workshop table."""
        columns = [
            TableColumn("name", tr("mods.mod_name"), QHeaderView.Stretch),
            TableColumn("version", tr("mods.mod_version"), QHeaderView.ResizeToContents),
            TableColumn("size", tr("mods.mod_size"), QHeaderView.ResizeToContents),
            TableColumn("date", tr("mods.mod_date"), QHeaderView.ResizeToContents),
            TableColumn("status", tr("mods.mod_status"), QHeaderView.ResizeToContents),
        ]
        table = ReusableTable(columns, has_checkbox=True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.checkbox_toggled.connect(self._on_workshop_checkbox_toggled)
        return table
    
    def _create_installed_table(self) -> ReusableTable:
        """Create and configure installed mods table."""
        columns = [
            TableColumn("name", tr("mods.mod_name"), QHeaderView.Stretch),
            TableColumn("version", tr("mods.mod_version"), QHeaderView.ResizeToContents),
            TableColumn("size", tr("mods.mod_size"), QHeaderView.ResizeToContents),
            TableColumn("date", tr("mods.mod_date"), QHeaderView.ResizeToContents),
            TableColumn("bikey", tr("mods.bikey_status"), QHeaderView.ResizeToContents),
        ]
        actions = [
            TableAction("action", "", lambda row: self._on_installed_action(row)),
        ]
        table = ReusableTable(columns, actions, has_checkbox=True)
        # Ensure rows are tall enough to accommodate action buttons
        try:
            table.verticalHeader().setDefaultSectionSize(36)
        except Exception:
            pass
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.checkbox_toggled.connect(self._on_installed_checkbox_toggled)
        return table
    
    # ========== Profile & Refresh ==========
    
    def showEvent(self, event):
        super().showEvent(event)
        if self.current_profile:
            self._refresh_all()
    
    def set_profile(self, profile_data: dict):
        """Set the current profile for mod management."""
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(250)

        self.current_profile = profile_data

        has_profile = bool(profile_data)
        self.lbl_no_profile.setVisible(not has_profile)
        self.content_widget.setVisible(has_profile)
        if not has_profile:
            self.workshop_table.setRowCount(0)
            self.installed_table.setRowCount(0)
            self._workshop_items = []
            self._installed_items = []
            self._update_ws_count()
            self._update_inst_count()
            self.lbl_workshop_path.setText("")
            self.lbl_server_path.setText("")
            return

        self.lbl_workshop_path.setText(profile_data.get("workshop_path", "") or "")
        self.lbl_server_path.setText(profile_data.get("server_path", "") or "")
        self._refresh_all()
    
    def _refresh_all(self):
        if not self.current_profile:
            return
        self._load_workshop_mods()
        self._load_installed_mods()
    
    # ========== Load Mods ==========
    
    def _load_workshop_mods(self):
        """Load mods from workshop source folder."""
        self._populating = True
        try:
            self.workshop_table.setRowCount(0)
            
            workshop_path_str = self.current_profile.get("workshop_path", "")
            server_path_str = self.current_profile.get("server_path", "")
            
            if not workshop_path_str:
                self._workshop_items = []
                self._update_ws_count()
                return
            
            workshop_path = Path(workshop_path_str)
            server_path = Path(server_path_str) if server_path_str else None
            
            # Use utility function
            self._workshop_items = scan_workshop_mods(workshop_path, server_path)
            
            # Get installed versions and dates for comparison
            installed_mods = {}
            installed_dates = {}
            name_manager = None
            try:
                if server_path and server_path.exists():
                    name_manager = ModNameManager(server_path)
            except Exception:
                name_manager = None
            
            if server_path and server_path.exists():
                for item in server_path.iterdir():
                    if item.is_dir() and item.name.startswith("@"):
                        ver = get_mod_version(item)
                        # Register multiple name variants to improve matching:
                        # - actual folder name (with @)
                        # - without @
                        # - resolved original name from mapping (with @)
                        # - any other shorts that map to the same original
                        try:
                            folder_name = item.name
                            installed_mods[folder_name.lower()] = ver
                            installed_mods[folder_name.lstrip("@").lower()] = ver

                            # Map to original name if optimized
                            original_name = name_manager.get_original_name(item.name) if name_manager else item.name
                            if original_name:
                                installed_mods[original_name.lower()] = ver
                                installed_mods[original_name.lstrip("@").lower()] = ver

                            # Also include other shorts for the same original
                            if name_manager:
                                try:
                                    for s in name_manager.get_all_shorts_for_original(original_name):
                                        if s:
                                            installed_mods[f"@{s}".lower()] = ver
                                            installed_mods[s.lower()] = ver
                                except Exception:
                                    pass

                        except Exception:
                            pass
                        # Get server install date for highlighting outdated mods
                        from shared.utils.mod_utils import get_folder_install_date
                        installed_dates[item.name.lower()] = get_folder_install_date(item)
            
            # Store for later comparison (highlighting outdated mods)
            self._installed_dates = installed_dates
            
            # Populate table
            workshop_data = []
            for workshop_id, mod_folder, version, size, is_installed, install_date in self._workshop_items:
                status_text, status_icon, status_color = self._get_workshop_status(
                    is_installed, version, installed_mods.get(mod_folder.lower())
                )
                date_format = self.settings.settings.datetime_format
                row_data = {
                    "name": mod_folder,
                    "version": version or "-",
                    "size": format_file_size(size),
                    "date": format_datetime(install_date, date_format),
                    "status": status_text,
                    "checked": False,  # Default unchecked
                    "status_color": status_color,
                    "status_icon": status_icon,
                    "workshop_id": workshop_id,
                    "install_date": install_date,
                }
                workshop_data.append(row_data)
            
            self.workshop_table.set_data(workshop_data)
            
            self._update_ws_count()
        finally:
            self._populating = False
    
    def _populate_workshop_row(self, row: int, workshop_id: str, mod_folder: str,
                               version: str, size: int, is_installed: bool,
                               install_date, installed_mods: dict):
        """Populate a single workshop table row."""
        # Checkbox
        check_item = QTableWidgetItem()
        check_item.setFlags(check_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        check_item.setCheckState(Qt.Unchecked)
        check_item.setData(Qt.UserRole, (workshop_id, mod_folder))
        self.workshop_table.setItem(row, WorkshopColumns.CHECK, check_item)
        
        # Name
        name_item = QTableWidgetItem(mod_folder)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.workshop_table.setItem(row, WorkshopColumns.NAME, name_item)
        
        # Version
        version_item = QTableWidgetItem(version or "-")
        version_item.setFlags(version_item.flags() & ~Qt.ItemIsEditable)
        self.workshop_table.setItem(row, WorkshopColumns.VERSION, version_item)
        
        # Size
        size_item = QTableWidgetItem(format_file_size(size))
        size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
        self.workshop_table.setItem(row, WorkshopColumns.SIZE, size_item)
        
        # Date
        date_format = self.settings.settings.datetime_format
        date_item = QTableWidgetItem(format_datetime(install_date, date_format))
        date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
        date_item.setData(Qt.UserRole, install_date)  # Store datetime for comparison
        self.workshop_table.setItem(row, WorkshopColumns.DATE, date_item)
        
        # Status
        status_text, status_icon, status_color = self._get_workshop_status(
            is_installed, version, installed_mods.get(mod_folder.lower())
        )
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        status_item.setForeground(QColor(status_color))
        try:
            status_item.setIcon(Icons.get_icon(status_icon, size=16))
        except Exception:
            pass
        self.workshop_table.setItem(row, WorkshopColumns.STATUS, status_item)
    
    def _get_workshop_status(self, is_installed: bool, version: str | None,
                             installed_ver: str | None) -> tuple[str, str, str]:
        """Get status text, icon, and color for workshop mod."""
        if is_installed:
            if version and installed_ver and version != installed_ver:
                return tr('mods.status_outdated'), "refresh", "#4caf50"
            return tr('mods.status_installed'), "success", "#4caf50"
        return tr('mods.status_not_installed'), "info", "#888"
    
    def _load_installed_mods(self):
        """Load mods installed on server."""
        self._populating = True
        try:
            self.installed_table.setRowCount(0)
            
            server_path_str = self.current_profile.get("server_path", "")
            if not server_path_str:
                self._installed_items = []
                self._update_inst_count()
                return
            
            server_path = Path(server_path_str)
            
            # Use utility function
            self._installed_items = scan_installed_mods(server_path)

            name_manager = None
            try:
                name_manager = ModNameManager(server_path)
            except Exception:
                name_manager = None
            
            # Build workshop dates map for comparison (to highlight outdated mods)
            workshop_dates = {}
            for item in self._workshop_items:
                if len(item) >= 6:
                    mod_name = item[1].lower()
                    workshop_dates[mod_name] = item[5]  # install_date
            
            # Populate table
            installed_data = []
            for mod_folder, version, size, has_bikey, mod_bikeys, install_date in self._installed_items:
                original_folder = name_manager.get_original_name(mod_folder) if name_manager else mod_folder
                has_update = False
                if original_folder.lower() in workshop_dates:
                    ws_date = workshop_dates[original_folder.lower()]
                    if ws_date and install_date and ws_date > install_date:
                        has_update = True
                
                bikey_text = self._get_bikey_status_text(has_bikey, mod_bikeys)
                date_format = self.settings.settings.datetime_format
                
                row_data = {
                    "name": original_folder,
                    "version": version or "-",
                    "size": format_file_size(size),
                    "date": format_datetime(install_date, date_format),
                    "bikey": bikey_text,
                    "checked": False,
                    "has_update": has_update,
                    "mod_folder": mod_folder,
                    "install_date": install_date,
                }
                installed_data.append(row_data)
            
            self.installed_table.set_data(installed_data)
            
            self._update_inst_count()
            self._maybe_initialize_mods_txt()
        finally:
            self._populating = False
    
    def _populate_installed_row(self, row: int, mod_folder: str, version: str,
                                size: int, has_bikey: bool, mod_bikeys: list,
                                install_date, workshop_dates: dict, name_manager: ModNameManager | None):
        """Populate a single installed table row."""
        # Check if this mod has an update in workshop (workshop date > server install date)
        original_folder = name_manager.get_original_name(mod_folder) if name_manager else mod_folder
        has_update = False
        workshop_date = workshop_dates.get(original_folder.lower())
        if workshop_date and install_date:
            has_update = workshop_date > install_date
        
        # Checkbox
        check_item = QTableWidgetItem()
        check_item.setFlags(check_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        check_item.setCheckState(Qt.Unchecked)
        check_item.setData(Qt.UserRole, mod_folder)
        self.installed_table.setItem(row, InstalledColumns.CHECK, check_item)
        
        # Name
        name_item = QTableWidgetItem(original_folder)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        if original_folder != mod_folder:
            name_item.setToolTip(f"{original_folder}\n({tr('mods.folder')}: {mod_folder})")
        if has_update:
            name_item.setForeground(QColor("#ff9800"))  # Orange for outdated
            name_item.setToolTip(tr("mods.update_available_tooltip"))
        self.installed_table.setItem(row, InstalledColumns.NAME, name_item)
        
        # Version
        version_item = QTableWidgetItem(version or "-")
        version_item.setFlags(version_item.flags() & ~Qt.ItemIsEditable)
        if has_update:
            version_item.setForeground(QColor("#ff9800"))
        self.installed_table.setItem(row, InstalledColumns.VERSION, version_item)
        
        # Size
        size_item = QTableWidgetItem(format_file_size(size))
        size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
        self.installed_table.setItem(row, InstalledColumns.SIZE, size_item)
        
        # Date
        date_format = self.settings.settings.datetime_format
        date_item = QTableWidgetItem(format_datetime(install_date, date_format))
        date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
        date_item.setData(Qt.UserRole, install_date)
        if has_update:
            date_item.setForeground(QColor("#ff9800"))
        self.installed_table.setItem(row, InstalledColumns.DATE, date_item)
        
        # Bikey status
        bikey_text, bikey_icon, bikey_color = self._get_bikey_status(has_bikey, mod_bikeys)
        bikey_item = QTableWidgetItem(bikey_text)
        bikey_item.setFlags(bikey_item.flags() & ~Qt.ItemIsEditable)
        bikey_item.setForeground(QColor(bikey_color))
        bikey_item.setToolTip("\n".join(mod_bikeys) if mod_bikeys else "No bikey files")
        try:
            bikey_item.setIcon(Icons.get_icon(bikey_icon, size=16))
        except Exception:
            pass
        self.installed_table.setItem(row, InstalledColumns.BIKEY, bikey_item)
        
        # Action buttons container: single widget that expands vertically
        actions_widget = QWidget()
        actions_widget.setObjectName("installed_actions_widget")
        actions_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(4, 0, 4, 0)
        actions_layout.setSpacing(6)
        actions_layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)

        # Add bikeys button (only if mod has bikeys but not installed in keys folder)
        if mod_bikeys and not has_bikey:
            btn_add_bikey = IconButton("key", icon_only=True, size=14)
            btn_add_bikey.setToolTip(tr("mods.add_bikeys"))
            btn_add_bikey.setMinimumSize(20, 20)
            btn_add_bikey.clicked.connect(lambda checked=False, mf=mod_folder: self._add_single_mod_bikeys(mf))
            actions_layout.addWidget(btn_add_bikey)

        # Remove button with theme-aware icon
        btn_remove = IconButton("trash", icon_only=True, size=14)
        btn_remove.setToolTip(tr("common.remove"))
        btn_remove.setMinimumSize(20, 20)
        btn_remove.clicked.connect(lambda checked=False, mf=mod_folder: self._remove_single_mod(mf))
        actions_layout.addWidget(btn_remove)

        # Let layouts compute sizes, then ensure actions_widget/min row height follow
        try:
            actions_widget.adjustSize()
            aw_h = actions_widget.sizeHint().height()
            if aw_h and aw_h > 0:
                actions_widget.setMinimumHeight(aw_h)
                # set row height slightly larger than widget to allow for focus borders
                self.installed_table.setRowHeight(row, max(self.installed_table.rowHeight(row), aw_h + 6))
        except Exception:
            pass

        self.installed_table.setCellWidget(row, InstalledColumns.ACTIONS, actions_widget)
    
    def _get_bikey_status(self, has_bikey: bool, mod_bikeys: list) -> tuple[str, str, str]:
        """Get bikey status text, icon, and color."""
        if not mod_bikeys:
            return "N/A", "info", "#888888"
        if has_bikey:
            return tr('mods.status_installed'), "success", "#4caf50"
        return tr('mods.status_missing_bikey'), "error", "#f44336"
    
    # ========== Count & Filter ==========
    
    def _update_ws_count(self):
        selected = len(self.workshop_table.get_checked_rows())
        self.lbl_ws_count.setText(f"{selected}/{len(self._workshop_items)} {tr('mods.selected')}")
    
    def _update_inst_count(self):
        selected = len(self.installed_table.get_checked_rows())
        self.lbl_inst_count.setText(f"{selected}/{len(self._installed_items)} {tr('mods.selected')}")
        
        # Update copy_all_bikeys button state - enable if any mods missing bikeys
        has_missing_bikeys = any(not item[3] and item[4] for item in self._installed_items)
        self.btn_copy_all_bikeys.setEnabled(has_missing_bikeys)
    
    def _on_workshop_checkbox_toggled(self, row: int, checked: bool):
        if not self._populating:
            self._update_ws_count()
    
    def _on_installed_checkbox_toggled(self, row: int, checked: bool):
        if not self._populating:
            self._update_inst_count()
    
    def _filter_workshop_table(self, text: str):
        search = text.lower().strip()
        for row in range(self.workshop_table.rowCount()):
            row_data = self.workshop_table.get_row_data(row)
            if row_data:
                name = row_data.get("name", "").lower()
                self.workshop_table.setRowHidden(row, search not in name)
    
    def _filter_installed_table(self, text: str):
        search = text.lower().strip()
        for row in range(self.installed_table.rowCount()):
            row_data = self.installed_table.get_row_data(row)
            if row_data:
                name = row_data.get("name", "").lower()
                self.installed_table.setRowHidden(row, search not in name)
    
    # ========== Selection ==========
    
    def _set_all_checked(self, table: ReusableTable, checked: bool, visible_only: bool = True):
        """Set check state for all rows, optionally only visible (not hidden by filter)."""
        self._populating = True
        try:
            for row in range(table.rowCount()):
                if visible_only and table.isRowHidden(row):
                    continue
                table.set_row_checked(row, checked)
        finally:
            self._populating = False
    
    def _select_all_workshop(self):
        # Select only visible (filtered) rows
        self._set_all_checked(self.workshop_table, True, visible_only=True)
        self._update_ws_count()
    
    def _deselect_all_workshop(self):
        # Deselect only visible (filtered) rows
        self._set_all_checked(self.workshop_table, False, visible_only=True)
        self._update_ws_count()
    
    def _select_all_installed(self):
        # Select only visible (filtered) rows
        self._set_all_checked(self.installed_table, True, visible_only=True)
        self._update_inst_count()
    
    def _deselect_all_installed(self):
        # Deselect only visible (filtered) rows
        self._set_all_checked(self.installed_table, False, visible_only=True)
        self._update_inst_count()
    
    def _get_selected_workshop_mods(self) -> list[tuple[str, str]]:
        """Get selected workshop mods as (workshop_id, mod_folder) tuples."""
        checked_rows = self.workshop_table.get_checked_rows()
        return [(row["workshop_id"], row["name"]) for row in checked_rows]
    
    def _get_selected_installed_mods(self) -> list[str]:
        """Get selected installed mods as mod_folder strings."""
        checked_rows = self.installed_table.get_checked_rows()
        return [row["mod_folder"] for row in checked_rows]
    
    # ========== Operations ==========
    
    def _add_selected_mods(self):
        if not self.current_profile:
            return
        
        mods = self._get_selected_workshop_mods()
        if not mods:
            QMessageBox.information(self, tr("common.info"), tr("mods.no_mods_selected"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))

        name_manager = None
        try:
            if server_path.exists():
                name_manager = ModNameManager(server_path)
        except Exception:
            name_manager = None

        new_mods: list[tuple[str, str]] = []
        existing_mods: list[tuple[str, str]] = []
        for wid, mf in mods:
            # Direct match (non-optimized installs)
            if (server_path / mf).exists():
                existing_mods.append((wid, mf))
                continue

            # Optimized installs: look up mapped @mN either by mod_id or by original name
            mapped_folder = None
            if name_manager:
                mapping_key = wid
                if wid == "local":
                    mapping_key = f"local:{str(mf).lower()}"
                mapped_folder = name_manager.get_shortened_name_by_mod_id(mapping_key) or name_manager.find_existing_m_short_for_original(mf)

            if mapped_folder and (server_path / mapped_folder).exists():
                existing_mods.append((wid, mf))
                continue

            new_mods.append((wid, mf))
        
        
        if existing_mods and not new_mods:
            if self.confirm_dialog(f"{len(existing_mods)} mod(s) {tr('mods.already_installed')}.\n{tr('mods.overwrite_existing')}?"):
                self._run_operation("add", existing_mods, copy_bikeys=True)
            return
        
        if existing_mods:
            reply = QMessageBox.question(
                self, tr("mods.confirm"),
                f"{len(new_mods)} new mod(s).\n{len(existing_mods)} already installed.\n\n{tr('mods.overwrite_existing')}?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                new_mods.extend(existing_mods)
        
        self._run_operation("add", new_mods, copy_bikeys=True)
    
    def _remove_selected_mods(self):
        if not self.current_profile:
            return
        
        mods = self._get_selected_installed_mods()
        if not mods:
            QMessageBox.information(self, tr("common.info"), tr("mods.no_mods_selected"))
            return
        
        if self.confirm_dialog(f"{tr('mods.confirm_remove')} {len(mods)} mod(s)?"):
            self._run_operation("remove", mods)
    
    def _remove_single_mod(self, mod_folder: str):
        if self.confirm_dialog(f"{tr('mods.confirm_remove')} {mod_folder}?"):
            self._run_operation("remove", [mod_folder])
    
    def _update_selected_mods(self):
        if not self.current_profile:
            return
        
        mods = self._get_selected_installed_mods()
        if not mods:
            QMessageBox.information(self, tr("common.info"), tr("mods.no_mods_selected"))
            return
        
        workshop_path_str = self.current_profile.get("workshop_path", "")
        if not workshop_path_str:
            QMessageBox.warning(self, tr("common.warning"), tr("mods.no_workshop_path"))
            return
        
        update_mods = []
        not_found = []

        server_path = Path(self.current_profile.get("server_path", ""))
        name_manager = None
        try:
            if server_path.exists():
                name_manager = ModNameManager(server_path)
        except Exception:
            name_manager = None
        
        for mod_folder in mods:
            found = False
            original_folder = name_manager.get_original_name(mod_folder) if name_manager else mod_folder
            for workshop_id, ws_folder, _, _, _ in self._workshop_items:
                if ws_folder.lower() == original_folder.lower():
                    update_mods.append((workshop_id, ws_folder))
                    found = True
                    break
            if not found:
                not_found.append(original_folder)
        
        if not_found:
            QMessageBox.warning(self, tr("common.warning"),
                f"{tr('mods.source_not_found')}:\n" + "\n".join(not_found))
        
        if update_mods:
            self._run_operation("update", update_mods)

    def _optimize_installed_mods(self):
        """Optimize already-installed mod folder names into @mN scheme."""
        if not self.current_profile:
            return

        server_path_str = self.current_profile.get("server_path", "")
        if not server_path_str:
            return

        if not self.confirm_dialog(tr("mods.optimize_installed_confirm")):
            return

        # Worker scans server folder; no explicit mods list needed.
        self._run_operation("optimize_installed", [], copy_bikeys=False)
    
    def _run_operation(self, operation: str, mods: list, copy_bikeys: bool = None):
        if self.worker and self.worker.isRunning():
            return
        
        if copy_bikeys is None:
            copy_bikeys = self.settings.settings.auto_copy_bikeys
        
        # Create and show progress dialog
        self.progress_dialog = QProgressDialog(
            f"{operation.capitalize()}ing mods...",
            tr("common.cancel"),
            0, 100,
            self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setMinimumWidth(500)
        self.progress_dialog.setMinimumHeight(150)
        self.progress_dialog.setStyleSheet("QLabel { padding: 10px; font-size: 12px; }")
        self.progress_dialog.canceled.connect(self._on_progress_cancel)
        self.progress_dialog.show()

        self._current_operation = operation
        
        self.btn_add_selected.setEnabled(False)
        self.btn_remove_selected.setEnabled(False)
        
        # Check if name optimization is enabled
        optimize_names = False
        if operation in ("add", "update") and hasattr(self, 'chk_optimize_names'):
            optimize_names = self.chk_optimize_names.isChecked()
        if operation == "optimize_installed":
            optimize_names = True
        
        self.worker = ModWorker(
            operation=operation,
            server_path=self.current_profile.get("server_path", ""),
            workshop_path=self.current_profile.get("workshop_path", ""),
            mods=mods,
            copy_bikeys=copy_bikeys,
            optimize_names=optimize_names
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_operation_finished)
        self.worker.start()

    def _show_friendly_result_dialog(self, operation: str | None, results: dict):
        success = results.get("success") or []
        failed = results.get("failed") or []
        bikeys_copied = results.get("bikeys_copied") or []
        bikeys_removed = results.get("bikeys_removed") or []

        success_count = len(success)
        failed_count = len(failed)
        bikeys_copied_count = len(bikeys_copied)
        bikeys_removed_count = len(bikeys_removed)

        title = tr("common.success")
        dialog_fn = QMessageBox.information
        if failed_count:
            if success_count or bikeys_copied_count or bikeys_removed_count:
                title = tr("common.warning")
                dialog_fn = QMessageBox.warning
            else:
                title = tr("common.error")
                dialog_fn = QMessageBox.critical

        op_key_map = {
            "add": "mods.result_add_success",
            "remove": "mods.result_remove_success",
            "update": "mods.result_update_success",
        }

        lines: list[str] = [tr("mods.result_header")]

        if success_count and operation in op_key_map:
            lines.append(tr(op_key_map[operation], count=success_count))
        elif success_count:
            lines.append(f"{tr('common.success')}: {success_count}")

        if bikeys_copied_count:
            lines.append(tr("mods.result_bikeys_copied", count=bikeys_copied_count))
        if bikeys_removed_count:
            lines.append(tr("mods.result_bikeys_removed", count=bikeys_removed_count))

        if failed_count:
            max_examples = min(3, failed_count)
            lines.append("")
            lines.append(tr("mods.result_failed", count=failed_count))
            lines.append(tr("mods.result_failed_examples", max=max_examples))
            for mod, reason in failed[:max_examples]:
                lines.append(f"- {mod}: {reason}")

        if operation in ("add", "update") and (success_count or bikeys_copied_count):
            lines.append("")
            lines.append(tr("mods.result_tip_launcher"))

        dialog_fn(self, title, "\n".join(lines))
    
    def _on_progress(self, message: str, current: int, total: int):
        if self.progress_dialog:
            if total > 0:
                percentage = int((current / total) * 100)
                self.progress_dialog.setValue(percentage)
            else:
                self.progress_dialog.setValue(0)
            self.progress_dialog.setLabelText(message)
    
    def _on_progress_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
    
    def _on_operation_finished(self, results: dict):
        if self.progress_dialog:
            self.progress_dialog.setValue(100)
            self.progress_dialog.close()
            self.progress_dialog = None
        self.btn_add_selected.setEnabled(True)
        self.btn_remove_selected.setEnabled(True)
        operation = self._current_operation
        self._current_operation = None
        self.worker = None

        if results and any(results.get(k) for k in ("success", "failed", "bikeys_copied", "bikeys_removed")):
            self._show_friendly_result_dialog(operation, results)
        self._refresh_all()
    
    def _copy_all_bikeys(self):
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            return
        
        try:
            checker = ModIntegrityChecker(str(server_path))
            count, bikeys = checker.extract_all_bikeys()

            if count <= 0:
                QMessageBox.information(self, tr("common.info"), tr("mods.no_bikeys_to_copy"))
                return

            msg_lines = [
                tr("mods.result_header"),
                tr("mods.result_bikeys_copied", count=count),
                "",
            ]
            if bikeys:
                msg_lines.append("\n".join(bikeys[:10]))
                if len(bikeys) > 10:
                    msg_lines.append(f"...{len(bikeys) - 10} {tr('common.more')}")
            QMessageBox.information(self, tr("common.success"), "\n".join(msg_lines))
            self._refresh_all()
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _add_single_mod_bikeys(self, mod_folder: str):
        """Add bikeys for a single mod."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            return
        
        mod_path = server_path / mod_folder
        keys_folder = server_path / "keys"
        
        if not mod_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("mods.mod_folder_not_found", mod=mod_folder))
            return
        
        try:
            keys_folder.mkdir(parents=True, exist_ok=True)
            
            # Find bikey files similar to ModWorker
            search_paths = [
                mod_path / "keys", mod_path / "Keys",
                mod_path / "key", mod_path / "Key", mod_path
            ]
            searched = set()
            bikey_files = []
            
            for path in search_paths:
                if path.exists() and path not in searched:
                    searched.add(path)
                    bikey_files.extend(path.glob("*.bikey"))
            
            if not bikey_files:
                bikey_files = list(mod_path.rglob("*.bikey"))
            
            copied = 0
            
            for bikey_file in bikey_files:
                dest = keys_folder / bikey_file.name
                if not dest.exists():
                    import shutil
                    shutil.copy2(bikey_file, dest)
                    copied += 1
            
            if copied > 0:
                QMessageBox.information(
                    self,
                    tr("common.success"),
                    tr("mods.result_bikeys_copied_for_mod", count=copied, mod=mod_folder)
                )
                self._refresh_all()
            else:
                QMessageBox.information(self, tr("common.info"), tr("mods.no_bikeys_to_copy"))
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    # ========== Utilities ==========
    
    def _get_installed_mod_folders(self) -> list[str]:
        return [item[0] for item in self._installed_items]
    
    def _maybe_initialize_mods_txt(self):
        """Initialize mods.txt if missing or empty."""
        if not self.current_profile:
            return
        
        server_path_str = self.current_profile.get("server_path", "")
        if not server_path_str:
            return
        
        server_path = Path(server_path_str)
        mods_file = server_path / "mods.txt"
        
        try:
            if mods_file.exists():
                if mods_file.read_text(encoding="utf-8", errors="replace").strip():
                    return
        except Exception:
            return
        
        mods = self._get_installed_mod_folders()
        mods_text = format_mods_txt(mods)
        
        try:
            mods_file.write_text(mods_text, encoding="utf-8")
            self.mods_list_updated.emit(mods_text)
        except Exception:
            pass
    
    def update_texts(self):
        """Update UI texts for language change."""
        super().update_texts()
        self.btn_refresh.setText(tr("common.refresh"))
        self.btn_copy_all_bikeys.setText(tr("mods.copy_all_bikeys"))
        self.lbl_no_profile.setText(tr("mods.select_profile_first"))
        self.workshop_box.setTitle(tr("mods.workshop_source"))
        self.installed_box.setTitle(tr("mods.server_installed"))
        self.btn_add_selected.setText(tr("mods.add_to_server"))
        self.btn_remove_selected.setText(tr("mods.remove_from_server"))
        self.btn_select_all_ws.setText(tr("common.select_all"))
        self.btn_deselect_all_ws.setText(tr("common.deselect_all"))
        self.btn_select_all_inst.setText(tr("common.select_all"))
        self.btn_deselect_all_inst.setText(tr("common.deselect_all"))
        self.search_workshop.setPlaceholderText(f"{tr('common.search')}...")
        self.search_installed.setPlaceholderText(f"{tr('common.search')}...")
        
        self.workshop_table.setHorizontalHeaderLabels([
            "", tr("mods.mod_name"), tr("mods.mod_version"),
            tr("mods.mod_size"), tr("mods.mod_date"), tr("mods.mod_status")
        ])
        self.installed_table.setHorizontalHeaderLabels([
            "", tr("mods.mod_name"), tr("mods.mod_version"),
            tr("mods.mod_size"), tr("mods.mod_date"), tr("mods.bikey_status"), tr("common.actions")
        ])
