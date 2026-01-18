"""
Config Preset Dialogs
Dialogs for managing config presets (save, load, delete).
"""

from pathlib import Path
from typing import Optional, List, Callable, Dict, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QDialogButtonBox, QGroupBox, QFormLayout, QTextEdit,
    QWidget, QAbstractItemView, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QBrush, QPalette

from src.utils.locale_manager import tr
from src.ui.theme_manager import ThemeManager
from src.ui.widgets import IconButton
from src.core.config_preset_manager import ConfigPresetManager, ConfigPreset


class SavePresetDialog(QDialog):
    """Dialog for saving a config preset with a name."""
    
    def __init__(self, existing_names: List[str] = None, parent=None):
        super().__init__(parent)
        self.existing_names = existing_names or []
        self.preset_name = ""
        self.description = ""
        
        self.setWindowTitle(tr("presets.save_preset"))
        self.setMinimumWidth(400)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Name input
        form = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText(tr("presets.preset_name_placeholder"))
        self.txt_name.textChanged.connect(self._on_name_changed)
        form.addRow(tr("presets.preset_name") + ":", self.txt_name)
        
        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText(tr("presets.description_placeholder"))
        form.addRow(tr("presets.description") + ":", self.txt_description)
        
        layout.addLayout(form)
        
        # Warning label
        self.lbl_warning = QLabel()
        self.lbl_warning.setStyleSheet("color: #f0ad4e;")
        self.lbl_warning.setVisible(False)
        layout.addWidget(self.lbl_warning)
        
        # Existing presets hint
        if self.existing_names:
            hint = QLabel(f"{tr('presets.existing_presets')}: {', '.join(self.existing_names)}")
            hint.setStyleSheet("color: gray; font-size: 11px;")
            hint.setWordWrap(True)
            layout.addWidget(hint)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        self.btn_save = button_box.button(QDialogButtonBox.Save)
        self.btn_save.setEnabled(False)
        layout.addWidget(button_box)
        
        self.txt_name.setFocus()
    
    def _on_name_changed(self, text: str):
        text = text.strip()
        self.btn_save.setEnabled(bool(text))
        
        if text in self.existing_names:
            self.lbl_warning.setText(tr("presets.overwrite_warning"))
            self.lbl_warning.setVisible(True)
        else:
            self.lbl_warning.setVisible(False)
    
    def _on_save(self):
        self.preset_name = self.txt_name.text().strip()
        self.description = self.txt_description.text().strip()
        
        if not self.preset_name:
            QMessageBox.warning(self, tr("common.warning"), tr("presets.name_required"))
            return
        
        self.accept()


