"""
Background worker for mod operations (add/remove/update).
Extracted from mods_tab.py for better separation of concerns.
"""

import shutil
from pathlib import Path
from PySide6.QtCore import QThread, Signal


class ModWorker(QThread):
    """Background worker for mod operations (add/remove/update)."""
    
    progress = Signal(str, int, int)  # message, current, total
    finished = Signal(object)  # dict with results
    error = Signal(str)
    
    def __init__(
        self,
        operation: str,  # "add", "remove", "update"
        server_path: str,
        workshop_path: str = None,
        mods: list = None,  # For add/update: [(workshop_id, mod_folder), ...], For remove: [mod_folder, ...]
        copy_bikeys: bool = True,
    ):
        super().__init__()
        self.operation = operation
        self.server_path = Path(server_path)
        self.workshop_path = Path(workshop_path) if workshop_path else None
        self.mods = mods or []
        self.copy_bikeys = copy_bikeys
    
    def run(self):
        results = {
            "success": [],
            "failed": [],
            "bikeys_copied": [],
            "bikeys_removed": []
        }
        
        total = len(self.mods)
        self.progress.emit(f"Starting {self.operation}...", 0, total)
        keys_folder = self.server_path / "keys"
        
        operations = {
            "add": self._perform_add,
            "remove": self._perform_remove,
            "update": self._perform_update,
        }
        
        if self.operation in operations:
            if self.operation in ("add", "update"):
                keys_folder.mkdir(parents=True, exist_ok=True)
            operations[self.operation](results, total, keys_folder)
        
        self.finished.emit(results)
    
    def _perform_add(self, results: dict, total: int, keys_folder: Path):
        """Add mods from workshop to server."""
        for idx, (workshop_id, mod_folder) in enumerate(self.mods):
            if self.isInterruptionRequested():
                break
            try:
                self.progress.emit(f"Adding: {mod_folder}", idx + 1, total)
                
                source_path = self._get_source_path(workshop_id, mod_folder)
                
                if not source_path.exists():
                    results["failed"].append((mod_folder, "Source not found"))
                    continue
                
                dest_path = self.server_path / mod_folder
                
                # Remove existing if present
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                
                # Copy mod folder
                shutil.copytree(source_path, dest_path)
                results["success"].append(mod_folder)
                
                # Copy bikeys
                if self.copy_bikeys:
                    self._copy_mod_bikeys(dest_path, keys_folder, results)
                    
            except Exception as e:
                results["failed"].append((mod_folder, str(e)))
    
    def _perform_remove(self, results: dict, total: int, keys_folder: Path):
        """Remove mods from server."""
        for idx, mod_folder in enumerate(self.mods):
            if self.isInterruptionRequested():
                break
            try:
                self.progress.emit(f"Removing: {mod_folder}", idx + 1, total)
                
                mod_path = self.server_path / mod_folder
                
                if not mod_path.exists():
                    results["failed"].append((mod_folder, "Not found"))
                    continue
                
                # Find and remove associated bikeys first
                bikeys_to_remove = self._find_mod_bikeys(mod_path)
                
                # Remove mod folder
                shutil.rmtree(mod_path)
                results["success"].append(mod_folder)
                
                # Remove bikeys (if not shared by other mods)
                if keys_folder.exists():
                    for bikey_name in bikeys_to_remove:
                        bikey_path = keys_folder / bikey_name
                        if bikey_path.exists():
                            try:
                                bikey_path.unlink()
                                results["bikeys_removed"].append(bikey_name)
                            except Exception:
                                pass
                    
            except Exception as e:
                results["failed"].append((mod_folder, str(e)))
    
    def _perform_update(self, results: dict, total: int, keys_folder: Path):
        """Update mods (remove old + add new)."""
        for idx, (workshop_id, mod_folder) in enumerate(self.mods):
            if self.isInterruptionRequested():
                break
            try:
                self.progress.emit(f"Updating: {mod_folder}", idx + 1, total)
                
                source_path = self._get_source_path(workshop_id, mod_folder)
                
                if not source_path.exists():
                    results["failed"].append((mod_folder, "Source not found"))
                    continue
                
                dest_path = self.server_path / mod_folder
                
                # Remove old version
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                
                # Copy new version
                shutil.copytree(source_path, dest_path)
                results["success"].append(mod_folder)
                
                # Update bikeys
                if self.copy_bikeys:
                    self._copy_mod_bikeys(dest_path, keys_folder, results)
                    
            except Exception as e:
                results["failed"].append((mod_folder, str(e)))
    
    def _get_source_path(self, workshop_id: str, mod_folder: str) -> Path:
        """Get source path for a mod."""
        if workshop_id == "local":
            return self.workshop_path / mod_folder
        return self.workshop_path / workshop_id / mod_folder
    
    def _find_mod_bikeys(self, mod_path: Path) -> list[str]:
        """Find bikey files in a mod folder."""
        bikeys = []
        search_paths = [
            mod_path / "keys", mod_path / "Keys",
            mod_path / "key", mod_path / "Key", mod_path
        ]
        searched = set()
        
        for path in search_paths:
            if path.exists() and path not in searched:
                searched.add(path)
                bikeys.extend(f.name for f in path.glob("*.bikey"))
        
        if not bikeys:
            bikeys = [f.name for f in mod_path.rglob("*.bikey")]
        
        return bikeys
    
    def _copy_mod_bikeys(self, mod_path: Path, keys_folder: Path, results: dict):
        """Copy bikey files from mod to server keys folder."""
        search_paths = [
            mod_path / "keys", mod_path / "Keys",
            mod_path / "key", mod_path / "Key", mod_path
        ]
        searched = set()
        bikey_files = []
        
        for path in search_paths:
            if path.exists() and path not in searched:
                searched.add(path)
                bikey_files.extend(path.glob("*.bikey"))
        
        if not bikey_files:
            bikey_files = list(mod_path.rglob("*.bikey"))
        
        for bikey_file in bikey_files:
            dest = keys_folder / bikey_file.name
            try:
                shutil.copy2(bikey_file, dest)
                if bikey_file.name not in results["bikeys_copied"]:
                    results["bikeys_copied"].append(bikey_file.name)
            except Exception:
                pass
