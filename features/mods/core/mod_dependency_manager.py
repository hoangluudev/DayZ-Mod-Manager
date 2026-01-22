"""
Mod Dependency Manager - Handles user-defined mod dependencies for custom sorting.

Features:
- Store mod dependencies (mod A depends on mod B)
- Topological sort based on dependencies
- Dependency count and tooltip data
"""

import json
from pathlib import Path
from typing import Optional


class ModDependencyManager:
    """Manages user-defined mod dependencies for custom load order sorting."""
    
    DEPENDENCIES_FILE = "mod_dependencies.json"
    GLOBAL_DEPENDENCIES_FILE = "mod_dependencies.json"
    
    def __init__(self, server_path: Optional[Path] = None):
        self.server_path = Path(server_path) if server_path else None
        self._dependencies: dict[str, list[str]] = {}  # mod -> [dependencies]
        self._load_dependencies()
    
    def _get_server_file_path(self) -> Optional[Path]:
        """Get path to the legacy dependencies file in server folder."""
        if not self.server_path:
            return None
        return self.server_path / self.DEPENDENCIES_FILE

    def _get_global_file_path(self) -> Optional[Path]:
        """Get path to the global dependencies file (shared across profiles)."""
        try:
            from shared.core.storage_paths import get_configs_path
            return get_configs_path() / self.GLOBAL_DEPENDENCIES_FILE
        except Exception:
            return None

    @staticmethod
    def _merge_dep_lists(base: list[str], extra: list[str]) -> list[str]:
        """Merge dependency lists preserving order and removing duplicates."""
        out: list[str] = []
        seen: set[str] = set()
        for dep in (base or []) + (extra or []):
            d = ModDependencyManager._normalize_name(str(dep))
            if not d or d in seen:
                continue
            seen.add(d)
            out.append(d)
        return out

    def _merge_dependencies(self, incoming: dict) -> None:
        """Merge dependency dict (mod -> deps) into current state."""
        if not isinstance(incoming, dict):
            return
        for mod, deps in incoming.items():
            key = self._normalize_name(str(mod))
            if not key:
                continue
            dep_list = []
            if isinstance(deps, list):
                dep_list = [self._normalize_name(str(d)) for d in deps if str(d).strip()]
            if not dep_list:
                continue
            existing = self._dependencies.get(key, [])
            self._dependencies[key] = self._merge_dep_lists(existing, dep_list)
    
    def _load_dependencies(self):
        """Load existing dependencies from file."""
        self._dependencies = {}

        # 1) Load global dependencies (shared across all profiles)
        global_path = self._get_global_file_path()
        if global_path and global_path.exists():
            try:
                with open(global_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._merge_dependencies(data.get("dependencies", {}))
            except Exception:
                pass

        # 2) Load legacy per-server dependencies (for backwards compatibility)
        server_path = self._get_server_file_path()
        if server_path and server_path.exists():
            try:
                with open(server_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._merge_dependencies(data.get("dependencies", {}))
            except Exception:
                pass

        # If we have legacy data but no global file yet, persist global once.
        if global_path and (not global_path.exists()) and self._dependencies:
            try:
                self._save_global()
            except Exception:
                pass
    
    def _save_global(self) -> bool:
        path = self._get_global_file_path()
        if not path:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {"dependencies": self._dependencies}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def _save_dependencies(self) -> bool:
        """Save dependencies globally (shared across all profiles)."""
        return self._save_global()
    
    def set_dependencies(self, mod_name: str, dependencies: list[str]):
        """Set dependencies for a mod."""
        key = self._normalize_name(mod_name)
        deps = [self._normalize_name(d) for d in dependencies if d.strip()]
        
        if deps:
            self._dependencies[key] = deps
        elif key in self._dependencies:
            del self._dependencies[key]
        
        self._save_dependencies()
    
    def get_dependencies(self, mod_name: str) -> list[str]:
        """Get dependencies for a mod."""
        key = self._normalize_name(mod_name)
        return list(self._dependencies.get(key, []))
    
    def get_dependency_count(self, mod_name: str) -> int:
        """Get number of dependencies for a mod."""
        return len(self.get_dependencies(mod_name))
    
    def get_all_dependencies(self) -> dict[str, list[str]]:
        """Get all defined dependencies."""
        return dict(self._dependencies)
    
    def remove_mod(self, mod_name: str):
        """Remove all dependency data for a mod."""
        key = self._normalize_name(mod_name)
        changed = False
        
        # Remove as key
        if key in self._dependencies:
            del self._dependencies[key]
            changed = True
        
        # Remove from other mods' dependencies
        for mod, deps in self._dependencies.items():
            if key in deps:
                deps.remove(key)
                changed = True
        
        if changed:
            self._save_dependencies()
    
    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize mod name for storage."""
        return name.strip().lstrip("@")
    
    def sort_by_dependencies(self, mods: list[str]) -> list[str]:
        """
        Sort mods by their dependencies using topological sort.
        Mods that are dependencies of other mods appear first.
        
        Example: If @Mod depends on @CF, and @CF depends on nothing,
        result will be [@CF, @Mod]
        """
        if not mods:
            return []
        
        # Normalize all mod names for lookup
        mod_set = {self._normalize_name(m) for m in mods}
        original_names = {self._normalize_name(m): m for m in mods}
        
        # Build dependency graph (only for mods in the list)
        graph: dict[str, list[str]] = {}  # mod -> list of mods that depend on it
        in_degree: dict[str, int] = {}     # mod -> number of dependencies
        
        for mod in mod_set:
            graph[mod] = []
            in_degree[mod] = 0
        
        for mod in mod_set:
            deps = self.get_dependencies(mod)
            for dep in deps:
                dep_normalized = self._normalize_name(dep)
                if dep_normalized in mod_set:
                    graph[dep_normalized].append(mod)
                    in_degree[mod] = in_degree.get(mod, 0) + 1
        
        # Kahn's algorithm for topological sort
        queue = [mod for mod in mod_set if in_degree.get(mod, 0) == 0]
        result = []
        
        while queue:
            # Sort queue alphabetically for consistent ordering
            queue.sort()
            mod = queue.pop(0)
            result.append(original_names[mod])
            
            for dependent in graph.get(mod, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # If there are cycles, add remaining mods at the end
        remaining = [original_names[m] for m in mod_set if original_names[m] not in result]
        remaining.sort()
        result.extend(remaining)
        
        return result
    
    def get_dependents(self, mod_name: str) -> list[str]:
        """Get list of mods that depend on this mod."""
        key = self._normalize_name(mod_name)
        dependents = []
        
        for mod, deps in self._dependencies.items():
            if key in [self._normalize_name(d) for d in deps]:
                dependents.append(mod)
        
        return dependents
    
    def get_full_dependency_chain(self, mod_name: str, visited: set = None) -> list[str]:
        """Get all dependencies recursively (transitive closure)."""
        if visited is None:
            visited = set()
        
        key = self._normalize_name(mod_name)
        if key in visited:
            return []
        
        visited.add(key)
        result = []
        
        for dep in self.get_dependencies(mod_name):
            dep_normalized = self._normalize_name(dep)
            if dep_normalized not in visited:
                result.append(dep)
                result.extend(self.get_full_dependency_chain(dep, visited))
        
        return result
