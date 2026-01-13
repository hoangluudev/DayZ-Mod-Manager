"""
Mods Tab - Mod Management with Add/Remove/Update functionality
"""

import re
import shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QGroupBox, QCheckBox, QFileDialog, QFrame,
    QSplitter, QTextEdit, QDialog, QDialogButtonBox, QListWidget,
    QListWidgetItem, QTabWidget, QMenu, QAbstractItemView, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor, QAction

from src.core.mod_integrity import ModIntegrityChecker
from src.core.profile_manager import ProfileManager
from src.core.settings_manager import SettingsManager
from src.models.mod_models import ModStatus, IntegrityReport
from src.utils.locale_manager import tr


def format_file_size(size_bytes: int | float) -> str:
    """Format file size with appropriate unit (KB/MB/GB)."""
    if not size_bytes or size_bytes <= 0:
        return "-"
    
    kb = size_bytes / 1024
    mb = size_bytes / (1024 * 1024)
    gb = size_bytes / (1024 * 1024 * 1024)
    
    if gb >= 1:
        return f"{gb:.1f} GB"
    elif mb >= 1:
        return f"{mb:.1f} MB"
    else:
        return f"{kb:.1f} KB"


class ModWorker(QThread):
    """Background worker for mod operations (add/remove/update)."""
    
    progress = Signal(str, int, int)  # message, current, total
    finished = Signal(object)  # dict with results
    error = Signal(str)
    
    def __init__(
        self,
        operation: str,  # "add", "remove", "update"
        server_path: str,
        workshop_path: str = None,
        mods: list = None,  # For add/update: [(workshop_id, mod_folder), ...], For remove: [mod_folder, ...]
        copy_bikeys: bool = True,
    ):
        super().__init__()
        self.operation = operation
        self.server_path = Path(server_path)
        self.workshop_path = Path(workshop_path) if workshop_path else None
        self.mods = mods or []
        self.copy_bikeys = copy_bikeys
    
    def run(self):
        results = {
            "success": [],
            "failed": [],
            "bikeys_copied": [],
            "bikeys_removed": []
        }
        
        total = len(self.mods)
        keys_folder = self.server_path / "keys"
        
        if self.operation == "add":
            keys_folder.mkdir(parents=True, exist_ok=True)
            self._perform_add(results, total, keys_folder)
        elif self.operation == "remove":
            self._perform_remove(results, total, keys_folder)
        elif self.operation == "update":
            keys_folder.mkdir(parents=True, exist_ok=True)
            self._perform_update(results, total, keys_folder)
        
        self.finished.emit(results)
    
    def _perform_add(self, results: dict, total: int, keys_folder: Path):
        """Add mods from workshop to server."""
        for idx, (workshop_id, mod_folder) in enumerate(self.mods):
            try:
                self.progress.emit(f"Adding: {mod_folder}", idx + 1, total)
                
                # Determine source path
                if workshop_id == "local":
                    source_path = self.workshop_path / mod_folder
                else:
                    source_path = self.workshop_path / workshop_id / mod_folder
                
                if not source_path.exists():
                    results["failed"].append((mod_folder, "Source not found"))
                    continue
                
                dest_path = self.server_path / mod_folder
                
                # Remove existing if present
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                
                # Copy mod folder
                shutil.copytree(source_path, dest_path)
                results["success"].append(mod_folder)
                
                # Copy bikeys
                if self.copy_bikeys:
                    self._copy_mod_bikeys(dest_path, keys_folder, results)
                    
            except Exception as e:
                results["failed"].append((mod_folder, str(e)))
    
    def _perform_remove(self, results: dict, total: int, keys_folder: Path):
        """Remove mods from server."""
        for idx, mod_folder in enumerate(self.mods):
            try:
                self.progress.emit(f"Removing: {mod_folder}", idx + 1, total)
                
                mod_path = self.server_path / mod_folder
                
                if not mod_path.exists():
                    results["failed"].append((mod_folder, "Not found"))
                    continue
                
                # Find and remove associated bikeys first
                bikeys_to_remove = self._find_mod_bikeys(mod_path)
                
                # Remove mod folder
                shutil.rmtree(mod_path)
                results["success"].append(mod_folder)
                
                # Remove bikeys (if not shared by other mods)
                if keys_folder.exists():
                    for bikey_name in bikeys_to_remove:
                        bikey_path = keys_folder / bikey_name
                        if bikey_path.exists():
                            try:
                                bikey_path.unlink()
                                results["bikeys_removed"].append(bikey_name)
                            except Exception:
                                pass
                    
            except Exception as e:
                results["failed"].append((mod_folder, str(e)))
    
    def _perform_update(self, results: dict, total: int, keys_folder: Path):
        """Update mods (remove old + add new)."""
        for idx, (workshop_id, mod_folder) in enumerate(self.mods):
            try:
                self.progress.emit(f"Updating: {mod_folder}", idx + 1, total)
                
                # Determine source path
                if workshop_id == "local":
                    source_path = self.workshop_path / mod_folder
                else:
                    source_path = self.workshop_path / workshop_id / mod_folder
                
                if not source_path.exists():
                    results["failed"].append((mod_folder, "Source not found"))
                    continue
                
                dest_path = self.server_path / mod_folder
                
                # Remove old version
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                
                # Copy new version
                shutil.copytree(source_path, dest_path)
                results["success"].append(mod_folder)
                
                # Update bikeys
                if self.copy_bikeys:
                    self._copy_mod_bikeys(dest_path, keys_folder, results)
                    
            except Exception as e:
                results["failed"].append((mod_folder, str(e)))
    
    def _find_mod_bikeys(self, mod_path: Path) -> list[str]:
        """Find bikey files in a mod folder."""
        bikeys = []
        search_paths = [
            mod_path / "keys", mod_path / "Keys",
            mod_path / "key", mod_path / "Key", mod_path
        ]
        searched = set()
        for path in search_paths:
            if path.exists() and path not in searched:
                searched.add(path)
                bikeys.extend(f.name for f in path.glob("*.bikey"))
        if not bikeys:
            bikeys = [f.name for f in mod_path.rglob("*.bikey")]
        return bikeys
    
    def _copy_mod_bikeys(self, mod_path: Path, keys_folder: Path, results: dict):
        """Copy bikey files from mod to server keys folder."""
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
        
        for bikey_file in bikey_files:
            dest = keys_folder / bikey_file.name
            try:
                shutil.copy2(bikey_file, dest)
                if bikey_file.name not in results["bikeys_copied"]:
                    results["bikeys_copied"].append(bikey_file.name)
            except Exception:
                pass


