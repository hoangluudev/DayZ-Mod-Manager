"""Mission Config Merger

Provides utilities for scanning mod config files (types.xml, events.xml, etc.)
and merging them into the mission folder with deduplication and validation.

Key features:
- Detect parent XML class to match correct target file
- Check for duplicate entries by comparing unique identifiers
- Support map-specific config files (e.g., cfgeventspawns_Chernarus.xml)
- Mark entries with source mod for traceability
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET


class ConfigFileType(Enum):
    """Known DayZ config file types and their parent XML elements."""
    
    TYPES = ("types.xml", "types")
    EVENTS = ("events.xml", "events")
    SPAWNABLETYPES = ("cfgspawnabletypes.xml", "spawnabletypes")
    RANDOMPRESETS = ("cfgrandompresets.xml", "randompresets")
    # DayZ cfgeventspawns.xml uses <eventposdef> root
    EVENTSPAWNS = ("cfgeventspawns.xml", "eventposdef")
    EVENTGROUPS = ("cfgeventgroups.xml", "eventgroups")  
    GLOBALS = ("globals.xml", "variables")
    ECONOMY = ("cfgeconomycore.xml", "economycore")
    TERRITORIES = ("cfgweather.xml", "weather")
    MAPGROUPPROTO = ("mapgroupproto.xml", "map")
    MAPGROUPPOS = ("mapgrouppos.xml", "map")
    UNKNOWN = ("", "")
    
    @property
    def filename(self) -> str:
        return self.value[0]
    
    @property
    def root_element(self) -> str:
        return self.value[1]
    
    @classmethod
    def from_root_element(cls, root_tag: str) -> "ConfigFileType":
        """Get ConfigFileType from XML root element tag."""
        tag_lower = root_tag.lower()
        for ft in cls:
            if ft.root_element and ft.root_element.lower() == tag_lower:
                return ft
        return cls.UNKNOWN
    
    @classmethod
    def from_filename(cls, filename: str) -> "ConfigFileType":
        """Get ConfigFileType from filename (handles map-specific files)."""
        name_lower = filename.lower()
        
        # Handle map-specific files like cfgeventspawns_Chernarus.xml
        # Extract base name before underscore + map name
        base_name = re.sub(r'_[a-zA-Z]+\.xml$', '.xml', name_lower)
        
        for ft in cls:
            if ft.filename and ft.filename.lower() == name_lower:
                return ft
            if ft.filename and ft.filename.lower() == base_name:
                return ft
        return cls.UNKNOWN


class MergeStatus(Enum):
    """Status of a config entry merge operation."""
    NEW = "new"                     # Entry does not exist, will be added
    DUPLICATE = "duplicate"         # Entry already exists (identical)
    CONFLICT = "conflict"           # Entry exists but different content
    SKIPPED = "skipped"             # User marked as skipped
    MANUAL = "manual"               # Requires manual handling
    MERGED = "merged"               # Successfully merged


@dataclass
class ConfigEntry:
    """Represents a single XML entry (e.g., one <type> in types.xml)."""
    
    element: ET.Element
    unique_key: str                 # e.g., type name for types.xml
    source_mod: str                 # Mod name this entry came from
    source_file: Path               # Original file path
    status: MergeStatus = MergeStatus.NEW
    
    def to_xml_string(self, indent: int = 4) -> str:
        """Convert element to formatted XML string."""
        return _element_to_string(self.element, indent)
    
    @property
    def tag(self) -> str:
        return self.element.tag


@dataclass
class ModConfigInfo:
    """Information about config files found in a mod."""
    
    mod_name: str
    mod_path: Path
    config_files: list[Path] = field(default_factory=list)
    entries_count: int = 0
    has_map_specific: bool = False
    map_specific_files: list[str] = field(default_factory=list)
    needs_manual_review: bool = False
    manual_review_reason: str = ""


@dataclass  
class MergeResult:
    """Result of a merge operation."""
    
    target_file: str                # e.g., "types.xml"
    total_entries: int = 0
    new_entries: int = 0
    duplicates: int = 0
    conflicts: int = 0
    merged_entries: list[ConfigEntry] = field(default_factory=list)
    conflict_entries: list[ConfigEntry] = field(default_factory=list)


@dataclass
class MergePreview:
    """Complete preview of all merge operations."""
    
    mission_path: Path
    mods_with_configs: list[ModConfigInfo] = field(default_factory=list)
    merge_results: dict[str, MergeResult] = field(default_factory=dict)  # filename -> result
    total_new: int = 0
    total_duplicates: int = 0
    total_conflicts: int = 0
    mods_needing_manual: list[str] = field(default_factory=list)
    # Conflict resolver output: {target_filename: [{entry: ConfigEntry, action: str}, ...]}
    resolved_conflicts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _element_to_string(elem: ET.Element, indent: int = 4) -> str:
    """Convert XML element to formatted string."""
    try:
        # Try to use indent (Python 3.9+)
        ET.indent(elem, space=" " * indent)
    except AttributeError:
        pass
    return ET.tostring(elem, encoding="unicode")


def _get_unique_key(element: ET.Element, parent_type: ConfigFileType) -> str:
    """Extract unique identifier from an XML element based on file type.
    
    For types.xml: name attribute of <type>
    For events.xml: name attribute of <event>
    For cfgspawnabletypes.xml: name attribute of <type>
    etc.
    """
    # Most DayZ config elements use 'name' attribute as unique key
    name = element.get("name") or element.get("type") or element.get("id")
    if name:
        return f"{element.tag}:{name}"
    
    # Fallback to tag + text content hash
    text = ET.tostring(element, encoding="unicode")
    return f"{element.tag}:{hash(text)}"


def _normalize_xml_element(elem: ET.Element) -> str:
    """Normalize element for comparison (ignore whitespace, attribute order)."""
    # Clone to avoid modifying original
    clone = ET.Element(elem.tag, dict(sorted(elem.attrib.items())))
    clone.text = (elem.text or "").strip()
    clone.tail = ""
    
    for child in elem:
        clone.append(_normalize_element_recursive(child))
    
    return ET.tostring(clone, encoding="unicode")


def _normalize_element_recursive(elem: ET.Element) -> ET.Element:
    """Recursively normalize an element."""
    clone = ET.Element(elem.tag, dict(sorted(elem.attrib.items())))
    clone.text = (elem.text or "").strip()
    clone.tail = ""
    for child in elem:
        clone.append(_normalize_element_recursive(child))
    return clone


def detect_map_from_filename(filename: str) -> Optional[str]:
    """Detect map name from filename like cfgeventspawns_Chernarus.xml."""
    match = re.search(r'_([a-zA-Z]+)\.xml$', filename, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def is_map_specific_file(filename: str) -> bool:
    """Check if filename is map-specific."""
    return detect_map_from_filename(filename) is not None


KNOWN_MAPS = {
    "chernarus", "chernarusplus", "enoch", "livonia", 
    "sakhal", "namalsk", "deer_isle", "deerisle", "esseker",
    "takistan", "banov", "chiemsee", "rostow", "valning"
}


def get_base_config_filename(filename: str) -> str:
    """Get base config filename without map suffix.
    
    e.g., 'cfgeventspawns_Chernarus.xml' -> 'cfgeventspawns.xml'
    """
    map_name = detect_map_from_filename(filename)
    if map_name and map_name.lower() in KNOWN_MAPS:
        return re.sub(r'_[a-zA-Z]+\.xml$', '.xml', filename, flags=re.IGNORECASE)
    return filename


class MissionConfigMerger:
    """Handles scanning and merging mod configs into mission folder."""
    
    # Common config folder names in mods
    CONFIG_FOLDER_NAMES = [
        "extras", "config", "configs", "mission_files", 
        "server_files", "ServerConfig", "Server", "xml"
    ]
    
    def __init__(self, mission_path: Path, server_path: Path, 
                 current_map: str = "chernarusplus"):
        """
        Initialize merger.
        
        Args:
            mission_path: Path to mission folder (e.g., mpmissions/dayzOffline.chernarusplus)
            server_path: Path to DayZ server root
            current_map: Current map name for handling map-specific files
        """
        self.mission_path = mission_path
        self.server_path = server_path
        self.current_map = current_map.lower()
        self._existing_entries: dict[str, dict[str, str]] = {}  # file -> {key: normalized_xml}
        self._skipped_mods: set[str] = set()
        
    def load_skipped_mods(self, skipped: set[str]):
        """Load set of mod names user has marked as skipped/already processed."""
        self._skipped_mods = skipped
        
    def _load_existing_entries(self, filename: str) -> dict[str, str]:
        """Load existing entries from a mission config file."""
        if filename in self._existing_entries:
            return self._existing_entries[filename]
            
        entries = {}
        file_path = self.mission_path / filename
        
        if not file_path.exists():
            self._existing_entries[filename] = entries
            return entries
            
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            file_type = ConfigFileType.from_root_element(root.tag)
            
            for child in root:
                key = _get_unique_key(child, file_type)
                entries[key] = _normalize_xml_element(child)
                
        except (ET.ParseError, OSError, PermissionError):
            pass
            
        self._existing_entries[filename] = entries
        return entries
    
    def scan_mod_configs(self, mod_path: Path) -> Optional[ModConfigInfo]:
        """Scan a mod folder for config files to merge."""
        mod_name = mod_path.name
        info = ModConfigInfo(mod_name=mod_name, mod_path=mod_path)
        
        # Check if mod is skipped
        if mod_name in self._skipped_mods:
            return None
            
        # Search for config folders
        config_dirs = []
        for folder_name in self.CONFIG_FOLDER_NAMES:
            for potential in [
                mod_path / folder_name,
                mod_path / folder_name.lower(),
                mod_path / folder_name.upper(),
            ]:
                if potential.exists() and potential.is_dir():
                    config_dirs.append(potential)
                    break
        
        # Also check root of mod
        config_dirs.append(mod_path)
        
        # Find XML config files
        for config_dir in config_dirs:
            for xml_file in config_dir.rglob("*.xml"):
                # rglob can yield directories that match '*.xml' on Windows
                if not xml_file.is_file():
                    continue

                # Skip known non-config files
                if xml_file.name.lower() in ["config.xml", "meta.xml", "mod.xml"]:
                    continue
                    
                # Try to parse and detect type
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    file_type = ConfigFileType.from_root_element(root.tag)
                    
                    if file_type != ConfigFileType.UNKNOWN:
                        info.config_files.append(xml_file)
                        info.entries_count += len(list(root))
                        
                        # Check for map-specific
                        if is_map_specific_file(xml_file.name):
                            info.has_map_specific = True
                            info.map_specific_files.append(xml_file.name)
                            
                            # Check if this is for current map
                            file_map = detect_map_from_filename(xml_file.name)
                            if file_map and file_map not in [self.current_map, "all"]:
                                info.needs_manual_review = True
                                info.manual_review_reason = (
                                    f"Map-specific file '{xml_file.name}' may not be for "
                                    f"current map ({self.current_map})"
                                )
                except (ET.ParseError, OSError, PermissionError) as e:
                    # Not a valid XML or cannot be read, skip without failing the full scan.
                    # On Windows it's possible to have folders that match '*.xml' or files with denied access.
                    if isinstance(e, PermissionError):
                        inferred = ConfigFileType.from_filename(xml_file.name)
                        if inferred != ConfigFileType.UNKNOWN:
                            if xml_file not in info.config_files:
                                info.config_files.append(xml_file)
                            info.needs_manual_review = True
                            if not info.manual_review_reason:
                                info.manual_review_reason = f"Cannot read file due to permission: {xml_file.name}"
                    pass
                    
        if info.config_files:
            return info
        return None
    
    def scan_all_mods(self) -> list[ModConfigInfo]:
        """Scan all installed mods for config files."""
        results = []
        
        for item in self.server_path.iterdir():
            if item.is_dir() and item.name.startswith("@"):
                mod_info = self.scan_mod_configs(item)
                if mod_info:
                    results.append(mod_info)
                    
        return results
    
    def preview_merge(
        self,
        mod_infos: list[ModConfigInfo],
        target_overrides: Optional[dict[Path, str]] = None,
    ) -> MergePreview:
        """Generate preview of merge operations without modifying files.

        Args:
            mod_infos: Mods and their selected config files.
            target_overrides: Optional mapping of source file path -> target filename.
                This enables UI workflows where the user chooses which mission config
                file a given source XML should merge into.
        """
        preview = MergePreview(mission_path=self.mission_path)
        preview.mods_with_configs = mod_infos
        
        # Group entries by target file
        entries_by_file: dict[str, list[ConfigEntry]] = {}
        
        for mod_info in mod_infos:
            if mod_info.needs_manual_review:
                preview.mods_needing_manual.append(mod_info.mod_name)
                
            for config_file in mod_info.config_files:
                try:
                    tree = ET.parse(config_file)
                    root = tree.getroot()
                    file_type = ConfigFileType.from_root_element(root.tag)
                    
                    # Determine target filename
                    override_target = None
                    if target_overrides:
                        override_target = target_overrides.get(config_file)
                        if not override_target:
                            try:
                                override_target = target_overrides.get(config_file.resolve())
                            except OSError:
                                override_target = None

                    if override_target:
                        target_file = override_target
                    else:
                        # Prefer filename-based inference for target mapping.
                        # This prevents structurally-similar files (e.g., both have <event name="...">)
                        # from being grouped into the wrong target file.
                        base_name = (
                            get_base_config_filename(config_file.name)
                            if is_map_specific_file(config_file.name)
                            else config_file.name
                        )

                        inferred_type = ConfigFileType.from_filename(base_name)
                        if inferred_type != ConfigFileType.UNKNOWN and inferred_type.filename:
                            target_file = inferred_type.filename
                        else:
                            target_file = file_type.filename or base_name
                        
                    if target_file not in entries_by_file:
                        entries_by_file[target_file] = []
                        
                    for child in root:
                        key = _get_unique_key(child, file_type)
                        entry = ConfigEntry(
                            element=child,
                            unique_key=key,
                            source_mod=mod_info.mod_name,
                            source_file=config_file
                        )
                        entries_by_file[target_file].append(entry)
                        
                except (ET.ParseError, OSError, PermissionError):
                    pass
        
        # Check each file for duplicates/conflicts
        for target_file, entries in entries_by_file.items():
            existing = self._load_existing_entries(target_file)
            result = MergeResult(target_file=target_file, total_entries=len(entries))
            
            # First, group entries by unique_key to detect conflicts between mods
            entries_by_key = {}
            for entry in entries:
                if entry.unique_key not in entries_by_key:
                    entries_by_key[entry.unique_key] = []
                entries_by_key[entry.unique_key].append(entry)
            
            # Process each unique key
            for key, key_entries in entries_by_key.items():
                if len(key_entries) == 1:
                    # Only one mod provides this entry
                    entry = key_entries[0]
                    
                    if key in existing:
                        # Compare with existing mission file entry
                        existing_xml = existing[key]
                        new_xml = _normalize_xml_element(entry.element)
                        
                        if existing_xml == new_xml:
                            entry.status = MergeStatus.DUPLICATE
                            result.duplicates += 1
                        else:
                            entry.status = MergeStatus.CONFLICT
                            result.conflicts += 1
                            result.conflict_entries.append(entry)
                    else:
                        # New entry
                        entry.status = MergeStatus.NEW
                        result.new_entries += 1
                        result.merged_entries.append(entry)
                else:
                    # Multiple mods provide this entry - check if they're identical
                    normalized_xmls = [_normalize_xml_element(e.element) for e in key_entries]
                    
                    if all(xml == normalized_xmls[0] for xml in normalized_xmls):
                        # All identical - treat first as new/duplicate, rest as duplicates
                        first_entry = key_entries[0]
                        
                        if key in existing:
                            existing_xml = existing[key]
                            if normalized_xmls[0] == existing_xml:
                                first_entry.status = MergeStatus.DUPLICATE
                                result.duplicates += 1
                            else:
                                first_entry.status = MergeStatus.CONFLICT
                                result.conflicts += 1
                                result.conflict_entries.append(first_entry)
                        else:
                            first_entry.status = MergeStatus.NEW
                            result.new_entries += 1
                            result.merged_entries.append(first_entry)
                        
                        # Mark others as duplicates
                        for entry in key_entries[1:]:
                            entry.status = MergeStatus.DUPLICATE
                            result.duplicates += 1
                    else:
                        # Different XML content between mods - all are conflicts
                        for entry in key_entries:
                            entry.status = MergeStatus.CONFLICT
                            result.conflicts += 1
                            result.conflict_entries.append(entry)
                    
            preview.merge_results[target_file] = result
            preview.total_new += result.new_entries
            preview.total_duplicates += result.duplicates
            preview.total_conflicts += result.conflicts
            
        return preview
    
    def execute_merge(self, preview: MergePreview, 
                      include_conflicts: bool = False) -> dict[str, int]:
        """Execute the merge based on preview.
        
        Args:
            preview: MergePreview from preview_merge()
            include_conflicts: If True, also merge conflicting entries (overwrite)
            
        Returns:
            Dict of filename -> entries merged count
        """
        merged_counts = {}
        
        for target_file, result in preview.merge_results.items():
            if not result.merged_entries and not (include_conflicts and result.conflict_entries):
                continue
                
            file_path = self.mission_path / target_file
            
            # Load or create target file
            if file_path.exists():
                tree = ET.parse(file_path)
                root = tree.getroot()
            else:
                # Create new file with appropriate root
                file_type = ConfigFileType.from_filename(target_file)
                root_tag = file_type.root_element or "root"
                root = ET.Element(root_tag)
                tree = ET.ElementTree(root)
            
            count = 0

            file_type = ConfigFileType.from_filename(target_file)
            resolved_for_file = (getattr(preview, "resolved_conflicts", None) or {}).get(target_file, []) or []

            resolved_keys: set[str] = set()
            for res in resolved_for_file:
                if isinstance(res, dict):
                    entry = res.get("entry")
                    if entry is not None and getattr(entry, "unique_key", None):
                        resolved_keys.add(str(entry.unique_key))

            def _iter_real_children(parent: ET.Element):
                for ch in list(parent):
                    if not isinstance(getattr(ch, "tag", None), str):
                        continue
                    yield ch

            def _find_children_by_key(parent: ET.Element, unique_key: str) -> list[ET.Element]:
                found: list[ET.Element] = []
                for ch in _iter_real_children(parent):
                    try:
                        k = _get_unique_key(ch, file_type)
                    except Exception:
                        continue
                    if k == unique_key:
                        found.append(ch)
                return found

            def _clone_element(elem: ET.Element) -> ET.Element:
                # ElementTree elements can't be shared across different trees safely.
                return ET.fromstring(ET.tostring(elem, encoding="unicode"))

            def _child_signature(ch: ET.Element) -> str:
                name = ch.get("name")
                if name:
                    return f"{ch.tag}:name:{name}"
                if ch.tag.lower() == "pos":
                    x = ch.get("x") or ""
                    y = ch.get("y") or ""
                    z = ch.get("z") or ""
                    a = ch.get("a") or ""
                    return f"pos:{x}:{y}:{z}:{a}"
                attrs = ";".join([f"{k}={v}" for k, v in sorted((ch.attrib or {}).items())])
                return f"{ch.tag}:{attrs}"
            
            # Add new entries
            for entry in result.merged_entries:
                # Add comment to mark source
                comment = ET.Comment(f" Added by DayZ Mod Manager from {entry.source_mod} ")
                root.append(comment)
                root.append(entry.element)
                count += 1

            # Apply resolved conflicts (selected by user)
            for res in resolved_for_file:
                if not isinstance(res, dict):
                    continue
                entry = res.get("entry")
                if entry is None:
                    continue
                action = str(res.get("action") or "replace")
                unique_key = str(getattr(entry, "unique_key", ""))
                if not unique_key:
                    continue

                if action == "merge" and file_type in (ConfigFileType.RANDOMPRESETS, ConfigFileType.EVENTSPAWNS):
                    # Merge children into existing parent (or create one)
                    existing_parents = _find_children_by_key(root, unique_key)
                    if existing_parents:
                        parent_elem = existing_parents[0]
                    else:
                        parent_elem = ET.Element(entry.element.tag, dict(entry.element.attrib))
                        root.append(ET.Comment(f" MERGED (created) from {entry.source_mod} "))
                        root.append(parent_elem)
                        count += 1

                    existing_sigs = {_child_signature(c) for c in _iter_real_children(parent_elem)}
                    added_any = False
                    for child in list(entry.element):
                        if not isinstance(getattr(child, "tag", None), str):
                            continue
                        sig = _child_signature(child)
                        if sig in existing_sigs:
                            continue
                        parent_elem.append(_clone_element(child))
                        existing_sigs.add(sig)
                        added_any = True
                    if added_any:
                        root.append(ET.Comment(f" MERGED items from {entry.source_mod} into {unique_key} "))
                else:
                    # Replace: remove existing entries with same key and append the selected one
                    for ch in _find_children_by_key(root, unique_key):
                        try:
                            root.remove(ch)
                        except ValueError:
                            pass
                    root.append(ET.Comment(f" RESOLVED CONFLICT (replace) from {entry.source_mod} "))
                    root.append(_clone_element(entry.element))
                    count += 1
                
            # Optionally add conflict entries
            if include_conflicts:
                for entry in result.conflict_entries:
                    # Skip conflicts that the user already resolved.
                    if str(getattr(entry, "unique_key", "")) in resolved_keys:
                        continue
                    comment = ET.Comment(
                        f" CONFLICT: Overwrites existing entry. Source: {entry.source_mod} "
                    )
                    root.append(comment)
                    root.append(entry.element)
                    count += 1
            
            # Format and save
            try:
                ET.indent(tree, space="    ")
            except AttributeError:
                pass
                
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            merged_counts[target_file] = count
            
        return merged_counts


def get_mission_folder_path(server_path: Path, mission_template: str) -> Path:
    """Get the mission folder path from server path and template.
    
    Args:
        server_path: DayZ server root path
        mission_template: Template string like "dayzOffline.chernarusplus"
        
    Returns:
        Path to mission folder (mpmissions/template)
    """
    return server_path / "mpmissions" / mission_template
