"""
Configuration Change Manager - Tracks changes across tabs and provides save/restore functionality
"""

import copy
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDialogButtonBox, QScrollArea, QWidget, QGroupBox,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject

from src.utils.locale_manager import tr


@dataclass
class ConfigSnapshot:
    """Snapshot of configuration state for a tab."""
    launcher: Dict[str, Any] = field(default_factory=dict)
    server_config: Dict[str, Any] = field(default_factory=dict)
    
    def copy(self) -> 'ConfigSnapshot':
        """Create a deep copy of this snapshot."""
        return ConfigSnapshot(
            launcher=copy.deepcopy(self.launcher),
            server_config=copy.deepcopy(self.server_config)
        )


class ConfigChangeManager(QObject):
    """
    Manages configuration changes across Launcher and Config tabs.
    Provides change tracking, preview, and restore functionality.
    """
    
    changes_detected = Signal(bool)  # Emits True if there are unsaved changes
    
    def __init__(self):
        super().__init__()
        self._original: Optional[ConfigSnapshot] = None
        self._current: Optional[ConfigSnapshot] = None
        self._has_changes = False
    
    def set_original_state(self, snapshot: ConfigSnapshot):
        """Set the original/saved state to compare against."""
        self._original = snapshot.copy()
        self._current = snapshot.copy()
        self._has_changes = False
        self.changes_detected.emit(False)
    
    def update_current_state(self, snapshot: ConfigSnapshot):
        """Update the current state and check for changes."""
        self._current = snapshot
        self._check_changes()
    
    def update_launcher_config(self, key: str, value: Any):
        """Update a specific launcher config value."""
        if self._current is None:
            self._current = ConfigSnapshot()
        self._current.launcher[key] = value
        self._check_changes()
    
    def update_server_config(self, key: str, value: Any):
        """Update a specific server config value."""
        if self._current is None:
            self._current = ConfigSnapshot()
        self._current.server_config[key] = value
        self._check_changes()
    
    def _check_changes(self):
        """Check if current state differs from original."""
        if self._original is None or self._current is None:
            has_changes = False
        else:
            has_changes = (
                self._original.launcher != self._current.launcher or
                self._original.server_config != self._current.server_config
            )
        
        if has_changes != self._has_changes:
            self._has_changes = has_changes
            self.changes_detected.emit(has_changes)
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_changes
    
    def get_changes_summary(self) -> Dict[str, List[tuple]]:
        """
        Get a summary of all changes.
        Returns dict with 'launcher' and 'server_config' keys,
        each containing list of (field, old_value, new_value) tuples.
        """
        changes = {
            'launcher': [],
            'server_config': []
        }
        
        if self._original is None or self._current is None:
            return changes
        
        # Compare launcher config
        all_launcher_keys = set(self._original.launcher.keys()) | set(self._current.launcher.keys())
        for key in all_launcher_keys:
            old_val = self._original.launcher.get(key)
            new_val = self._current.launcher.get(key)
            if old_val != new_val:
                changes['launcher'].append((key, old_val, new_val))
        
        # Compare server config
        all_server_keys = set(self._original.server_config.keys()) | set(self._current.server_config.keys())
        for key in all_server_keys:
            old_val = self._original.server_config.get(key)
            new_val = self._current.server_config.get(key)
            if old_val != new_val:
                changes['server_config'].append((key, old_val, new_val))
        
        return changes
    
    def restore_original(self):
        """Restore current state to original."""
        if self._original:
            self._current = self._original.copy()
            self._has_changes = False
            self.changes_detected.emit(False)
            return self._current
        return None
    
    def mark_saved(self):
        """Mark current state as saved (becomes new original)."""
        if self._current:
            self._original = self._current.copy()
            self._has_changes = False
            self.changes_detected.emit(False)
    
    def get_current_state(self) -> Optional[ConfigSnapshot]:
        """Get the current configuration state."""
        return self._current
    
    def get_original_state(self) -> Optional[ConfigSnapshot]:
        """Get the original configuration state."""
        return self._original