class LoadPresetDialog(QDialog):
    """Dialog for selecting and loading a config preset."""
    
    preset_selected = Signal(str)  # Emits action string
    
    def __init__(
        self,
        preset_options: List[Dict[str, str]],
        content_loader: Callable[[str, str], Optional[str]],
        current_profile_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self.preset_options = preset_options
        self._content_loader = content_loader
        self.current_profile_name = current_profile_name

        self.selected_preset_name: str = ""
        self.selected_profile_name: str = ""
        
        self.setWindowTitle(tr("presets.load_preset"))
        self.setMinimumSize(820, 640)
        self.setSizeGripEnabled(True)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(tr("presets.select_preset_to_load"))
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(max(12, header_font.pointSize() + 3))
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Presets list
        self.list_presets = QListWidget()
        self.list_presets.setSpacing(6)
        self.list_presets.setAlternatingRowColors(False)
        self.list_presets.setStyleSheet(
            "QListWidget {"
            "  padding: 6px;"
            "  border: 1px solid rgba(255, 255, 255, 0.08);"
            "  border-radius: 10px;"
            "  background-color: palette(base);"
            "}"
            "QListWidget::item {"
            "  padding: 10px 12px;"
            "  border-radius: 8px;"
            "}"
            "QListWidget::item:hover {"
            "  background-color: rgba(255, 255, 255, 0.06);"
            "}"
            "QListWidget::item:selected {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
        )
        self.list_presets.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_presets.currentItemChanged.connect(self._on_selection_changed)

        # Group by profile (current first)
        grouped: Dict[str, List[Dict[str, str]]] = {}
        for opt in self.preset_options:
            grouped.setdefault(opt.get("profile") or "", []).append(opt)

        def add_header(text: str):
            header_item = QListWidgetItem(text)
            header_item.setFlags(Qt.NoItemFlags)
            hf = QFont(self.list_presets.font())
            hf.setBold(True)
            header_item.setFont(hf)
            header_item.setForeground(QBrush(QColor(ThemeManager.get_text_color())))
            header_item.setBackground(QBrush(self.list_presets.palette().color(QPalette.Midlight)))
            header_item.setTextAlignment(Qt.AlignLeft)
            self.list_presets.addItem(header_item)

        # Current profile section
        current_opts = grouped.get(self.current_profile_name, [])
        if current_opts:
            add_header(tr("presets.current_profile_group").format(name=self.current_profile_name))
            for opt in sorted(current_opts, key=lambda x: (x.get("display_name") or x.get("name") or "").lower()):
                display = opt.get("display_name") or opt.get("name")
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, opt)
                self.list_presets.addItem(item)

        # Other profiles
        other_profiles = [p for p in grouped.keys() if p and p != self.current_profile_name]
        for profile in sorted(other_profiles, key=lambda x: x.lower()):
            add_header(tr("presets.other_profile_group").format(name=profile))
            for opt in sorted(grouped.get(profile, []), key=lambda x: (x.get("display_name") or x.get("name") or "").lower()):
                display = opt.get("display_name") or opt.get("name")
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, opt)
                self.list_presets.addItem(item)
        
        # Preview area
        preview_box = QGroupBox(tr("presets.preview"))
        preview_layout = QVBoxLayout(preview_box)
        
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setMinimumHeight(180)
        self.txt_preview.setLineWrapMode(QTextEdit.NoWrap)
        self.txt_preview.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self.txt_preview)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.list_presets)
        splitter.addWidget(preview_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_delete = IconButton("trash", tr("common.delete"), size=14)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        
        self.btn_load = QPushButton(tr("presets.load"))
        self.btn_load.setObjectName("primary")
        self.btn_load.setEnabled(False)
        self.btn_load.clicked.connect(self._on_load)
        btn_layout.addWidget(self.btn_load)
        
        btn_cancel = QPushButton(tr("common.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _on_selection_changed(self, current, previous):
        opt = current.data(Qt.UserRole) if current else None
        if not opt or not isinstance(opt, dict):
            self.selected_preset_name = ""
            self.selected_profile_name = ""
            self.btn_load.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.txt_preview.clear()
            return

        self.selected_preset_name = opt.get("name") or ""
        self.selected_profile_name = opt.get("profile") or ""
        self.btn_load.setEnabled(bool(self.selected_preset_name))
        # only allow delete for current profile presets
        self.btn_delete.setEnabled(self.selected_profile_name == self.current_profile_name)

        # Tooltip
        try:
            from datetime import datetime
            created_at = opt.get("created_at") or ""
            if created_at:
                date = datetime.fromisoformat(created_at)
                date_str = date.strftime("%Y-%m-%d %H:%M")
                tip = f"{tr('presets.created')}: {date_str}"
                desc = (opt.get("description") or "").strip()
                if desc:
                    tip += f"\n{desc}"
                current.setToolTip(tip)
        except Exception:
            pass

        # Lazy preview
        try:
            content = self._content_loader(self.selected_profile_name, self.selected_preset_name) or ""
        except Exception:
            content = ""
        lines = content.split('\n')[:50]
        preview = '\n'.join(lines)
        if len(content.split('\n')) > 50:
            preview += "\n..."
        self.txt_preview.setText(preview)
    
    def _on_item_double_clicked(self, item):
        self._on_load()
    
    def _on_load(self):
        if self.selected_preset_name:
            self.accept()
    
    def _on_delete(self):
        if not self.selected_preset_name or not self.selected_profile_name:
            return

        if self.selected_profile_name != self.current_profile_name:
            return
        
        reply = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("presets.confirm_delete").format(name=self.selected_preset_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove from list
            current_row = self.list_presets.currentRow()
            self.list_presets.takeItem(current_row)

            # Emit signal to notify parent to delete from manager (current profile only)
            self.preset_selected.emit(f"DELETE:{self.selected_preset_name}")

            self.selected_preset_name = ""
            self.selected_profile_name = ""
            self.txt_preview.clear()


class BulkLoadPresetDialog(QDialog):
    """Dialog for loading presets across multiple files."""
    
    def __init__(
        self,
        profiles: List[str],
        data_provider: Callable[[str], Tuple[List[str], Dict[str, List[str]]]],
        parent=None,
    ):
        super().__init__(parent)
        self.profiles = profiles
        self.data_provider = data_provider

        self.preset_names: List[str] = []
        self.files_with_presets: Dict[str, List[str]] = {}
        self.aggregate_files_with_presets: Dict[str, List[str]] = {}
        self.selected_preset = ""
        self.selected_profile = profiles[0] if profiles else ""
        
        self.setWindowTitle(tr("presets.load_config_presets"))
        self.setMinimumSize(760, 520)
        self.setSizeGripEnabled(True)
        self.setModal(True)

        # Precompute aggregate mapping across all profiles for counts (must happen before first render)
        try:
            agg: Dict[str, set] = {}
            for p in self.profiles:
                _, files_map = self.data_provider(p)
                for fp, presets in files_map.items():
                    agg.setdefault(fp, set()).update(presets)
            self.aggregate_files_with_presets = {fp: sorted(list(s)) for fp, s in agg.items()}
        except Exception:
            self.aggregate_files_with_presets = {}

        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(tr("presets.select_preset_group"))
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(max(12, header_font.pointSize() + 3))
        header.setFont(header_font)
        layout.addWidget(header)
        
        info = QLabel(tr("presets.bulk_load_info"))
        info.setStyleSheet("color: gray;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Profile selector
        profile_row = QHBoxLayout()
        lbl_profile = QLabel(tr("presets.select_profile"))
        profile_row.addWidget(lbl_profile)
        self.cmb_profile = QComboBox()
        for p in self.profiles:
            self.cmb_profile.addItem(p)
        self.cmb_profile.currentTextChanged.connect(self._on_profile_changed)
        profile_row.addWidget(self.cmb_profile, stretch=1)
        layout.addLayout(profile_row)
        
        # Presets list
        self.list_presets = QListWidget()
        self.list_presets.setSpacing(6)
        self.list_presets.setAlternatingRowColors(False)
        self.list_presets.setStyleSheet(
            "QListWidget {"
            "  padding: 6px;"
            "  border: 1px solid rgba(255, 255, 255, 0.08);"
            "  border-radius: 10px;"
            "  background-color: palette(base);"
            "}"
            "QListWidget::item {"
            "  padding: 10px 12px;"
            "  border-radius: 8px;"
            "}"
            "QListWidget::item:hover {"
            "  background-color: rgba(255, 255, 255, 0.06);"
            "}"
            "QListWidget::item:selected {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
        )
        self.list_presets.itemDoubleClicked.connect(self._on_load)
        self.list_presets.currentItemChanged.connect(self._on_selection_changed)

        layout.addWidget(self.list_presets)
        
        # Files that will be affected
        self.lbl_affected = QLabel()
        self.lbl_affected.setStyleSheet("color: gray; font-size: 11px;")
        self.lbl_affected.setWordWrap(True)
        layout.addWidget(self.lbl_affected)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_load = QPushButton(tr("presets.load"))
        self.btn_load.setObjectName("primary")
        self.btn_load.setEnabled(False)
        self.btn_load.clicked.connect(self._on_load)
        btn_layout.addWidget(self.btn_load)
        
        btn_cancel = QPushButton(tr("common.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        # Now that buttons exist, load presets for the initially-selected profile
        self._reload_for_profile(self.selected_profile)

        layout.addLayout(btn_layout)
    
    def _on_selection_changed(self, current, previous):
        if current:
            preset_name = current.data(Qt.UserRole)
            self.selected_preset = preset_name
            self.btn_load.setEnabled(True)
            
            # Show affected files
            affected = [
                Path(fp).name for fp, presets in self.files_with_presets.items() 
                if preset_name in presets
            ]
            if len(affected) > 5:
                affected_str = ", ".join(affected[:5]) + f" (+{len(affected)-5} {tr('common.more')})"
            else:
                affected_str = ", ".join(affected)
            self.lbl_affected.setText(f"{tr('presets.will_load')}: {affected_str}")
        else:
            self.selected_preset = ""
            self.btn_load.setEnabled(False)
            self.lbl_affected.clear()

    def _on_profile_changed(self, profile_name: str):
        self.selected_profile = profile_name
        self._reload_for_profile(profile_name)

    def _reload_for_profile(self, profile_name: str):
        self.selected_preset = ""
        self.btn_load.setEnabled(False)
        self.lbl_affected.clear()

        try:
            preset_names, files_with_presets = self.data_provider(profile_name)
        except Exception:
            preset_names, files_with_presets = [], {}

        self.preset_names = preset_names
        self.files_with_presets = files_with_presets

        self.list_presets.clear()
        for name in self.preset_names:
            # count across all profiles for clearer visibility
            count = sum(1 for presets in self.aggregate_files_with_presets.values() if name in presets)
            item = QListWidgetItem(f"{name} ({count} {tr('presets.files')})")
            item.setData(Qt.UserRole, name)
            self.list_presets.addItem(item)
    
    def _on_load(self):
        if self.selected_preset:
            self.accept()


class BulkSavePresetDialog(QDialog):
    """Dialog for saving presets across multiple files."""
    
    def __init__(self, file_paths: List[Path], existing_names: List[str] = None, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.existing_names = existing_names or []
        self.preset_name = ""
        self.description = ""
        
        self.setWindowTitle(tr("presets.save_config_presets"))
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"<h3>{tr('presets.save_all_configs')}</h3>")
        layout.addWidget(header)
        
        info = QLabel(tr("presets.bulk_save_info").format(count=len(self.file_paths)))
        info.setStyleSheet("color: gray;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Name input
        form = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText(tr("presets.preset_name_placeholder"))
        self.txt_name.textChanged.connect(self._on_name_changed)
        form.addRow(tr("presets.preset_name") + ":", self.txt_name)
        
        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText(tr("presets.description_placeholder"))
        form.addRow(tr("presets.description") + ":", self.txt_description)
        
        layout.addLayout(form)
        
        # Warning label
        self.lbl_warning = QLabel()
        self.lbl_warning.setStyleSheet("color: #f0ad4e;")
        self.lbl_warning.setVisible(False)
        layout.addWidget(self.lbl_warning)
        
        # Existing presets hint
        if self.existing_names:
            hint = QLabel(f"{tr('presets.existing_presets')}: {', '.join(self.existing_names[:10])}")
            if len(self.existing_names) > 10:
                hint.setText(hint.text() + f" (+{len(self.existing_names)-10})")
            hint.setStyleSheet("color: gray; font-size: 11px;")
            hint.setWordWrap(True)
            layout.addWidget(hint)
        
        # Files list
        files_box = QGroupBox(tr("presets.files_to_save"))
        files_layout = QVBoxLayout(files_box)
        
        files_list = QListWidget()
        files_list.setSpacing(3)
        files_list.setMaximumHeight(120)
        files_list.setStyleSheet(
            "QListWidget { padding: 2px; }"
            "QListWidget::item { padding: 6px 10px; }"
        )
        for fp in self.file_paths[:20]:
            files_list.addItem(fp.name)
        if len(self.file_paths) > 20:
            files_list.addItem(f"... +{len(self.file_paths)-20} {tr('common.more')}")
        files_layout.addWidget(files_list)
        
        layout.addWidget(files_box)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        self.btn_save = button_box.button(QDialogButtonBox.Save)
        self.btn_save.setEnabled(False)
        layout.addWidget(button_box)
        
        self.txt_name.setFocus()
    
    def _on_name_changed(self, text: str):
        text = text.strip()
        self.btn_save.setEnabled(bool(text))
        
        if text in self.existing_names:
            self.lbl_warning.setText(tr("presets.overwrite_warning"))
            self.lbl_warning.setVisible(True)
        else:
            self.lbl_warning.setVisible(False)
    
    def _on_save(self):
        self.preset_name = self.txt_name.text().strip()
        self.description = self.txt_description.text().strip()
        
        if not self.preset_name:
            QMessageBox.warning(self, tr("common.warning"), tr("presets.name_required"))
            return
        
        self.accept()
