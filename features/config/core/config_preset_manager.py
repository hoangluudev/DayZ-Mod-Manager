"""
Config Preset Manager
Handles save/load/restore config presets for mod configuration files.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field


@dataclass
class ConfigPreset:
    """Represents a saved config preset."""
    name: str
    file_path: str  # Relative path from server config folder
    content: str
    created_at: str = ""
    description: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class ConfigPresetsData:
    """Container for all presets of a profile."""
    defaults: Dict[str, str] = field(default_factory=dict)  # file_path -> content (default backup)
    presets: Dict[str, List[ConfigPreset]] = field(default_factory=dict)  # file_path -> list of presets


class ConfigPresetManager:
    """
    Manages configuration presets for mod config files.
    
    Features:
    - Save as default (backup for restore)
    - Save named presets
    - Load presets by name
    - Restore from default
    - List available presets for a file
    """
    
    def __init__(self, profile_data: dict, scope: str = "mods"):
        """
        Initialize with profile data.
        
        Args:
            profile_data: Profile dictionary containing server_path
        """
        self.profile_data = profile_data
        self.scope = (scope or "mods").strip() or "mods"

        self.server_path = Path(profile_data.get("server_path", ""))
        if self.server_path.is_file():
            self.server_path = self.server_path.parent
        self.config_root = self.server_path / "config"

        # Get presets storage path
        from shared.core.storage_paths import get_default_storage_path
        self.presets_dir = get_default_storage_path() / "config_presets"
        self.presets_dir.mkdir(parents=True, exist_ok=True)

        # v2 folder-based storage
        self.profile_name = profile_data.get("name", "default")
        self.profile_safe = self._safe_filename(self.profile_name)
        self.scope_safe = self._safe_filename(self.scope)

        self.profile_dir = self.presets_dir / self.profile_safe
        self.scope_dir = self.profile_dir / self.scope_safe
        self.defaults_dir = self.scope_dir / "defaults"
        self.presets_root_dir = self.scope_dir / "presets"
        self.defaults_dir.mkdir(parents=True, exist_ok=True)
        self.presets_root_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_profile_marker()

        # Legacy JSON files (v1) for migration
        self._legacy_json_files = [
            self.presets_dir / f"{self.profile_safe}_presets.json",
            self.presets_dir / f"{self.profile_safe}_{self.scope_safe}_presets.json",
        ]

        # Cached data used only for legacy migration (v1)
        self._data = ConfigPresetsData()
        self._maybe_migrate_from_legacy_json()
    
    def _safe_filename(self, name: str) -> str:
        """Convert name to safe filename."""
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

    def _ensure_profile_marker(self):
        """Write a marker file containing the original profile name for nicer UI display."""
        marker = self.profile_dir / "profile.json"
        if marker.exists():
            return
        try:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps({"name": self.profile_name}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _read_profile_marker(self, profile_safe: str) -> str:
        marker = self.presets_dir / profile_safe / "profile.json"
        if marker.exists():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                name = str(data.get("name") or "").strip()
                if name:
                    return name
            except Exception:
                pass
        return profile_safe

    def _preset_dir(self, preset_name: str, profile_safe: Optional[str] = None) -> Path:
        profile_safe = profile_safe or self.profile_safe
        safe_name = self._safe_filename(preset_name)
        return self.presets_dir / profile_safe / self.scope_safe / "presets" / safe_name

    def _preset_meta_path(self, preset_dir: Path) -> Path:
        return preset_dir / ".meta.json"

    def _default_backup_path(self, rel_path: str) -> Path:
        return self.defaults_dir / Path(rel_path)

    def _list_preset_dirs(self, profile_safe: Optional[str] = None) -> List[Path]:
        profile_safe = profile_safe or self.profile_safe
        root = self.presets_dir / profile_safe / self.scope_safe / "presets"
        if not root.exists():
            return []
        return sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())

    def _maybe_migrate_from_legacy_json(self):
        """Migrate legacy JSON presets into v2 folder-based storage (one-time)."""
        migrated_marker = self.scope_dir / ".migrated_from_json"
        if migrated_marker.exists():
            return

        legacy_file = next((p for p in self._legacy_json_files if p.exists()), None)
        if not legacy_file:
            return

        try:
            data = json.loads(legacy_file.read_text(encoding="utf-8"))
            defaults: Dict[str, str] = data.get("defaults", {}) or {}
            presets_data: Dict[str, list] = data.get("presets", {}) or {}

            # defaults
            for rel_path, content in defaults.items():
                try:
                    target = self._default_backup_path(rel_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                except Exception:
                    continue

            # presets: rel_path -> list[ConfigPreset dict]
            # store as presets/<preset_name>/<rel_path> plus meta per preset_name
            preset_meta: Dict[str, Dict[str, Any]] = {}
            for rel_path, preset_list in presets_data.items():
                for preset_obj in preset_list or []:
                    try:
                        preset = ConfigPreset(**preset_obj)
                        preset_dir = self._preset_dir(preset.name)
                        preset_dir.mkdir(parents=True, exist_ok=True)
                        target = preset_dir / Path(rel_path)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(preset.content, encoding="utf-8")

                        # collect meta (prefer newest)
                        meta = preset_meta.get(preset.name) or {
                            "created_at": preset.created_at,
                            "description": preset.description or "",
                        }
                        # choose max(created_at) if parseable
                        try:
                            if datetime.fromisoformat(preset.created_at) > datetime.fromisoformat(meta.get("created_at") or preset.created_at):
                                meta["created_at"] = preset.created_at
                        except Exception:
                            meta["created_at"] = meta.get("created_at") or preset.created_at
                        if preset.description and not meta.get("description"):
                            meta["description"] = preset.description
                        preset_meta[preset.name] = meta
                    except Exception:
                        continue

            for preset_name, meta in preset_meta.items():
                try:
                    preset_dir = self._preset_dir(preset_name)
                    self._preset_meta_path(preset_dir).write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    continue

            migrated_marker.write_text(datetime.now().isoformat(), encoding="utf-8")
        except Exception:
            # do not create marker on failure
            return
    
    def _load_presets_data(self) -> ConfigPresetsData:
        """Load presets data from file."""
        # Legacy-only (kept for migration support)
        if hasattr(self, "presets_file") and self.presets_file.exists():
            try:
                data = json.loads(self.presets_file.read_text(encoding="utf-8"))
                presets_dict = {}
                for file_path, presets_list in data.get("presets", {}).items():
                    presets_dict[file_path] = [
                        ConfigPreset(**p) for p in presets_list
                    ]
                return ConfigPresetsData(
                    defaults=data.get("defaults", {}),
                    presets=presets_dict
                )
            except Exception:
                pass
        return ConfigPresetsData()
    
    def _save_presets_data(self):
        """Save presets data to file."""
        # Legacy-only (no longer used; v2 stores on disk per preset)
        data = {
            "defaults": self._data.defaults,
            "presets": {
                file_path: [asdict(p) for p in presets]
                for file_path, presets in self._data.presets.items()
            },
        }
        if hasattr(self, "presets_file"):
            self.presets_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    
    def get_relative_path(self, file_path: Path) -> str:
        """Get a stable key for a file, preferring paths relative to the server root."""
        try:
            return str(file_path.relative_to(self.server_path)).replace("\\", "/")
        except ValueError:
            # Fall back to absolute path to avoid collisions across different roots
            return file_path.resolve().as_posix()

    def list_profiles_with_presets(self) -> List[str]:
        """List all profile names that have presets stored (for this scope)."""
        names: List[str] = []
        for p in sorted([d for d in self.presets_dir.iterdir() if d.is_dir()], key=lambda d: d.name.lower()):
            scope_dir = p / self.scope_safe
            if (scope_dir / "presets").exists() or (scope_dir / "defaults").exists():
                names.append(self._read_profile_marker(p.name))
        return names

    def _profile_safe_from_display(self, profile_display_name: str) -> Optional[str]:
        """Resolve display profile name back to safe folder name (best effort)."""
        # Prefer exact match via marker
        for p in [d for d in self.presets_dir.iterdir() if d.is_dir()]:
            if self._read_profile_marker(p.name) == profile_display_name:
                return p.name
        # Fall back: safe-filename of display name
        return self._safe_filename(profile_display_name)

    def _read_preset_meta(self, preset_dir: Path) -> Dict[str, Any]:
        meta_path = self._preset_meta_path(preset_dir)
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8")) or {}
            except Exception:
                return {}
        return {}

    def get_preset_options(
        self,
        file_path: Path,
        include_other_profiles: bool = True,
    ) -> List[Dict[str, str]]:
        """Return lightweight preset options without reading file contents."""
        rel_path = self.get_relative_path(file_path)

        options: List[Dict[str, str]] = []

        def collect(profile_safe: str, profile_display: str):
            for preset_dir in self._list_preset_dirs(profile_safe=profile_safe):
                candidate = preset_dir / Path(rel_path)
                if not candidate.exists():
                    continue
                meta = self._read_preset_meta(preset_dir)
                options.append(
                    {
                        "profile": profile_display,
                        "profile_safe": profile_safe,
                        "name": preset_dir.name,
                        "display_name": preset_dir.name,
                        "created_at": str(meta.get("created_at") or ""),
                        "description": str(meta.get("description") or ""),
                    }
                )

        # current profile first
        collect(self.profile_safe, self.profile_name)

        if include_other_profiles:
            for other_dir in sorted([d for d in self.presets_dir.iterdir() if d.is_dir()], key=lambda d: d.name.lower()):
                if other_dir.name == self.profile_safe:
                    continue
                # only include if scope folder exists
                scope_dir = other_dir / self.scope_safe / "presets"
                if not scope_dir.exists():
                    continue
                collect(other_dir.name, self._read_profile_marker(other_dir.name))

        return options

    def read_preset_content(self, file_path: Path, preset_name: str, source_profile: Optional[str] = None) -> Optional[str]:
        """Read preset content for a given file from current/other profile."""
        rel_path = self.get_relative_path(file_path)
        profile_safe = self.profile_safe
        if source_profile and source_profile != self.profile_name:
            profile_safe = self._profile_safe_from_display(source_profile) or profile_safe
        preset_dir = self._preset_dir(preset_name, profile_safe=profile_safe)
        candidate = preset_dir / Path(rel_path)
        if not candidate.exists():
            return None
        try:
            return candidate.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    
    def save_as_default(self, file_path: Path) -> bool:
        """
        Save current file content as default (for restore).
        
        Args:
            file_path: Path to the config file
            
        Returns:
            True if successful
        """
        try:
            if not file_path.exists():
                return False

            content = file_path.read_text(encoding="utf-8", errors="replace")
            rel_path = self.get_relative_path(file_path)
            target = self._default_backup_path(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False
    
    def save_preset(self, file_path: Path, preset_name: str, description: str = "") -> bool:
        """
        Save current file content as a named preset.
        
        Args:
            file_path: Path to the config file
            preset_name: Name for the preset
            description: Optional description
            
        Returns:
            True if successful
        """
        try:
            if not file_path.exists():
                return False

            content = file_path.read_text(encoding="utf-8", errors="replace")
            rel_path = self.get_relative_path(file_path)

            preset_dir = self._preset_dir(preset_name)
            preset_dir.mkdir(parents=True, exist_ok=True)

            target = preset_dir / Path(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            # meta
            meta_path = self._preset_meta_path(preset_dir)
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    meta = {}

            meta.setdefault("created_at", datetime.now().isoformat())
            # update description only if provided
            if description is not None:
                desc = description.strip()
                if desc:
                    meta["description"] = desc
                else:
                    meta.setdefault("description", "")
            meta["updated_at"] = datetime.now().isoformat()
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False
    
    def load_preset(self, file_path: Path, preset_name: str, source_profile: Optional[str] = None) -> bool:
        """
        Load a preset and write to file.
        
        Args:
            file_path: Path to the config file
            preset_name: Name of the preset to load
            
        Returns:
            True if successful
        """
        try:
            content = self.read_preset_content(file_path, preset_name, source_profile=source_profile)
            if content is None:
                return False
            file_path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False
    
    def restore_default(self, file_path: Path) -> bool:
        """
        Restore file from default backup.
        
        Args:
            file_path: Path to the config file
            
        Returns:
            True if successful
        """
        try:
            rel_path = self.get_relative_path(file_path)

            backup = self._default_backup_path(rel_path)
            if not backup.exists():
                return False
            file_path.write_text(backup.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            return True
        except Exception:
            return False
    
    def get_presets(self, file_path: Path) -> List[ConfigPreset]:
        """
        Get list of presets for a file.
        
        Args:
            file_path: Path to the config file
            
        Returns:
            List of ConfigPreset objects
        """
        rel_path = self.get_relative_path(file_path)
        presets: List[ConfigPreset] = []
        for preset_dir in self._list_preset_dirs(profile_safe=self.profile_safe):
            candidate = preset_dir / Path(rel_path)
            if not candidate.exists():
                continue
            meta = self._read_preset_meta(preset_dir)
            presets.append(
                ConfigPreset(
                    name=preset_dir.name,
                    file_path=rel_path,
                    content="",  # lazy-loaded via read_preset_content
                    created_at=str(meta.get("created_at") or ""),
                    description=str(meta.get("description") or ""),
                )
            )
        return presets
    
    def has_default(self, file_path: Path) -> bool:
        """Check if file has a default backup."""
        rel_path = self.get_relative_path(file_path)
        return self._default_backup_path(rel_path).exists()
    
    def has_presets(self, file_path: Path) -> bool:
        """Check if file has any saved presets."""
        return self.get_preset_count(file_path) > 0
    
    def get_preset_count(self, file_path: Path) -> int:
        """Get number of presets for a file."""
        rel_path = self.get_relative_path(file_path)
        count = 0
        for preset_dir in self._list_preset_dirs(profile_safe=self.profile_safe):
            if (preset_dir / Path(rel_path)).exists():
                count += 1
        return count

    def get_preset_count_all_profiles(self, file_path: Path) -> int:
        """Get number of presets for a file across all profiles (within this scope)."""
        rel_path = self.get_relative_path(file_path)
        total = 0
        try:
            for profile_dir in [d for d in self.presets_dir.iterdir() if d.is_dir()]:
                scope_dir = profile_dir / self.scope_safe
                presets_root = scope_dir / "presets"
                if not presets_root.exists():
                    continue
                for preset_dir in [d for d in presets_root.iterdir() if d.is_dir()]:
                    if (preset_dir / Path(rel_path)).exists():
                        total += 1
        except Exception:
            # Fall back to current profile only
            return self.get_preset_count(file_path)
        return total
    
    def delete_preset(self, file_path: Path, preset_name: str, source_profile: Optional[str] = None) -> bool:
        """
        Delete a preset.
        
        Args:
            file_path: Path to the config file
            preset_name: Name of the preset to delete
            
        Returns:
            True if successful
        """
        try:
            rel_path = self.get_relative_path(file_path)
            profile_safe = self.profile_safe
            if source_profile and source_profile != self.profile_name:
                profile_safe = self._profile_safe_from_display(source_profile) or profile_safe

            preset_dir = self._preset_dir(preset_name, profile_safe=profile_safe)
            target = preset_dir / Path(rel_path)
            if not target.exists():
                return False
            target.unlink(missing_ok=True)

            # cleanup empty dirs (best-effort)
            try:
                # if preset_dir contains only meta or nothing, remove it
                remaining_files = [p for p in preset_dir.rglob("*") if p.is_file() and p.name != ".meta.json"]
                if not remaining_files:
                    # remove meta too
                    meta = self._preset_meta_path(preset_dir)
                    if meta.exists():
                        meta.unlink(missing_ok=True)
                    # remove empty dirs bottom-up
                    for p in sorted([d for d in preset_dir.rglob("*") if d.is_dir()], reverse=True):
                        try:
                            p.rmdir()
                        except Exception:
                            pass
                    try:
                        preset_dir.rmdir()
                    except Exception:
                        pass
            except Exception:
                pass

            return True
        except Exception:
            return False
    
    def get_all_files_with_presets(self) -> List[str]:
        """Get list of all file paths that have presets."""
        files: set[str] = set()
        # defaults
        if self.defaults_dir.exists():
            for p in self.defaults_dir.rglob("*"):
                if p.is_file():
                    try:
                        files.add(str(p.relative_to(self.scope_dir)).replace("\\", "/").replace("defaults/", "", 1))
                    except Exception:
                        continue
        # presets
        for preset_dir in self._list_preset_dirs(profile_safe=self.profile_safe):
            for p in preset_dir.rglob("*"):
                if p.is_file() and p.name != ".meta.json":
                    try:
                        rel = str(p.relative_to(preset_dir)).replace("\\", "/")
                        files.add(rel)
                    except Exception:
                        continue
        return sorted(list(files))
    
    # ==================== Bulk Operations ====================
    
    def save_all_as_default(self, file_paths: List[Path]) -> int:
        """
        Save multiple files as defaults.
        
        Returns:
            Number of files successfully saved
        """
        count = 0
        for file_path in file_paths:
            if self.save_as_default(file_path):
                count += 1
        return count
    
    def save_all_preset(self, file_paths: List[Path], preset_name: str, description: str = "") -> int:
        """
        Save multiple files as a named preset group.
        
        Returns:
            Number of files successfully saved
        """
        count = 0
        for file_path in file_paths:
            if self.save_preset(file_path, preset_name, description):
                count += 1
        return count
    
    def restore_all_defaults(self, file_paths: List[Path]) -> int:
        """
        Restore multiple files from defaults.
        
        Returns:
            Number of files successfully restored
        """
        count = 0
        for file_path in file_paths:
            if self.restore_default(file_path):
                count += 1
        return count
    
    def get_all_preset_names(self) -> List[str]:
        """Get unique list of all preset names across all files (current profile)."""
        return [p.name for p in self._list_preset_dirs(profile_safe=self.profile_safe)]

    def get_all_preset_names_for_profile(self, source_profile: str) -> List[str]:
        """Get preset names for a specific profile (display name)."""
        profile_safe = self.profile_safe
        if source_profile and source_profile != self.profile_name:
            profile_safe = self._profile_safe_from_display(source_profile) or profile_safe
        return [p.name for p in self._list_preset_dirs(profile_safe=profile_safe)]

    def build_files_with_presets_for_profile(self, file_paths: List[Path], source_profile: str) -> Dict[str, List[str]]:
        """Build mapping rel_path -> [preset names] for the given file list in a profile."""
        rel_paths = [self.get_relative_path(p) for p in file_paths]
        rel_set = set(rel_paths)

        profile_safe = self.profile_safe
        if source_profile and source_profile != self.profile_name:
            profile_safe = self._profile_safe_from_display(source_profile) or profile_safe

        mapping: Dict[str, List[str]] = {}
        for preset_dir in self._list_preset_dirs(profile_safe=profile_safe):
            preset_name = preset_dir.name
            for p in preset_dir.rglob("*"):
                if not p.is_file() or p.name == ".meta.json":
                    continue
                rel = p.relative_to(preset_dir).as_posix()
                if rel in rel_set:
                    mapping.setdefault(rel, []).append(preset_name)
        return mapping
    
    def load_all_preset(self, file_paths: List[Path], preset_name: str, source_profile: Optional[str] = None) -> int:
        """
        Load preset for multiple files by name.
        
        Returns:
            Number of files successfully loaded
        """
        count = 0
        for file_path in file_paths:
            if self.load_preset(file_path, preset_name, source_profile=source_profile):
                count += 1
        return count
