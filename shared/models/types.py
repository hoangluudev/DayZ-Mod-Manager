"""
Type Definitions and Protocols
Shared type hints and protocols for the application.
"""

from typing import Protocol, Dict, Any, List, Optional, Callable, TypeVar
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# Generic Type Variables
# ============================================================================

T = TypeVar('T')
ConfigDict = Dict[str, Any]


# ============================================================================
# Observer Protocol
# ============================================================================

class Observer(Protocol):
    """Protocol for observer pattern callbacks."""
    
    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Called when the observed subject changes."""
        ...


# ============================================================================
# Manager Protocols
# ============================================================================

class SettingsProvider(Protocol):
    """Protocol for settings providers."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        ...
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        ...
    
    def save(self) -> bool:
        """Save settings to persistent storage."""
        ...


class LocaleProvider(Protocol):
    """Protocol for locale/translation providers."""
    
    def get(self, key: str, **kwargs: Any) -> str:
        """Get a translated string."""
        ...
    
    def set_language(self, lang_code: str) -> None:
        """Change the current language."""
        ...
    
    @property
    def current_language(self) -> str:
        """Get current language code."""
        ...


# ============================================================================
# Profile Types
# ============================================================================

@dataclass
class ProfileData:
    """Profile data structure."""
    name: str
    server_path: str
    workshop_path: str
    steamcmd_path: str
    mods: List[str]
    config: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileData":
        """Create ProfileData from dictionary."""
        return cls(
            name=data.get("name", ""),
            server_path=data.get("server_path", ""),
            workshop_path=data.get("workshop_path", ""),
            steamcmd_path=data.get("steamcmd_path", ""),
            mods=data.get("mods", []),
            config=data.get("config", {}),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "server_path": self.server_path,
            "workshop_path": self.workshop_path,
            "steamcmd_path": self.steamcmd_path,
            "mods": self.mods,
            "config": self.config,
        }


# ============================================================================
# Mod Types
# ============================================================================

class ModStatus(str, Enum):
    """Mod installation status."""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    INSTALLING = "installing"
    ERROR = "error"


@dataclass
class ModInfo:
    """Mod information structure."""
    workshop_id: str
    name: str
    status: ModStatus
    size: int = 0
    last_updated: Optional[str] = None
    local_path: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        """Get display name for UI."""
        return self.name or f"Mod {self.workshop_id}"


# ============================================================================
# Result Types
# ============================================================================

@dataclass
class Result:
    """Generic result type for operations that can fail."""
    success: bool
    message: str = ""
    data: Any = None
    error: Optional[Exception] = None
    
    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "Result":
        """Create a success result."""
        return cls(success=True, data=data, message=message)
    
    @classmethod
    def fail(cls, message: str, error: Optional[Exception] = None) -> "Result":
        """Create a failure result."""
        return cls(success=False, message=message, error=error)


# ============================================================================
# Callback Types
# ============================================================================

ProgressCallback = Callable[[int, int, str], None]  # (current, total, message)
CompletionCallback = Callable[[Result], None]
ErrorCallback = Callable[[Exception], None]
