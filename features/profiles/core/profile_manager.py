"""
Profile Manager
Handles server profile CRUD operations with JSON persistence.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import asdict
import uuid

from ..models.profile_models import ServerProfile


class ProfileManager:
    """
    Manages server profiles with file-based persistence.
    
    Features:
    - Create, read, update, delete profiles
    - Validate profile paths
    - Export/import profiles
    
    Usage:
        manager = ProfileManager()
        profile = manager.create_profile("My Server", Path("C:/DayZServer"))
        manager.save_profile(profile)
    """
    
    def __init__(self, profiles_dir: Optional[str] = None):
        """
        Initialize ProfileManager.
        
        Args:
            profiles_dir: Directory to store profile JSON files
        """
        if profiles_dir:
            self._profiles_dir = Path(profiles_dir)
        else:
            # Use storage_paths module for proper path resolution
            from shared.core.storage_paths import get_profiles_path
            self._profiles_dir = get_profiles_path()
        
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, ServerProfile] = {}
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all profiles from disk."""
        for profile_file in self._profiles_dir.glob("*.json"):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profile = ServerProfile(
                        name=data['name'],
                        server_path=Path(data['server_path']),
                        workshop_path=Path(data['workshop_path']) if data.get('workshop_path') else None,
                        selected_mods=list(data.get('selected_mods') or []),
                        keys_folder=Path(data['keys_folder']) if data.get('keys_folder') else None,
                        mods_folder=Path(data['mods_folder']) if data.get('mods_folder') else None,
                        config_path=Path(data['config_path']) if data.get('config_path') else None,
                    )
                    self._profiles[profile.name] = profile
            except Exception as e:
                print(f"Error loading profile {profile_file}: {e}")
    
    def create_profile(
        self,
        name: str,
        server_path: Path,
        workshop_path: Optional[Path] = None,
        selected_mods: Optional[List[str]] = None,
    ) -> ServerProfile:
        """Create a new profile."""
        profile = ServerProfile(
            name=name,
            server_path=server_path,
            workshop_path=workshop_path,
            selected_mods=list(selected_mods or []),
        )
        return profile
    
    def save_profile(self, profile: ServerProfile) -> bool:
        """Save a profile to disk."""
        try:
            profile_path = self._profiles_dir / f"{self._sanitize_filename(profile.name)}.json"
            data = {
                'name': profile.name,
                'server_path': str(profile.server_path),
                'workshop_path': str(profile.workshop_path) if getattr(profile, 'workshop_path', None) else None,
                'selected_mods': list(getattr(profile, 'selected_mods', []) or []),
                'keys_folder': str(profile.keys_folder) if profile.keys_folder else None,
                'mods_folder': str(profile.mods_folder) if profile.mods_folder else None,
                'config_path': str(profile.config_path) if profile.config_path else None,
                'created_date': profile.created_date.isoformat(),
                'last_used': profile.last_used.isoformat() if profile.last_used else None
            }
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self._profiles[profile.name] = profile
            return True
        except Exception as e:
            print(f"Error saving profile: {e}")
            return False
    
    def get_profile(self, name: str) -> Optional[ServerProfile]:
        """Get a profile by name."""
        return self._profiles.get(name)
    
    def get_all_profiles(self) -> List[ServerProfile]:
        """Get all profiles."""
        return list(self._profiles.values())
    
    def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        if name in self._profiles:
            profile_path = self._profiles_dir / f"{self._sanitize_filename(name)}.json"
            try:
                if profile_path.exists():
                    profile_path.unlink()
                del self._profiles[name]
                return True
            except Exception as e:
                print(f"Error deleting profile: {e}")
        return False
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize profile name for use as filename."""
        return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
