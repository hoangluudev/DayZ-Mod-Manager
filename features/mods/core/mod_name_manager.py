"""src.core.mod_name_manager

Mod Name Manager - Handles mod name optimization and mapping.

Current behavior:
- Allocate ultra-short names: @m1, @m2, @m3...
- Persist mappings so the same mod_id always resolves to the same short name
- Provide original-name lookup for sorting/UI

Backwards compatibility:
- Older mapping files that only contain {"mappings": {short: original}} are still read.
"""

import json
import re
from pathlib import Path
from typing import Optional


class ModNameManager:
    """Manages mod name optimizations and mappings."""
    
    MAPPING_FILE = "mod_name_mappings.json"
    
    def __init__(self, server_path: Path):
        self.server_path = Path(server_path) if server_path else None
        # v2 storage:
        # - by_short: short(without @) -> original(without @)
        # - by_mod_id: mod_id -> {"short": short(without @), "original": original(without @)}
        self._by_short: dict[str, str] = {}
        self._by_mod_id: dict[str, dict] = {}
        self._next_index: int = 1
        self._load_mappings()
    
    def _get_mapping_file_path(self) -> Optional[Path]:
        """Get path to the mapping file in server folder."""
        if not self.server_path:
            return None
        return self.server_path / self.MAPPING_FILE
    
    def _load_mappings(self):
        """Load existing mappings from file."""
        self._by_short = {}
        self._by_mod_id = {}
        self._next_index = 1
        path = self._get_mapping_file_path()
        if not path or not path.exists():
            self._next_index = self._compute_next_index()
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # v2
                by_short = data.get("by_short")
                by_mod_id = data.get("by_mod_id")
                if isinstance(by_short, dict) or isinstance(by_mod_id, dict):
                    self._by_short = by_short if isinstance(by_short, dict) else {}
                    self._by_mod_id = by_mod_id if isinstance(by_mod_id, dict) else {}
                    next_index = data.get("next_index")
                    if isinstance(next_index, int) and next_index >= 1:
                        self._next_index = next_index
                else:
                    # v1 legacy: {"mappings": {short: original}}
                    legacy = data.get("mappings", {})
                    if isinstance(legacy, dict):
                        self._by_short = {str(k): str(v) for k, v in legacy.items()}
        except Exception:
            pass

        self._next_index = self._compute_next_index()
    
    def _save_mappings(self):
        """Save mappings to file."""
        path = self._get_mapping_file_path()
        if not path:
            return
        
        try:
            data = {
                "version": 2,
                "by_short": self._by_short,
                "by_mod_id": self._by_mod_id,
                "next_index": self._compute_next_index(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def get_original_name(self, shortened_name: str) -> str:
        """Get original name for a shortened mod name."""
        # Normalize - remove @ prefix for lookup
        key = shortened_name.lstrip("@")
        original = self._by_short.get(key)
        if original:
            return f"@{original}" if shortened_name.startswith("@") else original
        return shortened_name
    
    def get_shortened_name(self, original_name: str) -> Optional[str]:
        """Get shortened name for an original mod name (reverse lookup)."""
        name = original_name.lstrip("@")
        for short, orig in self._by_short.items():
            if orig == name:
                return f"@{short}" if original_name.startswith("@") else short
        return None

    def get_shortened_name_by_mod_id(self, mod_id: str) -> Optional[str]:
        """Get shortened name for a mod_id if present."""
        if not mod_id:
            return None
        rec = self._by_mod_id.get(str(mod_id))
        if isinstance(rec, dict):
            short = rec.get("short")
            if isinstance(short, str) and short:
                return f"@{short}"
        return None

    @staticmethod
    def _is_m_short(short_without_at: str) -> bool:
        return bool(re.match(r"^m\d+$", str(short_without_at or ""), flags=re.IGNORECASE))

    def find_existing_m_short_for_original(self, original_name: str) -> Optional[str]:
        """Return an existing @mN for a given original name if present."""
        target = self._normalize_name(original_name).lower()
        for short, orig in self._by_short.items():
            if str(orig).lower() == target and self._is_m_short(short):
                return f"@{short}"
        return None

    def get_all_shorts_for_original(self, original_name: str) -> list[str]:
        """Return all shorts (without @) that map to original_name."""
        target = self._normalize_name(original_name).lower()
        shorts: list[str] = []
        for short, orig in self._by_short.items():
            if str(orig).lower() == target:
                shorts.append(str(short))
        return shorts
    
    def has_mapping(self, mod_name: str) -> bool:
        """Check if mod has a name mapping."""
        name = mod_name.lstrip("@")
        return name in self._by_short
    
    def get_or_allocate_short_name(self, original_name: str, mod_id: Optional[str] = None) -> str:
        """Return a stable short name for this mod.

        - If a mapping already exists for mod_id, re-use it.
        - Otherwise allocate the smallest available @mN name.

        Returns an @-prefixed folder name.
        """
        clean_original = self._normalize_name(original_name)
        clean_mod_id = str(mod_id) if mod_id else None

        # Prefer stable mapping by mod_id
        if clean_mod_id:
            existing = self.get_shortened_name_by_mod_id(clean_mod_id)
            if existing:
                existing_short = self._normalize_name(existing)
                # If legacy short was previously used, migrate to mN scheme
                if self._is_m_short(existing_short):
                    return f"@{existing_short}"

                short = self._allocate_next_short()
                self.register_mapping(f"@{short}", f"@{clean_original}", mod_id=clean_mod_id)
                return f"@{short}"

        # If original already has an mN mapping, re-use it
        existing_m = self.find_existing_m_short_for_original(f"@{clean_original}")
        if existing_m:
            return existing_m

        short = self._allocate_next_short()
        self.register_mapping(f"@{short}", f"@{clean_original}", mod_id=clean_mod_id)
        return f"@{short}"
    
    def _normalize_name(self, name: str) -> str:
        return str(name or "").strip().lstrip("@")

    def _existing_short_names(self) -> set[str]:
        existing: set[str] = set()
        # From filesystem
        if self.server_path and self.server_path.exists():
            try:
                for item in self.server_path.iterdir():
                    if item.is_dir() and item.name.startswith("@"):
                        existing.add(item.name.lstrip("@").lower())
            except Exception:
                pass
        # From mappings
        existing.update(k.lower() for k in self._by_short.keys())
        return existing

    def _allocate_next_short(self) -> str:
        """Allocate the smallest available mN (without @)."""
        existing = self._existing_short_names()
        idx = 1
        while True:
            candidate = f"m{idx}"
            if candidate.lower() not in existing:
                return candidate
            idx += 1

    def _compute_next_index(self) -> int:
        """Compute next index based on current mappings and folders."""
        max_idx = 0
        pattern = re.compile(r"^m(\d+)$", re.IGNORECASE)
        for name in self._existing_short_names():
            m = pattern.match(name)
            if m:
                try:
                    max_idx = max(max_idx, int(m.group(1)))
                except Exception:
                    pass
        return max_idx + 1 if max_idx >= 1 else 1
    
    def register_mapping(self, shortened_name: str, original_name: str, mod_id: Optional[str] = None):
        """Register a new name mapping."""
        short = self._normalize_name(shortened_name)
        orig = self._normalize_name(original_name)
        if not short or not orig:
            return

        self._by_short[short] = orig

        if mod_id:
            self._by_mod_id[str(mod_id)] = {"short": short, "original": orig}

        self._save_mappings()
    
    def remove_mapping(self, name: str):
        """Remove a mapping by shortened or original name."""
        key = name.lstrip("@")
        # Check if it's a shortened name
        if key in self._by_short:
            del self._by_short[key]
            # remove any mod_id records pointing to this short
            for mid in list(self._by_mod_id.keys()):
                rec = self._by_mod_id.get(mid)
                if isinstance(rec, dict) and rec.get("short") == key:
                    del self._by_mod_id[mid]
            self._save_mappings()
            return
        # Check if it's an original name
        to_remove = None
        for short, orig in self._by_short.items():
            if orig == key:
                to_remove = short
                break
        if to_remove:
            del self._by_short[to_remove]
            for mid in list(self._by_mod_id.keys()):
                rec = self._by_mod_id.get(mid)
                if isinstance(rec, dict) and rec.get("short") == to_remove:
                    del self._by_mod_id[mid]
            self._save_mappings()
    
    def get_all_mappings(self) -> dict[str, str]:
        """Get all current mappings (shortened -> original)."""
        return dict(self._by_short)
    
    def resolve_mod_name_for_sorting(self, mod_name: str) -> str:
        """
        Resolve mod name for sorting purposes.
        Returns the original name if a mapping exists, otherwise the input name.
        """
        original = self.get_original_name(mod_name)
        return original if original else mod_name