class ModsTab(QWidget):
    """Tab for managing server mods."""

    # Emitted after mod changes when we refresh the installed mods list.
    mods_list_updated = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self.profile_manager = ProfileManager()
        self.settings = SettingsManager()
        self.worker = None
        self._workshop_items: list[tuple[str, str, str, int, bool]] = []  # [(workshop_id, mod_folder, version, size, is_installed)]
        self._installed_items: list[tuple[str, str, int]] = []  # [(mod_folder, version, size)]
        self._populating = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        
        self.lbl_title = QLabel(f"<h2>{tr('mods.title')}</h2>")
        header.addWidget(self.lbl_title)
        header.addStretch()
        
        self.btn_refresh = QPushButton(f"🔄 {tr('common.refresh')}")
        self.btn_refresh.clicked.connect(self._refresh_all)
        header.addWidget(self.btn_refresh)
        
        self.btn_copy_all_bikeys = QPushButton(f"🔑 {tr('mods.copy_all_bikeys')}")
        self.btn_copy_all_bikeys.clicked.connect(self._copy_all_bikeys)
        header.addWidget(self.btn_copy_all_bikeys)
        
        layout.addLayout(header)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.lbl_progress = QLabel()
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)
        
        # No profile selected message
        self.lbl_no_profile = QLabel(tr("mods.select_profile_first"))
        self.lbl_no_profile.setAlignment(Qt.AlignCenter)
        self.lbl_no_profile.setStyleSheet("color: gray; padding: 30px; font-size: 14px;")
        layout.addWidget(self.lbl_no_profile)
        
        # Main content with splitter (2 panels side by side)
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)

        # Left Panel: Workshop Source Mods
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)
        
        self.workshop_box = QGroupBox(f"📦 {tr('mods.workshop_source')}")
        workshop_layout = QVBoxLayout(self.workshop_box)
        
        # Workshop path label
        self.lbl_workshop_path = QLabel()
        self.lbl_workshop_path.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_workshop_path.setWordWrap(True)
        workshop_layout.addWidget(self.lbl_workshop_path)
        
        # Search bar for workshop
        search_ws_layout = QHBoxLayout()
        self.search_workshop = QLineEdit()
        self.search_workshop.setPlaceholderText(f"🔍 {tr('common.search')}...")
        self.search_workshop.textChanged.connect(self._filter_workshop_table)
        self.search_workshop.setClearButtonEnabled(True)
        search_ws_layout.addWidget(self.search_workshop)
        workshop_layout.addLayout(search_ws_layout)
        
        # Workshop actions
        ws_actions = QHBoxLayout()
        self.btn_add_selected = QPushButton(f"➕ {tr('mods.add_to_server')}")
        self.btn_add_selected.clicked.connect(self._add_selected_mods)
        ws_actions.addWidget(self.btn_add_selected)
        
        self.btn_select_all_ws = QPushButton(tr("common.select_all"))
        self.btn_select_all_ws.clicked.connect(self._select_all_workshop)
        ws_actions.addWidget(self.btn_select_all_ws)
        
        self.btn_deselect_all_ws = QPushButton(tr("common.deselect_all"))
        self.btn_deselect_all_ws.clicked.connect(self._deselect_all_workshop)
        ws_actions.addWidget(self.btn_deselect_all_ws)
        
        ws_actions.addStretch()
        self.lbl_ws_count = QLabel("0 mods")
        self.lbl_ws_count.setStyleSheet("color: #0078d4;")
        ws_actions.addWidget(self.lbl_ws_count)
        workshop_layout.addLayout(ws_actions)
        
        # Workshop table
        self.workshop_table = QTableWidget()
        self.workshop_table.setColumnCount(5)
        self.workshop_table.setHorizontalHeaderLabels([
            "", tr("mods.mod_name"), tr("mods.mod_version"), tr("mods.mod_size"), tr("mods.mod_status")
        ])
        self.workshop_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.workshop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.workshop_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.workshop_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.workshop_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.workshop_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.workshop_table.setAlternatingRowColors(True)
        self.workshop_table.itemChanged.connect(self._on_workshop_item_changed)
        workshop_layout.addWidget(self.workshop_table)
        
        left_layout.addWidget(self.workshop_box)
        
        # Right Panel: Server Installed Mods
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        
        self.installed_box = QGroupBox(f"🖥️ {tr('mods.server_installed')}")
        installed_layout = QVBoxLayout(self.installed_box)
        
        # Server path label
        self.lbl_server_path = QLabel()
        self.lbl_server_path.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_server_path.setWordWrap(True)
        installed_layout.addWidget(self.lbl_server_path)
        
        # Search bar for installed
        search_inst_layout = QHBoxLayout()
        self.search_installed = QLineEdit()
        self.search_installed.setPlaceholderText(f"🔍 {tr('common.search')}...")
        self.search_installed.textChanged.connect(self._filter_installed_table)
        self.search_installed.setClearButtonEnabled(True)
        search_inst_layout.addWidget(self.search_installed)
        installed_layout.addLayout(search_inst_layout)
        
        # Installed actions
        inst_actions = QHBoxLayout()
        self.btn_remove_selected = QPushButton(f"➖ {tr('mods.remove_from_server')}")
        self.btn_remove_selected.clicked.connect(self._remove_selected_mods)
        self.btn_remove_selected.setStyleSheet("color: #f44336;")
        inst_actions.addWidget(self.btn_remove_selected)
        
        self.btn_update_selected = QPushButton(f"🔄 {tr('mods.update_selected')}")
        self.btn_update_selected.clicked.connect(self._update_selected_mods)
        inst_actions.addWidget(self.btn_update_selected)
        
        self.btn_select_all_inst = QPushButton(tr("common.select_all"))
        self.btn_select_all_inst.clicked.connect(self._select_all_installed)
        inst_actions.addWidget(self.btn_select_all_inst)
        
        self.btn_deselect_all_inst = QPushButton(tr("common.deselect_all"))
        self.btn_deselect_all_inst.clicked.connect(self._deselect_all_installed)
        inst_actions.addWidget(self.btn_deselect_all_inst)
        
        inst_actions.addStretch()
        self.lbl_inst_count = QLabel("0 mods")
        self.lbl_inst_count.setStyleSheet("color: #4caf50;")
        inst_actions.addWidget(self.lbl_inst_count)
        installed_layout.addLayout(inst_actions)
        
        # Installed table with bikey status column
        self.installed_table = QTableWidget()
        self.installed_table.setColumnCount(6)
        self.installed_table.setHorizontalHeaderLabels([
            "", tr("mods.mod_name"), tr("mods.mod_version"), tr("mods.mod_size"), 
            tr("mods.bikey_status"), tr("common.actions")
        ])
        self.installed_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.installed_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.installed_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.installed_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.installed_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.installed_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.installed_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.installed_table.setAlternatingRowColors(True)
        self.installed_table.itemChanged.connect(self._on_installed_item_changed)
        installed_layout.addWidget(self.installed_table)
        
        right_layout.addWidget(self.installed_box)
        
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([500, 500])
        
        content_layout.addWidget(self.splitter)
        
        layout.addWidget(self.content_widget)
        self.content_widget.setVisible(False)
    
    def showEvent(self, event):
        """Called when tab becomes visible - auto-load mods."""
        super().showEvent(event)
        if self.current_profile:
            self._refresh_all()
    
    def set_profile(self, profile_data: dict):
        """Set the current profile for mod management."""
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(250)

        self.current_profile = profile_data
        self.lbl_no_profile.setVisible(False)
        self.content_widget.setVisible(True)
        
        # Update path labels
        workshop_path = profile_data.get("workshop_path", "")
        server_path = profile_data.get("server_path", "")
        self.lbl_workshop_path.setText(f"📁 {workshop_path}" if workshop_path else "")
        self.lbl_server_path.setText(f"📁 {server_path}" if server_path else "")
        
        # Load both lists
        self._refresh_all()
    
    def _refresh_all(self):
        """Refresh both workshop and installed mods lists."""
        if not self.current_profile:
            return
        self._load_workshop_mods()
        self._load_installed_mods()
    
    def _load_workshop_mods(self):
        """Load mods from workshop source folder."""
        self._workshop_items = []
        self._populating = True
        
        try:
            self.workshop_table.setRowCount(0)
            
            workshop_path_str = self.current_profile.get("workshop_path", "")
            server_path_str = self.current_profile.get("server_path", "")
            
            if not workshop_path_str:
                self._update_ws_count()
                return
            
            workshop_path = Path(workshop_path_str)
            server_path = Path(server_path_str) if server_path_str else None
            
            if not workshop_path.exists():
                self._update_ws_count()
                return
            
            # Get installed mods for status
            installed_mods = {}
            if server_path and server_path.exists():
                for item in server_path.iterdir():
                    if item.is_dir() and item.name.startswith("@"):
                        version = self._get_mod_version(item)
                        installed_mods[item.name.lower()] = version
            
            # Scan workshop structure
            found_any = False
            for id_dir in sorted([p for p in workshop_path.iterdir() if p.is_dir()]):
                workshop_id = id_dir.name
                mod_dirs = [p for p in id_dir.iterdir() if p.is_dir() and p.name.startswith("@")]
                if not mod_dirs:
                    continue
                found_any = True
                for mod_dir in sorted(mod_dirs):
                    version = self._get_mod_version(mod_dir)
                    size = self._get_folder_size(mod_dir)
                    is_installed = mod_dir.name.lower() in installed_mods
                    self._workshop_items.append((workshop_id, mod_dir.name, version, size, is_installed))
            
            # Fallback: direct @mod folders
            if not found_any:
                for mod_dir in sorted([p for p in workshop_path.iterdir() if p.is_dir() and p.name.startswith("@")]):
                    version = self._get_mod_version(mod_dir)
                    size = self._get_folder_size(mod_dir)
                    is_installed = mod_dir.name.lower() in installed_mods
                    self._workshop_items.append(("local", mod_dir.name, version, size, is_installed))
            
            # Populate table
            self.workshop_table.setRowCount(len(self._workshop_items))
            for row, (workshop_id, mod_folder, version, size, is_installed) in enumerate(self._workshop_items):
                # Checkbox
                check_item = QTableWidgetItem()
                check_item.setFlags(check_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                check_item.setCheckState(Qt.Unchecked)
                check_item.setData(Qt.UserRole, (workshop_id, mod_folder))
                self.workshop_table.setItem(row, 0, check_item)
                
                # Name
                name_item = QTableWidgetItem(mod_folder)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.workshop_table.setItem(row, 1, name_item)
                
                # Version
                version_item = QTableWidgetItem(version or "-")
                version_item.setFlags(version_item.flags() & ~Qt.ItemIsEditable)
                self.workshop_table.setItem(row, 2, version_item)
                
                # Size
                size_item = QTableWidgetItem(format_file_size(size))
                size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
                self.workshop_table.setItem(row, 3, size_item)
                
                # Status
                if is_installed:
                    # Check if versions differ
                    installed_ver = installed_mods.get(mod_folder.lower())
                    if version and installed_ver and version != installed_ver:
                        status_text = f"🔄 {tr('mods.status_outdated')}"
                        status_color = "#2196f3"
                    else:
                        status_text = f"✅ {tr('mods.status_installed')}"
                        status_color = "#4caf50"
                else:
                    status_text = f"⬜ {tr('mods.status_not_installed')}"
                    status_color = "#888"
                
                status_item = QTableWidgetItem(status_text)
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                status_item.setForeground(QColor(status_color))
                self.workshop_table.setItem(row, 4, status_item)
            
            self._update_ws_count()
        finally:
            self._populating = False
    
    def _load_installed_mods(self):
        """Load mods installed on server."""
        self._installed_items = []
        self._populating = True
        
        try:
            self.installed_table.setRowCount(0)
            
            server_path_str = self.current_profile.get("server_path", "")
            if not server_path_str:
                self._update_inst_count()
                return
            
            server_path = Path(server_path_str)
            if not server_path.exists():
                self._update_inst_count()
                return
            
            # Scan server folder for @mods
            keys_folder = server_path / "keys"
            installed_bikeys = set()
            if keys_folder.exists():
                installed_bikeys = {f.name.lower() for f in keys_folder.glob("*.bikey")}
            
            for mod_dir in sorted([p for p in server_path.iterdir() if p.is_dir() and p.name.startswith("@")]):
                version = self._get_mod_version(mod_dir)
                size = self._get_folder_size(mod_dir)
                # Check bikey status
                mod_bikeys = self._find_mod_bikeys_in_folder(mod_dir)
                has_bikey = any(bk.lower() in installed_bikeys for bk in mod_bikeys) if mod_bikeys else False
                self._installed_items.append((mod_dir.name, version, size, has_bikey, mod_bikeys))
            
            # Populate table
            self.installed_table.setRowCount(len(self._installed_items))
            for row, (mod_folder, version, size, has_bikey, mod_bikeys) in enumerate(self._installed_items):
                # Checkbox
                check_item = QTableWidgetItem()
                check_item.setFlags(check_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                check_item.setCheckState(Qt.Unchecked)
                check_item.setData(Qt.UserRole, mod_folder)
                self.installed_table.setItem(row, 0, check_item)
                
                # Name
                name_item = QTableWidgetItem(mod_folder)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.installed_table.setItem(row, 1, name_item)
                
                # Version
                version_item = QTableWidgetItem(version or "-")
                version_item.setFlags(version_item.flags() & ~Qt.ItemIsEditable)
                self.installed_table.setItem(row, 2, version_item)
                
                # Size
                size_item = QTableWidgetItem(format_file_size(size))
                size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
                self.installed_table.setItem(row, 3, size_item)
                
                # Bikey status
                if not mod_bikeys:
                    bikey_text = "⚪ N/A"
                    bikey_color = "#888888"
                elif has_bikey:
                    bikey_text = f"✅ {tr('mods.status_installed')}"
                    bikey_color = "#4caf50"
                else:
                    bikey_text = f"❌ {tr('mods.status_missing_bikey')}"
                    bikey_color = "#f44336"
                
                bikey_item = QTableWidgetItem(bikey_text)
                bikey_item.setFlags(bikey_item.flags() & ~Qt.ItemIsEditable)
                bikey_item.setForeground(QColor(bikey_color))
                bikey_item.setToolTip("\n".join(mod_bikeys) if mod_bikeys else "No bikey files in mod")
                self.installed_table.setItem(row, 4, bikey_item)
                
                # Remove button
                btn_remove = QPushButton(f"🗑️ {tr('common.remove')}")
                btn_remove.setStyleSheet("color: #f44336; font-size: 11px;")
                btn_remove.clicked.connect(lambda checked, mf=mod_folder: self._remove_single_mod(mf))
                self.installed_table.setCellWidget(row, 5, btn_remove)
            
            self._update_inst_count()
            
            # Sync mods.txt
            self._sync_mods_txt_with_installed()
        finally:
            self._populating = False
    
    def _get_mod_version(self, mod_path: Path) -> str | None:
        """Extract version from mod's meta.cpp or mod.cpp."""
        try:
            for filename in ["meta.cpp", "mod.cpp"]:
                meta_file = mod_path / filename
                if meta_file.exists():
                    content = meta_file.read_text(encoding="utf-8", errors="ignore")
                    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
                    if match:
                        return match.group(1)
        except Exception:
            pass
        return None
    
    def _get_folder_size(self, folder_path: Path) -> int:
        """Calculate total size of a folder."""
        total = 0
        try:
            for f in folder_path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except Exception:
            pass
        return total
    
    def _update_ws_count(self):
        selected = sum(1 for row in range(self.workshop_table.rowCount())
                      if self.workshop_table.item(row, 0) and 
                      self.workshop_table.item(row, 0).checkState() == Qt.Checked)
        total = len(self._workshop_items)
        self.lbl_ws_count.setText(f"{selected}/{total} {tr('mods.selected')}")
    
    def _update_inst_count(self):
        selected = sum(1 for row in range(self.installed_table.rowCount())
                      if self.installed_table.item(row, 0) and 
                      self.installed_table.item(row, 0).checkState() == Qt.Checked)
        total = len(self._installed_items)
        self.lbl_inst_count.setText(f"{selected}/{total} {tr('mods.installed')}")
    
    def _on_workshop_item_changed(self, item):
        if self._populating or item.column() != 0:
            return
        self._update_ws_count()
    
    def _on_installed_item_changed(self, item):
        if self._populating or item.column() != 0:
            return
        self._update_inst_count()
    
    def _select_all_workshop(self):
        self._populating = True
        try:
            for row in range(self.workshop_table.rowCount()):
                item = self.workshop_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Checked)
        finally:
            self._populating = False
        self._update_ws_count()
    
    def _deselect_all_workshop(self):
        self._populating = True
        try:
            for row in range(self.workshop_table.rowCount()):
                item = self.workshop_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
        finally:
            self._populating = False
        self._update_ws_count()
    
    def _select_all_installed(self):
        """Select all visible installed mods."""
        self._populating = True
        try:
            for row in range(self.installed_table.rowCount()):
                if not self.installed_table.isRowHidden(row):
                    item = self.installed_table.item(row, 0)
                    if item:
                        item.setCheckState(Qt.Checked)
        finally:
            self._populating = False
        self._update_inst_count()
    
    def _deselect_all_installed(self):
        """Deselect all installed mods."""
        self._populating = True
        try:
            for row in range(self.installed_table.rowCount()):
                item = self.installed_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
        finally:
            self._populating = False
        self._update_inst_count()
    
    def _filter_workshop_table(self, text: str):
        """Filter workshop table by search text."""
        search = text.lower().strip()
        for row in range(self.workshop_table.rowCount()):
            name_item = self.workshop_table.item(row, 1)
            if name_item:
                mod_name = name_item.text().lower()
                self.workshop_table.setRowHidden(row, search not in mod_name)
    
    def _filter_installed_table(self, text: str):
        """Filter installed table by search text."""
        search = text.lower().strip()
        for row in range(self.installed_table.rowCount()):
            name_item = self.installed_table.item(row, 1)
            if name_item:
                mod_name = name_item.text().lower()
                self.installed_table.setRowHidden(row, search not in mod_name)
    
    def _find_mod_bikeys_in_folder(self, mod_path: Path) -> list[str]:
        """Find bikey files inside mod folder (without copying)."""
        bikeys = []
        search_paths = [
            mod_path / "keys", mod_path / "Keys",
            mod_path / "key", mod_path / "Key", mod_path
        ]
        searched = set()
        for path in search_paths:
            if path.exists() and path not in searched:
                searched.add(path)
                bikeys.extend(f.name for f in path.glob("*.bikey"))
        if not bikeys:
            bikeys = [f.name for f in mod_path.rglob("*.bikey")]
        return bikeys
    
    def _get_selected_workshop_mods(self) -> list[tuple[str, str]]:
        """Get list of selected workshop mods [(workshop_id, mod_folder), ...]"""
        mods = []
        for row in range(self.workshop_table.rowCount()):
            item = self.workshop_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if data:
                    mods.append(data)
        return mods
    
    def _get_selected_installed_mods(self) -> list[str]:
        """Get list of selected installed mod folders."""
        mods = []
        for row in range(self.installed_table.rowCount()):
            item = self.installed_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if data:
                    mods.append(data)
        return mods
    
    def _add_selected_mods(self):
        """Add selected workshop mods to server."""
        if not self.current_profile:
            return
        
        mods = self._get_selected_workshop_mods()
        if not mods:
            QMessageBox.information(self, tr("common.info"), tr("mods.no_mods_selected"))
            return
        
        # Check which are already installed
        server_path = Path(self.current_profile.get("server_path", ""))
        new_mods = []
        existing_mods = []
        
        for workshop_id, mod_folder in mods:
            if (server_path / mod_folder).exists():
                existing_mods.append((workshop_id, mod_folder))
            else:
                new_mods.append((workshop_id, mod_folder))
        
        if existing_mods and not new_mods:
            reply = QMessageBox.question(
                self, tr("mods.confirm"),
                f"{len(existing_mods)} mod(s) {tr('mods.already_installed')}.\n{tr('mods.overwrite_existing')}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._run_operation("update", existing_mods)
            return
        
        if existing_mods:
            reply = QMessageBox.question(
                self, tr("mods.confirm"),
                f"{len(new_mods)} new mod(s) to add.\n{len(existing_mods)} already installed.\n\n{tr('mods.overwrite_existing')}?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            elif reply == QMessageBox.Yes:
                new_mods.extend(existing_mods)
        
        self._run_operation("add", new_mods)
    
    def _remove_selected_mods(self):
        """Remove selected installed mods from server."""
        if not self.current_profile:
            return
        
        mods = self._get_selected_installed_mods()
        if not mods:
            QMessageBox.information(self, tr("common.info"), tr("mods.no_mods_selected"))
            return
        
        reply = QMessageBox.question(
            self, tr("mods.confirm"),
            f"{tr('mods.confirm_remove')} {len(mods)} mod(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._run_operation("remove", mods)
    
    def _remove_single_mod(self, mod_folder: str):
        """Remove a single mod."""
        reply = QMessageBox.question(
            self, tr("mods.confirm"),
            f"{tr('mods.confirm_remove')} {mod_folder}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._run_operation("remove", [mod_folder])
    
    def _update_selected_mods(self):
        """Update selected installed mods from workshop."""
        if not self.current_profile:
            return
        
        mods = self._get_selected_installed_mods()
        if not mods:
            QMessageBox.information(self, tr("common.info"), tr("mods.no_mods_selected"))
            return
        
        # Find workshop source for each mod
        workshop_path_str = self.current_profile.get("workshop_path", "")
        if not workshop_path_str:
            QMessageBox.warning(self, tr("common.warning"), tr("mods.no_workshop_path"))
            return
        
        # Map installed mods to workshop sources
        update_mods = []
        not_found = []
        
        for mod_folder in mods:
            found = False
            for workshop_id, ws_folder, _, _, _ in self._workshop_items:
                if ws_folder.lower() == mod_folder.lower():
                    update_mods.append((workshop_id, ws_folder))
                    found = True
                    break
            if not found:
                not_found.append(mod_folder)
        
        if not_found:
            QMessageBox.warning(
                self, tr("common.warning"),
                f"{tr('mods.source_not_found')}:\n" + "\n".join(not_found)
            )
        
        if update_mods:
            self._run_operation("update", update_mods)
    
    def _run_operation(self, operation: str, mods: list):
        """Run a mod operation (add/remove/update)."""
        if self.worker and self.worker.isRunning():
            return
        
        server_path = self.current_profile.get("server_path", "")
        workshop_path = self.current_profile.get("workshop_path", "")
        
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText(f"{operation.capitalize()}...")
        
        self.btn_add_selected.setEnabled(False)
        self.btn_remove_selected.setEnabled(False)
        self.btn_update_selected.setEnabled(False)
        
        self.worker = ModWorker(
            operation=operation,
            server_path=server_path,
            workshop_path=workshop_path,
            mods=mods,
            copy_bikeys=self.settings.settings.auto_copy_bikeys
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_operation_finished)
        self.worker.start()
    
    def _on_progress(self, message: str, current: int, total: int):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
        self.lbl_progress.setText(message)
    
    def _on_operation_finished(self, results: dict):
        self.progress.setVisible(False)
        self.lbl_progress.setVisible(False)
        self.btn_add_selected.setEnabled(True)
        self.btn_remove_selected.setEnabled(True)
        self.btn_update_selected.setEnabled(True)
        self.worker = None
        
        # Build result message
        parts = []
        if results["success"]:
            parts.append(f"✅ {tr('common.success')}: {len(results['success'])}")
        if results["failed"]:
            parts.append(f"❌ {tr('mods.install_failed')}: {len(results['failed'])}")
            for mod, reason in results["failed"][:3]:
                parts.append(f"   - {mod}: {reason}")
        if results["bikeys_copied"]:
            parts.append(f"🔑 {tr('mods.bikeys_copied')}: {len(results['bikeys_copied'])}")
        if results["bikeys_removed"]:
            parts.append(f"🔑 Bikeys removed: {len(results['bikeys_removed'])}")
        
        if parts:
            QMessageBox.information(self, tr("common.success"), "\n".join(parts))
        
        # Refresh lists
        self._refresh_all()
    
    def _copy_all_bikeys(self):
        """Copy all bikeys from installed mods."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            return
        
        try:
            checker = ModIntegrityChecker(str(server_path))
            count, bikeys = checker.extract_all_bikeys()
            
            QMessageBox.information(
                self, tr("common.success"),
                f"{tr('mods.bikeys_copied')}: {count}\n\n" + 
                "\n".join(bikeys[:10]) + 
                (f"\n...{len(bikeys)-10} more" if len(bikeys) > 10 else "")
            )
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def _get_installed_mod_folders(self) -> list[str]:
        """Return installed mod folder names."""
        return [item[0] for item in self._installed_items]
    
    def _format_mods_txt(self, mods: list[str]) -> str:
        if not mods:
            return ""
        cleaned = [m.strip().strip('"').strip() for m in mods if m and m.strip()]
        return ";".join(cleaned) + ";" if cleaned else ""
    
    def _sync_mods_txt_with_installed(self):
        """Write server/mods.txt and emit signal."""
        if not self.current_profile:
            return
        
        server_path_str = self.current_profile.get("server_path", "")
        if not server_path_str:
            return
        
        server_path = Path(server_path_str)
        mods = self._get_installed_mod_folders()
        mods_text = self._format_mods_txt(mods)
        
        try:
            (server_path / "mods.txt").write_text(mods_text, encoding="utf-8")
        except Exception:
            pass
        
        self.mods_list_updated.emit(mods_text)
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('mods.title')}</h2>")
        self.btn_refresh.setText(f"🔄 {tr('common.refresh')}")
        self.btn_copy_all_bikeys.setText(f"🔑 {tr('mods.copy_all_bikeys')}")
        self.lbl_no_profile.setText(tr("mods.select_profile_first"))
        self.workshop_box.setTitle(f"📦 {tr('mods.workshop_source')}")
        self.installed_box.setTitle(f"🖥️ {tr('mods.server_installed')}")
        self.btn_add_selected.setText(f"➕ {tr('mods.add_to_server')}")
        self.btn_remove_selected.setText(f"➖ {tr('mods.remove_from_server')}")
        self.btn_update_selected.setText(f"🔄 {tr('mods.update_selected')}")
        self.btn_select_all_ws.setText(tr("common.select_all"))
        self.btn_deselect_all_ws.setText(tr("common.deselect_all"))
        self.btn_select_all_inst.setText(tr("common.select_all"))
        self.btn_deselect_all_inst.setText(tr("common.deselect_all"))
        self.search_workshop.setPlaceholderText(f"🔍 {tr('common.search')}...")
        self.search_installed.setPlaceholderText(f"🔍 {tr('common.search')}...")
        
        # Update table headers
        self.workshop_table.setHorizontalHeaderLabels([
            "", tr("mods.mod_name"), tr("mods.mod_version"), tr("mods.mod_size"), tr("mods.mod_status")
        ])
        self.installed_table.setHorizontalHeaderLabels([
            "", tr("mods.mod_name"), tr("mods.mod_version"), tr("mods.mod_size"), 
            tr("mods.bikey_status"), tr("common.actions")
        ])