class ChangePreviewDialog(QDialog):
    """Dialog to preview and confirm configuration changes."""
    
    def __init__(self, changes: Dict[str, List[tuple]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("config.preview_changes"))
        self.setMinimumSize(600, 400)
        self.setModal(True)
        
        self._setup_ui(changes)
    
    def _setup_ui(self, changes: Dict[str, List[tuple]]):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"<h3>{tr('config.changes_to_save')}</h3>")
        layout.addWidget(header)
        
        # Scroll area for changes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        has_changes = False
        
        # Launcher changes
        if changes.get('launcher'):
            has_changes = True
            launcher_box = QGroupBox(tr("tabs.launcher"))
            launcher_layout = QVBoxLayout(launcher_box)
            
            for field, old_val, new_val in changes['launcher']:
                change_text = self._format_change(field, old_val, new_val)
                label = QLabel(change_text)
                label.setWordWrap(True)
                label.setTextFormat(Qt.RichText)
                launcher_layout.addWidget(label)
            
            content_layout.addWidget(launcher_box)
        
        # Server config changes
        if changes.get('server_config'):
            has_changes = True
            config_box = QGroupBox(tr("tabs.config"))
            config_layout = QVBoxLayout(config_box)
            
            for field, old_val, new_val in changes['server_config']:
                change_text = self._format_change(field, old_val, new_val)
                label = QLabel(change_text)
                label.setWordWrap(True)
                label.setTextFormat(Qt.RichText)
                config_layout.addWidget(label)
            
            content_layout.addWidget(config_box)
        
        if not has_changes:
            no_changes = QLabel(tr("config.no_changes"))
            no_changes.setAlignment(Qt.AlignCenter)
            no_changes.setStyleSheet("color: gray; padding: 20px;")
            content_layout.addWidget(no_changes)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Buttons
        button_box = QDialogButtonBox()
        
        if has_changes:
            self.btn_save = QPushButton(tr("common.save"))
            self.btn_save.setObjectName("primary")
            button_box.addButton(self.btn_save, QDialogButtonBox.AcceptRole)
        
        self.btn_cancel = QPushButton(tr("common.cancel"))
        button_box.addButton(self.btn_cancel, QDialogButtonBox.RejectRole)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
    
    def _format_change(self, field: str, old_val: Any, new_val: Any) -> str:
        """Format a single change for display."""
        old_display = self._truncate_value(old_val)
        new_display = self._truncate_value(new_val)
        
        return f"""
        <b>{field}</b><br>
        <span style="color: #c42b1c;">- {old_display}</span><br>
        <span style="color: #0f7b0f;">+ {new_display}</span>
        """
    
    def _truncate_value(self, value: Any, max_len: int = 100) -> str:
        """Truncate long values for display."""
        if value is None:
            return "<i>(empty)</i>"
        
        str_val = str(value)
        if len(str_val) > max_len:
            return str_val[:max_len] + "..."
        return str_val


class UnsavedChangesDialog(QDialog):
    """Dialog shown when navigating away with unsaved changes."""
    
    SAVE = 1
    DISCARD = 2
    CANCEL = 3
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("config.unsaved_changes"))
        self.setModal(True)
        self.result_action = self.CANCEL
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Message
        msg = QLabel(tr("config.unsaved_changes_msg"))
        msg.setWordWrap(True)
        layout.addWidget(msg)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton(tr("common.save"))
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_discard = QPushButton(tr("config.discard_changes"))
        self.btn_discard.setObjectName("danger")
        self.btn_discard.clicked.connect(self._on_discard)
        btn_layout.addWidget(self.btn_discard)
        
        self.btn_cancel = QPushButton(tr("common.cancel"))
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _on_save(self):
        self.result_action = self.SAVE
        self.accept()
    
    def _on_discard(self):
        self.result_action = self.DISCARD
        self.accept()
    
    def _on_cancel(self):
        self.result_action = self.CANCEL
        self.reject()
    
    def get_result(self) -> int:
        return self.result_action
