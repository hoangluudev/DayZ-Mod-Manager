"""
Profile Data Models
Defines data structures for server profiles.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from pathlib import Path


@dataclass
class ServerProfile:
    """Server profile containing paths and configuration."""
    name: str
    server_path: Path

    # Workshop
    workshop_path: Optional[Path] = None

    # Selected mods (for -mod generation / filtering integrity checks)
    # Format: "<workshop_id>:<mod_folder>" e.g. "1559212036:@CF"
    selected_mods: List[str] = field(default_factory=list)

    # Derived paths (can be customized)
    keys_folder: Optional[Path] = None
    mods_folder: Optional[Path] = None
    config_path: Optional[Path] = None

    # Metadata
    created_date: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None

    def __post_init__(self):
        """Set default paths based on server_path if not provided."""
        if self.keys_folder is None:
            self.keys_folder = self.server_path / "keys"
        if self.mods_folder is None:
            self.mods_folder = self.server_path
        if self.config_path is None:
            self.config_path = self.server_path / "serverDZ.cfg"

    @property
    def server_exe(self) -> Path:
        """Path to server executable."""
        return self.server_path / "DayZServer_x64.exe"

    @property
    def is_valid(self) -> bool:
        """Check if server path is valid."""
        return self.server_path.exists() and self.server_exe.exists()
