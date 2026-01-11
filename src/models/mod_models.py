"""
Mod Data Models
Defines data structures for mods, integrity status, and related entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path


class ModStatus(Enum):
    """Status of a mod's installation state."""
    NOT_INSTALLED = "not_installed"      # Mod not present on server
    FULLY_INSTALLED = "fully_installed"  # Mod folder + bikey present
    PARTIAL_FOLDER_ONLY = "folder_only"  # Mod folder exists, bikey missing
    PARTIAL_BIKEY_ONLY = "bikey_only"    # Bikey exists, mod folder missing
    OUTDATED = "outdated"                # Installed but newer version available
    CORRUPTED = "corrupted"              # Files exist but corrupted/incomplete


class IntegrityStatus(Enum):
    """Result of integrity check."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class BikeyInfo:
    """Information about a .bikey file."""
    name: str
    path: Path
    size: int
    modified_date: datetime
    
    @property
    def exists(self) -> bool:
        return self.path.exists()


@dataclass
class ModInfo:
    """Complete information about a DayZ mod."""
    # Basic identification
    name: str                           # Mod folder name (e.g., "@CF")
    workshop_id: Optional[str] = None   # Steam Workshop ID
    
    # Paths
    source_path: Optional[Path] = None  # Workshop source location
    installed_path: Optional[Path] = None  # Server mod location
    
    # Version and metadata
    version: Optional[str] = None
    last_updated: Optional[datetime] = None
    size_bytes: int = 0
    
    # Status
    status: ModStatus = ModStatus.NOT_INSTALLED
    
    # Files
    bikeys: List[BikeyInfo] = field(default_factory=list)
    file_count: int = 0
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)  # List of workshop IDs
    
    @property
    def is_installed(self) -> bool:
        """Check if mod is at least partially installed."""
        return self.status in [
            ModStatus.FULLY_INSTALLED,
            ModStatus.PARTIAL_FOLDER_ONLY,
            ModStatus.PARTIAL_BIKEY_ONLY,
            ModStatus.OUTDATED
        ]
    
    @property
    def is_fully_installed(self) -> bool:
        """Check if mod is completely installed."""
        return self.status == ModStatus.FULLY_INSTALLED
    
    @property
    def needs_bikey(self) -> bool:
        """Check if mod needs bikey installation."""
        return self.status == ModStatus.PARTIAL_FOLDER_ONLY
    
    @property
    def needs_folder(self) -> bool:
        """Check if mod folder needs installation."""
        return self.status in [ModStatus.NOT_INSTALLED, ModStatus.PARTIAL_BIKEY_ONLY]


@dataclass
class IntegrityIssue:
    """Represents a single integrity issue found during checking."""
    severity: IntegrityStatus
    category: str           # e.g., "bikey", "folder", "file", "duplicate"
    message: str
    mod_name: Optional[str] = None
    file_path: Optional[Path] = None
    suggestion: Optional[str] = None


@dataclass
class IntegrityReport:
    """Complete report from an integrity check."""
    timestamp: datetime
    server_path: Path
    total_mods_checked: int = 0
    
    # Status counts
    fully_installed: int = 0
    partial_installed: int = 0
    missing: int = 0
    corrupted: int = 0
    
    # Issues found
    issues: List[IntegrityIssue] = field(default_factory=list)
    
    # Detailed mod info
    mods: List[ModInfo] = field(default_factory=list)
    
    @property
    def status(self) -> IntegrityStatus:
        """Overall status of the integrity check."""
        if any(i.severity == IntegrityStatus.FAILED for i in self.issues):
            return IntegrityStatus.FAILED
        if any(i.severity == IntegrityStatus.WARNING for i in self.issues):
            return IntegrityStatus.WARNING
        return IntegrityStatus.PASSED
    
    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0
    
    @property
    def critical_issues(self) -> List[IntegrityIssue]:
        return [i for i in self.issues if i.severity == IntegrityStatus.FAILED]
    
    @property
    def warnings(self) -> List[IntegrityIssue]:
        return [i for i in self.issues if i.severity == IntegrityStatus.WARNING]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "server_path": str(self.server_path),
            "total_mods_checked": self.total_mods_checked,
            "status": self.status.value,
            "counts": {
                "fully_installed": self.fully_installed,
                "partial_installed": self.partial_installed,
                "missing": self.missing,
                "corrupted": self.corrupted
            },
            "issues": [
                {
                    "severity": i.severity.value,
                    "category": i.category,
                    "message": i.message,
                    "mod_name": i.mod_name,
                    "file_path": str(i.file_path) if i.file_path else None,
                    "suggestion": i.suggestion
                }
                for i in self.issues
            ]
        }


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
