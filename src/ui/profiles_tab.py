"""
Profiles Tab - Server Profile Management
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from src.core.profile_manager import ProfileManager
from src.utils.locale_manager import tr
from src.ui.profile_dialog import ProfileDialog
from src.ui.icons import Icons
from src.ui.widgets import IconButton


class ProfileCard(QFrame):
    """A card widget displaying profile information."""
    
    selected = Signal(str)  # profile name
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    
    def __init__(self, profile_data: dict, parent=None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.name = profile_data.get("name", "Unknown")
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setCursor(Qt.PointingHandCursor)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header with name and buttons
        header = QHBoxLayout()
        
        self.lbl_name = QLabel(f"<b>{self.name}</b>")
        self.lbl_name.setStyleSheet("font-size: 14px;")
        header.addWidget(self.lbl_name)
        header.addStretch()
        
        # Edit button with SVG icon
        self.btn_edit = IconButton(
            icon_name="edit",
            size=18,
            icon_only=True
        )
        self.btn_edit.setToolTip(tr("common.edit"))
        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.name))
        header.addWidget(self.btn_edit)
        
        # Delete button with SVG icon
        self.btn_delete = IconButton(
            icon_name="trash",
            size=18,
            icon_only=True
        )
        self.btn_delete.setToolTip(tr("common.delete"))
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.name))
        header.addWidget(self.btn_delete)
        
        layout.addLayout(header)
        
        # Server path with folder icon
        server_path = self.profile_data.get("server_path", "")
        path_layout = QHBoxLayout()
        path_layout.setSpacing(4)
        
        folder_label = QLabel()
        folder_label.setPixmap(Icons.get_pixmap("folder", size=14))
        path_layout.addWidget(folder_label)
        
        self.lbl_path = QLabel(server_path)
        self.lbl_path.setStyleSheet("color: #aaa; font-size: 11px;")
        self.lbl_path.setWordWrap(True)
        path_layout.addWidget(self.lbl_path, stretch=1)
        
        layout.addLayout(path_layout)
        
        # Status
        self._check_status(server_path)
    
    def _check_status(self, server_path: str):
        """Check if server path is valid."""
        path = Path(server_path)
        exe_exists = (path / "DayZServer_x64.exe").exists() if path.exists() else False
        
        status_layout = QHBoxLayout()
        status_layout.setSpacing(4)
        
        if exe_exists:
            status_text = tr('validation.server_valid')
            icon_name = "success"
            color = "#4caf50"
        elif path.exists():
            status_text = tr('validation.server_not_found')
            icon_name = "warning"
            color = "#ff9800"
        else:
            status_text = tr('validation.invalid_path')
            icon_name = "error"
            color = "#f44336"
        
        status_icon = QLabel()
        status_icon.setPixmap(Icons.get_pixmap(icon_name, color=color, size=14))
        status_layout.addWidget(status_icon)
        
        self.lbl_status = QLabel(status_text)
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 11px;")
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch()
        
        self.layout().addLayout(status_layout)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.name)
        super().mousePressEvent(event)


class ProfilesTab(QWidget):
    """Tab for managing server profiles."""
    
    profile_selected = Signal(dict)  # Emits selected profile data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile_manager = ProfileManager()
        self.current_profile = None
        
        self._setup_ui()
        self._load_profiles()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        
        self.lbl_title = QLabel(f"<h2>{tr('profiles.title')}</h2>")
        header.addWidget(self.lbl_title)
        header.addStretch()
        
        self.btn_new = IconButton(
            icon_name="plus",
            text=tr('profiles.new_profile'),
            size=16
        )
        self.btn_new.setStyleSheet("padding: 8px 16px;")
        self.btn_new.clicked.connect(self._create_profile)
        header.addWidget(self.btn_new)
        
        layout.addLayout(header)
        
        # Current profile indicator
        self.lbl_current = QLabel()
        self.lbl_current.setStyleSheet("color: #0078d4; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self.lbl_current)
        
        # Profiles container
        self.profiles_layout = QVBoxLayout()
        self.profiles_layout.setSpacing(8)
        layout.addLayout(self.profiles_layout)
        
        # Empty state
        self.lbl_empty = QLabel(tr("profiles.no_profiles"))
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet("color: gray; padding: 50px; font-size: 14px;")
        layout.addWidget(self.lbl_empty)
        
        layout.addStretch()
    
    def _load_profiles(self):
        """Load and display all profiles."""
        # Clear existing cards
        while self.profiles_layout.count():
            item = self.profiles_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        profiles = self.profile_manager.get_all_profiles()
        
        if not profiles:
            self.lbl_empty.show()
            self.lbl_current.hide()
            return
        
        self.lbl_empty.hide()
        
        for profile in profiles:
            profile_data = {
                "name": profile.name,
                "server_path": str(profile.server_path),
                "workshop_path": str(profile.workshop_path) if getattr(profile, 'workshop_path', None) else "",
                "keys_folder": str(profile.keys_folder) if profile.keys_folder else "",
                "selected_mods": list(getattr(profile, 'selected_mods', []) or []),
            }
            
            card = ProfileCard(profile_data)
            card.selected.connect(self._on_profile_selected)
            card.edit_requested.connect(self._edit_profile)
            card.delete_requested.connect(self._delete_profile)
            self.profiles_layout.addWidget(card)
        
        # Update current profile indicator
        self._update_current_indicator()
    
    def _update_current_indicator(self):
        """Update the current profile indicator."""
        if self.current_profile:
            self.lbl_current.setText(f"🔹 {tr('profiles.current')}: {self.current_profile}")
            self.lbl_current.show()
        else:
            self.lbl_current.hide()
    
    def _on_profile_selected(self, name: str):
        """Handle profile selection."""
        self.current_profile = name
        profile = self.profile_manager.get_profile(name)
        
        if profile:
            profile_data = {
                "name": profile.name,
                "server_path": str(profile.server_path),
                "workshop_path": str(profile.workshop_path) if getattr(profile, 'workshop_path', None) else "",
                "keys_folder": str(profile.keys_folder) if profile.keys_folder else "",
                "selected_mods": list(getattr(profile, 'selected_mods', []) or []),
            }
            self.profile_selected.emit(profile_data)
            self._update_current_indicator()
    
    def _create_profile(self):
        """Show dialog to create new profile."""
        dialog = ProfileDialog(self)
        if dialog.exec():
            data = dialog.get_result()
            if data:
                profile = self.profile_manager.create_profile(
                    data["name"],
                    Path(data["server_path"]),
                    workshop_path=Path(data["workshop_path"]) if data.get("workshop_path") else None,
                )
                self.profile_manager.save_profile(profile)
                self._load_profiles()
                self._on_profile_selected(data["name"])
    
    def _edit_profile(self, name: str):
        """Show dialog to edit existing profile."""
        profile = self.profile_manager.get_profile(name)
        if not profile:
            return
        
        profile_data = {
            "name": profile.name,
            "server_path": str(profile.server_path),
            "workshop_path": str(profile.workshop_path) if getattr(profile, 'workshop_path', None) else "",
        }
        
        dialog = ProfileDialog(self, profile_data)
        if dialog.exec():
            data = dialog.get_result()
            if data:
                # Delete old and create new if name changed
                if name != data["name"]:
                    self.profile_manager.delete_profile(name)
                
                new_profile = self.profile_manager.create_profile(
                    data["name"],
                    Path(data["server_path"]),
                    workshop_path=Path(data["workshop_path"]) if data.get("workshop_path") else None,
                    selected_mods=list(getattr(profile, 'selected_mods', []) or []),
                )
                self.profile_manager.save_profile(new_profile)
                self._load_profiles()
    
    def _delete_profile(self, name: str):
        """Delete a profile after confirmation."""
        reply = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("profiles.confirm_delete"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.profile_manager.delete_profile(name)
            if self.current_profile == name:
                self.current_profile = None
            self._load_profiles()
    
    def update_texts(self):
        """Update UI texts for language change."""
        self.lbl_title.setText(f"<h2>{tr('profiles.title')}</h2>")
        self.btn_new.setText(tr('profiles.new_profile'))
        self.lbl_empty.setText(tr("profiles.no_profiles"))
        self._update_current_indicator()
        self._load_profiles()
