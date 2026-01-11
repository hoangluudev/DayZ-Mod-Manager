"""
Mods Tab - Mod Management with Integrity Checking
"""

from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QGroupBox, QCheckBox, QFileDialog, QFrame,
    QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor

from src.core.mod_integrity import ModIntegrityChecker
from src.core.profile_manager import ProfileManager
from src.models.mod_models import ModStatus, IntegrityReport
from src.utils.locale_manager import tr


class IntegrityCheckWorker(QThread):
    """Background worker for integrity checking."""
    
    progress = Signal(str, int, int)  # message, current, total
    finished = Signal(object)  # IntegrityReport
    error = Signal(str)
    
    def __init__(self, server_path: str, workshop_path: str = None, mod_list: list[str] | None = None):
        super().__init__()
        self.server_path = server_path
        self.workshop_path = workshop_path
        self.mod_list = mod_list
    
    def run(self):
        try:
            checker = ModIntegrityChecker(
                self.server_path,
                workshop_path=self.workshop_path,
                progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
            )
            if self.mod_list is not None:
                report = checker.check_all_mods(self.mod_list)
            else:
                report = checker.check_server_integrity()
            self.finished.emit(report)
        except Exception as e:
            self.error.emit(str(e))


class ModsTab(QWidget):
    """Tab for managing server mods."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self.profile_manager = ProfileManager()
        self.integrity_report = None
        self.worker = None
        self._workshop_items: list[tuple[str, str]] = []  # [(workshop_id, mod_folder)]
        self._selected_keys: set[str] = set()  # "<id>:<mod>"
        self._populating_workshop = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        
        self.lbl_title = QLabel(f"<h2>{tr('mods.title')}</h2>")
        header.addWidget(self.lbl_title)
        header.addStretch()
        
        self.btn_verify = QPushButton(f"🔍 {tr('mods.verify_integrity')}")
        self.btn_verify.clicked.connect(self._run_integrity_check)
        header.addWidget(self.btn_verify)
        
        self.btn_copy_all = QPushButton(f"📋 {tr('mods.copy_all_bikeys')}")
        self.btn_copy_all.clicked.connect(self._copy_all_bikeys)
        header.addWidget(self.btn_copy_all)
        
        layout.addLayout(header)

        # Workshop list
        self.workshop_box = QGroupBox(tr("mods.workshop_list"))
        workshop_layout = QVBoxLayout(self.workshop_box)

        ws_actions = QHBoxLayout()
        self.lbl_workshop_path = QLabel()
        self.lbl_workshop_path.setStyleSheet("color: gray; font-size: 11px;")
        ws_actions.addWidget(self.lbl_workshop_path)
        ws_actions.addStretch()
        self.btn_select_all = QPushButton(tr("common.select_all"))
        self.btn_select_all.clicked.connect(self._select_all_workshop)
        ws_actions.addWidget(self.btn_select_all)
        self.btn_deselect_all = QPushButton(tr("common.deselect_all"))
        self.btn_deselect_all.clicked.connect(self._deselect_all_workshop)
        ws_actions.addWidget(self.btn_deselect_all)
        self.lbl_selected_count = QLabel()
        self.lbl_selected_count.setStyleSheet("color: #0078d4; font-size: 11px;")
        ws_actions.addWidget(self.lbl_selected_count)
        workshop_layout.addLayout(ws_actions)

        self.workshop_table = QTableWidget()
        self.workshop_table.setColumnCount(3)
        self.workshop_table.setHorizontalHeaderLabels([
            tr("common.select"),
            tr("mods.mod_name"),
            tr("mods.mod_id"),
        ])
        self.workshop_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.workshop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.workshop_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.workshop_table.setAlternatingRowColors(True)
        self.workshop_table.itemChanged.connect(self._on_workshop_item_changed)
        workshop_layout.addWidget(self.workshop_table)

        self.workshop_box.setVisible(False)

        layout.addWidget(self.workshop_box)
        
        # No profile selected message
        self.lbl_no_profile = QLabel(tr("mods.select_profile_first"))
        self.lbl_no_profile.setAlignment(Qt.AlignCenter)
        self.lbl_no_profile.setStyleSheet("color: gray; padding: 30px; font-size: 14px;")
        layout.addWidget(self.lbl_no_profile)
        
        # Content area (hidden initially)
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        content_layout.addWidget(self.progress)
        
        self.lbl_progress = QLabel()
        self.lbl_progress.setVisible(False)
        content_layout.addWidget(self.lbl_progress)
        
        # Summary box
        self.summary_box = QGroupBox(tr("mods.integrity_summary"))
        summary_layout = QHBoxLayout(self.summary_box)
        
        self.lbl_total = QLabel("Total: 0")
        self.lbl_installed = QLabel("✅ Installed: 0")
        self.lbl_installed.setStyleSheet("color: #4caf50;")
        self.lbl_partial = QLabel("⚠️ Partial: 0")
        self.lbl_partial.setStyleSheet("color: #ff9800;")
        self.lbl_missing = QLabel("❌ Missing: 0")
        self.lbl_missing.setStyleSheet("color: #f44336;")
        
        summary_layout.addWidget(self.lbl_total)
        summary_layout.addWidget(self.lbl_installed)
        summary_layout.addWidget(self.lbl_partial)
        summary_layout.addWidget(self.lbl_missing)
        summary_layout.addStretch()
        
        content_layout.addWidget(self.summary_box)
        
        # Mods table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            tr("mods.mod_name"),
            tr("mods.mod_status"),
            tr("mods.bikey_status"),
            tr("mods.mod_size"),
            tr("common.actions")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        content_layout.addWidget(self.table)
        
        # Issues panel
        self.issues_box = QGroupBox(tr("mods.issues_found"))
        issues_layout = QVBoxLayout(self.issues_box)
        self.txt_issues = QTextEdit()
        self.txt_issues.setReadOnly(True)
        self.txt_issues.setMaximumHeight(150)
        issues_layout.addWidget(self.txt_issues)
        content_layout.addWidget(self.issues_box)
        self.issues_box.setVisible(False)
        
        layout.addWidget(self.content_widget)
        self.content_widget.setVisible(False)
    
    def set_profile(self, profile_data: dict):
        """Set the current profile for mod management."""
        # Avoid overlapping integrity checks when switching profiles.
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(250)

        self.current_profile = profile_data
        self._selected_keys = set(profile_data.get("selected_mods") or [])
        self.lbl_no_profile.setVisible(False)
        self.content_widget.setVisible(True)

        self.workshop_box.setVisible(True)

        self._load_workshop_mods()
        
        # Clear previous data
        self.table.setRowCount(0)
        self.integrity_report = None
        self._update_summary(None)
    
    def _run_integrity_check(self):
        """Run integrity check on current profile."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("mods.select_profile_first"))
            return

        if self.worker and self.worker.isRunning():
            return
        
        server_path = self.current_profile.get("server_path", "")
        if not server_path or not Path(server_path).exists():
            QMessageBox.warning(self, tr("common.warning"), tr("validation.invalid_path"))
            return
        
        # Show progress
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText(tr("mods.checking"))
        self.btn_verify.setEnabled(False)
        
        # Determine selected mod list (folder names) if any
        selected_mods = self._get_selected_mod_folders()
        mod_list = selected_mods if selected_mods else None

        # Start worker
        workshop_path = self.current_profile.get("workshop_path", "")
        self.worker = IntegrityCheckWorker(server_path, workshop_path or None, mod_list=mod_list)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_check_finished)
        self.worker.error.connect(self._on_check_error)
        self.worker.start()

    def _get_selected_mod_folders(self) -> list[str]:
        """Return selected mod folder names (e.g. @CF)."""
        mods: list[str] = []
        for key in sorted(self._selected_keys):
            if ":" in key:
                _, mod_folder = key.split(":", 1)
                if mod_folder:
                    mods.append(mod_folder)
        return mods

    def _load_workshop_mods(self):
        """Load workshop mods from the current profile's workshop path."""
        self._workshop_items = []
        self._populating_workshop = True
        try:
            self.workshop_table.setRowCount(0)

            workshop_path_str = (self.current_profile or {}).get("workshop_path", "")
            self.lbl_workshop_path.setText(workshop_path_str or "")
            if not workshop_path_str:
                self._set_selected_count()
                return

            workshop_path = Path(workshop_path_str)
            if not workshop_path.exists() or not workshop_path.is_dir():
                self._set_selected_count()
                return

            # Steam workshop DayZ structure: <workshop_path>/<workshop_id>/.../@ModName
            found_any = False
            for id_dir in sorted([p for p in workshop_path.iterdir() if p.is_dir()]):
                workshop_id = id_dir.name
                mod_dirs = [p for p in id_dir.iterdir() if p.is_dir() and p.name.startswith("@")] 
                if not mod_dirs:
                    continue
                found_any = True
                for mod_dir in sorted(mod_dirs):
                    self._workshop_items.append((workshop_id, mod_dir.name))

            # Fallback: some users point workshop_path directly at a folder containing @Mods.
            if not found_any:
                direct_mods = [p for p in workshop_path.iterdir() if p.is_dir() and p.name.startswith("@")] 
                for mod_dir in sorted(direct_mods):
                    self._workshop_items.append(("local", mod_dir.name))

            self.workshop_table.setRowCount(len(self._workshop_items))
            for row, (workshop_id, mod_folder) in enumerate(self._workshop_items):
                key = f"{workshop_id}:{mod_folder}"

                check_item = QTableWidgetItem()
                check_item.setFlags(check_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                check_item.setCheckState(Qt.Checked if key in self._selected_keys else Qt.Unchecked)
                check_item.setData(Qt.UserRole, key)
                self.workshop_table.setItem(row, 0, check_item)

                name_item = QTableWidgetItem(mod_folder)
                name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
                self.workshop_table.setItem(row, 1, name_item)

                id_item = QTableWidgetItem(workshop_id)
                id_item.setFlags(id_item.flags() ^ Qt.ItemIsEditable)
                self.workshop_table.setItem(row, 2, id_item)

            self._set_selected_count()
        finally:
            self._populating_workshop = False

    def _set_selected_count(self):
        self.lbl_selected_count.setText(f"{tr('mods.selected')}: {len(self._selected_keys)}")

    def _select_all_workshop(self):
        if not self.current_profile:
            return
        self._populating_workshop = True
        try:
            for row in range(self.workshop_table.rowCount()):
                item = self.workshop_table.item(row, 0)
                if item is None:
                    continue
                item.setCheckState(Qt.Checked)
        finally:
            self._populating_workshop = False
        self._sync_selected_from_table()

    def _deselect_all_workshop(self):
        if not self.current_profile:
            return
        self._populating_workshop = True
        try:
            for row in range(self.workshop_table.rowCount()):
                item = self.workshop_table.item(row, 0)
                if item is None:
                    continue
                item.setCheckState(Qt.Unchecked)
        finally:
            self._populating_workshop = False
        self._sync_selected_from_table()

    def _on_workshop_item_changed(self, item: QTableWidgetItem):
        if self._populating_workshop:
            return
        if item.column() != 0:
            return
        self._sync_selected_from_table()

    def _sync_selected_from_table(self):
        selected: set[str] = set()
        for row in range(self.workshop_table.rowCount()):
            item = self.workshop_table.item(row, 0)
            if item is None:
                continue
            if item.checkState() == Qt.Checked:
                key = item.data(Qt.UserRole)
                if isinstance(key, str) and key:
                    selected.add(key)

        self._selected_keys = selected
        self._set_selected_count()
        self._persist_selected_mods()

    def _persist_selected_mods(self):
        """Persist selection into profile JSON."""
        if not self.current_profile:
            return
        name = self.current_profile.get("name")
        if not name:
            return

        profile = self.profile_manager.get_profile(name)
        if not profile:
            return

        profile.selected_mods = sorted(self._selected_keys)
        # Keep workshop_path synced as well
        ws = self.current_profile.get("workshop_path")
        profile.workshop_path = Path(ws) if ws else None
        self.profile_manager.save_profile(profile)
    
    def _on_progress(self, message: str, current: int, total: int):
        """Handle progress updates."""
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
        self.lbl_progress.setText(message)
    
    def _on_check_finished(self, report: IntegrityReport):
        """Handle integrity check completion."""
        self.progress.setVisible(False)
        self.lbl_progress.setVisible(False)
        self.btn_verify.setEnabled(True)

        self.worker = None
        
        self.integrity_report = report
        self._display_report(report)
    
    def _on_check_error(self, error_msg: str):
        """Handle integrity check error."""
        self.progress.setVisible(False)
        self.lbl_progress.setVisible(False)
        self.btn_verify.setEnabled(True)

        self.worker = None
        
        QMessageBox.critical(self, tr("common.error"), error_msg)
    
    def _display_report(self, report: IntegrityReport):
        """Display the integrity report in the UI."""
        self._update_summary(report)
        
        # Populate table
        self.table.setRowCount(len(report.mods))
        
        for row, mod in enumerate(report.mods):
            # Mod name
            name_item = QTableWidgetItem(mod.name)
            self.table.setItem(row, 0, name_item)
            
            # Status
            status_text, status_color = self._get_status_display(mod.status)
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            self.table.setItem(row, 1, status_item)
            
            # Bikey status
            if mod.bikeys:
                bikey_text = f"✅ {len(mod.bikeys)} bikey(s)"
                bikey_color = "#4caf50"
            else:
                bikey_text = f"❌ {tr('mods.status_missing_bikey')}"
                bikey_color = "#f44336"
            
            bikey_item = QTableWidgetItem(bikey_text)
            bikey_item.setForeground(QColor(bikey_color))
            self.table.setItem(row, 2, bikey_item)
            
            # Size
            size_mb = mod.size_bytes / (1024 * 1024) if mod.size_bytes else 0
            size_item = QTableWidgetItem(f"{size_mb:.1f} MB" if size_mb > 0 else "-")
            self.table.setItem(row, 3, size_item)
            
            # Actions button
            btn_action = QPushButton(tr("mods.copy_bikey"))
            btn_action.setEnabled(mod.needs_bikey and bool(mod.bikeys))
            btn_action.clicked.connect(lambda checked, m=mod: self._copy_mod_bikey(m))
            self.table.setCellWidget(row, 4, btn_action)
        
        # Show issues
        if report.issues:
            self.issues_box.setVisible(True)
            issues_text = "\n".join([
                f"{'❌' if i.severity.value == 'failed' else '⚠️'} [{i.category}] {i.message}"
                for i in report.issues
            ])
            self.txt_issues.setText(issues_text)
        else:
            self.issues_box.setVisible(False)
    
    def _update_summary(self, report: IntegrityReport):
        """Update the summary display."""
        if report:
            self.lbl_total.setText(f"Total: {report.total_mods_checked}")
            self.lbl_installed.setText(f"✅ {tr('mods.status_installed')}: {report.fully_installed}")
            self.lbl_partial.setText(f"⚠️ {tr('mods.status_partial')}: {report.partial_installed}")
            self.lbl_missing.setText(f"❌ {tr('mods.status_missing_folder')}: {report.missing}")
        else:
            self.lbl_total.setText("Total: 0")
            self.lbl_installed.setText(f"✅ {tr('mods.status_installed')}: 0")
            self.lbl_partial.setText(f"⚠️ {tr('mods.status_partial')}: 0")
            self.lbl_missing.setText(f"❌ {tr('mods.status_missing_folder')}: 0")
    
    def _get_status_display(self, status: ModStatus) -> tuple:
        """Get display text and color for mod status."""
        status_map = {
            ModStatus.FULLY_INSTALLED: (f"✅ {tr('mods.status_installed')}", "#4caf50"),
            ModStatus.PARTIAL_FOLDER_ONLY: (f"⚠️ {tr('mods.status_missing_bikey')}", "#ff9800"),
            ModStatus.PARTIAL_BIKEY_ONLY: (f"⚠️ {tr('mods.status_missing_folder')}", "#ff9800"),
            ModStatus.NOT_INSTALLED: (f"❌ {tr('mods.status_not_installed')}", "#f44336"),
            ModStatus.CORRUPTED: (f"💔 Corrupted", "#f44336"),
            ModStatus.OUTDATED: (f"🔄 {tr('mods.status_outdated')}", "#2196f3"),
        }
        return status_map.get(status, ("❓ Unknown", "#888"))
    
    def _copy_mod_bikey(self, mod):
        """Copy bikey files for a specific mod."""
        if not self.current_profile:
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        keys_folder = server_path / "keys"
        keys_folder.mkdir(exist_ok=True)
        
        import shutil
        copied = 0
        for bikey in mod.bikeys:
            dest = keys_folder / bikey.name
            if not dest.exists():
                try:
                    shutil.copy2(bikey.path, dest)
                    copied += 1
                except Exception as e:
                    print(f"Error copying bikey: {e}")
        
        if copied > 0:
            QMessageBox.information(
                self,
                tr("common.success"),
                f"{tr('mods.bikeys_copied')}: {copied}"
            )
            self._run_integrity_check()  # Refresh
    
    def _copy_all_bikeys(self):
        """Copy all bikeys from installed mods."""
        if not self.current_profile:
            QMessageBox.warning(self, tr("common.warning"), tr("mods.select_profile_first"))
            return
        
        server_path = Path(self.current_profile.get("server_path", ""))
        if not server_path.exists():
            return
        
        try:
            checker = ModIntegrityChecker(str(server_path))
            count, bikeys = checker.extract_all_bikeys()
            
            QMessageBox.information(
                self,
                tr("common.success"),
                f"{tr('mods.bikeys_copied')}: {count}\n\n" + "\n".join(bikeys[:10]) + 
                (f"\n...and {len(bikeys)-10} more" if len(bikeys) > 10 else "")
            )
            
            if self.integrity_report:
                self._run_integrity_check()  # Refresh
                
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('mods.title')}</h2>")
        self.btn_verify.setText(f"🔍 {tr('mods.verify_integrity')}")
        self.btn_copy_all.setText(f"📋 {tr('mods.copy_all_bikeys')}")
        self.lbl_no_profile.setText(tr("mods.select_profile_first"))
        self.workshop_box.setTitle(tr("mods.workshop_list"))
        self.btn_select_all.setText(tr("common.select_all"))
        self.btn_deselect_all.setText(tr("common.deselect_all"))
        self._set_selected_count()
        self.summary_box.setTitle(tr("mods.integrity_summary"))
        self.issues_box.setTitle(tr("mods.issues_found"))
        
        # Update table headers
        self.table.setHorizontalHeaderLabels([
            tr("mods.mod_name"),
            tr("mods.mod_status"),
            tr("mods.bikey_status"),
            tr("mods.mod_size"),
            tr("common.actions")
        ])

        self.workshop_table.setHorizontalHeaderLabels([
            tr("common.select"),
            tr("mods.mod_name"),
            tr("mods.mod_id"),
        ])
