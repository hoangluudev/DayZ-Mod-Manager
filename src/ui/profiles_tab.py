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
from src.ui.base import BaseTab, CardWidget, EmptyStateWidget
from src.ui.factories import create_action_button, create_status_label
from src.ui.theme_manager import ThemeManager


class ProfileCard(CardWidget):
    """A card widget displaying profile information."""
    
    selected = Signal(str)  # profile name
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    
    def __init__(self, profile_data: dict, parent=None):
        super().__init__(parent, clickable=True)
        self.profile_data = profile_data
        self.name = profile_data.get("name", "Unknown")
        self._setup_ui()
        
        # Connect click to selection
        self.clicked.connect(lambda: self.selected.emit(self.name))
    
    def _setup_ui(self):
        # Header with name and buttons
        header = QHBoxLayout()
        
        self.lbl_name = QLabel(f"<b>{self.name}</b>")
        self.lbl_name.setStyleSheet("font-size: 14px;")
        header.addWidget(self.lbl_name)
        header.addStretch()
        
        # Edit button
        self.btn_edit = create_action_button(
            "edit", tooltip=tr("common.edit"), size=18, icon_only=True,
            on_click=lambda: self.edit_requested.emit(self.name)
        )
        header.addWidget(self.btn_edit)
        
        # Delete button
        self.btn_delete = create_action_button(
            "trash", tooltip=tr("common.delete"), size=18, icon_only=True,
            on_click=lambda: self.delete_requested.emit(self.name)
        )
        header.addWidget(self.btn_delete)
        
        self.card_layout.addLayout(header)
        
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
        
        self.card_layout.addLayout(path_layout)
        
        # Status
        self._add_status(server_path)
    
    def _add_status(self, server_path: str):
        """Check if server path is valid and show status."""
        path = Path(server_path)
        exe_exists = (path / "DayZServer_x64.exe").exists() if path.exists() else False
        
        if exe_exists:
            status_widget = create_status_label(
                tr('validation.server_valid'), "success"
            )
        elif path.exists():
            status_widget = create_status_label(
                tr('validation.server_not_found'), "warning"
            )
        else:
            status_widget = create_status_label(
                tr('validation.invalid_path'), "error"
            )
        
        self.card_layout.addWidget(status_widget)


class ProfilesTab(BaseTab):
    """Tab for managing server profiles."""
    
    profile_selected = Signal(dict)  # Emits selected profile data
    
    def __init__(self, parent=None):
        super().__init__(parent, scrollable=False, title_key="profiles.title")
        self.profile_manager = ProfileManager()
        self.current_profile = None
        
        self._setup_content()
        self._load_profiles()
    
    def _setup_content(self):
        # Add new profile button to header
        self.btn_new = create_action_button(
            "plus", text=tr('profiles.new_profile'), size=16,
            on_click=self._create_profile
        )
        self.btn_new.setStyleSheet("padding: 8px 16px;")
        self.add_header_button(self.btn_new)
        
        # Current profile indicator
        self.lbl_current = QLabel()
        self.lbl_current.setStyleSheet(
            f"color: {ThemeManager.get_accent_color()}; font-size: 12px; padding: 4px 0;"
        )
        self.add_widget(self.lbl_current)
        
        # Profiles container
        self.profiles_layout = QVBoxLayout()
        self.profiles_layout.setSpacing(8)
        self.add_layout(self.profiles_layout)
        
        # Empty state
        self.empty_state = EmptyStateWidget(
            message=tr("profiles.no_profiles"),
            icon_name="folder",
            action_text=tr("profiles.new_profile"),
        )
        self.empty_state.action_clicked.connect(self._create_profile)
        self.add_widget(self.empty_state)
        
        self.add_stretch()
    
    def _load_profiles(self):
        """Load and display all profiles."""
        # Clear existing cards
        while self.profiles_layout.count():
            item = self.profiles_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        profiles = self.profile_manager.get_all_profiles()
        
        if not profiles:
            self.empty_state.show()
            self.lbl_current.hide()
            return
        
        self.empty_state.hide()
        
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
        if self.confirm_dialog(tr("profiles.confirm_delete")):
            self.profile_manager.delete_profile(name)
            if self.current_profile == name:
                self.current_profile = None
            self._load_profiles()
    
    def update_texts(self):
        """Update UI texts for language change."""
        super().update_texts()
        self.btn_new.setText(tr('profiles.new_profile'))
        self.empty_state.set_message(tr("profiles.no_profiles"))
        self.empty_state.set_action_text(tr("profiles.new_profile"))
        self._update_current_indicator()
        self._load_profiles()
