"""
Profile Dialog - Create/Edit Server Profile
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

from shared.utils.locale_manager import tr


class ProfileDialog(QDialog):
    """Dialog for creating or editing a server profile."""
    
    def __init__(self, parent=None, profile_data: dict = None):
        super().__init__(parent)
        self.profile_data = profile_data or {}
        self.result_data = None
        
        self.setWindowTitle(tr("profiles.new_profile") if not profile_data else tr("profiles.edit_profile"))
        self.setMinimumWidth(500)
        self.setModal(True)
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        # Profile name
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText(tr("profiles.profile_name"))
        form.addRow(tr("profiles.profile_name") + ":", self.txt_name)
        
        # Server path
        path_layout = QHBoxLayout()
        self.txt_server_path = QLineEdit()
        self.txt_server_path.setPlaceholderText("D:\\DayZServer")
        self.txt_server_path.setReadOnly(True)
        path_layout.addWidget(self.txt_server_path)
        
        self.btn_browse = QPushButton(tr("common.browse"))
        self.btn_browse.clicked.connect(self._browse_server_path)
        path_layout.addWidget(self.btn_browse)
        form.addRow(tr("profiles.server_path") + ":", path_layout)
        
        # Workshop path
        workshop_layout = QHBoxLayout()
        self.txt_workshop_path = QLineEdit()
        self.txt_workshop_path.setPlaceholderText("C:\\Steam\\steamapps\\workshop\\content\\221100")
        self.txt_workshop_path.setReadOnly(True)
        workshop_layout.addWidget(self.txt_workshop_path)
        
        self.btn_browse_workshop = QPushButton(tr("common.browse"))
        self.btn_browse_workshop.clicked.connect(self._browse_workshop_path)
        workshop_layout.addWidget(self.btn_browse_workshop)
        form.addRow(tr("profiles.workshop_path") + ":", workshop_layout)
        
        layout.addLayout(form)
        
        # Validation status
        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("color: orange;")
        layout.addWidget(self.lbl_status)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton(tr("common.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton(tr("common.save"))
        self.btn_save.clicked.connect(self._save)
        self.btn_save.setDefault(True)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)
    
    def _load_data(self):
        """Load existing profile data if editing."""
        if self.profile_data:
            self.txt_name.setText(self.profile_data.get("name", ""))
            self.txt_server_path.setText(self.profile_data.get("server_path", ""))
            self.txt_workshop_path.setText(self.profile_data.get("workshop_path", ""))
            self._validate_paths()
    
    def _browse_server_path(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("profiles.select_server_path"),
            self.txt_server_path.text() or "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            self.txt_server_path.setText(folder)
            # Auto-fill name if empty
            if not self.txt_name.text():
                self.txt_name.setText(Path(folder).name)
            self._validate_paths()
    
    def _browse_workshop_path(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("profiles.select_workshop_path"),
            self.txt_workshop_path.text() or "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            self.txt_workshop_path.setText(folder)
    
    def _validate_paths(self):
        """Validate the server path and show status."""
        server_path = Path(self.txt_server_path.text())
        
        if not server_path.exists():
            self.lbl_status.setText(tr('validation.invalid_path'))
            self.lbl_status.setStyleSheet("color: red;")
            return False
        
        exe_path = server_path / "DayZServer_x64.exe"
        if not exe_path.exists():
            self.lbl_status.setText(tr('validation.server_not_found'))
            self.lbl_status.setStyleSheet("color: orange;")
            return False
        
        self.lbl_status.setText(tr('validation.server_valid'))
        self.lbl_status.setStyleSheet("color: green;")
        return True
    
    def _save(self):
        """Save the profile."""
        name = self.txt_name.text().strip()
        server_path = self.txt_server_path.text().strip()
        workshop_path = self.txt_workshop_path.text().strip()
        
        if not name:
            QMessageBox.warning(self, tr("common.warning"), tr("validation.name_required"))
            return
        
        if not server_path:
            QMessageBox.warning(self, tr("common.warning"), tr("validation.path_required"))
            return
        
        self.result_data = {
            "name": name,
            "server_path": server_path,
            "workshop_path": workshop_path
        }
        self.accept()
    
    def get_result(self) -> dict:
        return self.result_data
